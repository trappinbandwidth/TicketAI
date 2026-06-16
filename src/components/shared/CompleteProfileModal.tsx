import { useEffect, useMemo, useRef, useState } from 'react';
import { useAtom } from 'jotai';
import {
    AlertCircle,
    ArrowLeft,
    CheckCircle,
    FileText,
    LoaderCircle,
    Mail,
    MapPin,
    Phone,
    ShieldCheck,
    UserPlus,
} from 'lucide-react';

import { toasterService } from 'src/apiSetUp';
import { constants } from 'src/constants.value';
import { formatPhoneNumber } from 'src/pages/signup/components/signup-flow/formatters';
import { useCompleteDriverProfileMutation } from 'src/queries/use-profile-mutations';
import { driverProfile } from 'src/store';
import { fDate, formatStr } from 'src/utils/format-time';
import { getUsStateCode, getUsStateName, isUsStateCode, US_STATE_SELECT_OPTIONS } from 'src/utils/us-states';
import { Modal, ModalContent, ModalTitle } from 'src/components/ui';

export type ProfileCompletionContext = 'submit-ticket' | 'referral' | 'general';

interface CompleteProfileModalProps {
    open: boolean;
    onClose: () => void;
    onCompleted?: () => void;
    actionContext?: ProfileCompletionContext;
    skipExplanation?: boolean;
}

interface ProfileFormValues {
    email: string;
    mobilePhone: string;
    birthdate: string;
    streetAddress: string;
    apt: string;
    city: string;
    state: string;
    stateCode?: string;
    zipCode: string;
    // cdlNumber: string;
    // cdlState: string;
}

interface GoogleAddressSuggestion {
    placeId: string;
    description: string;
    mainText: string;
    secondaryText: string;
}

type FormErrors = Partial<Record<keyof ProfileFormValues, string>>;

function parseGoogleAddress(addressComponents: Array<{ longText?: string; shortText?: string; types?: string[] }>) {
    const findComponent = (type: string) => addressComponents.find((component) => component.types?.includes(type));

    const streetNumber = findComponent('street_number')?.longText || '';
    const route = findComponent('route')?.longText || '';

    return {
        streetAddress: [streetNumber, route].filter(Boolean).join(' ').trim(),
        apt: findComponent('subpremise')?.longText || '',
        city: findComponent('locality')?.longText || findComponent('sublocality')?.longText || '',
        state: getUsStateCode(findComponent('administrative_area_level_1')?.shortText || findComponent('administrative_area_level_1')?.longText),
        stateCode: getUsStateCode(findComponent('administrative_area_level_1')?.shortText || findComponent('administrative_area_level_1')?.longText),
        zipCode: (findComponent('postal_code')?.longText || '').replace(/\D/g, '').slice(0, 5),
    };
}

function mapDriverDataToForm(driverData: any): ProfileFormValues {
    const rawPhone = String(driverData?.mobilePhone || '');
    const digitsPhone = rawPhone.replace(/\D/g, '');
    const stateCode = getUsStateCode(driverData?.address?.stateCode || driverData?.address?.state);

    return {
        email: String(driverData?.email || ''),
        mobilePhone: formatPhoneNumber(digitsPhone),
        birthdate: driverData?.birthdate ? fDate(driverData.birthdate, formatStr.paramCase.fromYear) : '',
        streetAddress: String(driverData?.address?.street || ''),
        apt: String(driverData?.address?.apt || ''),
        city: String(driverData?.address?.city || ''),
        state: stateCode,
        stateCode: stateCode,
        zipCode: String(driverData?.address?.zipCode || '').replace(/\D/g, '').slice(0, 5),
        // cdlNumber: String(driverData?.cdlNumber || driverData?.licenseNumber || '').trim(),
    };
}

