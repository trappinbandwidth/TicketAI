import { useCallback, useMemo, useState, memo } from 'react';
import { useForm } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import * as Yup from 'yup';
import { useAtom } from 'jotai';

import LucideIcon from 'src/components/lucide-icon';
import { Button, Modal, ModalContent } from 'src/components/ui';
import { toasterService } from 'src/apiSetUp';
import { FormProvider, RHFDropzone, RHFTextField } from 'src/hook-form';
import { driverProfile, firebaseUid, isLoading } from 'src/store';
import { uploadTicketFiles, type UploadProgress } from 'src/services/firebase-storage';
import { createTicketDoc } from 'src/services/firestore';
import { submitToAiEngine } from 'src/services/ai-engine';

interface AddTicketModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

interface TicketFormData {
  description: string;
  files: File[];
}

type StepType = 'form' | 'success';

const MEMBERSHIP_BENEFITS = [
  'Full legal representation included',
  'No out-of-pocket legal fees',
  '24/7 support from experienced attorneys',
  'Referral rewards and earning opportunities',
];

const ticketSchema = Yup.object().shape({
  description: Yup.string()
    .required('Please describe your ticket')
    .min(10, 'Description must be at least 10 characters'),
  files: Yup.array().of(Yup.mixed()).min(1, 'At least one document is required').required('Please upload at least one document'),
});

const MembershipCoverageCard = memo(
  ({ membershipPlansUrl, onOpenMembershipPlans }: { membershipPlansUrl: string; onOpenMembershipPlans: () => void }) => (
    <section className="rounded-[20px] border-[1.74px] border-[#fee685] bg-[linear-gradient(150.324deg,#fffbeb_0%,#fff7ed_100%)] px-[21.736px] pb-[21.736px] pt-[21.736px] shadow-[0_1px_3px_rgba(0,0,0,0.1),0_1px_2px_rgba(0,0,0,0.1)]">
      <div className="grid grid-cols-[40px_minmax(0,1fr)] items-start gap-[15.998px]">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#f2ae26]">
          <LucideIcon name="TriangleAlert" size={20} color="#ffffff" className="h-5 w-5" />
        </div>

        <div className="min-w-0">
          <h3 className="text-[16px] font-normal leading-6 text-[#1e3a5f]">This Ticket Is Not Covered</h3>
          <p className="mt-[23.992px] text-[14px] font-normal leading-[22.75px] text-[#364153]">
            As a non-member, you'll be responsible for all legal fees and court costs for this ticket. Sign up for a membership to get full coverage on all future tickets.
          </p>

          <div className="mt-[23.992px]">
            <p className="text-[18px] font-normal leading-[27px] text-[#1e3a5f]">Membership Benefits:</p>
            <div className="mt-[11.992px] space-y-[7.994px]">
              {MEMBERSHIP_BENEFITS.map((benefit) => (
                <div key={benefit} className="flex items-start gap-[7.994px]">
                  <LucideIcon name="CircleCheck" size={18} color="#00a63e" className="mt-[1px] h-[18px] w-[18px] shrink-0" />
                  <p className="text-[14px] font-normal leading-[22.75px] text-[#364153]">{benefit}</p>
                </div>
              ))}
            </div>
          </div>

          <button
            type="button"
            onClick={onOpenMembershipPlans}
            disabled={!membershipPlansUrl}
            className="mt-[23.992px] inline-flex h-[45.985px] w-full items-center justify-center gap-[7.994px] rounded-[19464800px] bg-[#0d3e6b] px-[19.995px] text-[14px] font-normal leading-5 text-white transition-colors hover:bg-[#0a3154] disabled:cursor-not-allowed disabled:bg-slate-400"
          >
            <span>Sign Up for Membership</span>
            <LucideIcon name="ChevronRight" size={16} color="#ffffff" className="h-4 w-4" />
          </button>
        </div>
      </div>
    </section>
  )
);

MembershipCoverageCard.displayName = 'MembershipCoverageCard';

