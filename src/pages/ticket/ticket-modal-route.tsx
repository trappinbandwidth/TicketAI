import { useState, useMemo, useCallback } from 'react';
import { useAtom } from 'jotai';
import { useLocation, useParams } from 'react-router-dom';

import LucideIcon from 'src/components/lucide-icon';
import { ticketStatusConfig } from 'src/store';
import { fDate } from 'src/utils/format-time';
import { TicketStatusConfigItem, S3Document, DriverTicketItem, CasesItem } from 'src/common-service/types.interface';
import { useRouter } from 'src/routes/hooks';
import { Button, Card, Modal, ModalContent } from 'src/components/ui';
import TicketPaymentModal from './TicketPaymentModal';
import { TICKET_STATUSES_ICON } from 'src/membership-config';
import { useDriverTicketDetailQuery } from 'src/queries/use-ticket-detail-query';
import { useTicketDocumentsQuery } from 'src/queries/use-ticket-documents-query';
import { cn } from 'src/lib/utils';

const getStepIcon = (label: string): string => {
  const normalized = label.toLowerCase();
  if (normalized.includes('received')) return 'FileText';
  if (normalized.includes('sent') || normalized.includes('processing')) return 'Clock';
  if (normalized.includes('attorney') || normalized.includes('attny') || normalized.includes('assigned')) return 'UserCheck';
  if (normalized.includes('agreement') || normalized.includes('progress')) return 'FileCheck';
  if (normalized.includes('closed') || normalized.includes('complete')) return 'CircleCheck';
  return 'Info';
};

function ProgressStep({
  label,
  isCompleted,
  isActive,
  isLast,
}: {
  label: string;
  isCompleted: boolean;
  isActive: boolean;
  isLast: boolean;
}) {
  return (
    <div className={cn('flex items-start', !isLast && 'flex-1')}>
      <div className="flex w-11 flex-col items-center">
        <div
          className={cn(
            'flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 transition-all',
            isCompleted ? 'border-[#1a365d] bg-[#1a365d] text-white' : isActive ? 'border-[#1a365d] bg-white text-[#1a365d]' : 'border-slate-300 bg-white text-slate-400'
          )}
        >
          {isCompleted || isActive ? <LucideIcon name={getStepIcon(label) as never} size={16} /> : <LucideIcon name="Circle" size={16} />}
        </div>
        <p
          className={cn(
            'mt-1 w-11 text-center text-[0.55rem] leading-[1.15]',
            isCompleted || isActive ? 'text-[#1a365d]' : 'text-slate-400',
            isActive && 'font-semibold'
          )}
          style={{
            overflow: 'hidden',
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
          }}
        >
          {label}
        </p>
      </div>
      {!isLast ? <div className={cn('mt-[15px] h-0.5 min-w-3 flex-1 rounded-full', isCompleted ? 'bg-[#1a365d]' : 'bg-slate-200')} /> : null}
    </div>
  );
}

function DetailRow({
  icon,
  label,
  value,
  valueClassName,
}: {
  icon: string;
  label: string;
  value: string;
  valueClassName?: string;
}) {
  return (
    <div className="flex items-start gap-3">
      <LucideIcon name={icon as never} size={18} color="#9e9e9e" style={{ marginTop: 2, flexShrink: 0 }} />
      <div className="min-w-0">
        <p className="block text-xs leading-tight text-slate-400">{label}</p>
        <p className={cn('text-sm font-medium leading-6 text-slate-900 whitespace-pre-wrap [overflow-wrap:anywhere]', valueClassName)}>{value}</p>
      </div>
    </div>
  );
}

function TicketCardSkeleton() {
  return (
    <div className="space-y-4 px-4 py-5 sm:px-6">
      <div className="flex items-center gap-3">
        <div className="h-8 w-8 animate-pulse rounded-full bg-slate-200" />
        <div className="flex-1 space-y-2">
          <div className="h-5 w-1/2 animate-pulse rounded bg-slate-200" />
          <div className="h-3 w-1/3 animate-pulse rounded bg-slate-200" />
        </div>
      </div>
      <div className="h-14 animate-pulse rounded-2xl bg-slate-200" />
      <div className="h-52 animate-pulse rounded-2xl bg-slate-200" />
      <div className="h-16 animate-pulse rounded-2xl bg-slate-200" />
      <div className="h-16 animate-pulse rounded-2xl bg-slate-200" />
    </div>
  );
}

