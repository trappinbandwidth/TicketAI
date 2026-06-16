import { useState, useEffect, useMemo } from 'react';
import { useForm } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import * as Yup from 'yup';
import { loadStripe } from '@stripe/stripe-js';
import { Elements } from '@stripe/react-stripe-js';
import LucideIcon from 'src/components/lucide-icon';
import { Button, Input, Modal, ModalContent } from 'src/components/ui';
import { FormProvider, RHFSelectbox, RHFTextField } from 'src/hook-form';
import { SendOTP, VerifyOTP } from 'src/utils/api-service';
import { constants } from 'src/constants.value';
import { toasterService } from 'src/apiSetUp';
import { useRegistrationProductsQuery } from 'src/queries/use-registration-products-query';
import { US_STATE_SELECT_OPTIONS } from 'src/utils/us-states';
import PlanSelectionStep from './signup-flow/PlanSelectionStep';
import PlanSummary from './signup-flow/PlanSummary';
import StripePaymentForm from './signup-flow/StripePaymentForm';
import { formatPhoneNumber } from './signup-flow/formatters';

// Initialize Stripe - Replace with your actual publishable key
const stripePromise = loadStripe(import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY);


// TypeScript interfaces matching API response
interface Plan {
    tierCode: string;
    tier: string;
    name: string;
    id: string;
    frequency: string;
    displayOrder: number;
    discountPercent: number;
    discountAmount: number;
    benefits: string[];
    amount: number;
}

interface Frequency {
    savingsPercent: number | null;
    savingsBadge: string | null;
    label: string;
    key: string;
}

interface GoogleAddressSuggestion {
    placeId: string;
    description: string;
    mainText: string;
    secondaryText: string;
}

function parseGoogleAddress(addressComponents: Array<{ longText?: string; shortText?: string; types?: string[] }>) {
    const findComponent = (type: string) => addressComponents.find((component) => component.types?.includes(type));

    const streetNumber = findComponent('street_number')?.longText || '';
    const route = findComponent('route')?.longText || '';
    const stateCode = (findComponent('administrative_area_level_1')?.shortText || '').toUpperCase();

    return {
        address: [streetNumber, route].filter(Boolean).join(' ').trim(),
        city: findComponent('locality')?.longText || findComponent('sublocality')?.longText || '',
        state: stateCode,
        zip: (findComponent('postal_code')?.longText || '').replace(/\D/g, '').slice(0, 5),
    };
}

// Dynamic plan details structure
interface PlanDetails {
    [key: string]: {
        name: string;
        color: string;
        icon: string;
        badge?: string;
        plans: {
            monthly?: Plan;
            quarterly?: Plan;
            annually?: Plan;
        };
    };
}

type PlanType = 'silver' | 'gold' | 'platinum';
type BillingFrequency = 'monthly' | 'quarterly' | 'annually';
type StepType = 'plan' | 'info' | 'payment' | 'success';

interface SignupFlowProps {
    isOpen: boolean;
    onClose: () => void;
    onSignupComplete: (plan: PlanType) => void;
    initialInfoValues?: {
        firstName?: string;
        lastName?: string;
        phone?: string;
    };
    initialPhoneVerified?: boolean;
}

// Validation schemas
const infoSchema = Yup.object().shape({
    firstName: Yup.string().required('First name is required'),
    lastName: Yup.string().required('Last name is required'),
    email: Yup.string().email('Invalid email address').required('Email is required'),
    phone: Yup.string()
        .matches(/^\(\d{3}\) \d{3}-\d{4}$/, 'Please enter a valid phone number')
        .required('Phone number is required'),
    address: Yup.string().required('Street address is required'),
    city: Yup.string().required('City is required'),
    state: Yup.string()
        .length(2, 'State must be 2 characters')
        .required('State is required'),
    zip: Yup.string()
        .matches(/^\d{5}$/, 'ZIP code must be 5 digits')
        .required('ZIP code is required'),
});