const SuccessStep = memo(
  ({
    membershipPlansUrl,
    onClose,
    onOpenMembershipPlans,
  }: {
    membershipPlansUrl: string;
    onClose: () => void;
    onOpenMembershipPlans: () => void;
  }) => (
    <div>
      <div className="rounded-t-[24px] bg-[#0d4679] px-6 pb-8 pt-7 text-center sm:px-8">
        <div className="mx-auto flex h-[64px] w-[64px] items-center justify-center rounded-full bg-white">
          <LucideIcon name="CircleCheckBig" size={30} color="#0d4679" />
        </div>
        <h2 className="mt-5 text-[22px] font-normal leading-[33px] text-white">Ticket Submitted</h2>
        <p className="mt-1 text-[16px] font-normal leading-6 text-white/90">We've received your submission</p>
      </div>

      <div className="px-6 pb-6 pt-6 sm:px-8 sm:pb-8">
        {membershipPlansUrl && (
          <section className="rounded-[16px] border-[1.74px] border-[#fee685] bg-[linear-gradient(150.324deg,#fffbeb_0%,#fffdf7_100%)] px-[21.736px] pb-[21.736px] pt-[21.736px] shadow-[0_1px_3px_rgba(0,0,0,0.1),0_1px_2px_rgba(0,0,0,0.1)]">
            <div className="grid grid-cols-[24px_minmax(0,1fr)] items-start gap-[15.998px]">
              <div className="flex h-6 w-6 items-center justify-center">
                <LucideIcon name="TriangleAlert" size={22} color="#f59e0b" className="h-[22px] w-[22px]" />
              </div>
              <div>
                <h3 className="text-[16px] font-normal leading-6 text-[#1e3a5f]">This Ticket Is Not Covered</h3>
                <p className="mt-4  text-[14px] font-normal leading-[22.75px] text-[#364153]">
                  As a non-member, you will be responsible for all legal fees and court costs associated with this ticket.
                </p>
              </div>
            </div>
          </section>
        )}

        <section className={`${membershipPlansUrl ? 'mt-6' : ''} rounded-[16px] border border-[#d8e0ea] bg-[#f8fafc] px-5 pb-5 pt-5 shadow-[0_1px_2px_rgba(15,23,42,0.04)]`}>
          <div className="flex items-center gap-3 text-[#1e3a5f]">
            <LucideIcon name="FileText" size={22} color="#0d4679" className="h-[22px] w-[22px]" />
            <h3 className="text-[16px] font-normal leading-6">What happens next:</h3>
          </div>

          <div className="mt-5 space-y-5">
            {[
              {
                title: 'Our ticket team will review your submission',
                subtitle: 'Usually within 24-48 hours',
              },
              {
                title: 'A team member will contact you to discuss your options',
                subtitle: "We'll explain your legal options and associated costs",
              },
              {
                title: "You'll decide how you'd like to proceed",
                subtitle: 'Our team is here to help guide you through the process',
              },
            ].map((item, index) => (
              <div key={item.title} className="flex items-start gap-3">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#0d4679] text-[15px] font-normal leading-5 text-white">
                  {index + 1}
                </div>
                <div className="pt-[1px]">
                  <p className="text-[16px] font-normal leading-[24px] text-[#1e3a5f]">{item.title}</p>
                  <p className="mt-1 text-[14px] font-normal leading-[21px] text-[#6a7282]">{item.subtitle}</p>
                </div>
              </div>
            ))}
          </div>
        </section>

        {membershipPlansUrl && (
          <section className="mt-6 rounded-[16px] border border-[#c9ddea] bg-[#eaf5fb] px-4 pb-4 pt-4">
            <h3 className="text-[16px] font-semibold leading-6 text-[#1e3a5f]">Want coverage for future tickets?</h3>
            <p className="mt-2 text-[14px] font-normal leading-[22.75px] text-[#364153]">
              Sign up for a membership to get full legal representation on all future tickets with no out-of-pocket fees.
            </p>
            <button
              type="button"
              onClick={onOpenMembershipPlans}
              className="mt-4 inline-flex items-center gap-2 text-[14px] font-normal leading-5 text-[#0d4679] transition-colors hover:text-[#0a3154]"
            >
              <LucideIcon name="Crown" size={16} color="#0d4679" className="h-4 w-4" />
              <span>Learn about membership plans</span>
            </button>
          </section>
        )}

        <Button type="button" fullWidth onClick={onClose} className="mt-6 h-[45.985px] rounded-[14px] bg-[#0d4679] text-[14px] font-normal text-white hover:bg-[#0a3154]">
          Back to Tickets
        </Button>
      </div>
    </div>
  )
);

