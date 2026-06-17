import { useMemo, useState } from 'react';
import { Helmet } from 'react-helmet-async';

import { CONFIG } from 'src/config-global';
import { DashboardContent } from 'src/layouts/dashboard';
import LucideIcon from 'src/components/lucide-icon';
import { Button, Modal, ModalContent } from 'src/components/ui';
import { fDate } from 'src/utils/format-time';
import authModule from 'src/apiSetUp/authService';
import { useInfiniteReferralsQuery } from 'src/queries/use-referrals-query';

const TIER_REWARDS = [
    {
        tier: 'Silver Membership',
        iconColor: '#9E9E9E',
        iconBg: 'rgba(158, 158, 158, 0.12)',
        borderColor: 'rgba(145, 158, 171, 0.2)',
        cardBg: 'rgba(145, 158, 171, 0.04)',
        values: [
            { label: 'Monthly', points: '500 pts' },
            { label: 'Quarterly', points: '1000 pts' },
            { label: 'Annually', points: '2500 pts' },
        ],
    },
    {
        tier: 'Gold Membership',
        iconColor: '#FFB300',
        iconBg: 'rgba(255, 179, 0, 0.12)',
        borderColor: 'rgba(255, 179, 0, 0.2)',
        cardBg: 'rgba(255, 179, 0, 0.04)',
        values: [
            { label: 'Monthly', points: '1000 pts' },
            { label: 'Quarterly', points: '2000 pts' },
            { label: 'Annually', points: '5000 pts' },
        ],
    },
    {
        tier: 'Platinum Membership',
        iconColor: '#424242',
        iconBg: 'rgba(66, 66, 66, 0.12)',
        borderColor: 'rgba(66, 66, 66, 0.2)',
        cardBg: 'rgba(66, 66, 66, 0.04)',
        values: [
            { label: 'Monthly', points: '1500 pts' },
            { label: 'Quarterly', points: '3000 pts' },
            { label: 'Annually', points: '6000 pts' },
        ],
    },
];

