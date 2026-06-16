import { useState, useCallback, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import LucideIcon from 'src/components/lucide-icon';
import ButtonAtom from 'src/components/Button';
import { useSessionStatusQuery } from 'src/queries/use-billing-query';

type PaymentStatus = 'loading' | 'complete' | 'open' | 'error';

export default function PaymentReturnPage() {
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    const sessionId = searchParams.get('session_id');

    const [status, setStatus] = useState<PaymentStatus>('loading');
    const [errorMessage, setErrorMessage] = useState<string>('');
    const sessionStatusQuery = useSessionStatusQuery(sessionId || undefined);

    useEffect(() => {
        if (!sessionId) {
            setStatus('error');
            setErrorMessage('No session ID found. Please try again.');
            return;
        }

        if (sessionStatusQuery.isLoading || sessionStatusQuery.isFetching) {
            setStatus('loading');
            return;
        }

        const response = sessionStatusQuery.data;
        if (response?.status === 'complete') {
            setStatus('complete');
        } else if (response?.status === 'open') {
            setStatus('open');
        } else {
            setStatus('error');
            setErrorMessage(response?.Message || 'Unable to verify payment status.');
        }
    }, [sessionId, sessionStatusQuery.data, sessionStatusQuery.isLoading, sessionStatusQuery.isFetching]);

    const handleGoToTickets = useCallback(() => {
        navigate('/tickets', { replace: true });
    }, [navigate]);

    const handleGoToDashboard = useCallback(() => {
        navigate('/dashboard', { replace: true });
    }, [navigate]);

    const handleRetry = useCallback(() => {
        setStatus('loading');
        sessionStatusQuery.refetch();
    }, [sessionStatusQuery]);

    const cardClassName = 'mvp-section-card w-full max-w-[480px] rounded-[32px] p-10 text-center shadow-[0_22px_50px_rgba(15,23,42,0.08)]';

    return (
        <div className="mvp-page-shell flex min-h-full max-w-[520px] items-center justify-center px-5 py-10 sm:px-6 sm:py-14">
            {/* Loading State */}
            {status === 'loading' && (
                <div className="mvp-section-card w-full max-w-[440px] rounded-[32px] p-10 text-center shadow-[0_22px_50px_rgba(15,23,42,0.08)]">
                    <div className="mx-auto mb-3 h-12 w-12 animate-spin rounded-full border-4 border-slate-200 border-t-[#1a365d]" />
                    <h2 className="mb-1 text-xl font-bold text-[#1a365d]">
                        Verifying Payment...
                    </h2>
                    <p className="text-sm text-gray-500">
                        Please wait while we confirm your payment with Stripe.
                    </p>
                </div>
            )}

            {/* Success State */}
            {status === 'complete' && (
                <div className={cardClassName}>
                    {/* Success Icon */}
                    <div className="mx-auto mb-4 flex h-[88px] w-[88px] animate-[popIn_0.4s_ease-out] items-center justify-center rounded-full bg-green-50 shadow-[0_14px_30px_rgba(34,197,94,0.18)]">
                        <LucideIcon name="CircleCheck" size={52} color="#22c55e" />
                    </div>

                    <h2 className="mb-1 text-2xl font-bold text-[#1a365d]">
                        Payment Successful!
                    </h2>

                    <p className="mb-4 text-sm leading-6 text-gray-500">
                        Your payment has been processed successfully. Your ticket status will be updated shortly.
                    </p>

                    {/* Confirmation Details */}
                    <div className="mb-4 rounded-[24px] border border-green-200 bg-green-50 p-4">
                        <div className="flex items-center justify-center gap-1.5">
                            <LucideIcon name="ShieldCheck" size={22} color="#22c55e" />
                            <p className="text-sm font-medium text-green-800">
                                Payment confirmed & secured by Stripe
                            </p>
                        </div>
                    </div>

                    {/* Session ID Reference */}
                    {sessionId && (
                        <div className="mb-4">
                            <p className="mb-0.5 block text-xs text-gray-400">
                                Reference ID
                            </p>
                            <span className="inline-block break-all rounded bg-gray-100 px-1.5 py-0.5 font-mono text-xs text-gray-500">
                                {sessionId}
                            </span>
                        </div>
                    )}

                    {/* Action Buttons */}
                    <div className="space-y-1.5">
                        <ButtonAtom
                            fullWidth
                            size="large"
                            variant="contained"
                            onClick={handleGoToTickets}
                            className="rounded-2xl bg-[#1a365d] hover:bg-[#152d47]"
                        >
                            <LucideIcon name="FileText" size={20} style={{ marginRight: 8 }} />
                            View My Tickets
                        </ButtonAtom>
                        <ButtonAtom
                            fullWidth
                            size="large"
                            variant="outlined"
                            onClick={handleGoToDashboard}
                            className="rounded-2xl border-[rgba(26,54,93,0.04)] text-[#1a365d] hover:border-[#152d47] hover:bg-[rgba(26,54,93,0.04)] hover:text-[#1a365d]"
                        >
                            <LucideIcon name="House" size={20} style={{ marginRight: 8 }} />
                            Go to Dashboard
                        </ButtonAtom>
                    </div>
                </div>
            )}

            {/* Payment Still Open (Incomplete) */}
            {status === 'open' && (
                <div className={cardClassName}>
                    <div className="mx-auto mb-4 flex h-[88px] w-[88px] items-center justify-center rounded-full bg-amber-50 shadow-[0_14px_30px_rgba(245,158,11,0.18)]">
                        <LucideIcon name="Clock" size={52} color="#f59e0b" />
                    </div>

                    <h2 className="mb-1 text-2xl font-bold text-[#1a365d]">
                        Payment Incomplete
                    </h2>

                    <p className="mb-4 text-sm leading-6 text-gray-500">
                        Your payment session is still open. It looks like the payment was not completed. Please go back to your tickets and try again.
                    </p>

                    <div className="space-y-1.5">
                        <ButtonAtom
                            fullWidth
                            size="large"
                            variant="contained"
                            onClick={handleGoToTickets}
                            className="rounded-2xl bg-[#1a365d] hover:bg-[#152d47]"
                        >
                            <LucideIcon name="FileText" size={20} style={{ marginRight: 8 }} />
                            Back to My Tickets
                        </ButtonAtom>
                    </div>
                </div>
            )}

            {/* Error State */}
            {status === 'error' && (
                <div className={cardClassName}>
                    <div className="mx-auto mb-4 flex h-[88px] w-[88px] items-center justify-center rounded-full bg-red-50 shadow-[0_14px_30px_rgba(239,68,68,0.18)]">
                        <LucideIcon name="TriangleAlert" size={52} color="#ef4444" />
                    </div>

                    <h2 className="mb-1 text-2xl font-bold text-[#1a365d]">
                        Verification Failed
                    </h2>

                    <p className="mb-2 text-sm leading-6 text-gray-500">
                        {errorMessage || 'We were unable to verify your payment. If you were charged, please contact support.'}
                    </p>

                    {/* Error Detail */}
                    <div className="mb-4 rounded-[24px] border border-red-200 bg-red-50 p-4">
                        <div className="flex items-center justify-center gap-1 text-center">
                            <LucideIcon name="Info" size={18} color="#ef4444" />
                            <p className="text-xs text-red-700">
                                If your payment was deducted, it will be refunded automatically or contact support for help.
                            </p>
                        </div>
                    </div>

                    <div className="space-y-1.5">
                        <ButtonAtom
                            fullWidth
                            size="large"
                            variant="contained"
                            onClick={handleRetry}
                            className="rounded-2xl bg-[#1a365d] hover:bg-[#152d47]"
                        >
                            <LucideIcon name="RefreshCw" size={20} style={{ marginRight: 8 }} />
                            Retry Verification
                        </ButtonAtom>
                        <ButtonAtom
                            fullWidth
                            size="large"
                            variant="outlined"
                            onClick={handleGoToTickets}
                            className="rounded-2xl border-[#1a365d] text-[#1a365d] hover:border-[#152d47] hover:bg-[rgba(26,54,93,0.04)]"
                        >
                            <LucideIcon name="FileText" size={20} style={{ marginRight: 8 }} />
                            Back to My Tickets
                        </ButtonAtom>
                    </div>
                </div>
            )}
        </div>
    );
}
