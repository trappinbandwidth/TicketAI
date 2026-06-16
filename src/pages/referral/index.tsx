import { useState, useCallback, useMemo, memo, ChangeEvent } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Helmet } from 'react-helmet-async';
import { useAtom } from 'jotai';

import { CONFIG } from 'src/config-global';
import { constants } from 'src/constants.value';
import { DashboardContent } from 'src/layouts/dashboard';
import { formatPhoneNumber } from 'src/pages/signup/components/signup-flow/formatters';
import { queryKeys } from 'src/queries/query-keys';
import { GetDriverProfile } from 'src/routes/index.service';
import { driverProfile } from 'src/store';
import LucideIcon from 'src/components/lucide-icon';
import { Button, Modal, ModalContent, ModalTitle } from 'src/components/ui';
import { useProfileGuard } from 'src/hooks/use-profile-guard';
import CompleteProfileModal from 'src/components/shared/CompleteProfileModal';
import { toasterService } from 'src/apiSetUp';
import { updateDriverRewards } from 'src/utils/api-service';
// import { useReferralQrLinkQuery } from 'src/queries/use-referral-qr-link-query';

// ================== Types ==================
interface StepInfo {
    number: number;
    title: string;
    description: string;
}

interface StepItemProps {
    step: StepInfo;
}

interface ShareTextModalProps {
    open: boolean;
    onClose: () => void;
    message: string;
}

type CashOutStep = 1 | 2 | 3;

interface CashOutFormState {
    step: CashOutStep;
    selectedAmount: number | null;
    email: string;
    phone: string;
}

interface CashOutFormErrors {
    amount?: string;
    email?: string;
    phone?: string;
}

// ================== Constants ==================
const BRAND_PRIMARY = '#0D3E6B';

const STEPS: StepInfo[] = [
    {
        number: 1,
        title: 'Share your QR code',
        description: 'Let other drivers scan your code or share your link',
    },
    {
        number: 2,
        title: 'They join & subscribe',
        description: 'New member signs up and completes their subscription',
    },
    {
        number: 3,
        title: 'Both earn cash rewards',
        description: 'You and your referral both earn the same cash based on their membership tier and subscription period.',
    },
];

const CASHOUT_OPTIONS = [25, 50, 75, 100];
const MIN_CASHOUT_AMOUNT = 25;

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const isValidEmail = (v: string) => EMAIL_REGEX.test(v.trim());
const isValidPhone = (v: string) => v.replace(/\D/g, '').length === 10;

const CASH_EARNED = {
    silver: { monthly: 5, quarterly: 10, annually: 25 },
    gold: { monthly: 10, quarterly: 20, annually: 50 },
    platinum: { monthly: 15, quarterly: 30, annually: 60 }
};

const IMAGE_EXTENSION_MAP: Record<string, string> = {
    'image/jpeg': 'jpg',
    'image/jpg': 'jpg',
    'image/png': 'png',
    'image/svg+xml': 'svg',
    'image/webp': 'webp',
};

const REFERRAL_MESSAGE_TEMPLATES = [
    "I use Rig Resolve for ticket defense and it's worth every penny. Don't wait until you need it. Sign up through my link: [LINK]",
    "I use Rig Resolve for ticket defense and it's paid for itself. Don't wait until you're already dealing with something. Sign up through my link: [LINK]",
    "I use Rig Resolve to protect my CDL and it's worth every penny. Get covered before something happens. My referral link: [LINK]",
    "I use Rig Resolve for ticket defense. Seriously worth it. Don't wait until you're already in a jam to figure it out. Sign up here: [LINK]"
] as const;

function getRandomReferralMessage(referralLink: string, previousMessage?: string) {
    const availableTemplates = REFERRAL_MESSAGE_TEMPLATES.filter(
        (template) => template.replace('[LINK]', referralLink) !== previousMessage
    );

    const messagePool = availableTemplates.length ? availableTemplates : [...REFERRAL_MESSAGE_TEMPLATES];
    const nextTemplate = messagePool[Math.floor(Math.random() * messagePool.length)];

    return nextTemplate.replace('[LINK]', referralLink);
}

function createInitialCashOutForm(driverData: any): CashOutFormState {
    return {
        step: 1,
        selectedAmount: null,
        email: String(driverData?.email || '').trim(),
        phone: formatPhoneNumber(String(driverData?.mobilePhone || '')),
    };
}

function validateCashOutAmount(amount: number | null, availableBalance: number) {
    if (amount === null) {
        return 'Select a cash out amount';
    }

    if (amount < MIN_CASHOUT_AMOUNT) {
        return `Minimum cashout is $${MIN_CASHOUT_AMOUNT}`;
    }

    if (amount > availableBalance) {
        return 'Selected amount exceeds your available balance';
    }

    return '';
}

function validateCashOutContact(email: string, phone: string): CashOutFormErrors {
    const nextErrors: CashOutFormErrors = {};

    if (!email.trim()) {
        nextErrors.email = 'Email is required';
    } else if (!isValidEmail(email)) {
        nextErrors.email = 'Enter a valid email address';
    }

    if (!phone.trim()) {
        nextErrors.phone = 'Phone number is required';
    } else if (!isValidPhone(phone)) {
        nextErrors.phone = 'Phone number must be 10 digits';
    }

    return nextErrors;
}

// ================== Loading Skeleton Components ==================
const HeaderSkeleton = memo(() => (
    <div className="mb-3 text-center">
        <div className="mx-auto mb-0.5 h-8 w-[200px] animate-pulse rounded bg-gray-200" />
        <div className="mx-auto h-5 w-[280px] animate-pulse rounded bg-gray-200" />
    </div>
));

