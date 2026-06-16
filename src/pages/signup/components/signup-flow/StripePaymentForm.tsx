import { useState } from 'react';
import { CardElement, useStripe, useElements } from '@stripe/react-stripe-js';
import { StripeCardElementOptions } from '@stripe/stripe-js';
import LucideIcon from 'src/components/lucide-icon';
import { constants } from 'src/constants.value';
import { httpService } from 'src/apiSetUp';
import { driverRegistraction, driverRegistration } from 'src/utils/api-service';
import { setDataIntoStorage } from 'src/common-service/index.service';
import { useNavigate } from 'react-router-dom';
import { Button } from 'src/components/ui';

interface StripePaymentFormProps {
    amount: number;
    billingFrequency: 'monthly' | 'quarterly' | 'annually';
    onSuccess: () => void;
    onError: (error: string) => void;
    userInfo: {
        firstName: string;
        lastName: string;
        email: string;
        phone: string;
        address: string;
        city: string;
        state: string;
        zip: string;
    };
    planData: {
        id: string;
        tier: string;
        frequency: string;
        amount: number;
    };
}

const CARD_ELEMENT_OPTIONS: StripeCardElementOptions = {
    style: {
        base: {
            fontSize: '16px',
            color: '#1e3a5f',
            fontFamily: '"Inter", "Helvetica", "Arial", sans-serif',
            fontSmoothing: 'antialiased',
            '::placeholder': {
                color: '#94a3b8',
            },
        },
        invalid: {
            color: '#d32f2f',
            iconColor: '#d32f2f',
        },
    },
    hidePostalCode: true,
};

