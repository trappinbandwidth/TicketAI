import { useState, useCallback, useEffect } from 'react';
import { loadStripe } from '@stripe/stripe-js';
import { Elements, CardCvcElement, useElements, useStripe } from '@stripe/react-stripe-js';
import { useAtom } from 'jotai';

import LucideIcon from 'src/components/lucide-icon';
import { Button, Modal, ModalContent } from 'src/components/ui';
import { httpService } from 'src/apiSetUp';
import { constants } from 'src/constants.value';
import { TicketPaymentItem } from 'src/common-service/types.interface';
import { fDate } from 'src/utils/format-time';
import { driverProfile } from 'src/store';
import { useDriverPaymentMethodsQuery } from 'src/queries/use-billing-query';
import { cn } from 'src/lib/utils';

const stripePromise = loadStripe(import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY);

const CVC_OPTIONS = {
  style: {
    base: {
      fontSize: '16px',
      color: '#1e3a5f',
      fontFamily: 'Inter, Helvetica, Arial, sans-serif',
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
};

interface SavedPaymentMethod {
  id: string;
  customerId?: string;
  cardId?: string;
  brand?: string;
  cardBrand?: string;
  cardLast4Digits?: string;
  last4?: string;
  expirationMonth?: string;
  expirationYear?: string;
  isDefault?: boolean;
  status?: string;
}

interface TicketPaymentModalProps {
  open: boolean;
  onClose: () => void;
  paymentItems: TicketPaymentItem[];
  ticketId: string;
  ticketName: string;
  onPaymentComplete: () => void;
}

function TicketPaymentModalContent({
  open,
  onClose,
  paymentItems,
  ticketId,
  ticketName,
  onPaymentComplete,
}: TicketPaymentModalProps) {
  const stripe = useStripe();
  const elements = useElements();
  const [selectedItem, setSelectedItem] = useState<TicketPaymentItem | null>(null);
  const [payOption, setPayOption] = useState<'now' | 'later' | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [paymentSuccess, setPaymentSuccess] = useState(false);
  const [savedCards, setSavedCards] = useState<SavedPaymentMethod[]>([]);
  const [selectedCardId, setSelectedCardId] = useState<string>('');
  const [isCvcComplete, setIsCvcComplete] = useState(false);
  const [driverData] = useAtom(driverProfile);
  const paymentMethodsQuery = useDriverPaymentMethodsQuery(open);
  const isCardsLoading = paymentMethodsQuery.isLoading || paymentMethodsQuery.isFetching;

  useEffect(() => {
    const methods = paymentMethodsQuery.data?.Result?.data?.paymentMethods || [];
    setSavedCards(methods);

    const defaultMethod = methods.find((method: SavedPaymentMethod) => method.isDefault || method.status === 'Default');
    setSelectedCardId(defaultMethod?.id || methods[0]?.id || '');
  }, [paymentMethodsQuery.data]);

  const handleSelectPayment = useCallback((item: TicketPaymentItem, option: 'now' | 'later') => {
    setSelectedItem(item);
    setPayOption(option);
    setError(null);
    setIsCvcComplete(false);
  }, []);

  const handleProceedToPayment = useCallback(async () => {
    if (!selectedItem || !payOption || !stripe || !elements) {
      if (!stripe || !elements) {
        setError('Stripe has not loaded yet. Please try again.');
      }
      return;
    }

    const selectedCard = savedCards.find((card) => card.id === selectedCardId);
    if (!selectedCard?.id) {
      setError('Please select a saved card.');
      return;
    }

    const paymentMethodId = selectedCard.cardId;
    if (!paymentMethodId) {
      setError('Selected card is missing payment method information. Please choose another card.');
      return;
    }

    if (!selectedCard.customerId) {
      setError('Selected card is missing customer information. Please choose another card.');
      return;
    }

    const cvcElement = elements.getElement(CardCvcElement);
    if (!cvcElement) {
      setError('CVC field is not ready. Please try again.');
      return;
    }

    const amount = payOption === 'now' ? selectedItem.payNow : selectedItem.payLater;
    setIsLoading(true);
    setError(null);

    try {
      const amountInCents = Math.round(Number(amount) * 100);
      const checkoutSessionResponse = await httpService()
        .post(`${constants.API_BASE}/${constants.API_VERSION}PaymentGateway/CreateCheckoutSession`, {
          UsageMode: 'saved_card',
          Amount: amountInCents,
          Currency: 'usd',
          CustomerId: selectedCard.customerId,
          PaymentMethodId: paymentMethodId,
          Description: 'Ticket payment - Driver Portal',
          metadata: {
            sf_id: `a1d${selectedItem.transactionId}`,
            bt_payment_key: selectedItem.stripeKey,
            opportunity_id: `006${selectedItem.opportunityId}`,
            contact_id: `003${selectedItem.contactId}`,
            driver_id: `001${selectedItem.accountId}`,
            ticket_id: `a0y${selectedItem.ticketId}`,
            ticketName: selectedItem.ticketName,
            customerEmail: driverData?.email || '',
          },
        })
        .then((response) => response.data);

      if (checkoutSessionResponse?.StatusCode !== constants.RESPONSE_STATUS.SUCCESS) {
        throw new Error(checkoutSessionResponse?.Message || 'Failed to initialize saved-card payment.');
      }

      const clientSecret = checkoutSessionResponse?.Result?.clientSecret;
      if (!clientSecret) {
        throw new Error('No client secret returned from payment service.');
      }

      const { error: stripeError, paymentIntent } = await stripe.confirmCardPayment(clientSecret, {
        payment_method: paymentMethodId,
        payment_method_options: {
          card: {
            cvc: cvcElement,
          },
        },
      });

      if (stripeError) {
        throw new Error(stripeError.message || 'Payment confirmation failed.');
      }

      if (paymentIntent?.status === 'succeeded') {
        setPaymentSuccess(true);
        return;
      }

      throw new Error(`Payment status: ${paymentIntent?.status || 'unknown'}`);
    } catch (err: any) {
      setError(err?.response?.data?.Message || err.message || 'Failed to process payment. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }, [selectedItem, payOption, stripe, elements, savedCards, selectedCardId, ticketId, ticketName, driverData?.email]);

  const handleBack = useCallback(() => {
    if (selectedItem) {
      setSelectedItem(null);
      setPayOption(null);
    }
    setIsCvcComplete(false);
    setError(null);
  }, [selectedItem]);

  const handleClose = useCallback(() => {
    if (paymentSuccess) {
      onPaymentComplete();
    }
    setSelectedItem(null);
    setPayOption(null);
    setSelectedCardId('');
    setIsCvcComplete(false);
    setError(null);
    setPaymentSuccess(false);
    onClose();
  }, [onClose, onPaymentComplete, paymentSuccess]);

  return (
    <Modal open={open} onOpenChange={(nextOpen) => !nextOpen && handleClose()}>
      <ModalContent hideCloseButton className="mvp-modal-shell w-[calc(100%-1rem)] max-w-2xl p-0 sm:w-[calc(100%-2rem)]">
        <div className="mvp-modal-header sticky top-0 z-10 px-5 py-4">
          <div className="flex min-w-0 flex-1 items-center gap-3">
            {selectedItem ? (
              <button
                type="button"
                onClick={handleBack}
                className="rounded-full p-2 text-[#1e3a5f] transition hover:bg-slate-100"
              >
                <LucideIcon name="ArrowLeft" size={20} />
              </button>
            ) : null}
            <div className="min-w-0">
              <h2 className="truncate text-base font-semibold text-[#1e3a5f]">
                {selectedItem ? 'Process Payment' : 'Payment Required'}
              </h2>
              <p className="truncate text-xs text-slate-500">{ticketName}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={handleClose}
            className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-100 text-slate-500 transition hover:bg-slate-200"
          >
            <LucideIcon name="CircleX" size={22} />
          </button>
        </div>

        <div className="mvp-modal-body p-5">
          {paymentSuccess && (
            <div className="py-6 text-center">
              <div className="mx-auto mb-4 flex h-[72px] w-[72px] items-center justify-center rounded-full bg-green-100">
                <LucideIcon name="CircleCheck" size={40} color="#4caf50" />
              </div>
              <h3 className="mb-2 text-xl font-bold text-[#1a365d]">Payment Successful!</h3>
              <p className="mb-6 text-sm text-slate-500">Your payment has been processed successfully.</p>
              <Button type="button" onClick={handleClose} className="rounded-xl bg-[#1a365d] px-6 hover:bg-[#152d47]">
                Done
              </Button>
            </div>
          )}

          {!paymentSuccess && selectedItem && (
            <div className="space-y-4 pb-2">
              <div className="overflow-hidden rounded-[28px] bg-[linear-gradient(135deg,#0D3E6B_0%,#1e3a5f_55%,#0b2e4f_100%)] p-6 text-white shadow-[0_24px_55px_rgba(13,62,107,0.28)]">
                <div className="mb-2 flex items-center gap-2 text-xs text-white/90">
                  <LucideIcon name="DollarSign" size={16} color="rgba(255,255,255,0.9)" />
                  <span>Payment Amount</span>
                </div>
                <p className="mb-1 text-4xl font-bold leading-tight text-white">
                  ${(payOption === 'now' ? selectedItem.payNow : selectedItem.payLater).toFixed(2)}
                </p>
                <p className="text-sm text-white/85">{selectedItem.reason}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <span className="rounded-full bg-white/15 px-3 py-1 text-xs font-semibold text-white">
                    Due {fDate(selectedItem.dueDate)}
                  </span>
                  <span className="rounded-full bg-white/15 px-3 py-1 text-xs font-semibold text-white">
                    {payOption === 'now' ? 'Pay Now' : 'Pay Later'}
                  </span>
                </div>
              </div>

              <div className="rounded-[24px] border border-[#BFDBFE] bg-[#EFF6FF] p-4">
                <div className="flex items-start gap-3">
                  <LucideIcon name="CircleAlert" size={18} color="#2563eb" />
                  <p className="text-sm text-[#1e3a5f]">
                    This payment will be processed immediately and applied to your ticket {ticketName}.
                  </p>
                </div>
              </div>

              <div className="rounded-[24px] border border-slate-200 bg-white p-4 shadow-[0_10px_24px_rgba(15,23,42,0.05)]">
                <p className="mb-3 text-sm text-slate-700">Select payment method</p>

                {isCardsLoading ? (
                  <div className="flex items-center gap-3 text-sm text-slate-500">
                    <span className="h-[18px] w-[18px] animate-spin rounded-full border-2 border-slate-300 border-t-[#1e3a5f]" />
                    <span>Loading saved cards...</span>
                  </div>
                ) : savedCards.length === 0 ? (
                  <p className="text-sm text-red-600">No saved card found. Please add a card in Billing & Payments.</p>
                ) : (
                  <div className="space-y-2">
                    {savedCards.map((card) => {
                      const isSelected = selectedCardId === card.id;
                      const brand = card.brand || card.cardBrand || 'Card';
                      const last4 = card.cardLast4Digits || card.last4 || '••••';
                      const isDefaultCard = card.isDefault || card.status === 'Default';

                      return (
                        <button
                          key={card.id}
                          type="button"
                          onClick={() => setSelectedCardId(card.id)}
                          className={cn(
                            'w-full rounded-xl border-2 px-4 py-3 text-left transition',
                            isSelected
                              ? 'border-[#003E6B] bg-[#EFF6FF]'
                              : 'border-slate-200 bg-white hover:border-slate-300'
                          )}
                        >
                          <div className="flex items-center gap-3">
                            <span
                              className={cn(
                                'flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2',
                                isSelected ? 'border-[#003E6B] bg-[#003E6B]' : 'border-slate-300 bg-transparent'
                              )}
                            >
                              {isSelected ? <span className="h-2 w-2 rounded-full bg-white" /> : null}
                            </span>
                            <div className="flex items-center gap-2">
                              <LucideIcon name="CreditCard" size={18} color="#6b7280" />
                              <span className="text-sm font-semibold text-[#1a365d]">
                                {brand} •••• {last4}
                              </span>
                            </div>
                            <div className="ml-auto">
                              {isDefaultCard ? (
                                <span className="rounded-full bg-[#EFF6FF] px-2.5 py-1 text-xs font-semibold text-[#1e3a5f]">
                                  Default
                                </span>
                              ) : null}
                            </div>
                          </div>
                          <p className="ml-8 mt-1 text-xs text-slate-500">
                            Expires {card.expirationMonth || '--'}/{card.expirationYear || '--'}
                          </p>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>

              <div className="rounded-[24px] border border-slate-300 bg-slate-50 p-4">
                <p className="mb-2 text-sm text-slate-700">CVV for verification</p>
                <CardCvcElement
                  options={CVC_OPTIONS}
                  onChange={(event) => {
                    setIsCvcComplete(Boolean(event.complete));
                    if (event.error) {
                      setError(event.error.message || 'Invalid CVC');
                    } else {
                      setError((prevError) => (prevError && prevError.toLowerCase().includes('cvc') ? null : prevError));
                    }
                  }}
                />
              </div>

              {error ? (
                <div className="rounded-xl border border-red-200 bg-red-50 p-4">
                  <div className="flex items-center gap-2">
                    <LucideIcon name="TriangleAlert" size={20} color="#ef4444" />
                    <p className="text-sm text-red-700">{error}</p>
                  </div>
                </div>
              ) : null}

              <div className="mt-2 flex gap-3">
                <button
                  type="button"
                  onClick={handleBack}
                  disabled={isLoading}
                  className="flex-1 rounded-xl bg-[#F3F4F6] py-3 text-[0.95rem] font-semibold text-[#374151] transition hover:bg-[#E5E7EB] disabled:cursor-not-allowed"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleProceedToPayment}
                  disabled={isLoading || isCardsLoading || savedCards.length === 0 || !selectedCardId || !isCvcComplete}
                  className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-[#dc2626] py-3 text-[0.95rem] font-semibold text-white transition hover:bg-[#b91c1c] disabled:cursor-not-allowed disabled:opacity-70"
                >
                  {isLoading ? (
                    <>
                      <span className="h-[18px] w-[18px] animate-spin rounded-full border-2 border-white/40 border-t-white" />
                      Processing...
                    </>
                  ) : (
                    <>
                      <LucideIcon name="DollarSign" size={18} />
                      Pay ${(payOption === 'now' ? selectedItem.payNow : selectedItem.payLater).toFixed(2)}
                    </>
                  )}
                </button>
              </div>

              <p className="text-center text-xs text-slate-500">Your payment information is secure and encrypted</p>
            </div>
          )}

          {!paymentSuccess && !selectedItem && (
            <div className="space-y-4 pb-2">
              <div className="rounded-[24px] border border-[#BFDBFE] bg-[#EFF6FF] p-4">
                <div className="flex items-start gap-3">
                  <LucideIcon name="CircleAlert" size={18} color="#2563eb" />
                  <div>
                    <p className="mb-1 text-sm font-semibold text-[#1e3a5f]">Payment Required</p>
                    <p className="text-sm text-[#1e3a5f]">
                      The following payment(s) are required to proceed with your case. Please select a payment option below.
                    </p>
                  </div>
                </div>
              </div>

              <div className="space-y-4">
                {paymentItems.map((item) => (
                  <div key={item.transactionId} className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
                    <div className="flex items-center justify-between gap-3 bg-slate-50 px-4 py-3">
                      <div className="flex items-center gap-2">
                        <LucideIcon name="FileText" size={16} color="#1e3a5f" />
                        <p className="text-sm font-semibold text-[#1a365d]">{item.reason}</p>
                      </div>
                      <span className="rounded-full border border-[#BFDBFE] bg-[#EFF6FF] px-2.5 py-1 text-[0.7rem] font-semibold text-[#1e3a5f]">
                        Due {fDate(item.dueDate)}
                      </span>
                    </div>

                    <div className="p-4">
                      <button
                        type="button"
                        onClick={() => handleSelectPayment(item, 'now')}
                        className="flex w-full items-center justify-between rounded-2xl border-2 border-green-600 bg-green-50 p-4 text-left transition hover:-translate-y-px hover:bg-green-100 hover:shadow-sm"
                      >
                        <div className="flex items-center gap-4">
                          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-green-600">
                            <LucideIcon name="Wallet" size={18} color="white" />
                          </div>
                          <div>
                            <p className="text-sm font-semibold text-green-800">Pay Now</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-2xl font-bold text-green-800">${item.payNow.toFixed(2)}</span>
                          <LucideIcon name="ArrowRight" size={18} color="#166534" />
                        </div>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </ModalContent>
    </Modal>
  );
}

export default function TicketPaymentModal(props: TicketPaymentModalProps) {
  return (
    <Elements stripe={stripePromise}>
      <TicketPaymentModalContent {...props} />
    </Elements>
  );
}