HeaderSkeleton.displayName = 'HeaderSkeleton';

const CardSkeleton = memo(() => (
    <div className="mb-3 h-[200px] w-full animate-pulse rounded-3xl bg-gray-200" />
));

CardSkeleton.displayName = 'CardSkeleton';

// ================== Sub-components ==================
const StepItem = memo(({ step }: StepItemProps) => (
    <div className="flex gap-2">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#dc2626] text-sm font-semibold text-white">
            {step.number}
        </div>
        <div className="flex-1">
            <p className="mb-0.5 text-[0.9375rem] font-semibold leading-[1.3] text-[#0D3E6B]">
                {step.title}
            </p>
            <p className="text-sm leading-6 text-gray-500">
                {step.description}
            </p>
        </div>
    </div>
));

StepItem.displayName = 'StepItem';

const ShareTextModal = memo(({ open, onClose, message }: ShareTextModalProps) => (
    <Modal open={open} onOpenChange={(nextOpen) => !nextOpen && onClose()}>
        <ModalContent className="mvp-modal-shell max-h-[85vh] max-w-md p-0">
            <div className="mvp-modal-header pr-12">
                <ModalTitle className="text-base font-bold text-[#0D3E6B]">
                    Share Your Referral
                </ModalTitle>
            </div>
            <div className="mvp-modal-body pt-4">
                <p className="mb-3 text-[0.8125rem] text-gray-500">
                    Copy this message and share it with other drivers:
                </p>

                <div className="mb-4 rounded-2xl border border-gray-200 bg-gray-50 p-4">
                    <p className="select-all whitespace-pre-wrap break-words text-[0.8125rem] leading-6 text-[#0D3E6B]">
                        {message}
                    </p>
                </div>

                <Button
                    type="button"
                    onClick={onClose}
                    fullWidth
                    className="rounded-2xl bg-[#0D3E6B] hover:bg-[#0b355b]"
                >
                    Done
                </Button>
            </div>
        </ModalContent>
    </Modal>
));

ShareTextModal.displayName = 'ShareTextModal';