export default function RewardsPage() {
    const [pointsExpanded, setPointsExpanded] = useState(false);
    const [cashOutOpen, setCashOutOpen] = useState(false);

    const isTokenAvailable = authModule.isLoggedIn();
    const referralsQuery = useInfiniteReferralsQuery(isTokenAvailable, 20);

    const referrals = useMemo(() => {
        const seen = new Set<string>();
        const merged: any[] = [];

        (referralsQuery.data?.pages || []).forEach((page) => {
            (page.referrals || []).forEach((item: any) => {
                const key = String(item.id || `${item.email}-${item.createdDate}`);
                if (seen.has(key)) return;
                seen.add(key);
                merged.push(item);
            });
        });

        return merged;
    }, [referralsQuery.data]);

    const hasMore = Boolean(referralsQuery.hasNextPage);
    const loading = referralsQuery.isLoading || referralsQuery.isFetching;

    const totalPoints = referrals.reduce((sum, ref) => sum + (ref.pointsAwarded || 0), 0);
    const activeReferrals = referrals.filter((ref) => ref.status === 'Active').length;
    const pointsThisMonth = referrals
        .filter((ref) => {
            const refDate = new Date(ref.createdDate);
            const now = new Date();
            return refDate.getMonth() === now.getMonth() && refDate.getFullYear() === now.getFullYear();
        })
        .reduce((sum, ref) => sum + (ref.pointsAwarded || 0), 0);

    const getTierColor = (tier: string) => {
        switch (tier?.toLowerCase()) {
            case 'platinum':
                return '#424242';
            case 'gold':
                return '#FFB300';
            case 'silver':
                return '#9E9E9E';
            default:
                return '#1a365d';
        }
    };

    const getStatusColor = (status: string) => {
        switch (status?.toLowerCase()) {
            case 'active':
                return { bg: 'rgba(34, 197, 94, 0.08)', color: '#15803d' };
            case 'pending':
                return { bg: 'rgba(255, 171, 0, 0.08)', color: '#b45309' };
            default:
                return { bg: 'rgba(145, 158, 171, 0.08)', color: '#6b7280' };
        }
    };

    return (
        <>
            <Helmet>
                <title>{`Rewards - ${CONFIG.appName}`}</title>
            </Helmet>

            <DashboardContent>
                <div className="mvp-page-shell">
                <div className="mb-6 text-center sm:text-left">
                    <h1 className="mb-0.5 text-3xl font-extrabold text-[#1a365d]">
                        Your Rewards
                    </h1>
                    <p className="text-sm text-gray-500">
                        Earn points and cash them out
                    </p>
                </div>

                <div className="mb-6 rounded-2xl bg-[linear-gradient(135deg,#1a365d_0%,#2c5282_100%)] p-6 text-white shadow-[0_20px_40px_rgba(15,23,42,0.18)]">
                    <div className="mb-1 flex items-center gap-1">
                        <LucideIcon name="Wallet" size={20} />
                        <p className="text-xs opacity-90">Total Points Balance</p>
                    </div>
                    <p className="mb-0.5 text-4xl font-extrabold text-white">
                        {totalPoints.toLocaleString()}
                    </p>
                    <p className="mb-2 block text-xs opacity-80">
                        points = ${(totalPoints / 100).toFixed(2)}
                    </p>
                    <Button
                        fullWidth
                        disabled={totalPoints < 2500}
                        size="lg"
                        variant="secondary"
                        onClick={() => setCashOutOpen(true)}
                        className="h-12 justify-center gap-2 rounded-xl border-white bg-white font-bold text-[#1a365d] hover:bg-white disabled:opacity-60"
                    >
                        <LucideIcon name="DollarSign" size={20} />
                        <span>{totalPoints < 2500 ? `${2500 - totalPoints} pts to Cash Out` : 'Cash Out — Gift Card or Visa'}</span>
                        <LucideIcon name="ArrowRight" size={20} />
                    </Button>
                </div>

                <div className="mb-4 grid grid-cols-2 gap-3">
                    <div className="rounded-lg bg-white p-5 shadow-sm">
                        <div className="mb-1 flex items-center gap-1">
                            <LucideIcon name="Users" size={18} color="#6b7280" />
                            <p className="text-xs text-gray-500">Active Referrals</p>
                        </div>
                        <p className="text-4xl font-extrabold text-[#1a365d]">{activeReferrals}</p>
                    </div>
                    <div className="rounded-lg bg-white p-5 shadow-sm">
                        <div className="mb-1 flex items-center gap-1">
                            <LucideIcon name="Calendar" size={18} color="#6b7280" />
                            <p className="text-xs text-gray-500">Points This Month</p>
                        </div>
                        <p className="text-4xl font-extrabold text-[#1a365d]">{pointsThisMonth.toLocaleString()}</p>
                    </div>
                </div>

                <div className="mb-4 rounded-2xl bg-white shadow-sm">
                    <button
                        type="button"
                        className="flex w-full items-center gap-1.5 p-5 text-left transition-colors hover:bg-[rgba(145,158,171,0.05)]"
                        onClick={() => setPointsExpanded(!pointsExpanded)}
                    >
                        <LucideIcon name="Gift" size={20} color="#1a365d" />
                        <span className="flex-grow text-base font-bold text-[#1a365d]">Points Per Referral</span>
                        <span
                            className="transition-transform duration-300"
                            style={{ transform: pointsExpanded ? 'rotate(180deg)' : 'rotate(0deg)' }}
                        >
                            <LucideIcon name="ChevronDown" size={20} color="#6b7280" />
                        </span>
                    </button>

                    {pointsExpanded && (
                        <div className="mt-1 px-5 pb-5">
                            {TIER_REWARDS.map((tierItem, index) => (
                                <div key={tierItem.tier} className={index < TIER_REWARDS.length - 1 ? 'mb-6' : ''}>
                                    <div className="mb-3 flex items-center gap-1.5">
                                        <div
                                            className="flex h-8 w-8 items-center justify-center rounded-full"
                                            style={{ backgroundColor: tierItem.iconBg }}
                                        >
                                            <LucideIcon name="Medal" size={18} color={tierItem.iconColor} />
                                        </div>
                                        <p className="text-sm font-bold text-[#1a365d]">{tierItem.tier}</p>
                                    </div>

                                    <div className="flex flex-wrap gap-3">
                                        {tierItem.values.map((value) => (
                                            <div
                                                key={value.label}
                                                className="min-w-[100px] flex-[1_1_auto] rounded-xl border p-3 text-center"
                                                style={{
                                                    borderColor: tierItem.borderColor,
                                                    backgroundColor: tierItem.cardBg,
                                                }}
                                            >
                                                <p className="mb-0.5 block text-xs text-gray-500">{value.label}</p>
                                                <p className="text-sm font-bold text-[#1a365d]">{value.points}</p>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                <div className="mb-4 rounded-2xl bg-[rgba(24,144,255,0.04)] p-5">
                    <div className="flex items-center gap-1.5">
                        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#1a365d] text-white">
                            <span className="text-lg font-bold text-white">$</span>
                        </div>
                        <div>
                            <p className="text-sm font-bold text-[#1a365d]">Points Conversion</p>
                            <p className="text-xs text-gray-500">100 points = $1.00</p>
                        </div>
                    </div>
                </div>

                <div className="mb-4">
                    <div className="mb-2 flex items-center gap-1">
                        <LucideIcon name="History" size={20} color="#1a365d" />
                        <p className="text-base font-bold text-[#1a365d]">Referral History</p>
                    </div>

                    {loading && referrals.length === 0 ? (
                        <div className="flex justify-center py-10">
                            <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-200 border-t-[#1a365d]" />
                        </div>
                    ) : referrals.length === 0 ? (
                        <div className="rounded-lg bg-white p-8 text-center shadow-sm">
                            <p className="text-sm text-gray-500">
                                No referrals yet. Start referring drivers to earn rewards!
                            </p>
                        </div>
                    ) : (
                        <div className="space-y-2">
                            {referrals.map((referral, index) => {
                                const statusStyle = getStatusColor(referral.status);

                                return (
                                    <div key={referral.id || index} className="rounded-lg bg-white p-5 shadow-sm">
                                        <div className="flex gap-2">
                                            <div
                                                className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-sm font-bold text-white"
                                                style={{ backgroundColor: getTierColor(referral.productTier) }}
                                            >
                                                {referral.referredDriverInitials || referral.referredDriverName?.substring(0, 2).toUpperCase()}
                                            </div>

                                            <div className="flex-grow">
                                                <div className="mb-0.5 flex items-start justify-between gap-2">
                                                    <div>
                                                        <p className="text-sm font-bold text-[#1a365d]">{referral.referredDriverName}</p>
                                                        <p className="text-xs text-gray-500">{fDate(referral.createdDate)}</p>
                                                    </div>
                                                    <p className="text-base font-bold text-green-600">
                                                        {referral.pointsAwarded?.toLocaleString()} pts
                                                    </p>
                                                </div>

                                                <div className="mt-2 flex flex-wrap gap-2">
                                                    <span
                                                        className="rounded-full px-2 py-1 text-[11px] font-semibold"
                                                        style={{
                                                            backgroundColor: `${getTierColor(referral.productTier)}15`,
                                                            color: getTierColor(referral.productTier),
                                                        }}
                                                    >
                                                        {referral.productTier}
                                                    </span>
                                                    <span className="rounded-full bg-[rgba(145,158,171,0.08)] px-2 py-1 text-[11px] text-gray-600">
                                                        {referral.billingFrequency}
                                                    </span>
                                                    <span
                                                        className="rounded-full px-2 py-1 text-[11px] font-semibold"
                                                        style={{ backgroundColor: statusStyle.bg, color: statusStyle.color }}
                                                    >
                                                        {referral.status}
                                                    </span>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                );
                            })}

                            {hasMore ? (
                                <div className="mt-2 text-center">
                                    <Button
                                        onClick={() => referralsQuery.fetchNextPage()}
                                        disabled={referralsQuery.isFetchingNextPage}
                                        variant="secondary"
                                        className="border border-slate-200 bg-white text-[#1a365d]"
                                    >
                                        {referralsQuery.isFetchingNextPage ? 'Loading...' : 'Load More'}
                                    </Button>
                                </div>
                            ) : (
                                referrals.length > 0 && (
                                    <div className="mb-2 mt-4 text-center">
                                        <p className="text-xs text-gray-400">All referrals loaded</p>
                                    </div>
                                )
                            )}
                        </div>
                    )}
                </div>

                <div className="rounded-2xl border border-[rgba(24,144,255,0.2)] bg-[rgba(24,144,255,0.04)] p-6">
                    <div className="flex items-start gap-2">
                        <LucideIcon name="Gift" size={20} color="#003e6b" />
                        <div>
                            <p className="mb-0.5 text-sm font-bold text-[#1a365d]">Maximize Your Earnings</p>
                            <p className="text-xs text-[#4a5565]">
                                Refer drivers with higher membership tiers and annual plans to earn more cash!
                            </p>
                        </div>
                    </div>
                </div>

                <Modal open={cashOutOpen} onOpenChange={setCashOutOpen}>
                    <ModalContent className="max-w-md rounded-2xl p-0" hideCloseButton>
                        <div className="flex items-center justify-between px-6 py-5">
                            <p className="text-base font-bold text-[#1a365d]">Cash Out Rewards</p>
                            <button
                                type="button"
                                onClick={() => setCashOutOpen(false)}
                                className="inline-flex h-9 w-9 items-center justify-center rounded-full text-slate-500 transition hover:bg-slate-100 hover:text-slate-900"
                            >
                                <LucideIcon name="CircleX" size={24} />
                            </button>
                        </div>

                        <div className="px-6 pb-6">
                        <div className="mb-3 rounded-lg bg-[linear-gradient(135deg,#1a365d_0%,#2c5282_100%)] p-6 text-center text-white">
                            <p className="mb-1 block text-xs opacity-90">Available to Cash Out</p>
                            <p className="mb-0.5 text-4xl font-extrabold text-white">${(totalPoints / 100).toFixed(2)}</p>
                            <p className="text-xs opacity-80">{totalPoints.toLocaleString()} points</p>
                        </div>

                        <p className="mb-2 text-sm text-gray-500">Choose how you'd like to receive your rewards</p>

                        <div className="space-y-1.5">
                            {[
                                {
                                    title: 'Visa Gift Card',
                                    description: 'Use anywhere Visa is accepted',
                                    icon: 'CreditCard' as const,
                                    iconBg: '#1976d2',
                                },
                                {
                                    title: 'Store Gift Card',
                                    description: 'Choose from popular retailers',
                                    icon: 'Store' as const,
                                    iconBg: '#2e7d32',
                                },
                            ].map((option) => (
                                <button
                                    key={option.title}
                                    type="button"
                                    className="flex w-full items-center rounded-xl border border-gray-200 p-4 text-left transition-colors hover:bg-gray-50"
                                >
                                    <div
                                        className="mr-3 flex h-10 w-10 items-center justify-center rounded-xl text-white"
                                        style={{ backgroundColor: option.iconBg }}
                                    >
                                        <LucideIcon name={option.icon} size={22} />
                                    </div>
                                    <div className="flex-grow">
                                        <p className="text-sm font-bold text-[#1a365d]">{option.title}</p>
                                        <p className="text-xs text-gray-500">{option.description}</p>
                                    </div>
                                    <LucideIcon name="ChevronRight" size={20} color="#6b7280" />
                                </button>
                            ))}
                        </div>

                        <div className="mt-3 flex gap-1.5 rounded-xl bg-[rgba(24,144,255,0.08)] p-4">
                            <LucideIcon name="Info" size={20} color="#2196f3" style={{ flexShrink: 0, marginTop: 2 }} />
                            <p className="text-xs text-sky-600">
                                Gift cards are typically delivered within 24-48 hours via email.
                            </p>
                        </div>
                        </div>
                    </ModalContent>
                </Modal>
                </div>
            </DashboardContent>
        </>
    );
}