export default function StripePaymentForm({
    amount,
    billingFrequency,
    onSuccess,
    onError,
    userInfo,
    planData,
}: StripePaymentFormProps) {
    const stripe = useStripe();
    const navigate = useNavigate();
    const elements = useElements();
    const [isProcessing, setIsProcessing] = useState(false);
    const [cardError, setCardError] = useState<string | null>(null);

    const handleSubmit = async (event: React.FormEvent) => {
        event.preventDefault();

        if (!stripe || !elements) {
            onError('Stripe has not loaded yet. Please try again.');
            return;
        }

        const cardElement = elements.getElement(CardElement);
        if (!cardElement) {
            onError('Card element not found. Please refresh the page.');
            return;
        }

        setIsProcessing(true);
        setCardError(null);

        try {
            // Step 1: Create Checkout Session on your backend
            const checkoutSessionResponse = await httpService()
                .post(`${constants.API_BASE}/${constants.API_VERSION}PaymentGateway/CreateCheckoutSession`, {
                    Amount: Math.round(amount * 100), // Convert to cents
                    Currency: 'usd',
                    metadata: {
                        planId: planData.id,
                        tier: planData.tier,
                        frequency: planData.frequency,
                        customerEmail: userInfo.email,
                        customerName: `${userInfo.firstName} ${userInfo.lastName}`,
                    },
                })
                .then((response) => response.data)
                .catch((error) => {
                    console.error('Checkout session error:', error);
                    throw new Error(error.response?.data?.Message || 'Failed to create payment session');
                });

            // Check if the API response is successful
            if (checkoutSessionResponse?.StatusCode !== constants.RESPONSE_STATUS.SUCCESS) {
                throw new Error(checkoutSessionResponse?.Message || 'Failed to create payment session');
            }

            // Extract client secret from response
            const { clientSecret, paymentIntentId } = checkoutSessionResponse.Result || {};

            if (!clientSecret) {
                throw new Error('No client secret received from server');
            }

            // Step 2: Confirm the payment with Stripe
            const { error: stripeError, paymentIntent } = await stripe.confirmCardPayment(clientSecret, {
                payment_method: {
                    card: cardElement,
                    billing_details: {
                        name: `${userInfo.firstName} ${userInfo.lastName}`,
                        email: userInfo.email,
                        phone: userInfo.phone,
                        address: {
                            line1: userInfo.address,
                            city: userInfo.city,
                            state: userInfo.state,
                            postal_code: userInfo.zip,
                            country: 'US',
                        },
                    },
                },
            });

            if (stripeError) {
                throw new Error(stripeError.message || 'Payment failed');
            }

            if (paymentIntent?.status === 'succeeded') {
                // Step 3: Call driver registration API (Salesforce) after successful payment
                const salesforceData = {
                    firstName: userInfo.firstName,
                    lastName: userInfo.lastName,
                    email: userInfo.email,
                    phone: userInfo.phone,
                    streetAddress: userInfo.address,
                    city: userInfo.city,
                    state: userInfo.state,
                    zipCode: userInfo.zip,
                    cdlNumber: '', // Optional - can be added to form if needed
                    cdlState: '', // Optional - can be added to form if needed
                    product: planData.id,
                    billingFrequency: planData.frequency,
                    amount: planData.amount.toString(),
                };

                const registrationResponse = await driverRegistration(salesforceData);

                // Extract driverId from Salesforce response
                const driverId = registrationResponse?.Result?.data?.driverId;

                if (!driverId) {
                    throw new Error('Registration incomplete. Please contact support.');
                }

                const mongoDbData = {
                    FirstName: userInfo.firstName,
                    LastName: userInfo.lastName,
                    Email: userInfo.email,
                    PhoneNumber: userInfo.phone,
                    Address: userInfo.address,
                    City: userInfo.city,
                    State: userInfo.state,
                    Zip: userInfo.zip,
                    DriverId: driverId, // Use driverId from Salesforce
                    IsMVR: false,
                    PlanData: {
                        id: planData.id,
                        tier: planData.tier,
                        frequency: planData.frequency,
                        amount: planData.amount,
                    },
                    PaymentData: {
                        paymentIntentId: paymentIntent.id,
                        amount: Number(paymentIntent.amount) / 100, // Convert from cents
                        status: paymentIntent.status,
                        paymentMethod: paymentIntent.payment_method as string,
                    },
                };
                const mongoDbResponse = await driverRegistraction(mongoDbData);
                if (mongoDbResponse?.StatusCode === constants.RESPONSE_STATUS.SUCCESS) {
                    await setDataIntoStorage('driver_token', mongoDbResponse.Result.Data.AccessToken);
                    await setDataIntoStorage('driver_refresh_token', mongoDbResponse.Result.Data.RefreshToken);
                    navigate('/dashboard');
                }
            } else {
                throw new Error('Payment not completed');
            }
        } catch (error: any) {
            setCardError(error.message || 'An unexpected error occurred');
            onError(error.message || 'Payment failed. Please try again.');
        } finally {
            setIsProcessing(false);
        }
    };

    const handleCardChange = (event: any) => {
        if (event.error) {
            setCardError(event.error.message);
        } else {
            setCardError(null);
        }
    };

    return (
        <form onSubmit={handleSubmit}>
            <div className="space-y-4">
                {/* Stripe Card Element */}
                <div
                    className={`rounded-lg border bg-white p-4 transition-colors hover:border-[#0D3E6B] ${
                        cardError ? 'border-red-500 hover:border-red-500' : 'border-gray-300'
                    }`}
                >
                    <CardElement
                        options={CARD_ELEMENT_OPTIONS}
                        onChange={handleCardChange}
                    />
                </div>

                {/* Card Error Message */}
                {cardError && (
                    <p className="mt-1 text-xs text-red-500">{cardError}</p>
                )}

                {/* Secure Payment Info */}
                <div className="rounded-xl border border-blue-200 bg-blue-50 p-4">
                    <div className="flex items-start gap-3">
                        <LucideIcon
                            name="ShieldCheck"
                            size={22}
                            color="#0D3E6B"
                            style={{ marginTop: 2 }}
                        />
                        <div>
                            <p className="mb-1 text-sm font-semibold text-[#0D3E6B]">
                                Secure Payment powered by Stripe
                            </p>
                            <p className="text-sm text-gray-500">
                                Your payment information is encrypted and secure. You&apos;ll be charged $
                                {amount.toFixed(2)} today
                                {billingFrequency === 'quarterly'
                                    ? ' and then quarterly'
                                    : billingFrequency === 'annually'
                                        ? ' and then annually'
                                        : ' and then monthly'}{' '}
                                on this date.
                            </p>
                        </div>
                    </div>
                </div>

                {/* Submit Button */}
                <Button
                    type="submit"
                    fullWidth
                    disabled={isProcessing || !stripe || !elements}
                    className="mt-3 bg-[#F97316] text-base hover:bg-[#ea580c] disabled:bg-gray-300"
                >
                    {isProcessing ? (
                        <div className="h-6 w-6 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                    ) : (
                        `Pay $${amount.toFixed(2)} and Complete Sign Up`
                    )}
                </Button>

                <p className="mt-4 block text-center text-xs text-gray-500">
                    By completing this purchase, you agree to our Terms of Service and Privacy Policy
                </p>
            </div>
        </form>
    );
}
