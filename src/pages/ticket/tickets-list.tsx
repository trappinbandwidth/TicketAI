import { useState, useCallback, useMemo, memo } from 'react';
import { Helmet } from 'react-helmet-async';
import { useNavigate, Outlet } from 'react-router-dom';

import { CONFIG } from 'src/config-global';
import { DashboardContent } from 'src/layouts/dashboard';
import { fDate } from 'src/utils/format-time';
import { useAtom } from 'jotai';
import { firebaseUid } from 'src/store';
import { CasesItem, DriverTicketItem } from 'src/common-service/types.interface';
import { TICKET_STATUSES_ICON } from 'src/membership-config';
import LucideIcon from 'src/components/lucide-icon';
import { useProfileGuard } from 'src/hooks/use-profile-guard';
import CompleteProfileModal from 'src/components/shared/CompleteProfileModal';
import { useTicketsRealtime } from 'src/hooks/use-tickets-realtime';
import { type FirestoreTicket } from 'src/services/firestore';
import AddTicketModal from './add-ticket-modal';

// ================== Constants ==================
const BRAND_PRIMARY = '#1a365d';
const BRAND_ACCENT = '#d32f2f';

interface StatusStyle {
    bg: string;
    color: string;
}

// ================== Helper Functions ==================
const getStatusColor = (status: string): StatusStyle => {
    switch (status?.toLowerCase()) {
        case 'attny assigned':
        case 'in progress':
            return { bg: 'rgba(24, 144, 255, 0.1)', color: '#1e3a5f' };
        case 'ticket closed':
        case 'closed':
        case 'reduced to 0 points':
            return { bg: '#f0fdf4', color: '#008236' };
        case 'active':
        case 'pending':
        case 'action required':
            return { bg: 'rgba(255, 86, 48, 0.1)', color: '#ff5630' };
        case 'waiting on court':
        case 'warning':
            return { bg: 'rgba(255, 171, 0, 0.1)', color: '#ffab00' };
        default:
            return { bg: 'rgba(145, 158, 171, 0.1)', color: '#637381' };
    }
};

const isClosed = (ticket: DriverTicketItem): boolean => {
    const status = ticket.attorneyStatus?.toLowerCase() || '';
    // const outcome = ticket.ticketOutcome?.toLowerCase() || '';
    // || outcome === 'reduced to 0 points'
    return status === 'ticket closed' || status === 'closed';
};

const isInProgress = (ticket: DriverTicketItem): boolean => !isClosed(ticket);

// ================== Skeleton Components ==================
const TicketCardSkeleton = memo(() => (
    <div className="rounded-lg bg-white p-4 shadow-sm">
        <div className="flex gap-1.5">
            <div className="h-10 w-10 shrink-0 animate-pulse rounded-xl bg-gray-200" />
            <div className="min-w-0 flex-1">
                <div className="mb-0.5 h-4 w-[40%] animate-pulse rounded bg-gray-200" />
                <div className="mb-1 h-5 w-[70%] animate-pulse rounded bg-gray-200" />
                <div className="mb-0.5 h-3.5 w-[50%] animate-pulse rounded bg-gray-200" />
                <div className="h-3.5 w-[45%] animate-pulse rounded bg-gray-200" />
                <div className="mt-1 flex justify-end">
                    <div className="h-[22px] w-20 animate-pulse rounded-full bg-gray-200" />
                </div>
            </div>
        </div>
    </div>
));
TicketCardSkeleton.displayName = 'TicketCardSkeleton';

