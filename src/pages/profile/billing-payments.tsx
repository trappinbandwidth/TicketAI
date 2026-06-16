import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { DashboardContent } from 'src/layouts/dashboard';
import { yupResolver } from '@hookform/resolvers/yup';
import * as Yup from 'yup';
import { useForm } from 'react-hook-form';
import { FormProvider, RHFCheckbox, RHFTextField } from 'src/hook-form';
import PaymentMethodItem from './components/payment-method-item';
import TransactionListItem from './components/transaction-list-item';
import LucideIcon from 'src/components/lucide-icon';
import { Button, Modal, ModalContent, ModalTitle } from 'src/components/ui';
import { toasterService } from 'src/apiSetUp';
import { fDate } from 'src/utils/format-time';
import { fetchDriverPaymentMethodStatusQuery, useDriverPaymentMethodsQuery, useDriverTransactionsQuery } from 'src/queries/use-billing-query';
import {
    useCreatePaymentMethodMutation,
    useDeletePaymentMethodMutation,
    useSetDefaultPaymentMethodMutation,
} from 'src/queries/use-billing-mutations';

export default function BillingPaymentsPage() {
    const navigate = useNavigate();
    const [isPaymentMethodsExpanded, setIsPaymentMethodsExpanded] = useState(true);
    const [isTransactionHistoryExpanded, setIsTransactionHistoryExpanded] = useState(true);
    const [selectedReceipt, setSelectedReceipt] = useState<any>(null);
    const [showReceiptModal, setShowReceiptModal] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [showAddCard, setShowAddCard] = useState(false);
    const [isActionLoading, setIsActionLoading] = useState(false);
    const [actionMessage, setActionMessage] = useState('');
    const [activeActionId, setActiveActionId] = useState<string | null>(null);
    const sectionCardClassName = 'mb-4 overflow-hidden rounded-[2rem] border border-slate-200 bg-white shadow-[0_22px_60px_rgba(15,23,42,0.08)]';
    const sectionBodyClassName = 'border-t border-slate-200 px-5 py-5 sm:px-6';

    const paymentSchema = Yup.object().shape({
        cardHolderName: Yup.string().required('Cardholder name is required'),
        cardNumber: Yup.string().required('Card number is required').min(12, 'Enter a valid card number'),
        expirationMonth: Yup.string()
            .required('Expiry month is required')
            .matches(/^(0?[1-9]|1[0-2])$/, 'Use MM format'),
        expirationYear: Yup.string()
            .required('Expiration year is required')
            .matches(/^[0-9]{4}$/, 'Expiration year must be 4 digits')
            .test('valid-year', 'Expiration year must be current year or later', function (value) {
                if (!value) return false;
                const currentYear = new Date().getFullYear();
                return parseInt(value) >= currentYear;
            }),
        cvv: Yup.string()
            .required('CVV is required')
            .min(3, 'Enter a valid CVV')
            .max(4, 'Enter a valid CVV'),
        billingPostalCode: Yup.string().optional(),
        isDefault: Yup.boolean().optional(),
    });

    const methodsForm = useForm({
        resolver: yupResolver(paymentSchema) as any,
        mode: 'all',
        defaultValues: {
            cardHolderName: '',
            cardNumber: '',
            expirationMonth: '',
            expirationYear: '',
            cvv: '',
            billingPostalCode: '',
            isDefault: false,
        },
    });

    const { handleSubmit: handlePaymentSubmit, reset: resetPaymentForm } = methodsForm;

    const paymentMethodsQuery = useDriverPaymentMethodsQuery(true);
    const transactionsQuery = useDriverTransactionsQuery(true);
    const setDefaultMutation = useSetDefaultPaymentMethodMutation();
    const deletePaymentMethodMutation = useDeletePaymentMethodMutation();
    const createPaymentMethodMutation = useCreatePaymentMethodMutation();

    useEffect(() => {
        setIsLoading(
            paymentMethodsQuery.isLoading ||
            paymentMethodsQuery.isFetching ||
            transactionsQuery.isLoading ||
            transactionsQuery.isFetching
        );
    }, [
        paymentMethodsQuery.isLoading,
        paymentMethodsQuery.isFetching,
        transactionsQuery.isLoading,
        transactionsQuery.isFetching,
    ]);

    useEffect(() => {
        if (showAddCard) {
            resetPaymentForm();
        }
    }, [showAddCard, resetPaymentForm]);

    const methods = paymentMethodsQuery.data?.Result?.data?.paymentMethods || [];
    const history = transactionsQuery.data?.Result?.data?.transactions || [];

    const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

    const refreshPaymentMethods = async () => {
        const result = await paymentMethodsQuery.refetch();

        if (result.error) {
            throw result.error;
        }

        return result.data;
    };

    const pollPaymentMethodStatus = async (paymentMethodId: string, operationType: string) => {
        const maxAttempts = 15;

        for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
            await wait(2000);
            const statusData = await fetchDriverPaymentMethodStatusQuery(paymentMethodId, operationType);
            if (!statusData) {
                continue;
            }
            if (statusData?.state === "processed") {
                return { ...statusData, isProcessed: true };
            } else if (statusData?.state === "failed") {
                return { ...statusData, isProcessed: true };
            }
        }

        return null;
    };

    const getStatusMessage = (status: string | null, action: 'create' | 'delete') => {
        if (!status) {
            return 'Payment method processing is taking longer than expected. Please try again shortly.';
        }

        if (status === 'Valid') {
            return 'Payment method added and validated successfully.';
        }

        if (status === 'Deleted from Payment Gateway"') {
            return 'Payment method removed successfully.';
        }

        if (status === 'Invalid') {
            return action === 'create'
                ? 'Card validation failed. Please check the card details and try again.'
                : 'Unable to delete the payment method. Please try again.';
        }

        if (status === 'Expired') {
            return 'This card is expired. Please use a different card.';
        }

        return `Payment method status: ${status}`;
    };

    const handleSetDefault = async (id: string) => {
        setIsActionLoading(true);
        setActionMessage('Updating default payment method...');
        setActiveActionId(id);

        try {
            const response = await setDefaultMutation.mutateAsync(id);

            if (response?.StatusCode >= 200 && response?.StatusCode < 300) {
                toasterService('Default payment method updated.', 2, 'Success');
            } else {
                const errorMessage = response?.Message || response?.Errors?.[0]?.Message || 'Failed to update default payment method.';
                toasterService(errorMessage, 4, 'Error');
            }
        } catch (error: any) {
            toasterService(error?.message || 'Failed to update default payment method.', 4, 'Error');
        } finally {
            setIsActionLoading(false);
            setActionMessage('');
            setActiveActionId(null);
        }
    };

    const handleRemoveCard = async (id: string) => {
        setIsActionLoading(true);
        setActionMessage('Removing payment method...');
        setActiveActionId(id);

        try {
            const response = await deletePaymentMethodMutation.mutateAsync(id);

            if (response?.StatusCode >= 200 && response?.StatusCode < 300) {
                const paymentMethodId = response?.Result?.data?.id || id;
                setActionMessage('Confirming removal...');
                const statusData = await pollPaymentMethodStatus(paymentMethodId, 'delete');

                if (statusData?.isProcessed) {
                    setActionMessage('Refreshing payment methods...');
                    await refreshPaymentMethods();
                    const message = getStatusMessage(statusData?.status ?? null, 'delete');
                    const isSuccess = statusData?.status === 'Deleted from Payment Gateway';
                    toasterService(message, isSuccess ? 2 : 4, isSuccess ? 'Success' : 'Error');
                } else {
                    toasterService(getStatusMessage(null, 'delete'), 3, 'Warning');
                }
            } else {
                const errorMessage = response?.Message || response?.Errors?.[0]?.Message || 'Failed to remove payment method.';
                toasterService(errorMessage, 4, 'Error');
            }
        } catch (error: any) {
            toasterService(error?.message || 'Failed to remove payment method.', 4, 'Error');
        } finally {
            setIsActionLoading(false);
            setActionMessage('');
            setActiveActionId(null);
        }
    };

    const handleAddCard = async (data: any) => {
        setIsActionLoading(true);
        setActionMessage('Adding payment method...');

        try {
            const payload = {
                action: 'create' as const,
                cardHolderName: data.cardHolderName.trim(),
                cardNumber: data.cardNumber.replace(/\s+/g, ''),
                expirationMonth: data.expirationMonth.padStart(2, '0'),
                expirationYear: data.expirationYear,
                cvv: data.cvv,
                ...(data.billingPostalCode ? { billingPostalCode: data.billingPostalCode.trim() } : {}),
                ...(data.isDefault ? { isDefault: true } : {}),
            };

            const response = await createPaymentMethodMutation.mutateAsync(payload);

            if (response?.StatusCode >= 200 && response?.StatusCode < 300) {
                const paymentMethodId = response?.Result?.data?.id;
                if (!paymentMethodId) {
                    toasterService('Payment method created but no ID was returned.', 3, 'Warning');
                    return;
                }
                setActionMessage('Validating payment method...');
                const statusData = await pollPaymentMethodStatus(paymentMethodId, 'create');

                if (statusData?.isProcessed) {
                    setActionMessage('Refreshing payment methods...');
                    await refreshPaymentMethods();
                    const message = getStatusMessage(statusData?.status ?? null, 'create');
                    const isSuccess = statusData?.status === 'Valid';
                    toasterService(message, isSuccess ? 2 : 4, isSuccess ? 'Success' : 'Error');
                } else {
                    toasterService(getStatusMessage(null, 'create'), 3, 'Warning');
                }

                setShowAddCard(false);
            } else {
                const errorMessage = response?.Message || response?.Errors?.[0]?.Message || 'Failed to add payment method.';
                toasterService(errorMessage, 4, 'Error');
            }
        } catch (error: any) {
            toasterService(error?.message || 'Failed to add payment method.', 4, 'Error');
        } finally {
            setIsActionLoading(false);
            setActionMessage('');
        }
    };

    const handleViewReceipt = (transaction: any) => {
        setSelectedReceipt(transaction);
        setShowReceiptModal(true);
    };

    const handleDownloadReceipt = (transaction: any) => {
        const receiptContent = `
CDL LEGAL - RECEIPT
Receipt ID: ${transaction.id}
Transaction ID: ${transaction.transactionId || transaction.id}

Date: ${fDate(transaction.dueDate || transaction.createdAt)}
Amount: $${(transaction.amount || 0).toFixed(2)}
Description: ${transaction.opportunityName || transaction.name}
Status: ${transaction.status || 'Completed'}
Type: ${transaction.transactionType || 'Normal'}

Thank you for your business!
        `.trim();

        const blob = new Blob([receiptContent], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `CDL-Receipt-${transaction.id}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    };

    const receiptStatus = selectedReceipt?.status || 'Completed';
    const receiptTitle = selectedReceipt?.opportunityName || selectedReceipt?.name || 'Transaction';
    const receiptType = selectedReceipt?.transactionType || 'Normal';
    const receiptStatusClasses =
        String(receiptStatus).toLowerCase() === 'completed'
            ? 'bg-green-100 text-green-700'
            : String(receiptStatus).toLowerCase() === 'pending'
                ? 'bg-amber-100 text-amber-700'
                : 'bg-red-100 text-red-700';

    return (
        <DashboardContent>
            <div className="flex items-center gap-3 mb-6">
                <Button
                    type="button"
                    variant="secondary"
                    size="icon"
                    onClick={() => navigate('/profile')}
                    className="mt-1 rounded-full border border-slate-200 bg-[#f8fafc] text-[#1a365d] flex items-center justify-center hover:bg-gray-200 transition-colors"
                >
                    <LucideIcon name="ChevronLeft" size={20} />
                </Button>
                <div>
                    <h2 className="text-[#1e3a5f] mb-1 text-2xl">Billing & Payments</h2>
                    <p className="text-gray-600 text-base">Manage your payment methods and view transaction history</p>
                </div>
            </div>

            <div className={sectionCardClassName}>
                <button
                    type="button"
                    className="flex w-full items-center justify-between px-5 py-5 text-left transition-colors hover:bg-slate-50 sm:px-6"
                    onClick={() => setIsPaymentMethodsExpanded(!isPaymentMethodsExpanded)}
                >
                    <div className="flex items-center gap-2">
                        <div className="flex h-11 w-11 items-center justify-center rounded-full bg-[rgba(26,54,93,0.08)] text-[#1e3a5f]">
                            <LucideIcon name="CreditCard" size={20} />
                        </div>
                        <div>
                            <p className="text-lg font-bold text-[#1e3a5f]">
                                Payment Methods
                            </p>
                            <p className="text-sm text-slate-500">
                                Choose a default card and keep backup payment methods ready.
                            </p>
                        </div>
                    </div>
                    <LucideIcon
                        name={isPaymentMethodsExpanded ? 'ChevronUp' : 'ChevronDown'}
                        size={20}
                        color="#6b7280"
                    />
                </button>

                {isPaymentMethodsExpanded && (
                    <div className={sectionBodyClassName}>
                        {isLoading ? (
                            <div className="space-y-3">
                                {[...Array(2)].map((_, i) => (
                                    <div key={i} className="rounded-3xl border border-slate-300 bg-slate-100 p-6 animate-pulse">
                                        <div className="mb-2 h-[180px] rounded-3xl bg-slate-200" />
                                        <div className="flex gap-2">
                                            <div className="h-10 flex-1 rounded-xl bg-slate-200" />
                                            <div className="h-10 flex-1 rounded-xl bg-slate-200" />
                                        </div>
                                    </div>
                                ))}
                            </div>
                        ) : methods.length === 0 ? (
                            <div className="rounded-2xl border border-dashed border-[rgba(145,158,171,0.24)] bg-[rgba(145,158,171,0.04)] py-6 text-center">
                                <div className="mb-2 flex justify-center text-slate-400">
                                    <LucideIcon name="CreditCard" />
                                </div>
                                <p className="text-sm text-slate-500">
                                    No payment methods found.
                                </p>
                            </div>
                        ) : (
                            <div className="space-y-3">
                                {methods.map((method: any) => (
                                    <PaymentMethodItem
                                        key={method.id}
                                        method={method}
                                        onSetDefault={handleSetDefault}
                                        onRemove={handleRemoveCard}
                                        isProcessing={isActionLoading && activeActionId === method.id}
                                    />
                                ))}
                            </div>
                        )}

                        <Button
                            type="button"
                            fullWidth
                            size="lg"
                            onClick={() => setShowAddCard(true)}
                            disabled={isActionLoading}
                            className="mt-4 gap-2 rounded-2xl bg-[#dc2626] text-[0.95rem] font-bold shadow-[0_8px_18px_rgba(220,38,38,0.24)] hover:bg-[#b91c1c]"
                        >
                            <LucideIcon name="Plus" size={18} />
                            Add New Card
                        </Button>

                        <div className="mt-4 rounded-[1.5rem] border border-[rgb(219_234_254)] bg-[#eff6ff] px-4 py-3">
                            <p className="block text-[0.8125rem] leading-6 text-[#1c398e]">
                                Your default payment method will be used for membership fees and service charges. You can add multiple cards and switch between them at any time.
                            </p>
                        </div>
                    </div>
                )}
            </div>

            <div className={sectionCardClassName}>
                <button
                    type="button"
                    className="flex w-full items-center justify-between px-5 py-5 text-left transition-colors hover:bg-slate-50 sm:px-6"
                    onClick={() => setIsTransactionHistoryExpanded(!isTransactionHistoryExpanded)}
                >
                    <div className="flex items-center gap-2">
                        <div className="flex h-11 w-11 items-center justify-center rounded-full bg-[rgba(26,54,93,0.08)] text-[#1e3a5f]">
                            <LucideIcon name="Receipt" size={20} />
                        </div>
                        <div>
                            <p className="text-lg font-bold text-[#1e3a5f]">
                                Transaction History
                            </p>
                            <p className="text-sm text-slate-500">
                                View receipt details or download a copy for your records.
                            </p>
                        </div>
                    </div>
                    <LucideIcon
                        name={isTransactionHistoryExpanded ? 'ChevronUp' : 'ChevronDown'}
                        size={20}
                        color="#6b7280"
                    />
                </button>

                {isTransactionHistoryExpanded && (
                    <div className={sectionBodyClassName}>
                        {isLoading ? (
                            <div className="space-y-2.5">
                                {[...Array(5)].map((_, i) => (
                                    <div key={i} className="rounded-3xl border border-slate-300 bg-slate-50 p-2.5 animate-pulse">
                                        <div className="mb-2.5 flex items-start gap-2">
                                            <div className="h-11 w-11 rounded-2xl bg-slate-200" />
                                            <div className="flex-1 space-y-2">
                                                <div className="h-5 w-2/3 rounded bg-slate-200" />
                                                <div className="h-4 w-1/3 rounded bg-slate-200" />
                                            </div>
                                            <div className="space-y-2">
                                                <div className="h-5 w-16 rounded bg-slate-200" />
                                                <div className="h-5 w-20 rounded-full bg-slate-200" />
                                            </div>
                                        </div>
                                        <div className="flex gap-1.5">
                                            <div className="h-9 flex-1 rounded-xl bg-slate-200" />
                                            <div className="h-9 flex-1 rounded-xl bg-slate-200" />
                                        </div>
                                    </div>
                                ))}
                            </div>
                        ) : history.length === 0 ? (
                            <div className="rounded-2xl border border-dashed border-[rgba(145,158,171,0.24)] bg-[rgba(145,158,171,0.04)] py-6 text-center">
                                <div className="mb-2 flex justify-center text-slate-400">
                                    <LucideIcon name="Receipt" />
                                </div>
                                <p className="text-sm text-slate-500">
                                    No transactions found.
                                </p>
                            </div>
                        ) : (
                            <div className="space-y-2.5">
                                {history.map((tx: any) => (
                                    <TransactionListItem
                                        key={tx.id}
                                        transaction={tx}
                                        onViewReceipt={handleViewReceipt}
                                        onDownload={handleDownloadReceipt}
                                    />
                                ))}
                            </div>
                        )}
                    </div>
                )}
            </div>

            <Modal
                open={showAddCard}
                onOpenChange={(nextOpen) => !nextOpen && !isActionLoading && setShowAddCard(false)}
            >
                <ModalContent className="max-h-[92vh] max-w-2xl overflow-y-auto rounded-[2rem] p-0">
                    <div className="border-b border-slate-200 bg-white px-5 py-5 sm:px-6">
                        <div className="flex items-center gap-3">
                            <Button
                                type="button"
                                onClick={() => setShowAddCard(false)}
                                disabled={isActionLoading}
                                variant="secondary"
                                size="icon"
                                className="rounded-full border border-slate-200 bg-[#f8fafc] text-[#1a365d] hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
                            >
                                <LucideIcon name="ChevronLeft" size={18} />
                            </Button>
                            <div>
                                <ModalTitle className="text-left text-[1.45rem] font-extrabold text-[#1e3a5f]">
                                    Add Payment Method
                                </ModalTitle>
                                <p className="text-sm text-slate-500">
                                    Enter your card details exactly as they appear on the card.
                                </p>
                            </div>
                        </div>
                    </div>

                    <div className="bg-[#f8fafc] px-5 py-5 sm:px-6 sm:py-6">

                        <FormProvider methods={methodsForm} onSubmit={handlePaymentSubmit(handleAddCard)}>
                            <div className="space-y-4 rounded-[1.75rem] border border-slate-200 bg-white p-5 shadow-[0_18px_45px_rgba(15,23,42,0.06)] sm:p-6">
                                <RHFTextField
                                    name="cardHolderName"
                                    label="Cardholder Name"
                                    placeholder="John Driver"
                                    inputProps={{ autoComplete: 'cc-name' }}
                                />
                                <RHFTextField
                                    name="cardNumber"
                                    label="Card Number"
                                    placeholder="1234 5678 9012 3456"
                                    inputProps={{ maxLength: 19, autoComplete: 'cc-number', inputMode: 'numeric' }}
                                />
                                <div className="grid gap-4 sm:grid-cols-3">
                                    <RHFTextField
                                        name="expirationMonth"
                                        label="Month"
                                        placeholder="12"
                                        inputProps={{ maxLength: 2, inputMode: 'numeric', autoComplete: 'cc-exp-month' }}
                                    />
                                    <RHFTextField
                                        name="expirationYear"
                                        label="Year"
                                        placeholder="2028"
                                        inputProps={{ maxLength: 4, inputMode: 'numeric', autoComplete: 'cc-exp-year' }}
                                    />
                                    <RHFTextField
                                        name="cvv"
                                        label="CVV"
                                        placeholder="123"
                                        type="password"
                                        inputProps={{ maxLength: 4, inputMode: 'numeric', autoComplete: 'cc-csc' }}
                                    />
                                </div>
                                <RHFTextField
                                    name="billingPostalCode"
                                    label="Billing ZIP / Postal Code"
                                    placeholder="10001"
                                    inputProps={{ autoComplete: 'postal-code' }}
                                />

                                <div className="rounded-2xl border border-slate-200 bg-[#f8fafc] px-4 py-3">
                                    <RHFCheckbox
                                        name="isDefault"
                                        label="Set as default payment method"
                                    />
                                </div>

                                <Button
                                    type="submit"
                                    disabled={isActionLoading}
                                    size="lg"
                                    className="gap-2 rounded-2xl bg-[#dc2626] font-bold shadow-[0_10px_22px_rgba(220,38,38,0.24)] hover:bg-[#b91c1c]"
                                >
                                    <LucideIcon name="Plus" size={18} />
                                    Add Card
                                </Button>
                            </div>
                        </FormProvider>

                        <div className="mt-4 flex gap-2 rounded-[1.5rem] border border-[rgba(59,130,246,0.16)] bg-[rgba(59,130,246,0.08)] px-4 py-3">
                            <LucideIcon name="ShieldCheck" size={20} />
                            <p className="text-xs leading-6 text-[rgba(30,58,95,0.85)]">
                                Your payment information is encrypted and secure. We use industry-standard security measures to protect your data.
                            </p>
                        </div>
                    </div>
                </ModalContent>
            </Modal>

            <Modal
                open={isActionLoading}
                onOpenChange={() => undefined}
            >
                <ModalContent className="max-w-sm" hideCloseButton>
                    <div className="flex flex-col items-center gap-2 py-2 text-center">
                        <span className="h-8 w-8 animate-spin rounded-full border-4 border-slate-300 border-t-[#1e3a5f]" />
                        <p className="font-semibold text-[#1e3a5f]">
                            {actionMessage || 'Processing payment method...'}
                        </p>
                    </div>
                </ModalContent>
            </Modal>

            {showReceiptModal && <Modal
                open={showReceiptModal}
                onOpenChange={(nextOpen) => !nextOpen && setShowReceiptModal(false)}
            >
                <ModalContent className="max-h-[85vh] w-full max-w-md overflow-hidden rounded-t-3xl sm:rounded-3xl p-0" hideCloseButton>
                    <div className="sticky top-0 flex items-center justify-between rounded-t-3xl border-b border-gray-200 bg-white p-4">
                        <ModalTitle className="text-[#1e3a5f]">
                            Receipt Details
                        </ModalTitle>
                        <button
                            type="button"
                            onClick={() => setShowReceiptModal(false)}
                            className="flex h-10 w-10 items-center justify-center rounded-full bg-gray-100 transition hover:bg-gray-200"
                        >
                            <LucideIcon name="ChevronLeft" size={20} color="#4b5563" />
                        </button>
                    </div>

                    <div className="flex-1 overflow-y-auto p-6 max-h-[70vh]">
                        {selectedReceipt && (
                            <>
                                <div className="mb-6 border-b border-gray-200 pb-6 text-center">
                                    <h3 className="mb-1 text-xl text-[#1e3a5f]">
                                        Rig Resolve
                                    </h3>
                                    <p className="text-sm text-gray-500">
                                        Payment Receipt
                                    </p>
                                </div>

                                <div className="mb-6 space-y-4">
                                    <div className="rounded-xl bg-gray-50 p-4">
                                        <div className="mb-1 text-xs text-gray-500">
                                            Receipt ID
                                        </div>
                                        <div className="text-[#1e3a5f]">
                                            {selectedReceipt.id}
                                        </div>
                                    </div>

                                    <div className="rounded-xl bg-gray-50 p-4">
                                        <div className="mb-1 text-xs text-gray-500">
                                            Transaction ID
                                        </div>
                                        <div className="text-[#1e3a5f]">
                                            {selectedReceipt.transactionId || selectedReceipt.id}
                                        </div>
                                    </div>

                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="rounded-xl bg-gray-50 p-4">
                                            <div className="mb-1 text-xs text-gray-500">
                                                Date
                                            </div>
                                            <div className="text-[#1e3a5f]">
                                                {fDate(selectedReceipt.dueDate || selectedReceipt.createdAt)}
                                            </div>
                                        </div>
                                        <div className="rounded-xl bg-gray-50 p-4">
                                            <div className="mb-1 text-xs text-gray-500">
                                                Status
                                            </div>
                                            <span className={`rounded-full px-2 py-1 text-xs ${receiptStatusClasses}`}>
                                                {receiptStatus}
                                            </span>
                                        </div>
                                    </div>

                                    <div className="rounded-xl bg-gray-50 p-4">
                                        <div className="mb-1 text-xs text-gray-500">
                                            Description
                                        </div>
                                        <div className="text-[#1e3a5f]">{receiptTitle}</div>
                                    </div>

                                    <div className="rounded-xl bg-gray-50 p-4">
                                        <div className="mb-1 text-xs text-gray-500">
                                            Type
                                        </div>
                                        <div className="capitalize text-[#1e3a5f]">{receiptType}</div>
                                    </div>
                                </div>

                                <div className="rounded-2xl bg-[#1e3a5f] p-6 text-white">
                                    <div className="mb-1 text-sm opacity-80">
                                        Total Amount
                                    </div>
                                    <div className="text-3xl">
                                        ${(selectedReceipt.amount || 0).toFixed(2)}
                                    </div>
                                </div>
                            </>
                        )}
                    </div>

                    <div className="sticky bottom-0 border-t border-gray-200 bg-white p-4">
                        {selectedReceipt && (
                            <Button
                                type="button"
                                fullWidth
                                onClick={() => handleDownloadReceipt(selectedReceipt)}
                                className="gap-2 rounded-xl bg-[#dc2626] py-3 text-white hover:bg-[#b91c1c]"
                            >
                                <LucideIcon name="Download" size={20} />
                                Download Receipt
                            </Button>
                        )}
                    </div>
                </ModalContent>
            </Modal>}
        </DashboardContent>
    );
}