export default function TicketDetailPage() {
  const { id: ticketId } = useParams();
  const route = useRouter();
  const location = useLocation();
  const state = location.state as { isCase: boolean; data: CasesItem } | undefined;

  const ticketQuery = useDriverTicketDetailQuery(state?.isCase ? '' : ticketId);
  const ticket = ticketQuery.data as DriverTicketItem | undefined;
  const loading = ticketQuery.isLoading || ticketQuery.isFetching;
  const [statusData] = useAtom(ticketStatusConfig) as [TicketStatusConfigItem[], unknown];

  const [selectedDocument, setSelectedDocument] = useState<S3Document | null>(null);
  const [documentViewerOpen, setDocumentViewerOpen] = useState(false);
  const [attorneyExpanded, setAttorneyExpanded] = useState(false);
  const [activityExpanded, setActivityExpanded] = useState(false);
  const [paymentModalOpen, setPaymentModalOpen] = useState(false);

  const ticketName = state?.isCase ? `Cases/${state.data?.caseNumber}/` : `Tickets/${ticket?.name}/`;
  const documentsQuery = useTicketDocumentsQuery(ticketName);
  const documents = (documentsQuery.data || []) as S3Document[];
  const documentsLoading = documentsQuery.isLoading || documentsQuery.isFetching;

  const getFileExtension = useCallback((filename: string): string => filename.split('.').pop()?.toLowerCase() || '', []);

  const isImageFile = useCallback(
    (filename: string): boolean => ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg'].includes(getFileExtension(filename)),
    [getFileExtension]
  );

  const isPdfFile = useCallback((filename: string): boolean => getFileExtension(filename) === 'pdf', [getFileExtension]);

  const getFileTypeLabel = useCallback(
    (filename: string): string => {
      const ext = getFileExtension(filename);
      const typeMap: Record<string, string> = {
        pdf: 'PDF',
        doc: 'DOC',
        docx: 'DOCX',
        xls: 'XLS',
        xlsx: 'XLSX',
        jpg: 'JPG',
        jpeg: 'JPEG',
        png: 'PNG',
        gif: 'GIF',
        webp: 'WEBP',
        txt: 'TXT',
        csv: 'CSV',
      };
      return typeMap[ext] || ext.toUpperCase();
    },
    [getFileExtension]
  );

  const formatLastModified = useCallback((dateString: string): string => {
    try {
      return fDate(dateString);
    } catch {
      return dateString;
    }
  }, []);

  const handleViewDocument = useCallback((doc: S3Document) => {
    setSelectedDocument(doc);
    setDocumentViewerOpen(true);
  }, []);

  const handleDownloadDocument = useCallback((doc: S3Document) => {
    window.open(doc.url, '_blank');
  }, []);

  const handleBack = useCallback(() => {
    route.back();
  }, [route]);

  const currentStatus = useMemo(() => ticket?.ticketStatus || '', [ticket]);

  const activeStep = useMemo(() => {
    if (!statusData.length) return 0;

    let step = statusData.findIndex(
      (status) =>
        status.rawValues?.some((value: { value: string }) => value.value.toLowerCase() === currentStatus.toLowerCase()) ||
        status.label?.toLowerCase() === currentStatus.toLowerCase()
    );

    if (step === -1) {
      step = statusData.findIndex(
        (status) =>
          currentStatus.toLowerCase().includes(status.rawValues?.map((value: { value: string }) => value.value.toLowerCase()).join('|')) ||
          currentStatus.toLowerCase().includes(status.label?.toLowerCase())
      );
    }

    return step === -1 ? 0 : step;
  }, [statusData, currentStatus]);

  const statusColor = useMemo(() => {
    const status = currentStatus.toLowerCase();
    if (status.includes('closed') || status.includes('complete')) {
      return { bg: 'bg-green-100', color: 'text-green-600' };
    }
    if (status.includes('court')) {
      return { bg: 'bg-[rgba(242,174,38,0.12)]', color: 'text-[#F2AE26]' };
    }
    return { bg: 'bg-[rgba(26,54,93,0.08)]', color: 'text-[#1a365d]' };
  }, [currentStatus]);

  const progressSteps = useMemo(() => statusData.filter((status) => status.inPath), [statusData]);

  const handleContactSupport = useCallback(() => {
    window.location.href =
      'mailto:support@rigresolve.com?subject=Support%20Request%20for%20Ticket%20' +
      encodeURIComponent(ticket?.stateCodeCitation || ticket?.name || '') +
      '&body=' +
      encodeURIComponent(ticket?.name ? `I need support regarding my ticket: ${ticket.name}` : 'I need support regarding my ticket.');
  }, [ticket]);

  if (loading) {
    return <TicketCardSkeleton />;
  }

  if (!ticket && !state?.isCase) {
    return (
      <div className="min-h-full px-4 py-5 sm:px-6">
        <div className="mb-4 flex items-center gap-3">
          <button type="button" onClick={handleBack} className="rounded-full p-2 transition hover:bg-slate-100">
            <LucideIcon name="ArrowLeft" size={20} />
          </button>
          <p className="text-base font-semibold">Ticket Details</p>
        </div>
        <Card className="rounded-2xl p-6 text-center shadow-sm">
          <LucideIcon name="TriangleAlert" size={48} color="#9e9e9e" style={{ marginBottom: 8, display: 'inline-block' }} />
          <p className="text-sm text-slate-500">Ticket not found</p>
          <Button type="button" onClick={handleBack} variant="secondary" className="mt-4 border border-slate-200 bg-white text-slate-700">
            Go Back
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="mvp-page-shell max-w-[860px] min-h-full px-4 py-5 sm:px-6">
      <div className="mvp-section-card mb-4 overflow-hidden rounded-[28px] border border-slate-200 shadow-[0_14px_32px_rgba(15,23,42,0.06)]">
        <div className="bg-[linear-gradient(180deg,rgba(248,250,252,0.96),rgba(255,255,255,0.98))] px-4 py-4 sm:px-5">
          <div className="mb-3 flex items-center gap-3">
            <button
              type="button"
              onClick={handleBack}
              className="rounded-full bg-slate-100 p-2 transition hover:bg-slate-200"
            >
              <LucideIcon name="ArrowLeft" size={20} />
            </button>
            <div className="min-w-0 flex-1">
              <p className="mb-1 text-[0.7rem] font-semibold uppercase tracking-[0.24em] text-[#0d3e6b]/55">Case Tracking</p>
              <h1 className="truncate text-base font-bold text-[#1a365d] sm:text-lg">{state?.isCase ? 'Case Details' : 'Ticket Details'}</h1>
              <p className="text-xs text-slate-500">{state?.isCase ? state.data?.caseNumber : ticket?.stateCodeCitation}</p>
            </div>
          </div>

          {!state?.isCase && <div className="flex items-center gap-2">
            {currentStatus && TICKET_STATUSES_ICON[currentStatus as keyof typeof TICKET_STATUSES_ICON] ? (
              <img width={20} height={20} loading="lazy" src={TICKET_STATUSES_ICON[currentStatus as keyof typeof TICKET_STATUSES_ICON]} alt={currentStatus} />
            ) : null}
            <span
              className={cn(
                'inline-flex h-7 items-center rounded-full px-3 text-xs font-semibold',
                currentStatus?.toLowerCase() === 'ticket closed' && ticket?.ticketOutcome ? `${statusColor.bg} ${statusColor.color}` : 'border border-[oklch(88.2%_.059_254.128)] bg-[oklch(97%_.014_254.604)] text-[#0d3e6b]'
              )}
            >
              {currentStatus?.toLowerCase() === 'ticket closed' && ticket?.ticketOutcome ? 'Closed' : currentStatus}
            </span>
          </div>}
        </div>
      </div>

      {currentStatus?.toLowerCase() === 'ticket closed' && ticket?.ticketOutcome ? (
        <div className="mb-4 rounded-2xl border-2 border-green-300 bg-[linear-gradient(to_bottom_right,#f0fdf4,#ecfdf5)] p-4 shadow-sm">
          <div className="flex items-start gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-green-500">
              <LucideIcon name="CircleCheckBig" size={28} color="#ffffff" />
            </div>
            <div className="flex-1">
              <p className="mb-1 text-sm font-medium text-green-700">Case Outcome</p>
              <p className="text-lg font-semibold text-green-900">{state?.isCase ? '' : ticket?.ticketOutcome}</p>
            </div>
          </div>
        </div>
      ) : null}

      {progressSteps.length > 0 ? (
        <Card className="mb-4 rounded-[28px] p-4 shadow-[0_14px_32px_rgba(15,23,42,0.06)]">
          <div
            className="flex items-start overflow-x-auto overflow-y-hidden pb-1"
            style={{ scrollbarWidth: 'none', msOverflowStyle: 'none', WebkitOverflowScrolling: 'touch' }}
          >
            {progressSteps.map((step, index) => (
              <ProgressStep
                key={`${step.displayOrder}-${step.label}-${step.rawValues?.map((value) => value.value).join('-') || index}`}
                label={step.label}
                isCompleted={index < activeStep}
                isActive={index === activeStep}
                isLast={index === progressSteps.length - 1}
              />
            ))}
          </div>
        </Card>
      ) : null}

      {ticket?.actionRequired && ticket?.actions?.payment && ticket?.actions.payment.items.length > 0 ? (
        <Card className="mb-4 overflow-hidden rounded-[28px] border-2 border-red-200 bg-red-50 shadow-[0_14px_32px_rgba(239,68,68,0.08)]">
          <div className="h-1 bg-red-600" />
          <div className="p-4 sm:p-5">
            <div className="flex items-start gap-4">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-red-100">
                <LucideIcon name="TriangleAlert" size={22} color="#dc2626" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="mb-1 text-sm font-bold text-red-600">{ticket?.actions.payment.label || 'Payment Required'}</p>
                <p className="mb-4 text-sm text-slate-500">Action needed to proceed with your case. Please complete the payment below.</p>

                <div className="mb-4 space-y-2">
                  {ticket?.actions.payment.items.map((item) => (
                    <div key={item.transactionId} className="rounded-xl border border-red-200 bg-white p-3">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold text-[#1a365d]">{item.reason}</p>
                          <p className="text-xs text-slate-500">Due: {fDate(item.dueDate)}</p>
                        </div>
                        <p className="text-lg font-bold text-[#1a365d]">${item.payNow.toFixed(2)}</p>
                      </div>
                    </div>
                  ))}
                </div>

                <button
                  type="button"
                  onClick={() => setPaymentModalOpen(true)}
                  className="flex w-full items-center justify-center gap-2 rounded-2xl bg-red-600 py-3 text-sm font-semibold text-white transition hover:bg-red-700"
                >
                  <LucideIcon name="Wallet" size={18} />
                  Make Payment
                </button>
              </div>
            </div>
          </div>
        </Card>
      ) : null}

      <Card className="mb-4 rounded-[28px] bg-slate-50 p-4 shadow-[0_14px_32px_rgba(15,23,42,0.05)] sm:p-5">
        <p className="mb-4 text-sm font-semibold text-[#1a365d]">Violation Details</p>
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <DetailRow icon="FileText" label="Type" value={ticket?.violationCategory || '-'} />
            <DetailRow icon="MapPin" label="Location" value={ticket?.violationLocation || '-'} />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <DetailRow
              icon="FileText"
              label="Description"
              value={state?.isCase ? state.data.description : ticket?.violationDescription || '-'}
              valueClassName="max-h-72 overflow-y-auto pr-2"
            />
            <DetailRow icon="Building2" label="Court" value={ticket?.courtName || '-'} />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <DetailRow icon="Calendar" label="Court Date" value={ticket?.courtDate ? fDate(ticket?.courtDate) : 'Pending'} />
            <DetailRow icon="CalendarDays" label="Date Issued" value={state?.isCase ? state.data.createdDate ? fDate(state.data.createdDate) : '-' : ticket?.createdDate ? fDate(ticket?.createdDate) : '-'} />
          </div>
        </div>
      </Card>

      <Card className="mb-3 rounded-[28px] p-4 shadow-[0_14px_32px_rgba(15,23,42,0.05)] sm:p-5">
        <button
          type="button"
          onClick={() => setAttorneyExpanded((current) => !current)}
          className="flex w-full items-center justify-between text-left"
        >
          <div className="flex items-center gap-2">
            <LucideIcon name="IdCard" size={18} color="#6b7280" />
            <span className="text-sm font-semibold">Your Attorney</span>
            {!ticket?.attorney ? <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[0.65rem] text-amber-700">Pending</span> : null}
          </div>
          <LucideIcon name={attorneyExpanded ? 'ChevronUp' : 'ChevronDown'} size={18} color="#9e9e9e" />
        </button>
        {attorneyExpanded ? (
          ticket?.attorney ? (
            <div className="mt-4">
              <p className="text-sm font-semibold">{ticket?.attorney.name || 'Assigned Attorney'}</p>
              <p className="mb-4 text-xs text-slate-500">Rig Resolve Group</p>
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <div className="flex h-7 w-7 items-center justify-center rounded-full bg-[#1a365d]">
                    <LucideIcon name="Mail" size={14} color="white" />
                  </div>
                  <p className="text-xs">{ticket?.attorney.email || 'support@rigresolve.com'}</p>
                </div>
                <div className="flex items-center gap-3">
                  <div className="flex h-7 w-7 items-center justify-center rounded-full bg-[#1a365d]">
                    <LucideIcon name="PhoneCall" size={14} color="white" />
                  </div>
                  <p className="text-xs">{ticket?.attorney.phone || '(913) 361-1575'}</p>
                </div>
              </div>
            </div>
          ) : (
            <p className="mt-3 text-xs text-slate-500">An attorney will be assigned to your case soon.</p>
          )
        ) : null}
      </Card>

      <Card className="mb-4 rounded-[28px] p-4 shadow-[0_14px_32px_rgba(15,23,42,0.05)] sm:p-5">
        <button
          type="button"
          onClick={() => setActivityExpanded((current) => !current)}
          className="flex w-full items-center justify-between text-left"
        >
          <div className="flex items-center gap-2">
            <LucideIcon name="Clock" size={18} color="#6b7280" />
            <span className="text-sm font-semibold">Activity & Updates</span>
            <span className="flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-slate-200 px-1 text-[0.65rem] text-slate-500">0</span>
          </div>
          <LucideIcon name={activityExpanded ? 'ChevronUp' : 'ChevronDown'} size={18} color="#9e9e9e" />
        </button>
        {activityExpanded ? <p className="mt-3 text-xs text-slate-500">No updates yet. Check back later for activity on your ticket.</p> : null}
      </Card>

      <div className="mb-4">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <LucideIcon name="FileText" size={18} color="#6b7280" />
            <span className="text-sm font-semibold">Documents</span>
            {documents.length > 0 ? (
              <span className="flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-blue-100 px-1 text-[0.65rem] text-blue-700">
                {documents.length}
              </span>
            ) : null}
          </div>
        </div>

        {documentsLoading ? (
          <Card className="rounded-[28px] p-6 text-center shadow-[0_14px_32px_rgba(15,23,42,0.05)]">
            <div className="mb-2 flex justify-center">
              <span className="h-6 w-6 animate-spin rounded-full border-2 border-slate-300 border-t-[#1a365d]" />
            </div>
            <p className="text-xs text-slate-500">Loading documents...</p>
          </Card>
        ) : null}

        {!documentsLoading && documents.length > 0 ? (
          <div className="space-y-3">
            {documents.map((doc, index) => (
              <Card key={`${doc.name}-${index}`} className="rounded-[28px] p-4 shadow-[0_14px_32px_rgba(15,23,42,0.05)] sm:p-5">
                <div className="flex items-center gap-4">
                  <div
                    className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl"
                    style={{
                      backgroundColor: isImageFile(doc.name) ? 'rgba(76,175,80,0.12)' : isPdfFile(doc.name) ? 'rgba(244,67,54,0.12)' : 'rgba(26,54,93,0.12)',
                    }}
                  >
                    <LucideIcon
                      name={isImageFile(doc.name) ? 'Image' : isPdfFile(doc.name) ? 'FileText' : 'File'}
                      size={22}
                      color={isImageFile(doc.name) ? '#4caf50' : isPdfFile(doc.name) ? '#f44336' : '#1a365d'}
                    />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-slate-900">{doc.name}</p>
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
                      <span
                        className="rounded-full px-2 py-0.5 font-bold"
                        style={{
                          backgroundColor: isImageFile(doc.name) ? '#dcfce7' : isPdfFile(doc.name) ? '#fee2e2' : '#dbeafe',
                          color: isImageFile(doc.name) ? '#166534' : isPdfFile(doc.name) ? '#991b1b' : '#1d4ed8',
                        }}
                      >
                        {getFileTypeLabel(doc.name)}
                      </span>
                      <span className="text-slate-500">{doc.size}</span>
                      <span className="text-slate-400">•</span>
                      <span className="text-slate-500">{formatLastModified(doc.lastModified)}</span>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => handleViewDocument(doc)}
                      className="rounded-full bg-slate-100 p-2 transition hover:bg-blue-100"
                    >
                      <LucideIcon name="Eye" size={16} />
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDownloadDocument(doc)}
                      className="rounded-full bg-slate-100 p-2 transition hover:bg-green-100"
                    >
                      <LucideIcon name="Download" size={16} />
                    </button>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        ) : null}

        {!documentsLoading && documents.length === 0 ? (
          <Card className="rounded-[28px] bg-slate-50 p-6 text-center shadow-[0_14px_32px_rgba(15,23,42,0.05)]">
            <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-slate-200">
              <LucideIcon name="FolderOpen" size={24} color="#9e9e9e" />
            </div>
            <p className="text-sm font-medium text-slate-500">No documents available</p>
            <p className="mt-1 text-xs text-slate-400">Documents will appear here once uploaded</p>
          </Card>
        ) : null}
      </div>

      <div className="pb-2">
        <Button
          type="button"
          fullWidth
          variant="secondary"
          onClick={handleContactSupport}
          className="gap-2 rounded-2xl border border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
        >
          <LucideIcon name="Mail" size={18} />
          Contact Support
        </Button>
      </div>

      {ticket?.actionRequired && ticket?.actions?.payment && ticket?.actions.payment.items.length > 0 ? (
        <TicketPaymentModal
          open={paymentModalOpen}
          onClose={() => setPaymentModalOpen(false)}
          paymentItems={ticket?.actions.payment.items}
          ticketId={ticket?.id}
          ticketName={ticket?.stateCodeCitation}
          onPaymentComplete={() => {
            setPaymentModalOpen(false);
            ticketQuery.refetch();
            documentsQuery.refetch();
          }}
        />
      ) : null}

      <Modal open={documentViewerOpen} onOpenChange={(nextOpen) => !nextOpen && setDocumentViewerOpen(false)}>
        <ModalContent hideCloseButton className="mvp-modal-shell w-[calc(100%-1rem)] max-w-6xl p-0 sm:w-[calc(100%-2rem)]">
          {selectedDocument ? (
            <>
              <div className="flex items-center justify-between bg-[#1a365d] px-5 py-4">
                <div className="mr-4 min-w-0 flex-1">
                  <h2 className="truncate text-base font-semibold text-white">{selectedDocument.name}</h2>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-white/70">
                    <span>{getFileTypeLabel(selectedDocument.name)}</span>
                    <span className="text-white/50">•</span>
                    <span>{selectedDocument.size}</span>
                    <span className="text-white/50">•</span>
                    <span>{formatLastModified(selectedDocument.lastModified)}</span>
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => handleDownloadDocument(selectedDocument)}
                    className="rounded-full p-2 text-white transition hover:bg-white/10"
                  >
                    <LucideIcon name="Download" size={20} />
                  </button>
                  <button
                    type="button"
                    onClick={() => setDocumentViewerOpen(false)}
                    className="rounded-full p-2 text-white transition hover:bg-white/10"
                  >
                    <LucideIcon name="CircleX" size={20} />
                  </button>
                </div>
              </div>

              <div className="flex min-h-[50vh] items-center justify-center bg-[radial-gradient(circle_at_top,rgba(255,255,255,0.8),rgba(226,232,240,0.75))] p-4 sm:p-6">
                {isImageFile(selectedDocument.name) ? (
                  <img
                    src={selectedDocument.url}
                    alt={selectedDocument.name}
                    className="block max-h-[70vh] max-w-full rounded-[24px] bg-white object-contain shadow-[0_20px_40px_rgba(15,23,42,0.12)]"
                    onError={(event) => {
                      (event.currentTarget as HTMLImageElement).style.display = 'none';
                    }}
                  />
                ) : isPdfFile(selectedDocument.name) ? (
                  <iframe src={selectedDocument.url} className="h-[70vh] w-full rounded-[24px] border-0 bg-white shadow-[0_20px_40px_rgba(15,23,42,0.12)]" title={selectedDocument.name} />
                ) : (
                  <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
                    <div className="mb-4 flex h-20 w-20 items-center justify-center rounded-full bg-slate-200">
                      <LucideIcon name="File" size={40} color="#6b7280" />
                    </div>
                    <p className="mb-2 text-base font-semibold text-slate-900">Preview not available</p>
                    <p className="mb-6 max-w-[300px] text-sm text-slate-500">
                      This file type cannot be previewed in the browser. Click download to view the file.
                    </p>
                    <Button type="button" onClick={() => handleDownloadDocument(selectedDocument)} className="gap-2">
                      <LucideIcon name="Download" size={18} />
                      Download File
                    </Button>
                  </div>
                )}
              </div>
            </>
          ) : null}
        </ModalContent>
      </Modal>
    </div>
  );
}
