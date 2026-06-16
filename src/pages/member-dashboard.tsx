import { useCallback, useMemo } from 'react';
import { useAtom } from 'jotai';
import { useNavigate } from 'react-router-dom';

import { driverProfile, ticketList, ticketLoading } from 'src/store';
import { CasesItem } from 'src/common-service/types.interface';
import { TICKET_STATUSES_ICON } from 'src/membership-config';
import { DashboardContent } from 'src/layouts/dashboard';
import LucideIcon from 'src/components/lucide-icon';
import CompleteProfileModal from 'src/components/shared/CompleteProfileModal';
import { fDate } from 'src/utils/format-time';
import { useProfileGuard } from 'src/hooks/use-profile-guard';

const EMPTY_STATE_COPY = {
  heading: "Nice work, you're ticket free!",
  subtext: 'Keep up the safe driving out there.',
};

type RecentTicketCard = {
  id: string;
  routeId: string;
  citationNumber: string;
  title: string;
  incidentDate: string;
  courtDate: string;
  actionRequired: boolean;
  ticketStatus: string;
  statusLabel: string;
  statusTone: string;
  statusBadgeClassName: string;
  statusIcon: string | null;
};

function formatDisplayName(firstName?: string) {
  if (!firstName) return 'Driver';
  return firstName.charAt(0).toUpperCase() + firstName.slice(1);
}

function getStatusAppearance(status?: string, actionRequired?: boolean) {
  if (actionRequired) {
    return {
      label: 'Action Required',
      tone: '#dc2626',
      badgeClassName: 'border-red-200 bg-red-50 text-[#dc2626]',
    };
  }

  if (status?.toLowerCase().includes('closed')) {
    return {
      label: status || 'Closed',
      tone: '#15803d',
      badgeClassName: 'border-green-200 bg-green-50 text-green-700',
    };
  }

  return {
    label: status || 'In Progress',
    tone: '#0D3E6B',
    badgeClassName: 'border-blue-200 bg-blue-50 text-[#0D3E6B]',
  };
}