// Tier configuration for UI (colors, icons, badges)
const TIER_CONFIG: { [key: string]: { color: string; icon: string; badge?: string } } = {
    silver: {
        color: '#8B9BA8',
        icon: 'Star',
    },
    gold: {
        color: '#F2AE26',
        icon: 'Award',
        badge: 'Most Popular',
    },
    platinum: {
        color: '#0D3E6B',
        icon: 'Crown',
        badge: 'Best Value',
    },
};

/**
 * SignupFlow Modal - Multi-step signup process
 * Optimized for mobile devices (iOS & Android)
 * Step 1: Plan Selection (Dynamic)
 * Step 2: Personal Information
 * Step 3: Payment Details
 * Step 4: Success Confirmation
 */
export default function SignupFlow({
    isOpen,
    onClose,
    onSignupComplete,
    initialInfoValues,
    initialPhoneVerified = false,
}: SignupFlowProps) {
    const [step, setStep] = useState<StepType>('plan');
    const [selectedPlan, setSelectedPlan] = useState<PlanType | null>(null);
    const [selectedPlanData, setSelectedPlanData] = useState<Plan | null>(null);
    const [billingFrequency, setBillingFrequency] = useState<BillingFrequency>('monthly');
    const googleApiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY as string | undefined;
    const registrationProductsQuery = useRegistrationProductsQuery(isOpen);

    // Form for personal info
    const infoMethods = useForm({
        resolver: yupResolver(infoSchema),
        defaultValues: {
            firstName: initialInfoValues?.firstName || '',
            lastName: initialInfoValues?.lastName || '',
            email: '',
            phone: initialInfoValues?.phone || '',
            address: '',
            city: '',
            state: '',
            zip: '',
        },
    });

    // OTP Verification States
    const [isPhoneVerified, setIsPhoneVerified] = useState(initialPhoneVerified);
    const [showOtpInput, setShowOtpInput] = useState(false);
    const [otpCode, setOtpCode] = useState('');
    const [isSendingOtp, setIsSendingOtp] = useState(false);
    const [isVerifyingOtp, setIsVerifyingOtp] = useState(false);
    const [otpCooldown, setOtpCooldown] = useState(0);
    const [lastVerifiedPhone, setLastVerifiedPhone] = useState(initialPhoneVerified ? (initialInfoValues?.phone || '') : '');
    const [otpError, setOtpError] = useState('');
    const [isAddressLoading, setIsAddressLoading] = useState(false);
    const [addressOptions, setAddressOptions] = useState<GoogleAddressSuggestion[]>([]);
    const [isAddressFocused, setIsAddressFocused] = useState(false);

    // Watch phone field for changes
    const phoneValue = infoMethods.watch('phone');
    const addressValue = infoMethods.watch('address');
    const addressField = infoMethods.register('address');
    const addressError = infoMethods.formState.errors.address?.message as string | undefined;

    const { planDetails, frequencies } = useMemo<{ planDetails: PlanDetails; frequencies: Frequency[] }>(() => {
        if (!registrationProductsQuery.data) {
            return { planDetails: {}, frequencies: [] };
        }

        const grouped: PlanDetails = {};
        registrationProductsQuery.data.plans.forEach((plan) => {
            const tier = plan.tier.toLowerCase() as PlanType;
            if (!grouped[tier]) {
                grouped[tier] = {
                    name: plan.tier.charAt(0).toUpperCase() + plan.tier.slice(1),
                    color: TIER_CONFIG[tier]?.color || '#8B9BA8',
                    icon: TIER_CONFIG[tier]?.icon || '',
                    badge: TIER_CONFIG[tier]?.badge,
                    plans: {},
                };
            }

            grouped[tier].plans[plan.frequency as BillingFrequency] = plan;
        });

        return {
            planDetails: grouped,
            frequencies: registrationProductsQuery.data.frequencies,
        };
    }, [registrationProductsQuery.data]);

    const isLoadingPlans = registrationProductsQuery.isLoading;
    const plansError = registrationProductsQuery.isError
        ? (registrationProductsQuery.error as Error)?.message || 'Failed to load plans'
        : null;

    // Reset verification if phone number changes
    useEffect(() => {
        if (phoneValue !== lastVerifiedPhone && isPhoneVerified) {
            setIsPhoneVerified(false);
            setShowOtpInput(false);
            setOtpCode('');
            setOtpError('');
        }
    }, [phoneValue, lastVerifiedPhone, isPhoneVerified]);

    // OTP Cooldown Timer
    useEffect(() => {
        if (otpCooldown > 0) {
            const timer = setTimeout(() => setOtpCooldown(otpCooldown - 1), 1000);
            return () => clearTimeout(timer);
        }
    }, [otpCooldown]);

    useEffect(() => {
        if (step !== 'info' || !googleApiKey) return;

        const query = (addressValue || '').trim();
        if (query.length < 3) {
            setAddressOptions([]);
            return;
        }

        const controller = new AbortController();
        const debounceTimer = setTimeout(async () => {
            try {
                setIsAddressLoading(true);
                const response = await fetch('https://places.googleapis.com/v1/places:autocomplete', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Goog-Api-Key': googleApiKey,
                        'X-Goog-FieldMask': 'suggestions.placePrediction.placeId,suggestions.placePrediction.text.text,suggestions.placePrediction.structuredFormat.mainText.text,suggestions.placePrediction.structuredFormat.secondaryText.text',
                    },
                    signal: controller.signal,
                    body: JSON.stringify({
                        input: query,
                        languageCode: 'en-US',
                        regionCode: 'US',
                        includedRegionCodes: ['us'],
                    }),
                });

                if (!response.ok) {
                    setAddressOptions([]);
                    return;
                }

                const result = await response.json();
                const suggestions = (result?.suggestions || [])
                    .map((suggestion: any) => {
                        const prediction = suggestion?.placePrediction;
                        if (!prediction?.placeId) return null;

                        return {
                            placeId: prediction.placeId,
                            description: prediction?.text?.text || '',
                            mainText: prediction?.structuredFormat?.mainText?.text || prediction?.text?.text || '',
                            secondaryText: prediction?.structuredFormat?.secondaryText?.text || '',
                        } as GoogleAddressSuggestion;
                    })
                    .filter(Boolean) as GoogleAddressSuggestion[];

                setAddressOptions(suggestions);
            } catch {
                setAddressOptions([]);
            } finally {
                setIsAddressLoading(false);
            }
        }, 350);

        return () => {
            controller.abort();
            clearTimeout(debounceTimer);
        };
    }, [step, addressValue, googleApiKey]);

    const handleAddressSelect = async (selectedOption: GoogleAddressSuggestion | null) => {
        if (!selectedOption || !googleApiKey) return;

        try {
            setIsAddressLoading(true);
            const response = await fetch(
                `https://places.googleapis.com/v1/places/${selectedOption.placeId}?fields=addressComponents,formattedAddress`,
                {
                    method: 'GET',
                    headers: {
                        'X-Goog-Api-Key': googleApiKey,
                    },
                }
            );

            if (!response.ok) return;

            const place = await response.json();
            const parsed = parseGoogleAddress(place?.addressComponents || []);

            infoMethods.setValue('address', parsed.address || selectedOption.mainText || selectedOption.description, {
                shouldDirty: true,
                shouldValidate: true,
            });

            if (parsed.city) {
                infoMethods.setValue('city', parsed.city, {
                    shouldDirty: true,
                    shouldValidate: true,
                });
            }

            if (parsed.state) {
                infoMethods.setValue('state', parsed.state, {
                    shouldDirty: true,
                    shouldValidate: true,
                });
            }

            if (parsed.zip) {
                infoMethods.setValue('zip', parsed.zip, {
                    shouldDirty: true,
                    shouldValidate: true,
                });
            }
        } finally {
            setIsAddressLoading(false);
        }
    };

    // Send OTP Handler
    const handleSendOtp = async () => {
        const phone = infoMethods.getValues('phone');

        // Validate phone format
        if (!phone || !/^\(\d{3}\) \d{3}-\d{4}$/.test(phone)) {
            infoMethods.setError('phone', {
                type: 'manual',
                message: 'Please enter a valid phone number'
            });
            return;
        }

        setIsSendingOtp(true);
        setOtpError('');

        try {
            // Clean phone number for API
            const cleanPhone = phone.replace(/\D/g, '');
            const response = await SendOTP({ PhoneNumber: cleanPhone, send_otp: true });

            if (response.StatusCode === constants.RESPONSE_STATUS.SUCCESS) {
                setShowOtpInput(true);
                setOtpCooldown(60); // 60 second cooldown
            }
        } catch (error: any) {
            toasterService(error?.message || 'Failed to send verification code', 4, 'Error');
        } finally {
            setIsSendingOtp(false);
        }
    };

    // Verify OTP Handler - accepts code as parameter for auto-verification
    const handleVerifyOtp = async (code: string) => {
        if (code.length !== 6) {
            return;
        }
        setIsVerifyingOtp(true);
        setOtpError('');
        try {
            const phone = infoMethods.getValues('phone');
            const cleanPhone = phone.replace(/\D/g, '');

            const response = await VerifyOTP({
                PhoneNumber: cleanPhone,
                OTPCode: code,
                verify_otp: true
            });

            if (response.StatusCode === constants.RESPONSE_STATUS.SUCCESS) {
                setIsPhoneVerified(true);
                setLastVerifiedPhone(phone);
                setShowOtpInput(false);
                setOtpCode('');
            } else {
                setOtpError(response.Message || 'Invalid verification code');
                setOtpCode(''); // Clear on error for retry
            }
        } catch (error: any) {
            setOtpError(error?.message || 'Verification failed');
            setOtpCode(''); // Clear on error for retry
        } finally {
            setIsVerifyingOtp(false);
        }
    };
    // Helper to get current plan data
    const getCurrentPlanData = (tier: PlanType): Plan | null => {
        return planDetails[tier]?.plans[billingFrequency] || null;
    };

    // Navigation handlers
    const handleBack = () => {
        if (step === 'plan') {
            onClose();
        } else if (step === 'info') {
            setStep('plan');
        } else if (step === 'payment') {
            setStep('info');
        }
    };

    const handlePlanSelect = (plan: PlanType) => {
        setSelectedPlan(plan);
        const planData = getCurrentPlanData(plan);
        setSelectedPlanData(planData);
        setStep('info');
    };

    const handleInfoSubmit = infoMethods.handleSubmit(() => {
        // Require phone verification before proceeding to payment
        if (!isPhoneVerified) {
            toasterService('Please verify your phone number to continue', 4, 'Warning');
            return;
        }
        setStep('payment');
    });

    // Stripe Payment Handlers
    const handlePaymentSuccess = () => {
        setStep('success');
        // Auto-redirect after success
        setTimeout(() => {
            if (selectedPlan) {
                onSignupComplete(selectedPlan);
            }
        }, 4000);
    };

    const handlePaymentError = (error: string) => {
        console.error('Payment error:', error);
        // You can show a toast/snackbar here
        alert(`Payment failed: ${error}`);
    };


    const getStepTitle = () => {
        switch (step) {
            case 'plan':
                return 'Choose Your Plan';
            case 'info':
                return 'Your Information';
            case 'payment':
                return 'Payment Details';
            default:
                return '';
        }
    };

    return (
        <Modal open={isOpen} onOpenChange={(open) => !open && onClose()}>
            <ModalContent
                hideCloseButton
                className="left-0 right-0 top-auto mx-0 flex w-full max-w-none translate-x-0 translate-y-0 flex-col rounded-t-[20px] rounded-b-none border-0 p-0 sm:left-1/2 sm:right-auto sm:top-1/2 sm:w-[calc(100%-2rem)] sm:max-w-[440px] sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-3xl sm:border sm:border-slate-200"
            >
                    {step !== 'success' && (
                        <div className="mx-auto mb-1 mt-3 block h-1 w-10 rounded-full bg-gray-300 sm:hidden" />
                    )}

                    {step !== 'success' && (
                        <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3 sm:py-4">
                            <button
                                type="button"
                                onClick={handleBack}
                                className="inline-flex h-10 w-10 items-center justify-center rounded-full text-slate-600 transition hover:bg-slate-100"
                            >
                                <LucideIcon name="ArrowLeft" size={22} />
                            </button>
                            <h2 className="text-base font-semibold text-[#1e3a5f] sm:text-lg">
                                {getStepTitle()}
                            </h2>
                            <button
                                type="button"
                                onClick={onClose}
                                className="inline-flex h-10 w-10 items-center justify-center rounded-full text-slate-600 transition hover:bg-slate-100"
                            >
                                <LucideIcon name="X" size={22} />
                            </button>
                        </div>
                    )}

                    <div className="flex-1 overflow-auto pb-[env(safe-area-inset-bottom,0px)] sm:pb-0">
                        {/* Step 1: Plan Selection */}
                        {step === 'plan' && (
                            <div className="px-5 py-4 sm:px-6 sm:py-6">
                                <p className="mb-4 text-center text-sm text-gray-500 sm:mb-6">
                                    Select the membership plan that best fits your needs
                                </p>

                                {/* Plan Selection Step */}
                                {step === 'plan' && (
                                    <PlanSelectionStep
                                        planDetails={planDetails}
                                        frequencies={frequencies}
                                        billingFrequency={billingFrequency}
                                        isLoadingPlans={isLoadingPlans}
                                        plansError={plansError}
                                        onFrequencyChange={setBillingFrequency}
                                        onPlanSelect={handlePlanSelect}
                                    />
                                )}
                            </div>
                        )}
                        {/* Step 2: Personal Information */}
                        {step === 'info' && selectedPlan && (
                            <div className="px-5 py-4 sm:px-6 sm:py-6">
                                {/* Selected Plan Summary */}
                                {selectedPlanData && (
                                    <PlanSummary
                                        tierName={planDetails[selectedPlan]?.name || ''}
                                        tierColor={planDetails[selectedPlan]?.color || '#0D3E6B'}
                                        planData={selectedPlanData}
                                        billingFrequency={billingFrequency}
                                        title="Selected Plan"
                                    />
                                )}

                                {/* Form Fields */}
                                <FormProvider methods={infoMethods} onSubmit={handleInfoSubmit}>
                                    <div className="space-y-4">
                                        <div className="flex gap-4">
                                            <RHFTextField
                                                name="firstName"
                                                label="First Name"
                                                type="text"
                                            />
                                            <RHFTextField
                                                name="lastName"
                                                label="Last Name"
                                                type="text"
                                            />
                                        </div>

                                        <RHFTextField
                                            name="email"
                                            label="Email Address"
                                            type="email"
                                        />
                                        {/* Phone Number with Verification */}
                                        <div>
                                            <div className="flex items-center gap-2">
                                                <div className="flex-1">
                                                    <RHFTextField
                                                        name="phone"
                                                        label="Phone Number"
                                                        type="text"
                                                        maxLength={14}
                                                        disabled={isPhoneVerified}
                                                        handleChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                                                            const formatted = formatPhoneNumber(e.target.value);
                                                            infoMethods.setValue('phone', formatted);
                                                        }}
                                                    />
                                                    {isPhoneVerified && (
                                                        <div className="mt-1 flex items-center gap-1 text-xs font-semibold text-green-600">
                                                            <LucideIcon name="CircleCheck" size={18} />
                                                            <span>Phone verified</span>
                                                        </div>
                                                    )}
                                                </div>
                                                {!isPhoneVerified && (
                                                    <Button
                                                        type="button"
                                                        onClick={handleSendOtp}
                                                        disabled={isSendingOtp || otpCooldown > 0 || !phoneValue || phoneValue.length < 14}
                                                        className="h-14 min-w-[90px] rounded-lg text-xs font-semibold sm:min-w-[110px] sm:text-sm"
                                                        variant={otpCooldown > 0 ? 'secondary' : 'primary'}
                                                    >
                                                        {isSendingOtp ? (
                                                            <div className="h-5 w-5 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                                                        ) : otpCooldown > 0 ? (
                                                            `${otpCooldown}s`
                                                        ) : showOtpInput ? (
                                                            'Resend'
                                                        ) : (
                                                            'Verify'
                                                        )}
                                                    </Button>
                                                )}
                                            </div>

                                            {/* OTP Input Section */}
                                            {showOtpInput && !isPhoneVerified && (
                                                <div className="mt-4 rounded-lg border border-blue-200 bg-blue-50 p-4">
                                                    <p className="mb-3 flex items-center gap-2 text-sm font-medium text-[#0D3E6B]">
                                                        <LucideIcon name="MessageSquareText" size={18} />
                                                        Enter the 6-digit code sent to your phone
                                                    </p>
                                                    <div className="relative">
                                                        <Input
                                                            value={otpCode}
                                                            onChange={(e) => {
                                                                const value = e.target.value.replace(/\D/g, '').slice(0, 6);
                                                                setOtpCode(value);
                                                                setOtpError('');

                                                                // Auto-verify when 6 digits are entered
                                                                if (value.length === 6) {
                                                                    handleVerifyOtp(value);
                                                                }
                                                            }}
                                                            placeholder="• • • • • •"
                                                            disabled={isVerifyingOtp}
                                                            autoFocus
                                                            maxLength={6}
                                                            inputMode="numeric"
                                                            pattern="[0-9]*"
                                                            className={`h-14 rounded-2xl border bg-white py-2 text-center text-2xl font-bold tracking-[0.75rem] text-[#1e3a5f] placeholder:text-slate-400 focus:border-[#0D3E6B] focus:ring-2 focus:ring-[#0D3E6B]/15 ${
                                                                otpError ? 'border-red-500' : 'border-slate-300'
                                                            } ${isVerifyingOtp ? 'pr-12' : ''}`}
                                                        />
                                                        {/* Loading indicator inside input */}
                                                        {isVerifyingOtp && (
                                                            <div className="absolute right-4 top-1/2 flex -translate-y-1/2 items-center">
                                                                <div className="h-6 w-6 animate-spin rounded-full border-2 border-[#0D3E6B]/20 border-t-[#0D3E6B]" />
                                                            </div>
                                                        )}
                                                    </div>
                                                    {otpError && <p className="mt-2 text-sm text-red-600">{otpError}</p>}
                                                    {isVerifyingOtp && (
                                                        <p className="mt-2 flex items-center justify-center gap-1 text-xs font-medium text-[#0D3E6B]">
                                                            <LucideIcon name="ShieldCheck" size={14} />
                                                            Verifying your code...
                                                        </p>
                                                    )}
                                                </div>
                                            )}
                                        </div>

                                        <div className="relative">
                                            <label className="mb-1 block text-sm font-medium text-[#1e3a5f]">
                                                Street Address
                                            </label>
                                            <div className="relative">
                                                <Input
                                                    {...addressField}
                                                    value={addressValue || ''}
                                                    onFocus={() => setIsAddressFocused(true)}
                                                    onBlur={(event) => {
                                                        addressField.onBlur(event);
                                                        window.setTimeout(() => setIsAddressFocused(false), 150);
                                                    }}
                                                    onChange={(event) => {
                                                        addressField.onChange(event);
                                                    }}
                                                    placeholder="Start typing your address"
                                                    className={`h-14 rounded-2xl border bg-white px-4 text-sm text-[#1e3a5f] placeholder:text-slate-400 focus:border-[#0D3E6B] focus:ring-2 focus:ring-[#0D3E6B]/15 ${
                                                        addressError ? 'border-red-500' : 'border-slate-300'
                                                    }`}
                                                />
                                                {isAddressLoading && (
                                                    <div className="absolute right-4 top-1/2 -translate-y-1/2">
                                                        <div className="h-[18px] w-[18px] animate-spin rounded-full border-2 border-slate-300 border-t-[#0D3E6B]" />
                                                    </div>
                                                )}
                                            </div>
                                            {addressError ? (
                                                <p className="mt-1 text-sm text-red-600">{addressError}</p>
                                            ) : !googleApiKey ? (
                                                <p className="mt-1 text-sm text-slate-500">
                                                    Set VITE_GOOGLE_MAPS_API_KEY in your .env to enable address search
                                                </p>
                                            ) : null}

                                            {isAddressFocused && addressValue?.trim().length >= 3 && (
                                                <div className="absolute z-20 mt-2 w-full overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xl">
                                                    {addressOptions.length > 0 ? (
                                                        <ul className="max-h-64 overflow-auto py-2">
                                                            {addressOptions.map((option) => (
                                                                <li key={option.placeId}>
                                                                    <button
                                                                        type="button"
                                                                        onMouseDown={(event) => {
                                                                            event.preventDefault();
                                                                            handleAddressSelect(option);
                                                                            setIsAddressFocused(false);
                                                                        }}
                                                                        className="w-full px-4 py-3 text-left transition hover:bg-slate-50"
                                                                    >
                                                                        <p className="text-sm font-semibold text-slate-900">
                                                                            {option.mainText}
                                                                        </p>
                                                                        <p className="text-xs text-slate-500">
                                                                            {option.secondaryText || option.description}
                                                                        </p>
                                                                    </button>
                                                                </li>
                                                            ))}
                                                        </ul>
                                                    ) : !isAddressLoading ? (
                                                        <div className="px-4 py-3 text-sm text-slate-500">
                                                            Start typing to search address
                                                        </div>
                                                    ) : null}
                                                </div>
                                            )}
                                        </div>
                                        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                                            <div className="min-w-0 sm:col-span-2">
                                                <RHFTextField
                                                    name="city"
                                                    label="City"
                                                    type="text"
                                                />
                                            </div>
                                            <div className="min-w-0 sm:col-span-1">
                                                <RHFTextField
                                                    name="state"
                                                    label="State"
                                                    type="text"
                                                    maxLength={2}
                                                    handleChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                                                        const formatted = e.target.value.toUpperCase().replace(/[^A-Z]/g, '').slice(0, 2);
                                                        infoMethods.setValue('state', formatted);
                                                    }}
                                                />
                                            </div>
                                        </div>

                                        <RHFTextField
                                            name="zip"
                                            label="ZIP Code"
                                            type="text"
                                            maxLength={5}
                                            handleChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                                                const formatted = e.target.value.replace(/\D/g, '').slice(0, 5);
                                                infoMethods.setValue('zip', formatted);
                                            }}
                                        />
                                    </div>

                                    <div className="space-y-2">
                                        <Button
                                            type="submit"
                                            fullWidth
                                            className={`mt-5 gap-1.5 py-1.5 text-base ${
                                                isPhoneVerified
                                                    ? 'bg-[#F97316] shadow-[0_4px_14px_rgba(249,115,22,0.4)] hover:bg-[#ea580c]'
                                                    : 'bg-[#94a3b8] hover:bg-[#94a3b8]'
                                            }`}
                                        >
                                            {isPhoneVerified ? (
                                                <>
                                                    <LucideIcon name="LockOpen" size={20} />
                                                    Continue to Payment
                                                </>
                                            ) : (
                                                <>
                                                    <LucideIcon name="Lock" size={20} />
                                                    Verify Phone to Continue
                                                </>
                                            )}
                                        </Button>
                                        {!isPhoneVerified && (
                                            <p className="flex items-center justify-center gap-1 text-center text-xs text-gray-500">
                                                <LucideIcon name="ShieldCheck" size={14} color="#0D3E6B" />
                                                Phone verification required for security
                                            </p>
                                        )}
                                    </div>
                                </FormProvider>
                            </div>
                        )}

                        {/* Step 3: Payment */}
                        {step === 'payment' && selectedPlan && selectedPlanData && (
                            <div className="px-5 py-4 sm:px-6 sm:py-6">
                                {/* Plan Summary */}
                                <PlanSummary
                                    tierName={planDetails[selectedPlan]?.name || ''}
                                    tierColor={planDetails[selectedPlan]?.color || '#0D3E6B'}
                                    planData={selectedPlanData}
                                    billingFrequency={billingFrequency}
                                    title="Your Plan"
                                />

                                {/* Stripe Payment Form */}
                                <Elements stripe={stripePromise}>
                                    <StripePaymentForm
                                        amount={selectedPlanData.amount}
                                        billingFrequency={billingFrequency}
                                        onSuccess={handlePaymentSuccess}
                                        onError={handlePaymentError}
                                        userInfo={infoMethods.getValues()}
                                        planData={{
                                            id: selectedPlanData.id,
                                            tier: selectedPlanData.tier,
                                            frequency: selectedPlanData.frequency,
                                            amount: selectedPlanData.amount,
                                        }}
                                    />
                                </Elements>
                            </div>
                        )}

                        {/* Step 4: Success */}
                        {step === 'success' && selectedPlan && (
                            <div className="p-8 text-center">
                                <div className="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-green-50">
                                    <LucideIcon name="CircleCheck" size={48} color="#16a34a" />
                                </div>
                                <h2 className="mb-3 text-xl font-bold text-[#1e3a5f]">
                                    Welcome to Rig Resolve!
                                </h2>
                                <p className="mb-6 text-base text-gray-500">
                                    Your {planDetails[selectedPlan]?.name} membership is now active. You'll receive a
                                    confirmation email shortly.
                                </p>
                                <div className="mb-6 rounded-2xl border border-green-300 bg-green-50 p-4">
                                    <div className="mb-2 flex items-center justify-center gap-2">
                                        <LucideIcon name="CircleCheck" size={20} color="#16a34a" />
                                        <p className="text-base font-semibold text-green-800">
                                            Payment Processed
                                        </p>
                                    </div>
                                    <p className="mb-1 text-2xl font-bold text-green-800">
                                        ${selectedPlanData?.amount.toFixed(2)}
                                    </p>
                                    <p className="text-sm text-green-800">
                                        First{' '}
                                        {billingFrequency === 'quarterly'
                                            ? 'quarterly'
                                            : billingFrequency === 'annually'
                                                ? 'annual'
                                                : 'monthly'}{' '}
                                        charge
                                    </p>
                                </div>
                                <div className="mb-6 space-y-2 text-left">
                                    {[
                                        'Account created successfully',
                                        'Benefits activated immediately',
                                        `Welcome email sent to ${infoMethods.getValues('email')}`,
                                    ].map((item, idx) => (
                                        <div key={idx} className="flex items-center gap-2">
                                            <LucideIcon name="Check" size={18} color="#16a34a" />
                                            <p className="text-sm text-gray-500">
                                                {item}
                                            </p>
                                        </div>
                                    ))}
                                </div>
                                <div className="flex items-center justify-center gap-2">
                                    <div className="h-4 w-4 animate-spin rounded-full border-2 border-[#0D3E6B]/20 border-t-[#0D3E6B]" />
                                    <p className="text-sm font-medium text-[#0D3E6B]">
                                        Redirecting to your dashboard...
                                    </p>
                                </div>
                            </div>
                        )}
                    </div>
            </ModalContent>
        </Modal>
    );
}
