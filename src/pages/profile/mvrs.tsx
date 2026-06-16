import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { DashboardContent } from 'src/layouts/dashboard';
import LucideIcon from 'src/components/lucide-icon';
import { Button } from 'src/components/ui';
import authModule from 'src/apiSetUp/authService';
import { useInfiniteDriverMvrsQuery } from 'src/queries/use-driver-mvrs-query';

export default function MVRsPage() {
    const navigate = useNavigate();
    const mvrsQuery = useInfiniteDriverMvrsQuery(authModule.isLoggedIn(), 20);

    const displayMVRs = useMemo(
        () => (mvrsQuery.data?.pages || []).flatMap((page) => page.mvrs || []),
        [mvrsQuery.data]
    );

    const hasMore = Boolean(mvrsQuery.hasNextPage);

    return (
        <DashboardContent>
            <div className="mb-3 flex items-center">
                <Button
                    type="button"
                    onClick={() => navigate('/profile')}
                    variant="secondary"
                    size="icon"
                    className="mr-2 rounded-full border border-slate-200 bg-white text-[#1a365d] shadow-sm"
                >
                    <LucideIcon name="ChevronLeft" size={24} />
                </Button>
                <div>
                    <h1 className="text-2xl font-extrabold text-[#1a365d]">
                        Your MVRs
                    </h1>
                    <p className="text-sm text-gray-500">
                        Motor Vehicle Records on file
                    </p>
                </div>
            </div>

            <div className="mb-3 flex gap-2 rounded-lg border border-[rgba(26,54,93,0.1)] bg-[rgba(26,54,93,0.05)] p-2">
                <LucideIcon name="FileText" size={24} color="#1a365d" style={{ marginTop: 4 }} />
                <div>
                    <p className="mb-0.5 text-sm font-bold text-[#1a365d]">
                        About Your MVRs
                    </p>
                    <p className="block text-xs leading-5 text-gray-500">
                        We maintain your motor vehicle records for compliance and safety monitoring. These records are pulled from state DMVs and include violations, accidents, and license status.
                    </p>
                </div>
            </div>

            <div className="space-y-2">
                {displayMVRs.length === 0 ? (
                    <div className="rounded-lg bg-white p-4 text-center shadow-sm">
                        <p className="text-sm text-gray-500">
                            No MVR records found.
                        </p>
                    </div>
                ) : (
                    displayMVRs.map((item: any, index: number) => {
                        const isAvailable = item.mvrStatus === 'Completed' || item.mvrStatus === 'Available';
                        const isProcessing = item.mvrStatus === 'In Process' || item.mvrStatus === 'Pending';

                        return (
                            <div key={item.id || index} className="overflow-visible rounded-lg bg-white shadow-sm">
                                <div className="flex items-start justify-between p-2.5 pb-2">
                                    <div className="flex gap-2">
                                        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[#1a365d] text-white">
                                            <LucideIcon name="FileText" size={24} />
                                        </div>
                                        <div>
                                            <p className="mb-0.5 text-base font-extrabold text-[#1a365d]">
                                                {item.name || 'MVR Report'}
                                            </p>
                                            <p className="text-xs text-gray-500">
                                                {item.carrierFromDriver || 'Carrier Record'}
                                            </p>
                                        </div>
                                    </div>
                                    <div
                                        className="flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-[11px] font-bold"
                                        style={{
                                            backgroundColor: isAvailable ? 'rgba(34, 197, 94, 0.08)' : 'rgba(24, 144, 255, 0.08)',
                                            color: isAvailable ? '#15803d' : '#0369a1',
                                        }}
                                    >
                                        {isProcessing && <LucideIcon name="RefreshCw" size={12} />}
                                        {isAvailable && <LucideIcon name="CircleCheck" size={12} />}
                                        {item.mvrStatus || 'Unknown'}
                                    </div>
                                </div>

                                <div className="px-2.5 pb-2.5">
                                    <div className="mb-2 grid grid-cols-2 gap-2">
                                        <div>
                                            <p className="mb-0.5 block text-xs text-gray-500">
                                                States
                                            </p>
                                            <p className="text-sm font-semibold text-[#1a365d]">
                                                {item.driverState || '-'}
                                            </p>
                                        </div>
                                    </div>

                                    {isProcessing && (
                                        <div className="mb-2.5 rounded bg-[rgba(145,158,171,0.04)] p-2 text-center">
                                            <p className="text-xs text-gray-500">
                                                MVR is being processed. Check back in 3-5 business days.
                                            </p>
                                        </div>
                                    )}

                                    {isAvailable && (
                                        <div className="flex gap-1">
                                            <Button
                                                type="button"
                                                fullWidth
                                                size="lg"
                                                className="gap-2 rounded-lg bg-[#003358] hover:bg-[#002642]"
                                            >
                                                <LucideIcon name="Eye" size={20} />
                                                View Details
                                            </Button>
                                            <Button
                                                type="button"
                                                variant="secondary"
                                                size="icon"
                                                className="h-12 w-12 shrink-0 rounded-lg border border-[rgba(145,158,171,0.32)] bg-white px-0 text-slate-700"
                                            >
                                                <LucideIcon name="Download" size={22} />
                                            </Button>
                                        </div>
                                    )}
                                </div>
                            </div>
                        );
                    })
                )}
            </div>
            {hasMore && (
                <div className="mt-3 text-center">
                    <Button
                        type="button"
                        variant="secondary"
                        onClick={() => mvrsQuery.fetchNextPage()}
                        disabled={mvrsQuery.isFetchingNextPage}
                        className="border border-[rgba(145,158,171,0.32)] bg-white text-slate-700"
                    >
                        Load More
                    </Button>
                </div>
            )}

            <div className="mb-2 mt-4">
                <div className="border border-dashed border-[rgba(145,158,171,0.2)] bg-[rgba(145,158,171,0.04)] p-6 text-center shadow-none">
                    <div className="mx-auto mb-2 flex h-12 w-12 items-center justify-center rounded-full bg-white text-gray-500">
                        <LucideIcon name="FileText" size={24} />
                    </div>
                    <p className="mb-1 text-base text-gray-900">
                        Need Help with MVRs?
                    </p>
                    <p className="mb-3 text-sm text-gray-500">
                        Contact our support team to request a new motor vehicle record
                    </p>
                    <Button type="button" onClick={() => navigate('/support')}>
                        Contact Support
                    </Button>
                </div>
            </div>
        </DashboardContent>
    );
}