function validateForm(values: ProfileFormValues): FormErrors {
    const errors: FormErrors = {};
    const phoneDigits = values.mobilePhone.replace(/\D/g, '');
    const zipDigits = values.zipCode.replace(/\D/g, '');

    if (!values.email.trim()) {
        errors.email = 'Email is required';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(values.email.trim())) {
        errors.email = 'Enter a valid email address';
    }

    if (phoneDigits.length !== 10) {
        errors.mobilePhone = 'Phone number must be 10 digits';
    }

    if (!values.birthdate) {
        errors.birthdate = 'Date of birth is required';
    }

    if (!values.streetAddress.trim()) {
        errors.streetAddress = 'Street address is required';
    }

    if (!values.city.trim()) {
        errors.city = 'City is required';
    }

    if (!isUsStateCode(values.state)) {
        errors.state = 'Select a state';
    }

    if (zipDigits.length !== 5) {
        errors.zipCode = 'ZIP code must be 5 digits';
    }

    // if (!values.cdlNumber.trim()) {
    //     errors.cdlNumber = 'CDL number is required';
    // }

    // if (values.cdlState.trim().length !== 2) {
    //     errors.cdlState = 'Use 2-letter CDL state code';
    // }

    return errors;
}

const profileInputClassName =
    'w-full rounded-xl border border-gray-300 bg-white px-3 py-2.5 text-gray-900 placeholder:text-gray-400 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-[#0D3E6B]';