export default function MemberDashboard() {
  const [loadingTickets] = useAtom(ticketLoading);
  const [userDetails] = useAtom(driverProfile);
  const [tickets] = useAtom(ticketList);
  const navigate = useNavigate();
  const { hasIncompleteProfile, openProfileCompletion, completeProfileModalProps } = useProfileGuard();
  const firstName = useMemo(() => formatDisplayName(userDetails?.firstName), [userDetails?.firstName]);

  const recentCases = useMemo<CasesItem[]>(() => {
    return (tickets.cases || [])
      .slice()
      .sort((left, right) => {
        const leftTime = left.createdDate ? new Date(left.createdDate).getTime() : 0;
        const rightTime = right.createdDate ? new Date(right.createdDate).getTime() : 0;
        return rightTime - leftTime;
      });
  }, [tickets.cases]);

  const membershipPlansUrl = useMemo(() => {
    const url = userDetails?.membershipInfo?.url;

    return typeof url === 'string' ? url.trim() : '';
  }, [userDetails?.membershipInfo?.url]);

  const recentTickets = useMemo<RecentTicketCard[]>(() => {
    return (tickets.tickets || []).map((ticket) => {
      const statusAppearance = getStatusAppearance(ticket.ticketStatus, ticket.actionRequired);

      return {
        id: ticket.id || '',
        routeId: ticket.id || '',
        citationNumber: ticket.stateCodeCitation || ticket.name || 'Citation',
        title: ticket.violationCategory || ticket.violationDescription || 'Citation details unavailable',
        incidentDate: ticket.createdDate ? fDate(ticket.createdDate) : 'N/A',
        courtDate: ticket.courtDate ? fDate(ticket.courtDate) : 'Not Set',
        actionRequired: Boolean(ticket.actionRequired),
        ticketStatus: ticket.ticketStatus || '',
        statusLabel: statusAppearance.label,
        statusTone: statusAppearance.tone,
        statusBadgeClassName: statusAppearance.badgeClassName,
        statusIcon: ticket.attorneyStatus
          ? TICKET_STATUSES_ICON[ticket.attorneyStatus as keyof typeof TICKET_STATUSES_ICON] || null
          : null,
      };
    });
  }, [tickets.tickets]);

  const handleTicketClick = useCallback(
    (ticket: RecentTicketCard) => {
      if (!ticket.routeId) return;
      navigate(`/tickets/${ticket.routeId}`);
    },
    [navigate]
  );

  const handleCaseClick = useCallback(
    (ticket: CasesItem) => {
      const routeId = ticket.caseNumber || ticket.id;
      if (!routeId) return;

      navigate(`/tickets/${routeId}`, {
        state: { isCase: true, data: ticket },
      });
    },
    [navigate]
  );

  return (
    <DashboardContent>
      <div className="relative lg:pb-[145px] lg:pt-9">
        <div className="mvp-page-shell lg:max-w-[1027px] lg:mx-0">
          <div className="mb-4 text-left sm:mb-6 md:mb-8 lg:mb-[19px]">
            <h1 className="mb-1 text-[1.72rem] font-medium leading-[1.08] tracking-[-0.03em] text-[#1e3a5f] sm:text-[1.9rem] md:mb-2 md:text-[2.05rem] lg:text-[22.5px] lg:leading-[33.75px] lg:tracking-normal">
              Welcome back, {firstName}
            </h1>
            <p className="text-[0.94rem] text-gray-600 sm:text-[0.98rem] lg:text-[18px] lg:leading-[27px] lg:text-[#4a5565]">Here's what's happening with your account</p>
          </div>
          {!hasIncompleteProfile && membershipPlansUrl && (
            <section
              aria-label="Membership coverage notice"
              className="mb-6 min-h-[210.448px] w-full rounded-[16px] border-[1.74px] border-[#fee685] bg-[linear-gradient(150.324deg,#fffbeb_0%,#fff7ed_100%)] px-[21.736px] pb-[21.736px] pt-[21.736px] shadow-[0_1px_3px_rgba(0,0,0,0.1),0_1px_2px_rgba(0,0,0,0.1)] lg:mb-7"
            >
              <div className="grid grid-cols-[40px_minmax(0,1fr)] items-start gap-[15.998px]">
                <div className="mt-[0.5px] flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#f2ae26]">
                  <LucideIcon name="TriangleAlert" size={20} color="#fff" className="h-5 w-5" />
                </div>

                <div className="min-w-0 pt-[0.16px]">
                  <h2 className="text-[16px] font-normal leading-6 text-[#1e3a5f] sm:whitespace-nowrap">Your Tickets Are Not Covered</h2>
                  <p className="mt-[3.998px]  text-[14px] font-normal leading-[22.75px] text-[#364153]">
                    As a non-member, you're responsible for all legal fees and court costs. Upgrade to a membership plan to get full coverage on all future tickets.
                  </p>
                  <a
                    href={membershipPlansUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-[11.987px] inline-flex h-[35.993px] max-w-[267px] items-center justify-start gap-[7.994px] rounded-[19464800px] bg-[#0d3e6b] pl-[15.998px] pr-[17px] text-[14px] font-normal leading-5 text-white transition-colors hover:bg-[#0a3154] focus:outline-none focus:ring-2 focus:ring-[#0d3e6b]/25 focus:ring-offset-2"
                  >
                    <LucideIcon name="Crown" size={16} color="#fff" className="h-4 w-4" />
                    <span>View Membership Plans</span>
                  </a>
                </div>
              </div>
            </section>
          )}
          {hasIncompleteProfile && (
            <div className="mb-6 bg-gradient-to-br from-[#E8F4F8] to-[#d4e9f2] rounded-2xl p-5 border-2 border-[#0D3E6B]/20 shadow-sm">
              <div className="flex items-start gap-4">
                <div className="w-10 h-10 bg-[#0D3E6B] rounded-full flex items-center justify-center flex-shrink-0">
                  <LucideIcon name="User" size={20} color="#fff" className="w-5 h-5" />
                </div>
                <div className="flex-1">
                  <h4 className="text-[#1e3a5f] mb-1">Complete Your Profile</h4>
                  <p className="text-gray-600 text-sm mb-3">
                    Finish setting up your account to access all features and submit tickets.
                  </p>
                  <button
                    onClick={() => openProfileCompletion('general')}
                    className="bg-[#0D3E6B] text-white px-4 py-2 rounded-full text-sm hover:bg-[#1e3a5f] transition-colors flex items-center gap-2"
                  >
                    <span>Complete Now</span>
                     <LucideIcon name="ArrowRight" className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          )}
          <section aria-labelledby="recent-citations-heading">
            <div className="mb-4 lg:mb-[18px]">
              <h2 id="recent-citations-heading" className="mb-3 text-[1.12rem] font-medium tracking-[-0.02em] text-[#1e3a5f] sm:text-[1.2rem] lg:text-[20.25px] lg:leading-[30.375px] lg:tracking-normal">
                Recent Citations
              </h2>
            </div>

            {loadingTickets ? (
              <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-2 lg:grid-cols-4 sm:gap-4 md:gap-5 lg:gap-[18px]">
                {[...Array(6)].map((_, index) => (
                  <div
                    key={index}
                    className="h-full rounded-2xl border border-gray-200 bg-white p-3 shadow-[0_10px_24px_rgba(15,23,42,0.08)] sm:p-4 md:p-6 lg:min-h-[418px] lg:rounded-[18px] lg:px-[22.5px] lg:pb-[22.5px] lg:pt-[22.5px]"
                  >
                    <div className="mb-2 flex items-center justify-between sm:mb-3 md:mb-4">
                      <div className="flex items-center gap-1.5 sm:gap-2">
                        <div className="h-4 w-4 animate-pulse rounded-full bg-slate-200 sm:h-5 sm:w-5 md:h-6 md:w-6" />
                        <div className="h-3 w-20 animate-pulse rounded bg-slate-200 sm:h-4 sm:w-24 md:w-28" />
                      </div>
                      <div className="h-4 w-4 animate-pulse rounded-full bg-slate-200 sm:h-5 sm:w-5 md:h-6 md:w-6" />
                    </div>
                    <div className="mb-2 h-5 w-4/5 animate-pulse rounded bg-slate-200 sm:mb-3 sm:h-6 md:mb-4" />
                    <div className="mb-2 space-y-1.5 sm:mb-3 sm:space-y-2 md:mb-4">
                      <div className="h-3.5 w-3/5 animate-pulse rounded bg-slate-200 sm:h-4 md:h-5" />
                      <div className="h-3.5 w-1/2 animate-pulse rounded bg-slate-200 sm:h-4 md:h-5" />
                    </div>
                    <div className="flex items-center justify-end">
                      <div className="h-6 w-20 animate-pulse rounded-full bg-slate-200 sm:h-7 sm:w-28 md:h-9 md:w-32" />
                    </div>
                  </div>
                ))}
              </div>
            ) : recentCases.length === 0 && recentTickets.length === 0 ? (
              <div className="rounded-2xl border-2 border-green-200 bg-gradient-to-br from-green-50 to-emerald-50 p-6 text-center shadow-sm">
                <div className="mb-3 inline-flex h-16 w-16 items-center justify-center rounded-full bg-green-100">
                  <LucideIcon name="CircleCheckBig" size={32} color="#16a34a" />
                </div>
                <p className="mb-2 text-[1rem] font-semibold text-green-900">{EMPTY_STATE_COPY.heading}</p>
                <p className="text-sm text-[#15803d]">{EMPTY_STATE_COPY.subtext}</p>
              </div>
            ) : (
              <div className="space-y-4 lg:space-y-5">
                {recentCases.length > 0 && (
                  <div className="space-y-2 sm:space-y-2">
                    <h3 className="text-[0.95rem] font-medium text-[#1e3a5f] sm:text-base">
                      New Cases
                    </h3>
                    {recentCases.map((ticket) => (
                      <div
                        key={ticket.id}
                        onClick={() => handleCaseClick(ticket)}
                        className="relative cursor-not-allowed overflow-visible rounded-lg border border-[#8ec5ff] bg-[#a5e5f833] shadow-sm transition-all duration-200 hover:-translate-y-px hover:shadow-lg active:translate-y-0"
                      >
                        <div className="absolute -right-[5px] -top-[5px] z-[1] flex items-center gap-0.5 rounded-full bg-[#0D3E6B] px-1 py-0.25 text-[0.61rem] font-medium text-white">
                          <LucideIcon name="TriangleAlert" size={12} />
                          Rig Resolve's experts are reviewing - You're in good hands
                        </div>
                        <div className="flex gap-1.5 p-4">
                          <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-xl text-[#1a365d]">
                            <img
                              width={20}
                              height={20}
                              src={TICKET_STATUSES_ICON['Ticket Received']}
                              alt={ticket.caseNumber}
                            />
                          </div>

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

                            <div className="mb-0.75 space-y-0.5">
                              <div className="flex items-center gap-0.5 text-[0.7rem] text-gray-500 sm:text-xs">
                                <LucideIcon name="Calendar" width={14} />
                                <span>Court: TBD</span>
                              </div>
                            </div>

                            <div className="flex justify-end">
                              <div className="whitespace-nowrap rounded-full bg-[rgba(24,144,255,0.1)] px-1.25 py-0.25 text-[10px] font-semibold text-[#637381] sm:text-[11px]">
                                Received
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {recentTickets.length > 0 && (
                  <div className="grid gap-3 sm:grid-cols-2 sm:gap-4 md:grid-cols-2 md:gap-5 lg:grid-cols-4 lg:gap-[18px]">
                    {recentTickets.map((ticket) => (
                      <article
                        key={ticket.id || ticket.citationNumber}
                        onClick={() => handleTicketClick(ticket)}
                        className="relative flex h-full cursor-pointer flex-col overflow-visible rounded-2xl border border-gray-200 bg-white p-3 transition-shadow active:scale-[0.985] hover:shadow-lg sm:p-4 md:p-6 lg:min-h-[418px] lg:rounded-[18px] lg:px-[22.5px] lg:pb-[24px] lg:pt-[22.5px]"
                      >
                        {ticket.actionRequired && (
                          <span className="absolute -right-2 -top-2 z-10 flex items-center gap-1 rounded-full bg-[rgb(236,28,36)] px-2 py-0.5 text-[10px] text-white shadow-lg sm:px-3 sm:py-1 sm:text-xs md:px-4 md:py-1.5 md:text-sm lg:left-[104.9px] lg:right-auto lg:top-[-9px] lg:h-[26.992px] lg:w-[145.352px] lg:justify-start lg:rounded-full lg:px-[13.5px] lg:py-0 lg:text-[13.5px] lg:leading-[18px]">
                            <LucideIcon name="TriangleAlert" size={12} className="lg:h-[13.5px] lg:w-[13.5px]" />
                            Action Required
                          </span>
                        )}

                        <div className="mb-2 flex items-start justify-between sm:mb-3 md:mb-4 lg:mb-0 lg:h-[22.5px]">
                          <div className="flex min-w-0 items-center gap-1.5 sm:gap-2 lg:gap-[9px]">
                            <LucideIcon name="FileText" size={20} color="#1e3a5f" className="lg:h-[22.5px] lg:w-[22.5px]" />
                            <span className="truncate text-xs text-gray-500 sm:text-sm md:text-base lg:text-[15.75px] lg:leading-[22.5px] lg:text-[#6a7282]">{ticket.citationNumber}</span>
                          </div>

                          {ticket.statusIcon ? (
                            <img
                              width={22.5}
                              height={22.5}
                              loading="lazy"
                              src={ticket.statusIcon}
                              alt={ticket.ticketStatus || ticket.statusLabel}
                              className="h-5 w-5 shrink-0 lg:h-[22.5px] lg:w-[22.5px]"
                            />
                          ) : (
                            <LucideIcon name={ticket.actionRequired ? 'TriangleAlert' : 'ShieldCheck'} size={18} color={ticket.statusTone} className="lg:h-[22.5px] lg:w-[22.5px]" />
                          )}
                        </div>

                        <h3 className="mb-2 text-sm text-[#1e3a5f] sm:text-base md:mb-3 lg:mb-0 lg:mt-[18px] lg:min-h-[54px] lg:text-[18px] lg:leading-[27px]">{ticket.title}</h3>

                        <div className="mb-2 space-y-1 text-xs text-gray-500 sm:mb-3 sm:space-y-1.5 sm:text-sm md:mb-4 md:space-y-2 md:text-base lg:mb-0 lg:mt-[13.5px] lg:min-h-[117px] lg:space-y-[9px] lg:text-[18px] lg:leading-[27px] lg:text-[#6a7282]">
                          <div className="flex items-center gap-1.5 sm:gap-2 lg:h-[54px] lg:items-start lg:gap-[9px]">
                            <LucideIcon name="Calendar" size={16} color="#6b7280" className="mt-0.5 lg:mt-0 lg:h-[18px] lg:w-[18px]" />
                            <span>Incident: {ticket.incidentDate}</span>
                          </div>
                          <div className="flex items-center gap-1.5 sm:gap-2 lg:h-[54px] lg:items-start lg:gap-[9px]">
                            <LucideIcon name="Calendar" size={16} color="#6b7280" className="mt-0.5 lg:mt-0 lg:h-[18px] lg:w-[18px]" />
                            <span>Court Date: {ticket.courtDate}</span>
                          </div>
                        </div>

                        {ticket.actionRequired ? (
                          <div className="mt-auto rounded-xl border border-red-200 bg-red-50 p-2 sm:mt-3 sm:p-3 md:mt-4 md:p-4 lg:h-[110px] lg:rounded-[15.25px] lg:border-[#ffc9c9] lg:px-[14.5px] lg:pb-px lg:pt-[14.5px]">
                            <div className="flex items-center gap-1.5 text-xs text-[#dc2626] sm:gap-2 sm:text-sm md:text-base lg:h-[81px] lg:items-start lg:gap-[9px] lg:text-[18px] lg:leading-[27px]">
                              <LucideIcon name="DollarSign" size={16} color="#dc2626" className="mt-0.5 lg:mt-0 lg:h-[18px] lg:w-[9.2px]" />
                              <span>{ticket.statusLabel}</span>
                            </div>
                          </div>
                        ) : (
                          <div className="mt-auto flex justify-end lg:h-[28.992px] lg:items-center">
                            <span className={`rounded-full border px-2 py-0.5 text-[10px] sm:px-3 sm:py-1 sm:text-xs md:px-4 md:py-1.5 md:text-sm lg:h-[28.992px] lg:px-[13.5px] lg:py-[4px] lg:text-[13.5px] lg:leading-[18px] ${ticket.statusBadgeClassName}`}>
                              {ticket.statusLabel}
                            </span>
                          </div>
                        )}
                      </article>
                    ))}
                  </div>
                )}
              </div>
            )}
          </section>
          <CompleteProfileModal {...completeProfileModalProps} />
        </div>
      </div>
    </DashboardContent>
  );
}