SuccessStep.displayName = 'SuccessStep';

const AddTicketModal = memo(({ open, onClose, onSuccess }: AddTicketModalProps) => {
  const [step, setStep] = useState<StepType>('form');
  const [profileData] = useAtom(driverProfile);
  const [fbUid] = useAtom(firebaseUid);
  const [isSubmitting, setIsSubmitting] = useAtom(isLoading);
  const [uploadProgress, setUploadProgress] = useState<UploadProgress[]>([]);
  const [statusLabel, setStatusLabel] = useState('');

  const membershipPlansUrl = useMemo(() => {
    const url = profileData?.membershipInfo?.url;
    return typeof url === 'string' ? url.trim() : '';
  }, [profileData?.membershipInfo?.url]);

  // Use Firebase UID as the Firestore driverId (anonymous auth, set on OTP verify)
  const driverId: string = fbUid || (profileData as any)?.id || (profileData as any)?.driverId || '';
  const driverName = [profileData?.firstName, profileData?.lastName].filter(Boolean).join(' ');

  const methods = useForm<TicketFormData>({
    resolver: yupResolver(ticketSchema) as any,
    mode: 'onChange',
    defaultValues: { description: '', files: [] },
  });

  const { handleSubmit, reset, watch, formState: { isValid } } = methods;
  const uploadedFiles = watch('files') || [];

  const handleOpenMembershipPlans = useCallback(() => {
    if (!membershipPlansUrl) return;
    window.open(membershipPlansUrl, '_blank', 'noopener,noreferrer');
  }, [membershipPlansUrl]);

  const overallProgress = uploadProgress.length
    ? Math.round(uploadProgress.reduce((sum, p) => sum + p.percent, 0) / uploadProgress.length)
    : 0;

  const onSubmitTicket = handleSubmit(async (data) => {
    if (!driverId) {
      toasterService('Could not identify your account. Please log out and back in.', 4, 'Error');
      return;
    }

    setIsSubmitting(true);
    const ticketId = crypto.randomUUID();
    const files = data.files as File[];

    try {
      // Step 1 — upload images to Firebase Storage
      setStatusLabel('Uploading documents…');
      const imageUrls = await uploadTicketFiles(driverId, ticketId, files, setUploadProgress);

      // Step 2 — create Firestore document (status: "processing")
      setStatusLabel('Saving ticket…');
      await createTicketDoc(driverId, ticketId, {
        description: data.description,
        image_urls: imageUrls,
      });

      // Step 3 — send files to AI engine for extraction
      setStatusLabel('Scanning ticket with AI…');
      await submitToAiEngine(files, driverName, driverId, ticketId);

      toasterService('Ticket submitted — AI scan complete!', 2, 'Success');
      setStep('success');
    } catch (error: any) {
      console.error('[AddTicketModal] submission error:', error);
      toasterService(error?.message || 'An error occurred while submitting your ticket', 4, 'Error');
    } finally {
      setIsSubmitting(false);
      setStatusLabel('');
      setUploadProgress([]);
    }
  });

  const handleClose = () => {
    if (!isSubmitting) {
      onSuccess?.();
      reset();
      setStep('form');
      onClose();
    }
  };

  return (
    <Modal open={open} onOpenChange={(nextOpen) => !nextOpen && handleClose()}>
      <ModalContent
        hideCloseButton
        className="w-[calc(100vw-16px)] max-w-[600px] overflow-hidden rounded-[24px] border border-[#e5e7eb] bg-white p-0 shadow-[0_24px_48px_rgba(15,23,42,0.18)] sm:w-[calc(100vw-32px)]"
      >
        <div className="max-h-[90vh] overflow-y-auto">
          {step === 'form' && (
            <>
              <div className="sticky top-0 flex items-center justify-between border-b border-[#e5e7eb] bg-white px-6 py-4 sm:px-8">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#dc2626]">
                    <LucideIcon name="FileText" size={20} color="#ffffff" />
                  </div>
                  <h2 className="text-[16px] font-normal leading-6 text-[#1e3a5f]">Submit a Ticket</h2>
                </div>

                {!isSubmitting && (
                  <button
                    type="button"
                    onClick={handleClose}
                    className="flex h-10 w-10 items-center justify-center rounded-full bg-[#f3f4f6] transition-colors hover:bg-gray-200"
                  >
                    <LucideIcon name="X" size={20} color="#374151" />
                  </button>
                )}
              </div>

              <div className="px-6 pb-6 pt-6 sm:px-8 sm:pb-8">
                <p className="mb-6 text-[16px] leading-[27px] text-[#4a5565]">
                  Tell us about your ticket or inspection and upload a copy of the citation.
                </p>

                <FormProvider methods={methods} onSubmit={onSubmitTicket}>
                  <div className="space-y-6">
                    {membershipPlansUrl && (
                      <MembershipCoverageCard membershipPlansUrl={membershipPlansUrl} onOpenMembershipPlans={handleOpenMembershipPlans} />
                    )}

                    <div>
                      <p className="mb-2 text-[18px] leading-[27px] text-[#1e3a5f]">Ticket/Inspection Details *</p>
                      <RHFTextField
                        name="description"
                        multiline
                        rows={6}
                        placeholder="Describe what happened, where it occurred, the type of violation, any relevant details..."
                        size="small"
                        margin="none"
                        className="text-[0.9375rem]"
                      />
                    </div>

                    <div>
                      <p className="mb-2 text-[#1e3a5f]">Upload Ticket (Documents) *</p>
                      <RHFDropzone
                        name="files"
                        accept={{
                          'application/pdf': ['.pdf'],
                          'image/jpeg': ['.jpg', '.jpeg'],
                          'image/png': ['.png'],
                        }}
                        multiple
                        helperText="Upload a PDF citation or supporting JPG/PNG documents."
                      />
                    </div>

                    {uploadedFiles.length > 0 && (
                      <div className="space-y-2 rounded-xl border border-green-200 bg-green-50 p-4">
                        <div className="flex items-center justify-center gap-2 text-green-600">
                          <LucideIcon name="CircleCheck" size={20} />
                          <span className="text-sm">File uploaded successfully</span>
                        </div>
                        <div className="text-center text-[#1e3a5f]">
                          {uploadedFiles[0]?.name}
                        </div>
                        <div className="text-center text-sm text-gray-500">
                          {uploadedFiles.length} file{uploadedFiles.length > 1 ? 's' : ''} ready to upload
                        </div>
                      </div>
                    )}

                    {/* Upload progress bar */}
                    {isSubmitting && (
                      <div className="space-y-1">
                        <div className="flex items-center justify-between text-xs text-gray-500">
                          <span>{statusLabel}</span>
                          {uploadProgress.length > 0 && <span>{overallProgress}%</span>}
                        </div>
                        <div className="h-1.5 w-full overflow-hidden rounded-full bg-gray-200">
                          <div
                            className="h-full rounded-full bg-[#0d4679] transition-all duration-300"
                            style={{ width: `${uploadProgress.length > 0 ? overallProgress : 30}%` }}
                          />
                        </div>
                      </div>
                    )}

                    <div className="flex gap-3">
                      <Button
                        type="button"
                        fullWidth
                        onClick={handleClose}
                        variant="secondary"
                        className="h-12 rounded-xl border-2 border-gray-200 bg-white text-gray-700 hover:bg-gray-50"
                      >
                        Cancel
                      </Button>
                      <Button
                        type="button"
                        fullWidth
                        onClick={onSubmitTicket}
                        disabled={!isValid || isSubmitting}
                        className="h-12 rounded-xl bg-[#dc2626] text-white hover:bg-[#b91c1c] disabled:cursor-not-allowed disabled:bg-gray-400"
                      >
                        {isSubmitting ? (
                          <span className="inline-flex items-center gap-2">
                            <span className="h-5 w-5 animate-spin rounded-full border-2 border-white border-t-transparent" />
                            <span>{statusLabel || 'Submitting…'}</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-2">
                            <LucideIcon name="FileText" size={18} />
                            <span>Submit Ticket</span>
                          </span>
                        )}
                      </Button>
                    </div>
                  </div>
                </FormProvider>
              </div>
            </>
          )}

          {step === 'success' && <SuccessStep
            membershipPlansUrl={membershipPlansUrl}
            onClose={handleClose}
            onOpenMembershipPlans={handleOpenMembershipPlans}
          />}
        </div>
      </ModalContent>
    </Modal>
  );
});

AddTicketModal.displayName = 'AddTicketModal';

export default AddTicketModal;