// ================== Main Component ==================
export default function ReferralPage() {
    const queryClient = useQueryClient();
    const [driverData, setDriverData] = useAtom(driverProfile);
    const { guardAction, hasIncompleteProfile, openProfileCompletion, profileDialogProps, completeProfileModalProps } = useProfileGuard();

    const [showShareText, setShowShareText] = useState(false);
    const [shareMessage, setShareMessage] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [currentCardSide, setCurrentCardSide] = useState<'points' | 'qr'>('points');
    const [isHowItWorksExpanded, setIsHowItWorksExpanded] = useState(false);

    // const qrLinkUrl = driverData.referralProfile.qrCodeImageUrl || '';
    const referralCode = driverData?.referralProfile?.referralCode || '';
    // const displayUrl = `cdllegal.com/ref/${referralCode}`; // Simplified display URL
    const referralUrl = driverData?.referralProfile?.qrCodeImageUrl || '';
    const referralLink = driverData?.referralProfile?.referralUrl || '';

    const getNextShareMessage = useCallback(() => {
        const nextMessage = getRandomReferralMessage(referralLink, shareMessage || undefined);
        setShareMessage(nextMessage);
        return nextMessage;
    }, [referralLink, shareMessage]);

    const handleCopy = useCallback(async () => {
        if (!referralLink) return;

        const nextMessage = getNextShareMessage();

        try {
            await navigator.clipboard.writeText(nextMessage);
        } catch (err) {
            setShowShareText(true);
        }
    }, [getNextShareMessage, referralLink]);

    const handleShare = useCallback(async () => {
        if (!referralLink) return;

        const nextMessage = getNextShareMessage();

        if (navigator.share) {
            try {
                await navigator.share({
                    title: 'Rig Resolve Referral',
                    text: nextMessage,
                });
            } catch (err) {
                if (err instanceof Error && err.name !== 'AbortError') {
                    setShowShareText(true);
                }
            }
        } else {
            setShowShareText(true);
        }
    }, [getNextShareMessage, referralLink]);

    const handleDownloadQR = useCallback(async () => {
        if (isLoading || !referralUrl) return;

        setIsLoading(true);

        const fallbackDownload = () => {
            const directLink = document.createElement('a');
            directLink.href = referralUrl;
            directLink.target = '_blank';
            directLink.rel = 'noopener noreferrer';
            directLink.download = `cdl-legal-referral-${referralCode || 'qr-code'}`;
            document.body.appendChild(directLink);
            directLink.click();
            document.body.removeChild(directLink);
        };

        try {
            const response = await fetch(referralUrl);

            if (!response.ok) {
                throw new Error(`Unable to download QR code: ${response.status}`);
            }

            const blob = await response.blob();

            if (!blob.size) {
                throw new Error('QR code response was empty');
            }

            const objectUrl = URL.createObjectURL(blob);
            const contentType = blob.type.toLowerCase();
            const extensionFromType = IMAGE_EXTENSION_MAP[contentType];
            const extensionFromUrl = referralUrl.split('?')[0]?.split('.').pop()?.toLowerCase();
            const fileExtension = extensionFromType || extensionFromUrl || 'png';

            const downloadLink = document.createElement('a');
            downloadLink.href = objectUrl;
            downloadLink.download = `cdl-legal-referral-${referralCode || 'qr-code'}.${fileExtension}`;
            document.body.appendChild(downloadLink);
            downloadLink.click();
            document.body.removeChild(downloadLink);
            URL.revokeObjectURL(objectUrl);
        } catch (error) {
            fallbackDownload();
        } finally {
            setIsLoading(false);
        }
    }, [isLoading, referralCode, referralUrl]);

    const qrCodeSize = 144;
    const isShareUnavailable = !referralLink;
    const isQrUnavailable = !referralUrl;

    // availableCashBalance may be a plain number (local API) or { source, parsedValue } (deployed API)
    const rawCashBalance = driverData?.referralProfile?.availableCashBalance;
    const availableBalance = typeof rawCashBalance === 'number'
        ? rawCashBalance
        : (rawCashBalance?.parsedValue ?? 0);
    const canCashOut = availableBalance >= MIN_CASHOUT_AMOUNT;

    // ── Cash-out flow state ──
    const [showCashOutModal, setShowCashOutModal] = useState(false);
    const [cashOutForm, setCashOutForm] = useState<CashOutFormState>(() => createInitialCashOutForm(driverData));
    const [cashOutErrors, setCashOutErrors] = useState<CashOutFormErrors>({});
    const [showSuccessModal, setShowSuccessModal] = useState(false);
    const [confirmedAmount, setConfirmedAmount] = useState(0);

    const selectedAmount = cashOutForm.selectedAmount;
    const cashOutEmail = cashOutForm.email;
    const cashOutPhone = cashOutForm.phone;
    const cashOutStep = cashOutForm.step;

    const amountError = useMemo(
        () => validateCashOutAmount(selectedAmount, availableBalance),
        [selectedAmount, availableBalance]
    );
    const contactErrors = useMemo(
        () => validateCashOutContact(cashOutEmail, cashOutPhone),
        [cashOutEmail, cashOutPhone]
    );
    const contactValid = !contactErrors.email && !contactErrors.phone;
    const displayedEmailError = cashOutErrors.email || (cashOutEmail.trim() ? contactErrors.email : '');
    const displayedPhoneError = cashOutErrors.phone || (cashOutPhone.trim() ? contactErrors.phone : '');
    const remainingBalance = Math.max(availableBalance - (selectedAmount ?? 0), 0);

    const resetCashOutFlow = useCallback(() => {
        setCashOutForm(createInitialCashOutForm(driverData));
        setCashOutErrors({});
    }, [driverData]);

    const refreshDriverProfile = useCallback(async () => {
        const response = await GetDriverProfile();

        if (response?.StatusCode !== constants.RESPONSE_STATUS.SUCCESS || !response?.Result?.data) {
            throw new Error(response?.Message || 'Cash out submitted, but the balance could not be refreshed.');
        }

        const nextProfile = response.Result.data;
        queryClient.setQueryData(queryKeys.driverProfile, nextProfile);
        setDriverData(nextProfile);

        return nextProfile;
    }, [queryClient, setDriverData]);

    const cashOutMutation = useMutation({
        mutationKey: ['mutation', 'update-driver-rewards'],
        mutationFn: async (payload: Parameters<typeof updateDriverRewards>[0]) => {
            const response = await updateDriverRewards(payload);

            if (response?.StatusCode !== constants.RESPONSE_STATUS.SUCCESS) {
                throw new Error(response?.Message || response?.Errors?.[0]?.Message || 'Cash out request failed. Please try again.');
            }

            return response;
        },
    });

    const openCashOutModal = useCallback(() => {
        if (!canCashOut) {
            toasterService(`Minimum cashout is $${MIN_CASHOUT_AMOUNT}`, 4, 'Warning');
            return;
        }

        resetCashOutFlow();
        setShowCashOutModal(true);
    }, [canCashOut, resetCashOutFlow]);

    const closeCashOutModal = useCallback(() => {
        setShowCashOutModal(false);
    }, []);

    const setCashOutStep = useCallback((step: CashOutStep) => {
        setCashOutForm((prev) => ({ ...prev, step }));
    }, []);

    const updateCashOutField = useCallback((field: 'email' | 'phone', value: string) => {
        setCashOutForm((prev) => ({ ...prev, [field]: value }));
        setCashOutErrors((prev) => ({ ...prev, [field]: undefined }));
    }, []);

    const handleSelectAmount = useCallback((amount: number) => {
        const nextAmountError = validateCashOutAmount(amount, availableBalance);

        if (nextAmountError) {
            setCashOutErrors((prev) => ({ ...prev, amount: nextAmountError }));
            return;
        }

        setCashOutErrors((prev) => ({ ...prev, amount: undefined }));
        setCashOutForm((prev) => ({ ...prev, selectedAmount: amount, step: 2 }));
    }, [availableBalance]);

    const handleContinueCashOut = useCallback(() => {
        const nextErrors = validateCashOutContact(cashOutEmail, cashOutPhone);

        if (nextErrors.email || nextErrors.phone) {
            setCashOutErrors((prev) => ({ ...prev, ...nextErrors }));
            return;
        }

        setCashOutErrors((prev) => ({ ...prev, email: undefined, phone: undefined }));
        setCashOutStep(3);
    }, [cashOutEmail, cashOutPhone, setCashOutStep]);

    const handleConfirmCashOut = useCallback(async () => {
        const nextAmountError = validateCashOutAmount(selectedAmount, availableBalance);
        const nextContactErrors = validateCashOutContact(cashOutEmail, cashOutPhone);

        if (nextAmountError || nextContactErrors.email || nextContactErrors.phone) {
            setCashOutErrors({ amount: nextAmountError || undefined, ...nextContactErrors });
            if (nextAmountError) {
                setCashOutStep(1);
                return;
            }

            setCashOutStep(2);
            return;
        }

        if (selectedAmount === null) {
            return;
        }

        const confirmedCashOutAmount = selectedAmount;

        try {
            await cashOutMutation.mutateAsync({
                driverPhone: String(driverData?.mobilePhone || ''),
                driverEmail: String(driverData?.email || ''),
                requestInfo: {
                    email: cashOutEmail.trim(),
                    phone: cashOutPhone.replace(/\D/g, '').slice(0, 10),
                    amount: confirmedCashOutAmount,
                },
            });

            setConfirmedAmount(confirmedCashOutAmount);

            try {
                await refreshDriverProfile();
            } catch (error: any) {
                toasterService(error?.message || 'Cash out submitted, but the balance could not be refreshed.', 4, 'Warning');
                await queryClient.invalidateQueries({ queryKey: queryKeys.driverProfile });
            }

            closeCashOutModal();
            setShowSuccessModal(true);
        } catch (err: any) {
            toasterService(err?.message || 'Something went wrong. Please try again.', 4, 'Error');
        }
    }, [
        selectedAmount,
        availableBalance,
        cashOutEmail,
        cashOutPhone,
        cashOutMutation,
        closeCashOutModal,
        driverData,
        queryClient,
        refreshDriverProfile,
        setCashOutStep,
    ]);

    return (
        <>
            <Helmet>
                <title>{`Referral - ${CONFIG.appName}`}</title>
                <meta name="description" content="Share your referral code and earn rewards when friends join Rig Resolve Services" />
            </Helmet>

            <DashboardContent>
                <div className="mvp-page-shell space-y-4">
                    {/* Header */}
                    <div className="text-center">
                        <p className="mb-1 text-[0.7rem] font-semibold uppercase tracking-[0.28em] text-[#0D3E6B]/55">
                            Referral Program
                        </p>
                        <h1 className="mb-0.5 text-[1.25rem] font-medium text-[#0D3E6B] sm:text-[1.5rem]">
                            Rewards & Sharing
                        </h1>
                        <p className="text-[0.9375rem] text-gray-500">
                            Manage your rewards and share your referral code
                        </p>
                    </div>

                    {/* Flip Card Container */}
                    <div className="relative mb-3 min-h-[230px] sm:min-h-[250px]">
                        {currentCardSide === 'points' ? (
                            <div className={`w-full animate-in fade-in-0 duration-300 ${hasIncompleteProfile ? 'opacity-90' : ''}`}>
                                <div
                                    className="relative min-h-[217px] overflow-hidden rounded-3xl p-6 text-white shadow-2xl  sm:min-h-[250px]"
                                    style={{
                                        background: 'linear-gradient(to bottom right, #0D3E6B 0%, #1e3a5f 50%, #003E6B 100%)',
                                    }}
                                >
                                    {/* Decorative circles */}
                                    <div className="absolute -right-16 -top-16 h-32 w-32 rounded-full bg-white/5" />
                                    <div className="absolute -bottom-12 -left-12 h-24 w-24 rounded-full bg-white/5" />

                                    <div className="relative z-10 flex h-full flex-col">
                                        {/* Header */}
                                        <div className="mb-4 flex items-center justify-between">
                                            <div className="flex items-center gap-1">
                                                <LucideIcon name='CreditCard' size={16} color="white" />
                                                <p className="text-xs opacity-80">Rewards Card</p>
                                            </div>
                                            <div className="rounded-full border border-white/30 bg-white/20 px-1.5 py-0.5">
                                                <p className="text-[0.625rem]">Active</p>
                                            </div>
                                        </div>

                                        {/* Balance */}
                                        <div className="mb-3 flex flex-1 flex-col justify-center">
                                            <p className="mb-0.5 text-[0.625rem] uppercase tracking-[1px] opacity-60">
                                                Rewards Balance
                                            </p>
                                            <p className="text-[2.5rem] font-normal leading-none tracking-[-1px] sm:text-[3rem]">
                                                ${availableBalance.toFixed(2)}
                                            </p>
                                        </div>

                                        {/* Footer */}
                                        <div className="mt-3 border-t border-white/20 pt-4 flex items-center justify-end">
                                            <button
                                                type="button"
                                                onClick={() => setCurrentCardSide('qr')}
                                                disabled={hasIncompleteProfile}
                                                className={`mt-1 flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all text-sm ${hasIncompleteProfile
                                                    ? 'bg-white/10 text-white/40 cursor-not-allowed'
                                                    : 'bg-white/20 hover:bg-white/30 border border-white/30'
                                                    }`}
                                            >
                                                <LucideIcon name="QrCode" size={14} />
                                                <span className="text-xs">View QR</span>
                                                <LucideIcon name="ChevronRight" size={13} />
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        ) : (
                            <div className="w-full animate-in fade-in-0 duration-300">
                                <div className="rounded-3xl bg-white p-6 shadow-[0_25px_50px_-12px_rgba(0,0,0,0.25)]">
                                    {/* Header */}
                                    <div className="mb-2 flex items-center justify-between">
                                        <Button
                                            type="button"
                                            onClick={() => setCurrentCardSide('points')}
                                            variant="secondary"
                                            size="sm"
                                            className="gap-1 rounded-2xl border border-slate-200 bg-white px-3 text-xs text-[#0D3E6B]"
                                        >
                                            <LucideIcon name="ChevronLeft" size={14} />
                                            Back
                                        </Button>
                                        <div className="rounded-full bg-[rgba(13,62,107,0.1)] px-1.5 py-0.5">
                                            <p className="text-[0.625rem] text-[#0D3E6B]">Share & Earn</p>
                                        </div>
                                    </div>

                                    {/* QR Code */}
                                    <div className="mb-2 flex flex-col items-center">
                                        <div
                                            className="mb-2 flex items-center justify-center rounded-2xl border-2 border-gray-200 bg-white p-1 shadow-[0_10px_25px_-5px_rgba(0,0,0,0.1)]"
                                            style={{ width: qrCodeSize + 16, height: qrCodeSize + 16 }}
                                        >
                                            <img
                                                id="referral-qr-code"
                                                width={qrCodeSize}
                                                height={qrCodeSize}
                                                src={referralUrl}
                                                alt="QR Code"
                                            />
                                        </div>
                                        <p className="mb-0.5 text-[1.125rem] font-semibold tracking-[2px] text-[#0D3E6B]">
                                            {referralCode}
                                        </p>
                                        {/* <p className="text-center text-xs text-gray-500 break-all">
                                            {displayUrl}
                                        </p> */}
                                    </div>

                                    {/* Action Buttons */}
                                    <div className="grid grid-cols-3 gap-2">
                                        <button
                                            type="button"
                                            onClick={handleShare}
                                            disabled={isShareUnavailable}
                                            className="bg-[#0D3E6B] text-white py-2.5 rounded-xl hover:bg-[#1e3a5f] transition-all flex flex-col items-center justify-center gap-1 shadow-lg disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-[#0D3E6B]"
                                        >
                                            <LucideIcon name='Share2' size={16} />
                                            <span className="text-xs">Share</span>
                                        </button>
                                        <button
                                            type="button"
                                            onClick={handleCopy}
                                            disabled={isShareUnavailable}
                                            className="bg-gray-100 text-gray-700 py-2.5 rounded-xl hover:bg-gray-200 transition-all flex flex-col items-center justify-center gap-1 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-gray-100"
                                        >
                                            <LucideIcon name='Copy' size={16} />
                                            <span className="text-xs">Copy</span>
                                        </button>
                                        <button
                                            type="button"
                                            onClick={handleDownloadQR}
                                            disabled={isQrUnavailable || isLoading}
                                            className="bg-gray-100 text-gray-700 py-2.5 rounded-xl hover:bg-gray-200 transition-all flex flex-col items-center justify-center gap-1 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-gray-100"
                                        >
                                            <LucideIcon name='Download' size={16} />
                                            <span className="text-xs">{isLoading ? 'Saving...' : 'Download'}</span>
                                        </button>
                                    </div>
                                </div>
                            </div>
                        )}

                        {hasIncompleteProfile && currentCardSide === 'points' && (
                            <div className="absolute inset-0 bg-[#0D3E6B]/95 backdrop-blur-sm flex items-center justify-center rounded-2xl z-20">
                                <div className="text-center px-6">
                                    <div className="w-14 h-14 bg-white/20 backdrop-blur-sm rounded-full flex items-center justify-center mx-auto mb-3 border border-white/30">
                                        <LucideIcon name="Lock" size={32} color="white" />
                                    </div>
                                    <h3 className="text-white mb-2">Complete Your Profile</h3>
                                    <p className="text-white/80 text-sm mb-3">
                                        Start earning cash rewards
                                    </p>
                                    <button
                                        type="button"
                                        onClick={() => openProfileCompletion('referral')}
                                        className="bg-white text-[#0D3E6B] px-5 py-2.5 rounded-xl hover:bg-gray-100 transition-all shadow-lg font-medium text-sm"
                                    >
                                        Complete Profile
                                    </button>
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Cash Out Button */}
                    <div className="mvp-section-card rounded-3xl p-4 shadow-[0_14px_30px_rgba(15,23,42,0.06)]">
                        {canCashOut ? (
                            <Button
                                type="button"
                                fullWidth
                                size="lg"
                                onClick={openCashOutModal}
                                className="justify-center gap-2 rounded-2xl bg-[#15803d] text-white hover:bg-[#166534]"
                            >
                                <LucideIcon name='DollarSign' size={20} />
                                Cash Out Now
                            </Button>
                        ) : (
                            <Button
                                type="button"
                                disabled
                                fullWidth
                                size="lg"
                                variant="secondary"
                                className="justify-center gap-2 rounded-2xl border border-slate-200 bg-slate-100 text-slate-400 hover:bg-slate-100 cursor-not-allowed"
                            >
                                <LucideIcon name='DollarSign' size={20} />
                                Minimum cashout is ${MIN_CASHOUT_AMOUNT}
                            </Button>
                        )}
                    </div>

                    {/* How It Works - Collapsible */}
                    <div className="mvp-section-card rounded-3xl p-5 shadow-[0_14px_30px_rgba(15,23,42,0.06)]">
                        <div
                            onClick={() => setIsHowItWorksExpanded(!isHowItWorksExpanded)}
                            className="flex cursor-pointer items-center justify-between"
                        >
                            <div className="flex items-center gap-1">
                                <LucideIcon name='Gift' size={20} color={BRAND_PRIMARY} />
                                <p className="text-base font-semibold text-[#0D3E6B]">
                                    How It Works
                                </p>
                            </div>
                            <LucideIcon
                                name={isHowItWorksExpanded ? 'ChevronDown' : 'ChevronRight'}
                                size={20}
                                color='#99a1af'
                            />
                        </div>

                        {isHowItWorksExpanded && (
                            <div className="mt-3">
                                {/* Steps */}
                                <div className="mb-3 space-y-2.5">
                                    {STEPS.map((step) => (
                                        <StepItem key={step.number} step={step} />
                                    ))}
                                </div>

                                {/* Divider */}
                                <div className="my-3 border-t border-gray-200" />

                                {/* Cash Per Referral */}
                                <p className="mb-2 font-semibold text-[#0D3E6B]">
                                    Cash Per Referral
                                </p>

                                <div className="space-y-2.5">
                                    {/* Silver */}
                                    <div>
                                        <div className="mb-1.5 flex items-center gap-1">
                                            <div className="flex h-6 w-6 items-center justify-center rounded-full bg-gray-400">
                                                <LucideIcon name="Star" size={12} color="white" />
                                            </div>
                                            <p className="font-medium text-[#0D3E6B]">Silver Membership</p>
                                        </div>
                                        <div className="ml-4 grid grid-cols-3 gap-1">
                                            {['monthly', 'quarterly', 'annually'].map((period) => (
                                                <div key={period} className="rounded-2xl border border-gray-300 bg-gray-50 py-3 text-center">
                                                    <p className="mb-0.5 text-xs capitalize text-gray-500">{period}</p>
                                                    <p className="font-semibold text-gray-600">${CASH_EARNED.silver[period as keyof typeof CASH_EARNED.silver]}</p>
                                                </div>
                                            ))}
                                        </div>
                                    </div>

                                    {/* Gold */}
                                    <div>
                                        <div className="mb-1.5 flex items-center gap-1">
                                            <div className="flex h-6 w-6 items-center justify-center rounded-full bg-[#F2AE26]">
                                                <LucideIcon name="Award" size={12} color="white" />
                                            </div>
                                            <p className="font-medium text-[#0D3E6B]">Gold Membership</p>
                                        </div>
                                        <div className="ml-4 grid grid-cols-3 gap-1">
                                            {['monthly', 'quarterly', 'annually'].map((period) => (
                                                <div key={period} className="rounded-2xl border border-[rgba(242,174,38,0.3)] bg-[rgba(242,174,38,0.1)] py-3 text-center">
                                                    <p className="mb-0.5 text-xs capitalize text-gray-500">{period}</p>
                                                    <p className="font-semibold text-[#F2AE26]">${CASH_EARNED.gold[period as keyof typeof CASH_EARNED.gold]}</p>
                                                </div>
                                            ))}
                                        </div>
                                    </div>

                                    {/* Platinum */}
                                    <div>
                                        <div className="mb-1.5 flex items-center gap-1">
                                            <div className="flex h-6 w-6 items-center justify-center rounded-full bg-[#0D3E6B]">
                                                <LucideIcon name="Crown" size={12} color="white" />
                                            </div>
                                            <p className="font-medium text-[#0D3E6B]">Platinum Membership</p>
                                        </div>
                                        <div className="ml-4 grid grid-cols-3 gap-1">
                                            {['monthly', 'quarterly', 'annually'].map((period) => (
                                                <div key={period} className="rounded-2xl border border-[rgba(13,62,107,0.3)] bg-[rgba(13,62,107,0.1)] py-3 text-center">
                                                    <p className="mb-0.5 text-xs capitalize text-gray-500">{period}</p>
                                                    <p className="font-semibold text-[#0D3E6B]">${CASH_EARNED.platinum[period as keyof typeof CASH_EARNED.platinum]}</p>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Tip Card */}
                    <div className="rounded-3xl border border-[rgba(13,62,107,0.3)] bg-[rgba(13,62,107,0.1)] p-4 shadow-none">
                        <div className="flex gap-1.5">
                            <LucideIcon name="Gift" size={20} color={BRAND_PRIMARY} style={{ flexShrink: 0, marginTop: 2 }} />
                            <div>
                                <p className="mb-0.5 font-semibold text-[#0D3E6B]">
                                    Maximize Your Earnings
                                </p>
                                <p className="text-sm text-gray-500">
                                    Refer drivers with higher membership tiers and annual plans to earn more cash!
                                </p>
                            </div>
                        </div>
                    </div>
                </div>
            </DashboardContent>

            {/* ── Cash Out Flow Modal ── */}
            <Modal open={showCashOutModal} onOpenChange={(open) => !open && closeCashOutModal()}>
                <ModalContent hideCloseButton className="max-w-sm rounded-3xl p-0 overflow-hidden">

                    {/* ── Step 1: Select Amount ── */}
                    {cashOutStep === 1 && (
                        <div>
                            <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between rounded-t-3xl">
                                <h2 className="text-[#1e3a5f]">Select Cash Out Amount</h2>
                                <button onClick={closeCashOutModal} className="w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center hover:bg-gray-200 transition-colors">
                                    <LucideIcon name="X" size={16} />
                                </button>
                            </div>

                            <div className="px-5 pb-6 space-y-4">
                                {/* Available Balance Card */}
                                <div
                                    className="w-full rounded-2xl p-4 text-center text-white"
                                    style={{ background: 'linear-gradient(to bottom right, #0D3E6B, #1e3a5f)' }}
                                >
                                    <p className="text-xs opacity-70 mb-1">Available Balance</p>
                                    <p className="text-3xl font-light tracking-tight">${availableBalance.toFixed(2)}</p>
                                </div>

                                {/* Amount options */}
                                <div>
                                    <p className="text-sm text-slate-500 mb-3">Select the amount you'd like to cash out</p>
                                    <div className="grid grid-cols-2 gap-3">
                                        {CASHOUT_OPTIONS.map((amount) => {
                                            const affordable = availableBalance >= amount && amount >= MIN_CASHOUT_AMOUNT;
                                            return (
                                                <button
                                                    key={amount}
                                                    type="button"
                                                    disabled={!affordable}
                                                    onClick={() => handleSelectAmount(amount)}
                                                    className={`rounded-2xl border py-5 text-center transition-all ${affordable
                                                        ? 'border-slate-200 bg-white text-[#0D3E6B] hover:border-[#0D3E6B] hover:shadow-md cursor-pointer'
                                                        : 'border-slate-100 bg-slate-50 cursor-not-allowed'
                                                        }`}
                                                >
                                                    <p className={`text-xl font-semibold ${affordable ? 'text-[#0D3E6B]' : 'text-slate-300'}`}>
                                                        ${amount}
                                                    </p>
                                                    {!affordable && (
                                                        <p className="text-xs text-slate-300 mt-0.5">
                                                            {availableBalance < MIN_CASHOUT_AMOUNT ? `Minimum cashout is $${MIN_CASHOUT_AMOUNT}` : 'Not enough funds'}
                                                        </p>
                                                    )}
                                                </button>
                                            );
                                        })}
                                    </div>
                                    {cashOutErrors.amount && (
                                        <p className="mt-2 text-sm text-red-600">{cashOutErrors.amount}</p>
                                    )}
                                </div>
                            </div>
                        </div>
                    )}

                    {/* ── Step 2: Contact Information ── */}
                    {cashOutStep === 2 && (
                        <div>
                            <div className="flex items-center gap-3 px-5 pt-5 pb-4">
                                <button
                                    type="button"
                                    onClick={() => setCashOutStep(1)}
                                    className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-100 text-slate-600 hover:bg-slate-200 transition-colors"
                                >
                                    <LucideIcon name="ChevronLeft" size={18} />
                                </button>
                                <ModalTitle className="text-base font-semibold text-[#0D3E6B]">
                                    Contact Information
                                </ModalTitle>
                            </div>

                            <div className="px-5 pb-6 space-y-4">
                                {/* Selected amount summary */}
                                <div
                                    className="w-full rounded-2xl p-4 text-center text-white"
                                    style={{ background: 'linear-gradient(to bottom right, #0D3E6B, #1e3a5f)' }}
                                >
                                    <p className="text-xs opacity-70 mb-1">Cash Out Amount</p>
                                    <p className="text-3xl font-light tracking-tight">${(selectedAmount ?? 0).toFixed(2)}</p>
                                </div>

                                <p className="text-sm text-center text-slate-500">
                                    Enter your contact information to receive your Imburse virtual card
                                </p>

                                {/* Email */}
                                <div>
                                    <label className="block text-sm font-medium text-slate-700 mb-1.5">
                                        Email Address
                                    </label>
                                    <div className="relative">
                                        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">
                                            <LucideIcon name="Mail" size={16} />
                                        </span>
                                        <input
                                            type="email"
                                            placeholder="your@email.com"
                                            value={cashOutEmail}
                                            onChange={(e: ChangeEvent<HTMLInputElement>) => updateCashOutField('email', e.target.value)}
                                            className={`w-full rounded-xl border bg-white py-3 pl-9 pr-4 text-sm text-slate-700 outline-none placeholder:text-slate-400 focus:border-[#0D3E6B] focus:ring-1 focus:ring-[#0D3E6B] ${displayedEmailError ? 'border-red-400' : 'border-slate-200'}`}
                                        />
                                    </div>
                                    <p className="mt-1 text-xs text-slate-400">Virtual card details will be sent here</p>
                                    {displayedEmailError && <p className="mt-1 text-sm text-red-600">{displayedEmailError}</p>}
                                </div>

                                {/* Phone */}
                                <div>
                                    <label className="block text-sm font-medium text-slate-700 mb-1.5">
                                        Phone Number
                                    </label>
                                    <input
                                        type="tel"
                                        placeholder="(555) 555-5555"
                                        value={cashOutPhone}
                                        onChange={(e: ChangeEvent<HTMLInputElement>) => updateCashOutField('phone', formatPhoneNumber(e.target.value))}
                                        className={`w-full rounded-xl border bg-white py-3 px-4 text-sm text-slate-700 outline-none placeholder:text-slate-400 focus:border-[#0D3E6B] focus:ring-1 focus:ring-[#0D3E6B] ${displayedPhoneError ? 'border-red-400' : 'border-slate-200'}`}
                                    />
                                    {displayedPhoneError && <p className="mt-1 text-sm text-red-600">{displayedPhoneError}</p>}
                                </div>

                                {/* Continue button — enabled only when both fields are valid */}
                                <Button
                                    type="button"
                                    fullWidth
                                    size="lg"
                                    disabled={!contactValid}
                                    onClick={handleContinueCashOut}
                                    className={`rounded-2xl font-semibold transition-all ${contactValid
                                        ? 'bg-[#0D3E6B] text-white hover:bg-[#0b355b]'
                                        : 'bg-slate-200 text-slate-400 cursor-not-allowed'
                                        }`}
                                >
                                    Continue
                                </Button>
                            </div>
                        </div>
                    )}

                    {/* ── Step 3: Confirm Cash Out ── */}
                    {cashOutStep === 3 && (
                        <div>
                            <div className="flex items-center gap-3 px-5 pt-5 pb-4">
                                <button
                                    type="button"
                                    onClick={() => setCashOutStep(2)}
                                    className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-100 text-slate-600 hover:bg-slate-200 transition-colors"
                                >
                                    <LucideIcon name="ChevronLeft" size={18} />
                                </button>
                                <ModalTitle className="text-base font-semibold text-[#0D3E6B]">
                                    Confirm Cash Out
                                </ModalTitle>
                            </div>

                            <div className="px-5 pb-6 space-y-4">
                                {/* Summary card */}
                                <div className="rounded-2xl border border-slate-100 bg-[#f0f5fb] p-5">
                                    {/* Card icon */}
                                    <div className="flex flex-col items-center mb-4">
                                        <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-xl bg-[#0D3E6B]">
                                            <LucideIcon name="CreditCard" size={26} color="white" />
                                        </div>
                                        <p className="text-sm text-slate-500">Cash Out Amount</p>
                                        <p className="text-3xl font-light text-[#0D3E6B] tracking-tight">
                                            ${(selectedAmount ?? 0).toFixed(2)}
                                        </p>
                                        <p className="text-xs text-slate-400 mt-0.5">Imburse Virtual Card</p>
                                    </div>

                                    {/* Contact + amount rows */}
                                    <div className="rounded-xl border border-slate-200 bg-white p-3 space-y-2">
                                        <div className="flex items-center justify-between text-sm">
                                            <span className="text-slate-500">Email</span>
                                            <span className="font-medium text-slate-700 truncate max-w-[180px] text-right">{cashOutEmail}</span>
                                        </div>
                                        <div className="flex items-center justify-between text-sm">
                                            <span className="text-slate-500">Phone</span>
                                            <span className="font-medium text-slate-700">{cashOutPhone}</span>
                                        </div>
                                        <div className="border-t border-slate-100 pt-2 flex items-center justify-between text-sm">
                                            <span className="text-slate-500">Amount to cash out</span>
                                            <span className="font-medium text-slate-700">${(selectedAmount ?? 0).toFixed(2)}</span>
                                        </div>
                                        <div className="flex items-center justify-between text-sm">
                                            <span className="text-slate-500">Remaining balance</span>
                                            <span className="font-medium text-slate-700">${remainingBalance.toFixed(2)}</span>
                                        </div>
                                    </div>
                                </div>

                                {/* Processing info */}
                                <div className="flex gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-3">
                                    <LucideIcon name="Mail" size={18} color="#b45309" style={{ flexShrink: 0, marginTop: 1 }} />
                                    <div>
                                        <p className="text-sm font-semibold text-amber-800">Processing Information</p>
                                        <p className="text-xs text-amber-700 leading-5">
                                            Virtual card details will be emailed to you within 3-5 business days.
                                        </p>
                                    </div>
                                </div>

                                {/* Confirm button */}
                                <Button
                                    type="button"
                                    fullWidth
                                    size="lg"
                                    disabled={Boolean(amountError) || !contactValid || cashOutMutation.isPending}
                                    onClick={handleConfirmCashOut}
                                    className="rounded-2xl bg-[#0D3E6B] font-semibold text-white hover:bg-[#0b355b]"
                                >
                                    {cashOutMutation.isPending ? 'Processing...' : 'Confirm Cash Out'}
                                </Button>
                                {amountError && <p className="text-sm text-red-600">{amountError}</p>}

                                {/* Go Back link */}
                                <button
                                    type="button"
                                    onClick={() => setCashOutStep(2)}
                                    disabled={cashOutMutation.isPending}
                                    className="w-full text-center text-sm text-slate-500 hover:text-slate-700 transition-colors disabled:opacity-50"
                                >
                                    Go Back
                                </button>
                            </div>
                        </div>
                    )}

                </ModalContent>
            </Modal>

            {/* ── Cash Out Success Modal ── */}
            <Modal open={showSuccessModal} onOpenChange={(open) => !open && setShowSuccessModal(false)}>
                <ModalContent className="max-w-sm rounded-3xl p-0 overflow-hidden">
                    <div className="flex flex-col items-center px-6 py-8 text-center">
                        {/* Green checkmark icon */}
                        <div className="mb-5 flex h-20 w-20 items-center justify-center rounded-full bg-green-100">
                            <LucideIcon name="CircleCheck" size={52} color="#16a34a" />
                        </div>

                        {/* Title */}
                        <h2 className="mb-3 text-xl font-semibold text-[#0D3E6B]">
                            Request Submitted!
                        </h2>

                        {/* Body */}
                        <p className="mb-2 text-sm leading-6 text-slate-600">
                            Your <span className="font-semibold">${confirmedAmount.toFixed(2)}</span> cash out request has been sent to our payments team.
                        </p>
                        <p className="mb-6 text-sm leading-6 text-slate-500">
                            You'll receive your Imburse virtual card via email within 3-5 business days.
                        </p>

                        {/* Three dots indicator */}
                        <div className="mb-2 flex items-center gap-1.5">
                            <span className="h-2.5 w-2.5 rounded-full bg-[#0D3E6B]" />
                            <span className="h-2.5 w-2.5 rounded-full bg-[#0D3E6B]" />
                            <span className="h-2.5 w-2.5 rounded-full bg-[#0D3E6B]" />
                        </div>
                    </div>
                </ModalContent>
            </Modal>

            {/* Share Text Modal */}
            <ShareTextModal
                open={showShareText}
                onClose={() => setShowShareText(false)}
                message={shareMessage}
            />
            <CompleteProfileModal {...completeProfileModalProps} />
        </>
    );
}