// ================== Ticket Card Component ==================
interface TicketCardProps {
    ticket: DriverTicketItem;
    onClick: () => void;
}
const TicketCard = memo(({ ticket, onClick }: TicketCardProps) => {
    const isClosedTicket = isClosed(ticket);
    const hasAttorney = ticket.attorney !== null && ticket.attorney !== undefined && !isClosedTicket;
    const displayStatus = ticket.ticketStatus;
    const statusStyle = getStatusColor(displayStatus);

    const getBottomStatus = () => {
        if (isClosedTicket) {
            return { label: 'Closed', ...getStatusColor('closed') };
        }
        if (hasAttorney) {
            return { label: 'Attorney Assigned', bg: 'rgba(24, 144, 255, 0.1)', color: BRAND_PRIMARY };
        }
        return { label: displayStatus, ...statusStyle };
    };

    const bottomStatus = getBottomStatus();

    return (
        <div
            className="relative cursor-pointer overflow-visible rounded-lg bg-white shadow-sm transition-all duration-200 hover:-translate-y-px hover:shadow-lg active:translate-y-0"
            onClick={onClick}
        >
            {ticket.actionRequired && (
                <div className="absolute -right-[5px] -top-[5px] z-[1] flex items-center gap-0.5 rounded-full bg-[#ec1c24] px-1 py-0.5 text-[0.65rem] font-bold text-white">
                    <LucideIcon name="TriangleAlert" size={12} />
                    Action Required
                </div>
            )}
            <div className="flex gap-1.5 p-4">
                {/* Icon */}
                <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-xl text-[#1a365d]">
                    <img
                        width={20}
                        height={20}
                        src={TICKET_STATUSES_ICON['Ticket Received']}
                        alt={displayStatus}
                    />
                </div>

                {/* Details */}
                <div className="min-w-0 flex-1">
                    <div className="mb-0.5 flex items-center justify-between gap-1">
                        <span className="block text-[0.7rem] text-gray-500 sm:text-xs">
                            {ticket.stateCodeCitation}
                        </span>
                        {ticket.attorneyStatus && TICKET_STATUSES_ICON[ticket.attorneyStatus as keyof typeof TICKET_STATUSES_ICON] && (
                            <img
                                width={20}
                                height={20}
                                src={TICKET_STATUSES_ICON[ticket.attorneyStatus as keyof typeof TICKET_STATUSES_ICON]}
                                alt={ticket.attorneyStatus}
                            />
                        )}
                    </div>
                    <p
                        className="mb-3 text-[0.8125rem] font-bold leading-[1.3] text-[#1a365d] sm:text-sm"
                        style={{
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            display: '-webkit-box',
                            WebkitLineClamp: 2,
                            WebkitBoxOrient: 'vertical',
                        }}
                    >
                        {ticket.violationCategory || ticket.violationDescription || 'No Description'}
                    </p>
                    {isClosedTicket &&
                        (
                            <div className="mb-0.75 flex items-center gap-1">
                                <LucideIcon name="CircleCheckBig" width={16} color="#22c55e" />
                                <span className="text-sm text-[#008236]">
                                    {ticket.ticketOutcome}
                                </span>
                            </div>
                        )
                    }
                    {/* Date Info */}
                    <div className="mb-0.75 space-y-0.5">
                        <div className="flex items-center gap-0.5 text-[0.7rem] text-gray-500 sm:text-xs">
                            <LucideIcon name="Calendar" width={14} />
                            <span>Incident: {ticket.createdDate ? fDate(ticket.createdDate) : 'N/A'}</span>
                        </div>
                        <div className="flex items-center gap-0.5 text-[0.7rem] text-gray-500 sm:text-xs">
                            <LucideIcon name="Calendar" width={14} />
                            <span>Court: {ticket.courtDate ? fDate(ticket.courtDate) : 'N/A'}</span>
                        </div>
                    </div>

                    {/* Status Pill */}
                    <div className="flex justify-end">
                        <div
                            className="whitespace-nowrap rounded-full px-1.25 py-0.25 text-[10px] font-semibold sm:text-[11px]"
                            style={{ backgroundColor: bottomStatus.bg, color: bottomStatus.color }}
                        >
                            {bottomStatus.label}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
});
TicketCard.displayName = 'TicketCard';

interface CaseCardProps {
    ticket: CasesItem;
    onClick: () => void;
}
const CaseCard = memo(({ ticket, onClick }: CaseCardProps) => {
    return (
        <div
            onClick={onClick}
            className="relative cursor-not-allowed overflow-visible rounded-lg border border-[#8ec5ff] bg-[#a5e5f833] shadow-sm transition-all duration-200 hover:-translate-y-px hover:shadow-lg active:translate-y-0"
        >
            <div className="absolute -right-[5px] -top-[5px] z-[1] flex items-center gap-0.5 rounded-full bg-[#0D3E6B] px-1 py-0.25 text-[0.61rem] font-medium text-white">
                <LucideIcon name="TriangleAlert" size={12} />
                Rig Resolve's experts are reviewing - You're in good hands
            </div>
            <div className="flex gap-1.5 p-4">
                {/* Icon */}
                <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-xl text-[#1a365d]">
                    <img
                        width={20}
                        height={20}
                        src={TICKET_STATUSES_ICON['Ticket Received']}
                        alt={ticket.caseNumber}
                    />
                </div>

                {/* Details */}
                <div className="min-w-0 flex-1">
                    <div className="mb-0.5 flex items-center justify-between gap-1">
                        <span className="block text-[0.7rem] text-gray-500 sm:text-xs">
                            {ticket.caseNumber}
                        </span>
                        <img
                            width={20}
                            height={20}
                            src={TICKET_STATUSES_ICON['Ticket Received']}
                            alt={ticket.caseNumber}
                        />
                    </div>
                    <p
                        className="mb-3 text-[0.8125rem] font-bold leading-[1.3] text-[#1a365d] sm:text-sm"
                        style={{
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            display: '-webkit-box',
                            WebkitLineClamp: 2,
                            WebkitBoxOrient: 'vertical',
                        }}
                    >
                        {ticket.description}
                    </p>

                    {/* Date Info */}
                    <div className="mb-0.75 space-y-0.5">
                        <div className="flex items-center gap-0.5 text-[0.7rem] text-gray-500 sm:text-xs">
                            <LucideIcon name="Calendar" width={14} />
                            <span>Court: TBD</span>
                        </div>
                    </div>

                    {/* Status Pill */}
                    <div className="flex justify-end">
                        <div className="whitespace-nowrap rounded-full bg-[rgba(24,144,255,0.1)] px-1.25 py-0.25 text-[10px] font-semibold text-[#637381] sm:text-[11px]">
                            Received
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
});
CaseCard.displayName = 'CaseCard';
// ================== Tab Label Component ==================
interface TabLabelProps {
    label: string;
    count: number;
}

const TabLabel = memo(({ label, count }: TabLabelProps) => (
    <div className="flex items-center gap-0.75">
        <span>{label}</span>
        <span className="min-w-5 rounded-full bg-[rgba(255,255,255,0.2)] px-0.75 py-0.125 text-center text-[10px] font-bold sm:text-[11px]">
            {count}
        </span>
    </div>
));
TabLabel.displayName = 'TabLabel';


// ── Firestore → legacy shape adapters ───────────────────────────────────────

const STATUS_LABEL: Record<string, string> = {
    processing: 'Pending',
    needs_review: 'In Progress',
    approved: 'Attny Assigned',
    rejected: 'Action Required',
    closed: 'Ticket Closed',
};

function toDriverTicket(t: FirestoreTicket): DriverTicketItem {
    const statusLabel = STATUS_LABEL[t.status] ?? 'Pending';
    return {
        id: t.id,
        stateCodeCitation: t.ticket_state ?? '',
        createdDate: t.date_of_ticket ?? (t.created_at ? t.created_at.toDate().toISOString() : ''),
        courtDate: t.court_date ?? undefined,
        violationCategory: t.violation_category ?? '',
        violationDescription: t.violation_description ?? '',
        violationLocation: [t.ticket_city, t.ticket_county, t.ticket_state].filter(Boolean).join(', '),
        ticketOutcome: '',
        paymentRequired: null,
        fineAmount: t.price_low,
        attorneyStatus: t.attorney_name ? 'Attny Assigned' : statusLabel,
        ticketStatus: statusLabel,
        attorney: t.attorney_name
            ? { name: t.attorney_name ?? undefined, email: t.attorney_email ?? undefined, phone: t.attorney_phone ?? undefined }
            : null,
        actionRequired: t.pass_status === 'red',
    };
}

function toCaseItem(t: FirestoreTicket): CasesItem {
    return {
        id: t.id,
        caseNumber: t.id.slice(0, 8).toUpperCase(),
        createdDate: t.created_at ? t.created_at.toDate().toISOString() : '',
        description: t.description || t.violation_category || 'Ticket scan in progress…',
        priority: 'Normal',
        status: 'Processing',
        subject: t.violation_category ?? 'Scanning ticket…',
    };
}

// ================== Main Component ==================
export default function TicketsPage() {
    const navigate = useNavigate();
    const [fbUid] = useAtom(firebaseUid);
    const [tabDetails, setTabDetails] = useState('all');
    const [openAddTicket, setOpenAddTicket] = useState(false);
    const { hasIncompleteProfile, completeProfileModalProps, openProfileCompletion } = useProfileGuard();

    const { tickets: firestoreTickets, loading } = useTicketsRealtime(fbUid || null);

    // Split: processing tickets show as "cases" (scanning banner), rest as regular tickets
    const { tickets, cases } = useMemo(() => {
        const t: DriverTicketItem[] = [];
        const c: CasesItem[] = [];
        for (const ft of firestoreTickets) {
            if (ft.status === 'processing') {
                c.push(toCaseItem(ft));
            } else {
                t.push(toDriverTicket(ft));
            }
        }
        return { tickets: t, cases: c };
    }, [firestoreTickets]);

    // Memoized counts
    const ticketCounts = useMemo(
        () => ({
            all: tickets.length + cases.length,
            progress: tickets.filter(isInProgress).length,
            closed: tickets.filter(isClosed).length,
        }),
        [tickets, cases]
    );

    // Filtered tickets
    const filteredTickets = useMemo(() => {
        switch (tabDetails) {
            case 'progress':
                return tickets.filter(isInProgress);
            case 'closed':
                return tickets.filter(isClosed);
            default:
                return tickets;
        }
    }, [tickets, tabDetails]);

    const onSuccess = useCallback(() => {
        setOpenAddTicket(false);
    }, []);

    const addTicketClose = useCallback(() => {
        setOpenAddTicket(false);
    }, []);

    return (
        <DashboardContent>
            <Helmet>
                <title>{`Tickets - ${CONFIG.appName}`}</title>
            </Helmet>
            {/* Header */}

            <div className="mvp-page-shell">
                <div className="mb-6 text-left">
                    <h2 className="mb-1 text-[1.75rem] font-medium text-[#1e3a5f] sm:text-[2rem]">Your Tickets</h2>
                    <p className="mb-4 text-base text-gray-600">Manage all your citations in one place</p>
                    <button className="bg-[#dc2626] text-white px-4 py-2 rounded-full text-sm hover:bg-[#b91c1c] transition-colors flex items-center gap-2" onClick={hasIncompleteProfile ? () => openProfileCompletion('submit-ticket') : () => setOpenAddTicket(true)}>
                        <LucideIcon name="FileText" width={18} />
                        <span>Add Ticket</span>
                    </button>
                </div>
                {/* Tabs */}
                <div className="mb-3 flex gap-2 overflow-x-auto pb-1">
                    {[
                        { value: 'all', label: 'All', count: ticketCounts.all },
                        { value: 'progress', label: 'In Progress', count: ticketCounts.progress },
                        { value: 'closed', label: 'Closed', count: ticketCounts.closed, activeBg: '#22c55e' },
                    ].map((tab) => {
                        const selected = tabDetails === tab.value;

                        return (
                            <button
                                key={tab.value}
                                type="button"
                                onClick={() => setTabDetails(tab.value)}
                                className="min-h-10 shrink-0 rounded-full px-4 py-2 text-[0.75rem] font-semibold sm:min-w-[110px] sm:text-[0.8125rem]"
                                style={{
                                    color: selected ? '#fff' : '#6b7280',
                                    backgroundColor: selected ? (tab.activeBg || BRAND_PRIMARY) : 'rgba(145, 158, 171, 0.08)',
                                }}
                            >
                                <TabLabel label={tab.label} count={tab.count} />
                            </button>
                        );
                    })}
                </div>

                {/* Ticket List */}
                <div className="space-y-2 sm:space-y-2">
                    {loading ? (
                        // Loading Skeleton
                        [...Array(3)].map((_, i) => <TicketCardSkeleton key={i} />)
                    ) : !cases.length && filteredTickets.length === 0 ? (
                        // Empty State
                        <div className="rounded-lg bg-white px-2 py-6 text-center shadow-sm sm:py-8">
                            <div className="mx-auto mb-1.5 flex h-12 w-12 items-center justify-center rounded-full bg-[rgba(145,158,171,0.08)]">
                                <LucideIcon name="FileText" size={24} />

                            </div>
                            <p className="mb-0.5 text-sm font-semibold text-gray-500">
                                No tickets found
                            </p>
                            <p className="text-xs text-gray-400">
                                {tabDetails === 'all'
                                    ? "You don't have any tickets yet"
                                    : `No ${tabDetails === 'progress' ? 'in progress' : 'closed'} tickets`}
                            </p>
                        </div>
                    ) : (
                        // Ticket Cards
                        <>
                            {tabDetails === "all" && cases.length > 0 && (
                                cases.map((ticket) => (
                                    <CaseCard
                                        key={ticket.id}
                                        ticket={ticket}
                                        onClick={() => navigate(`/tickets/${ticket.caseNumber}`, {
                                            state: { isCase: true, data: ticket }
                                        })}
                                    />
                                ))
                            )}
                            {filteredTickets.map((ticket) => (
                                <TicketCard
                                    key={ticket.id}
                                    ticket={ticket}
                                    onClick={() => navigate(`/tickets/${ticket.id}`)}
                                />
                            ))}
                        </>
                    )}

                    {tickets.length > 0 && filteredTickets.length > 0 && (
                        <p className="block pb-2 pt-1 text-center text-xs text-gray-400">
                            That's all the tickets
                        </p>
                    )}
                </div>
                {/* Add Ticket Modal */}
                <AddTicketModal
                    onSuccess={onSuccess}
                    open={openAddTicket}
                    onClose={addTicketClose} />
                <CompleteProfileModal {...completeProfileModalProps} />

                <Outlet />
            </div>
        </DashboardContent>
    );
}