export default function CompleteProfileModal({
    open,
    onClose,
    onCompleted,
    actionContext = 'general',
    skipExplanation = true,
}: CompleteProfileModalProps) {
    const [driverData, setDriverData] = useAtom(driverProfile);
    const completeDriverProfileMutation = useCompleteDriverProfileMutation();
    const [step, setStep] = useState<'explanation' | 'info' | 'success'>('info');
    const [formValues, setFormValues] = useState<ProfileFormValues>(() => mapDriverDataToForm(driverData));
    const [errors, setErrors] = useState<FormErrors>({});
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [isAddressLoading, setIsAddressLoading] = useState(false);
    const [isAddressMenuOpen, setIsAddressMenuOpen] = useState(false);
    const [addressOptions, setAddressOptions] = useState<GoogleAddressSuggestion[]>([]);
    const completionTimerRef = useRef<number | null>(null);
    const addressFieldRef = useRef<HTMLDivElement | null>(null);
    const googleApiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY as string | undefined;
    const shouldShowAddressOptions = isAddressMenuOpen && formValues.streetAddress.trim().length >= 3;

    useEffect(() => {
        if (!open) {
            if (completionTimerRef.current) {
                window.clearTimeout(completionTimerRef.current);
                completionTimerRef.current = null;
            }
            return;
        }

        setFormValues(mapDriverDataToForm(driverData));
        setErrors({});
        setIsSubmitting(false);
        setAddressOptions([]);
        setIsAddressLoading(false);
        setIsAddressMenuOpen(false);
        setStep(skipExplanation || actionContext === 'general' ? 'info' : 'explanation');
    }, [actionContext, driverData, open, skipExplanation]);

    useEffect(() => {
        if (!open || !step || step !== 'info') {
            setIsAddressMenuOpen(false);
            return;
        }

        const handlePointerDown = (event: MouseEvent) => {
            if (!addressFieldRef.current?.contains(event.target as Node)) {
                setIsAddressMenuOpen(false);
            }
        };

        document.addEventListener('mousedown', handlePointerDown);

        return () => {
            document.removeEventListener('mousedown', handlePointerDown);
        };
    }, [open, step]);

    useEffect(() => {
        if (!open || step !== 'info' || !googleApiKey) {
            return;
        }

        const query = formValues.streetAddress.trim();
        if (query.length < 3) {
            setAddressOptions([]);
            return;
        }

        const controller = new AbortController();
        const debounceTimer = window.setTimeout(async () => {
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
                        if (!prediction?.placeId) {
                            return null;
                        }

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
            window.clearTimeout(debounceTimer);
        };
    }, [formValues.streetAddress, googleApiKey, open, step]);

    useEffect(() => {
        return () => {
            if (completionTimerRef.current) {
                window.clearTimeout(completionTimerRef.current);
            }
        };
    }, []);

    const explanationContent = {
        'submit-ticket': {
            icon: FileText,
            iconColor: 'text-[#dc2626]',
            iconBg: 'bg-red-50',
            title: 'Complete Your Profile to Submit Tickets',
            description: 'To submit and manage your citations, we need to verify your information and complete your account setup.',
            reasons: [
                'Verify your identity for legal representation',
                'Keep your contact details current for case updates',
                'Ensure accurate court and attorney documentation',
                'Unlock the full ticket workflow in the app',
            ],
        },
        referral: {
            icon: UserPlus,
            iconColor: 'text-[#dc2626]',
            iconBg: 'bg-red-50',
            title: 'Complete Your Profile to Start Referring',
            description: 'To share your referral code and earn rewards, we need to finish setting up your profile.',
            reasons: [
                'Verify your account before reward activity starts',
                'Keep your payout and contact information accurate',
                'Track referral activity against the right account',
                'Enable the full rewards experience in the app',
            ],
        },
        general: {
            icon: AlertCircle,
            iconColor: 'text-[#0D3E6B]',
            iconBg: 'bg-blue-50',
            title: 'Complete Your Profile',
            description: 'Finish your account details to unlock all features and keep your information up to date.',
            reasons: [
                'Access protected account features',
                'Submit and manage tickets without interruption',
                'Use the referral program and rewards features',
                'Receive accurate support and case communication',
            ],
        },
    } as const;

    const successContent = {
        'submit-ticket': {
            title: 'Profile Complete',
            description: 'Your profile has been updated. Opening ticket submission now.',
        },
        referral: {
            title: 'Profile Complete',
            description: 'Your profile has been updated. You can now access referral features.',
        },
        general: {
            title: 'Profile Complete',
            description: 'Your profile has been updated successfully.',
        },
    } as const;

    const driverFirstName = String(driverData?.firstName || '').trim();
    const driverLastName = String(driverData?.lastName || '').trim();

    const handleValueChange = (field: keyof ProfileFormValues, value: string) => {
        setFormValues((prev) => {
            if (field === 'state') {
                const stateCode = getUsStateCode(value);
                return {
                    ...prev,
                    state: stateCode,
                    stateCode,
                };
            }

            return { ...prev, [field]: value };
        });
        setErrors((prev) => {
            if (!prev[field]) {
                return prev;
            }

            const nextErrors = { ...prev };
            delete nextErrors[field];
            return nextErrors;
        });
    };

    const handleBack = () => {
        if (isSubmitting) {
            return;
        }

        if (step === 'info' && !skipExplanation && actionContext !== 'general') {
            setStep('explanation');
            return;
        }

        onClose();
    };

    const handleSubmit = async () => {
        const nextErrors = validateForm(formValues);

        if (Object.keys(nextErrors).length > 0) {
            setErrors(nextErrors);
            return;
        }

        const normalizedMobilePhone = formValues.mobilePhone.replace(/\D/g, '').slice(0, 10);
        const payload = {
            firstName: driverFirstName,
            lastName: driverLastName,
            email: formValues.email.trim(),
            phone: String(driverData?.phone || normalizedMobilePhone).replace(/\D/g, '').slice(0, 10),
            mobilePhone: normalizedMobilePhone,
            birthdate: fDate(formValues.birthdate, formatStr.paramCase.date),
            address: {
                street: formValues.streetAddress.trim(),
                apt: formValues.apt.trim() || undefined,
                city: formValues.city.trim(),
                state: getUsStateName(formValues.state) || formValues.state.trim(),
                stateCode: formValues.state.trim().toUpperCase() || undefined,
                zipCode: formValues.zipCode.replace(/\D/g, '').slice(0, 5),
                country: 'United States',
            },
        };

        try {
            setIsSubmitting(true);
            const response = await completeDriverProfileMutation.mutateAsync(payload);

            if (response?.StatusCode !== constants.RESPONSE_STATUS.SUCCESS) {
                toasterService(response?.Message || 'Unable to update profile right now.', 4, 'complete-profile-fail');
                setIsSubmitting(false);
                return;
            }

            const updatedProfile = response?.Result?.data || {};
            // const resolvedCdlNumber = updatedProfile?.licenseNumber;
            // const resolvedCdlState = updatedProfile?.cdlState;
            setDriverData((prev: any) => ({
                ...prev,
                ...updatedProfile,
                incompleteProfile: false,
                phone: String(updatedProfile?.phone || payload.phone),
                mobilePhone: formatPhoneNumber(String(updatedProfile?.mobilePhone || payload.mobilePhone)),
                // cdlNumber: resolvedCdlNumber,
                // licenseNumber: resolvedCdlNumber,
                // cdlState: resolvedCdlState,
            }));

            setStep('success');
            completionTimerRef.current = window.setTimeout(() => {
                onCompleted?.();
            }, 1600);
        } catch (error: any) {
            toasterService(error?.message || 'Unable to update profile right now.', 4, 'complete-profile-catch');
            setIsSubmitting(false);
        }
    };

    const handleAddressSelect = async (selectedOption: GoogleAddressSuggestion | null) => {
        if (!selectedOption || !googleApiKey) {
            return;
        }

        setIsAddressLoading(true);
        try {
            const response = await fetch(
                `https://places.googleapis.com/v1/places/${selectedOption.placeId}?fields=addressComponents,formattedAddress`,
                {
                    method: 'GET',
                    headers: {
                        'X-Goog-Api-Key': googleApiKey,
                    },
                }
            );

            if (!response.ok) {
                return;
            }

            const place = await response.json();
            const parsed = parseGoogleAddress(place?.addressComponents || []);

            setFormValues((prev) => ({
                ...prev,
                streetAddress: parsed.streetAddress || selectedOption.mainText || selectedOption.description,
                apt: parsed.apt || prev.apt,
                city: parsed.city || prev.city,
                state: parsed.state || prev.state,
                stateCode: parsed.stateCode || prev.stateCode,
                zipCode: parsed.zipCode || prev.zipCode,
            }));

            setErrors((prev) => {
                const nextErrors = { ...prev };
                delete nextErrors.streetAddress;
                delete nextErrors.city;
                delete nextErrors.zipCode;
                return nextErrors;
            });

            setIsAddressMenuOpen(false);
        } finally {
            setIsAddressLoading(false);
        }
    };

    const content = explanationContent[actionContext];
    const successState = successContent[actionContext];
    const IconComponent = content.icon;

    return (
        <Modal
            open={open}
            onOpenChange={(nextOpen) => {
                if (!nextOpen && !isSubmitting && step !== 'success') {
                    onClose();
                }
            }}
        >
            <ModalContent hideCloseButton className="mvp-modal-shell max-h-[90vh] w-[calc(100%-1rem)] max-w-md overflow-hidden p-0 sm:w-[calc(100%-2rem)]">
                {step !== 'success' && (
                    <div className="mvp-modal-header sticky top-0 z-10 px-5 py-4">
                        <button
                            type="button"
                            onClick={handleBack}
                            className="flex h-9 w-9 items-center justify-center rounded-full text-gray-600 transition-colors hover:bg-gray-100"
                        >
                            <ArrowLeft className="h-5 w-5" />
                        </button>
                        <ModalTitle className="text-base font-bold text-[#1e3a5f]">
                            Complete Your Profile
                        </ModalTitle>
                        <div className="w-9" />
                    </div>
                )}

                <div className="mvp-modal-body pt-4">
                    {step === 'explanation' && (
                        <div className="px-1 pb-1">
                            <div className={`mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-full ${content.iconBg}`}>
                                <IconComponent className={`h-10 w-10 ${content.iconColor}`} />
                            </div>

                            <h3 className="mb-3 text-center text-xl text-[#1e3a5f]">{content.title}</h3>
                            <p className="mb-6 text-center text-sm leading-6 text-gray-600">{content.description}</p>

                            <div className="mb-6 rounded-2xl bg-gradient-to-br from-[#E8F4F8] to-[#d4e9f2] p-5">
                                <h4 className="mb-3 text-[#1e3a5f]">We'll need to collect:</h4>
                                <ul className="space-y-2.5">
                                    {content.reasons.map((reason) => (
                                        <li key={reason} className="flex items-start gap-3">
                                            <CheckCircle className="mt-0.5 h-5 w-5 shrink-0 text-[#0D3E6B]" />
                                            <span className="text-sm text-gray-700">{reason}</span>
                                        </li>
                                    ))}
                                </ul>
                            </div>

                            <div className="mb-6 rounded-xl bg-gray-50 p-4">
                                <div className="flex items-start gap-3">
                                    <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-gray-400" />
                                    <p className="text-sm text-gray-600">
                                        Your information is used only for account verification, service delivery, and legal support workflows.
                                    </p>
                                </div>
                            </div>

                            <div className="space-y-3">
                                <button
                                    type="button"
                                    onClick={() => setStep('info')}
                                    className="w-full rounded-xl bg-[#0D3E6B] py-3 text-white transition-colors hover:bg-[#1e3a5f]"
                                >
                                    Continue to Complete Profile
                                </button>

                                <button
                                    type="button"
                                    onClick={onClose}
                                    className="w-full rounded-xl py-3 text-gray-600 transition-colors hover:bg-gray-100"
                                >
                                    Maybe Later
                                </button>
                            </div>
                        </div>
                    )}

                    {step === 'info' && (
                        <div className="space-y-4 px-1 pb-1">
                            <p className="text-sm leading-6 text-gray-600">
                                Please provide the missing profile information required to unlock all protected features.
                            </p>

                            <div>
                                <h4 className="mb-4 text-[#1e3a5f]">Contact Information</h4>
                                <div className="space-y-4">
                                    <div>
                                        <label className="mb-2 block text-sm text-gray-600">Email Address</label>
                                        <div className="relative">
                                            <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                                            <input
                                                type="email"
                                                value={formValues.email}
                                                onChange={(event) => handleValueChange('email', event.target.value)}
                                                placeholder="john.smith@example.com"
                                                className={`${profileInputClassName} pl-10 ${errors.email ? 'border-red-500 focus:ring-red-500/20' : ''}`}
                                            />
                                        </div>
                                        {errors.email && <p className="mt-1 text-sm text-red-600">{errors.email}</p>}
                                    </div>

                                    <div>
                                        <label className="mb-2 block text-sm text-gray-600">Phone Number</label>
                                        <div className="relative">
                                            <Phone className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                                            <input
                                                type="tel"
                                                value={formValues.mobilePhone}
                                                onChange={(event) => handleValueChange('mobilePhone', formatPhoneNumber(event.target.value))}
                                                placeholder="(555) 123-4567"
                                                className={`${profileInputClassName} pl-10 ${errors.mobilePhone ? 'border-red-500 focus:ring-red-500/20' : ''}`}
                                            />
                                        </div>
                                        {errors.mobilePhone && <p className="mt-1 text-sm text-red-600">{errors.mobilePhone}</p>}
                                    </div>
                                </div>
                            </div>

                            <div className="border-t border-gray-200 pt-4">
                                <h4 className="mb-4 text-[#1e3a5f]">Personal Information</h4>
                                <div className="space-y-4">
                                    <div>
                                        <label className="mb-2 block text-sm text-gray-600">Date of Birth</label>
                                        <input
                                            type="date"
                                            value={formValues.birthdate}
                                            onChange={(event) => handleValueChange('birthdate', event.target.value)}
                                            max={new Date().toISOString().split('T')[0]}
                                            min="1940-01-01"
                                            className={`${profileInputClassName} [color-scheme:light] ${errors.birthdate ? 'border-red-500 focus:ring-red-500/20' : ''}`}
                                        />
                                        {errors.birthdate && <p className="mt-1 text-sm text-red-600">{errors.birthdate}</p>}
                                    </div>
                                </div>
                            </div>

                            <div className="border-t border-gray-200 pt-4">
                                <h4 className="mb-4 text-[#1e3a5f]">Address</h4>
                                <div className="space-y-4">
                                    <div>
                                        <label className="mb-2 block text-sm text-gray-600">Street Address</label>
                                        <div ref={addressFieldRef} className="relative z-30">
                                            <MapPin className="absolute left-3 top-[18px] h-4 w-4 text-gray-400" />
                                            <input
                                                type="text"
                                                value={formValues.streetAddress}
                                                onFocus={() => setIsAddressMenuOpen(true)}
                                                onChange={(event) => {
                                                    handleValueChange('streetAddress', event.target.value);
                                                    setIsAddressMenuOpen(true);
                                                }}
                                                placeholder="123 Main Street"
                                                className={`${profileInputClassName} pl-10 ${errors.streetAddress ? 'border-red-500 focus:ring-red-500/20' : ''}`}
                                            />
                                            {isAddressLoading && (
                                                <div className="absolute right-4 top-1/2 -translate-y-1/2">
                                                    <div className="h-[18px] w-[18px] animate-spin rounded-full border-2 border-slate-300 border-t-[#dc2626]" />
                                                </div>
                                            )}

                                            {shouldShowAddressOptions && (
                                                <div className="absolute left-0 right-0 top-full z-[100] mt-2 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl ring-1 ring-black/5">
                                                    {addressOptions.length > 0 ? (
                                                        <ul className="max-h-64 overflow-auto py-2">
                                                            {addressOptions.map((option) => (
                                                                <li key={option.placeId}>
                                                                    <button
                                                                        type="button"
                                                                        onMouseDown={(event) => {
                                                                            event.preventDefault();
                                                                            handleAddressSelect(option);
                                                                        }}
                                                                        className="w-full px-4 py-3 text-left transition hover:bg-slate-50"
                                                                    >
                                                                        <p className="text-sm font-semibold text-slate-900">{option.mainText}</p>
                                                                        <p className="text-xs text-slate-500">{option.secondaryText || option.description}</p>
                                                                    </button>
                                                                </li>
                                                            ))}
                                                        </ul>
                                                    ) : isAddressLoading ? (
                                                        <div className="px-4 py-3 text-sm text-slate-500">Searching addresses...</div>
                                                    ) : (
                                                        <div className="px-4 py-3 text-sm text-slate-500">No address matches found</div>
                                                    )}
                                                </div>
                                            )}
                                        </div>
                                        {errors.streetAddress && <p className="mt-1 text-sm text-red-600">{errors.streetAddress}</p>}
                                        {!errors.streetAddress && !googleApiKey && (
                                            <p className="mt-1 text-sm text-slate-500">Set VITE_GOOGLE_MAPS_API_KEY in your .env to enable address search</p>
                                        )}
                                    </div>

                                    <div>
                                        <label className="mb-2 block text-sm text-gray-600">Apt / Unit</label>
                                        <input
                                            type="text"
                                            value={formValues.apt}
                                            onChange={(event) => handleValueChange('apt', event.target.value)}
                                            placeholder="Apt, suite, unit"
                                            className={profileInputClassName}
                                        />
                                    </div>

                                    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
                                        <div className="col-span-2 min-w-0 sm:col-span-2">
                                            <label className="mb-2 block text-sm text-gray-600">City</label>
                                            <input
                                                type="text"
                                                value={formValues.city}
                                                onChange={(event) => handleValueChange('city', event.target.value)}
                                                placeholder="City"
                                                className={`${profileInputClassName} ${errors.city ? 'border-red-500 focus:ring-red-500/20' : ''}`}
                                            />
                                            {errors.city && <p className="mt-1 text-sm text-red-600">{errors.city}</p>}
                                        </div>

                                        <div className="min-w-0">
                                            <label className="mb-2 block text-sm text-gray-600">State</label>
                                            <select
                                                value={formValues.state}
                                                onChange={(event) => handleValueChange('state', event.target.value)}
                                                className={`${profileInputClassName} pr-10 ${!formValues.state ? 'text-gray-400' : ''} ${errors.state ? 'border-red-500 focus:ring-red-500/20' : ''}`}
                                            >
                                                <option value="" disabled>
                                                    Select a state
                                                </option>
                                                {US_STATE_SELECT_OPTIONS.map((option) => (
                                                    <option key={option.value} value={option.value}>
                                                        {option.name}
                                                    </option>
                                                ))}
                                            </select>
                                            {errors.state && <p className="mt-1 text-sm text-red-600">{errors.state}</p>}
                                        </div>
                                    </div>

                                    <div className="min-w-0">
                                        <label className="mb-2 block text-sm text-gray-600">ZIP Code</label>
                                        <input
                                            type="text"
                                            value={formValues.zipCode}
                                            onChange={(event) => handleValueChange('zipCode', event.target.value.replace(/\D/g, '').slice(0, 5))}
                                            placeholder="75001"
                                            maxLength={5}
                                            className={`${profileInputClassName} ${errors.zipCode ? 'border-red-500 focus:ring-red-500/20' : ''}`}
                                        />
                                        {errors.zipCode && <p className="mt-1 text-sm text-red-600">{errors.zipCode}</p>}
                                    </div>
                                </div>
                            </div>

                            {/*
                            <div className="border-t border-gray-200 pt-4">
                                <h4 className="mb-4 text-[#1e3a5f]">License Information</h4>
                                <div className="space-y-4">
                                    <div>
                                        <label className="mb-2 block text-sm text-gray-600">CDL Number</label>
                                        <input
                                            type="text"
                                            value={formValues.cdlNumber}
                                            onChange={(event) => handleValueChange('cdlNumber', event.target.value.toUpperCase())}
                                            placeholder="TN-998877"
                                            className={`${profileInputClassName} ${errors.cdlNumber ? 'border-red-500 focus:ring-red-500/20' : ''}`}
                                        />
                                        {errors.cdlNumber && <p className="mt-1 text-sm text-red-600">{errors.cdlNumber}</p>}
                                    </div>

                                    <div>
                                        <label className="mb-2 block text-sm text-gray-600">CDL State</label>
                                        <select
                                            value={formValues.cdlState}
                                            onChange={(event) => handleValueChange('cdlState', event.target.value)}
                                            className={`${profileInputClassName} ${!formValues.cdlState ? 'text-gray-400' : ''} ${errors.cdlState ? 'border-red-500 focus:ring-red-500/20' : ''}`}
                                        >
                                            <option value="" disabled>
                                                {isCdlStateOptionsLoading ? 'Loading states...' : 'Select a CDL state'}
                                            </option>
                                            {cdlStateOptions.map((option) => (
                                                <option key={option.value} value={option.value}>
                                                    {option.Name}
                                                </option>
                                            ))}
                                        </select>
                                        {errors.cdlState && <p className="mt-1 text-sm text-red-600">{errors.cdlState}</p>}
                                    </div>
                                </div>
                            </div>
                            */}

                            <button
                                type="button"
                                onClick={handleSubmit}
                                disabled={isSubmitting}
                                className={`mt-2 flex w-full items-center justify-center gap-2 rounded-full py-3 transition-all ${isSubmitting
                                        ? 'cursor-wait bg-[#0D3E6B]/70 text-white'
                                        : 'bg-[#0D3E6B] text-white hover:bg-[#1e3a5f]'
                                    }`}
                            >
                                {isSubmitting && <LoaderCircle className="h-4 w-4 animate-spin" />}
                                <span>{isSubmitting ? 'Saving Profile...' : 'Complete Profile'}</span>
                            </button>

                            <button
                                type="button"
                                onClick={onClose}
                                disabled={isSubmitting}
                                className="w-full rounded-full py-3 text-gray-600 transition-colors hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-60"
                            >
                                I'll do this later
                            </button>
                        </div>
                    )}

                    {step === 'success' && (
                        <div className="px-2 py-8 text-center">
                            <div className="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-[#E8F4F8]">
                                <CheckCircle className="h-12 w-12 text-[#0D3E6B]" />
                            </div>
                            <h2 className="mb-3 text-2xl text-[#1e3a5f]">{successState.title}</h2>
                            <p className="mx-auto max-w-sm text-sm leading-6 text-gray-600">{successState.description}</p>
                        </div>
                    )}
                </div>
            </ModalContent>
        </Modal>
    );
}