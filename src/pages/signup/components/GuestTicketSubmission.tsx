import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import * as Yup from 'yup';
import LucideIcon from 'src/components/lucide-icon';
import { FormProvider, RHFAutocomplete, RHFDatePicker, RHFTextField, RHFDropzone } from 'src/hook-form';
import { Button, Modal, ModalContent } from 'src/components/ui';
import { submitGuestTicket, uploadCaseDocuments } from 'src/utils/api-service';
import { constants } from 'src/constants.value';
import { isLoading } from 'src/store';
import { useAtom } from 'jotai';
import { toasterService } from 'src/apiSetUp';
import { fDate, formatStr } from 'src/utils/format-time';
import { formatPhoneNumber } from './signup-flow';
import { setDataIntoStorage } from 'src/common-service/index.service';
import { useNavigate } from 'react-router-dom';
import { useViolationCategoryOptionsQuery } from 'src/queries/use-config-data-query';

interface GuestTicketSubmissionProps {
    isOpen: boolean;
    onClose: () => void;
    onSignupInstead: () => void;
}

// Multi-step flow
type StepType = 'warning' | 'details' | 'upload' | 'success';

// Violation type for dropdown (matches RHFSelectbox format)
interface ViolationTypeOption {
    value: string;
    Name: string;
}

// Extended file type with VersionData
interface ExtendedFile extends File {
    VersionData?: string;
}

// Validation schema for ticket details
const ticketSchema = Yup.object().shape({
    firstName: Yup.string().required('First name is required'),
    lastName: Yup.string().required('Last name is required'),
    email: Yup.string().email('Invalid email address').required('Email is required'),
    phone: Yup.string()
        .matches(/^\(\d{3}\) \d{3}-\d{4}$/, 'Please enter a valid phone number')
        .required('Phone number is required'),
    violationType: Yup.object().shape({
        value: Yup.string().required('Please select a violation type'),
        Name: Yup.string().required('Please select a violation type'),
    }).required('Please select a violation type'),
    violationDate: Yup.date().required('Violation date is required'),
    courtDate: Yup.date().required('Court date is required'),
    location: Yup.string().required('Location is required'),
    description: Yup.string(),
    files: Yup.array().required('Please upload at least one file').min(1, 'Please upload at least one file'),
});

// Validation schema for file upload (optional files)
const uploadSchema = Yup.object().shape({

});


/**
 * GuestTicketSubmission Modal - For users who want to submit a ticket without signing up
 * Multi-step flow: Warning → Details → Upload → Success
 */
export default function GuestTicketSubmission({
    isOpen,
    onClose,
    onSignupInstead,
}: GuestTicketSubmissionProps) {
    const navigate = useNavigate();
    const [step, setStep] = useState<StepType>('warning');
    const [isSubmitting, setIsSubmitting] = useState(false);
    const { data: violationTypes = [] } = useViolationCategoryOptionsQuery(isOpen);

    // Form for ticket details
    const methods = useForm({
        resolver: yupResolver(ticketSchema),
        defaultValues: {
            firstName: '',
            lastName: '',
            email: '',
            phone: '',
            violationType: { value: '', Name: '' },
            violationDate: new Date(),
            courtDate: new Date(),
            location: '',
            description: '',
            files: [],
        },
    });

    const handleSubmit = methods.handleSubmit(async (data) => {
        try {
            setIsSubmitting(true);
            const cleanPhone = data.phone.replace(/\D/g, '');
            const payload = {
                firstName: data.firstName,
                lastName: data.lastName,
                email: data.email,
                phone: cleanPhone,
                ticket: {
                    violationType: data.violationType.value,
                    ticketDate: fDate(data.violationDate, formatStr.paramCase.fromYear),
                    courtDate: fDate(data.courtDate, formatStr.paramCase.fromYear),
                    location: data.location,
                    description: data.description || '',
                },
            };
            const response = await submitGuestTicket(payload);
            if (response.StatusCode === constants.RESPONSE_STATUS.SUCCESS) {
                if (response.Result?.data?.ticketCase?.caseNumber) {
                    uploadDocument(data.files, response.Result.Data.AccessToken, response.Result.Data.RefreshToken, {
                        caseNumber: response.Result.data.ticketCase.caseNumber,
                        caseNumberId: response.Result.data.ticketCase.id,
                    });
                };
            } else {
                setIsSubmitting(false);
                toasterService('Failed to submit ticket', 4, 'Error');
            }
        } catch (error: any) {
            setIsSubmitting(false);
            toasterService(error?.message || 'An unexpected error occurred. Please try again.', 4, 'Error');
        }
    });

    const uploadDocument = async (file: ExtendedFile[], AccessToken: string, RefreshToken: string, caseNumber: { caseNumber: string; caseNumberId: string }) => {
        const files = file as ExtendedFile[];
        const formData = new FormData();
        files.forEach((file) => {
            formData.append('Files', file);
        });
        formData.append('CaseNumber', caseNumber.caseNumber);
        formData.append('CaseNumberId', caseNumber.caseNumberId);
        try {
            const response = await uploadCaseDocuments(formData);
            if (response.StatusCode === constants.RESPONSE_STATUS.SUCCESS) {
                toasterService(response.Result.Message, 1, 5345353535);
                // setStep('success');
                setIsSubmitting(false);
                await setDataIntoStorage('driver_token', AccessToken);
                await setDataIntoStorage('driver_refresh_token', RefreshToken);
                navigate('/dashboard');
            } else {
                toasterService('Failed to upload documents', 4, 'Error');
            }
        } catch (error: any) {
            toasterService(error?.message || 'An error occurred while uploading files', 4, 'Error');
        } finally {
            setIsSubmitting(false);
        }
    };

    const resetAndClose = () => {
        setStep('warning');
        methods.reset();
        onClose();
    };

    const handleClose = () => {
        if (!isSubmitting) {
            resetAndClose();
        }
    };

    return (
        <Modal open={isOpen} onOpenChange={(open) => !open && handleClose()}>
            <ModalContent
                hideCloseButton
                className="left-0 right-0 top-auto mx-0 flex w-full max-w-none translate-x-0 translate-y-0 flex-col rounded-t-[20px] rounded-b-none border-0 p-0 sm:left-1/2 sm:right-auto sm:top-1/2 sm:w-[calc(100%-2rem)] sm:max-w-[640px] sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-3xl sm:border sm:border-slate-200"
            >
                    <div className="mx-auto mb-1 mt-3 h-1 w-10 rounded-full bg-gray-300 sm:hidden" />

                    <div className="flex items-center justify-between border-b border-gray-200 px-5 py-3 sm:px-6 sm:py-5">
                        {step === 'details' ? (
                            <button
                                type="button"
                                onClick={() => { setStep('warning'); methods.reset(); }}
                                disabled={isSubmitting}
                                className="inline-flex h-10 w-10 items-center justify-center rounded-full text-slate-600 transition hover:bg-slate-100 disabled:opacity-50"
                            >
                                <LucideIcon name="ArrowLeft" size={22} />
                            </button>
                        ) : step === 'upload' ? (
                            <button
                                type="button"
                                onClick={() => setStep('details')}
                                disabled={isSubmitting}
                                className="inline-flex h-10 w-10 items-center justify-center rounded-full text-slate-600 transition hover:bg-slate-100 disabled:opacity-50"
                            >
                                <LucideIcon name="ArrowLeft" size={22} />
                            </button>
                        ) : (
                            <div className="w-10" />
                        )}

                        <h2 className="text-base font-semibold text-[#1e3a5f] sm:text-xl">
                            {step === 'warning' && 'Important Notice'}
                            {step === 'details' && 'Submit Your Ticket'}
                            {step === 'upload' && 'Upload Documents'}
                            {step === 'success' && 'Ticket Submitted'}
                        </h2>

                        <button
                            type="button"
                            onClick={handleClose}
                            disabled={isSubmitting}
                            className="inline-flex h-10 w-10 items-center justify-center rounded-full text-slate-600 transition hover:bg-slate-100 disabled:opacity-50"
                        >
                            <LucideIcon name="X" size={22} />
                        </button>
                    </div>

                    <div className="flex-1 overflow-auto px-5 py-5 pb-[env(safe-area-inset-bottom,0px)] sm:px-6 sm:py-6 sm:pb-6">
                        {/* Step 1: Warning */}
                        {step === 'warning' && (
                            <div className="space-y-6">
                                {/* Not Covered Warning */}
                                <div className="rounded-xl border-2 border-red-200 bg-red-50 p-5 sm:p-6">
                                    <div className="mb-4 flex gap-4">
                                        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-red-100">
                                            <LucideIcon name="TriangleAlert" size={24} color="#dc2626" />
                                        </div>
                                        <div>
                                            <h3 className="mb-2 text-base font-semibold text-red-900 sm:text-lg">
                                                This Ticket Will NOT Be Covered
                                            </h3>
                                            <p className="text-sm leading-relaxed text-red-700">
                                                You'll pay out-of-pocket for all legal services related to this ticket. Membership is required for coverage.
                                            </p>
                                        </div>
                                    </div>

                                    <div className="rounded-lg bg-white p-4">
                                        <p className="mb-2 text-sm font-semibold text-red-900">
                                            What this means:
                                        </p>
                                        <ul className="ml-5 list-disc space-y-1.5">
                                            {[
                                                'Legal fees are not included',
                                                'Court representation costs extra',
                                                'Document processing fees apply',
                                                'No membership benefits'
                                            ].map((text, index) => (
                                                <li key={index} className="text-sm text-black">
                                                    {text}
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                </div>

                                {/* Better Option */}
                                <div className="rounded-xl bg-gradient-to-br from-[#0D3E6B] to-[#1e3a5f] p-6 text-white">
                                    <div className="mb-5 flex gap-4">
                                        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-white/20">
                                            <LucideIcon name="ShieldCheck" size={24} color="white" />
                                        </div>
                                        <div>
                                            <h3 className="mb-2 text-base font-medium text-white sm:text-lg">
                                                Better Option: Get Coverage
                                            </h3>
                                            <p className="text-sm leading-relaxed text-white/90">
                                                Sign up for membership now and all future tickets will be covered starting today
                                            </p>
                                        </div>
                                    </div>

                                    <Button
                                        fullWidth
                                        onClick={onSignupInstead}
                                        className="h-11 bg-white text-[#1e3a5f] hover:bg-[#f0f9ff]"
                                    >
                                        Sign Up for Membership Instead
                                    </Button>
                                </div>

                                {/* Continue Anyway */}
                                <div className="space-y-3">
                                    <Button
                                        fullWidth
                                        onClick={() => setStep('details')}
                                        className="h-11 bg-gray-100 text-gray-700 shadow-none hover:bg-gray-200"
                                    >
                                        I Understand - Continue Without Coverage
                                    </Button>

                                    <Button
                                        onClick={resetAndClose}
                                        variant="secondary"
                                        className="border-0 bg-transparent text-gray-700 shadow-none hover:bg-gray-100"
                                    >
                                        Go Back
                                    </Button>
                                </div>
                            </div>
                        )}

                        {/* Step 2: Details */}
                        {step === 'details' && (
                            <>
                                {/* Uncovered Badge */}
                                <div className="mb-6 flex items-center gap-3 rounded-lg border border-yellow-300 bg-amber-50 p-3">
                                    <LucideIcon name="TriangleAlert" size={20} color="#d97706" style={{ flexShrink: 0 }} />
                                    <p className="text-sm text-amber-900">
                                        <strong>Reminder:</strong> This ticket is not covered by membership
                                    </p>
                                </div>

                                {/* Form */}
                                <FormProvider methods={methods} onSubmit={handleSubmit}>
                                    <div className="space-y-6">
                                        {/* Personal Information */}
                                        <div>
                                            <h3 className="mb-4 text-base font-semibold text-[#1e3a5f]">
                                                Your Information
                                            </h3>
                                            <div className="space-y-4">
                                                <div className="flex gap-4">
                                                    <RHFTextField
                                                        name="firstName"
                                                        label="First Name"
                                                    />
                                                    <RHFTextField
                                                        name="lastName"
                                                        label="Last Name"
                                                    />
                                                </div>

                                                <RHFTextField
                                                    name="email"
                                                    label="Email Address"
                                                    type="email"
                                                />

                                                <RHFTextField
                                                    name="phone"
                                                    label="Phone Number"
                                                    type="text"
                                                    maxLength={14}
                                                    handleChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                                                        const formatted = formatPhoneNumber(e.target.value);
                                                        methods.setValue('phone', formatted);
                                                    }}
                                                />
                                            </div>
                                        </div>

                                        {/* Ticket Details */}
                                        <div>
                                            <h3 className="mb-4 text-base font-semibold text-[#1e3a5f]">
                                                Ticket Details
                                            </h3>
                                            <div className="space-y-4">
                                                <RHFAutocomplete
                                                    name="violationType"
                                                    label="Violation Type"
                                                    value=""
                                                    options={violationTypes}
                                                />
                                                <div className="flex gap-4">
                                                    <RHFDatePicker
                                                        name="violationDate"
                                                        label="Violation Date"
                                                        disableFuture
                                                    />
                                                    <RHFDatePicker
                                                        name="courtDate"
                                                        label="Court Date"
                                                        disablePast
                                                    />
                                                </div>

                                                <RHFTextField
                                                    name="location"
                                                    label="Location"
                                                    placeholder="City, State"
                                                />

                                                <RHFTextField
                                                    name="description"
                                                    multiline
                                                    label="Description (Optional)"
                                                    placeholder="Any additional details about your ticket..."
                                                />
                                            </div>
                                        </div>
                                    </div>
                                    <div className="space-y-6">
                                        <div>
                                            <h3 className="my-4 text-base font-medium text-[#1e3a5f]">
                                                Upload Supporting Documents
                                            </h3>

                                            <RHFDropzone
                                                name="files"
                                                accept={{
                                                    'image/jpeg': ['.jpg', '.jpeg'],
                                                    'image/png': ['.png'],
                                                    'application/pdf': ['.pdf'],
                                                }}
                                                maxSize={10485760} // 10MB
                                                multiple
                                            />

                                            <p className="mt-2 block text-xs text-gray-500">
                                                Accepted formats: PDF, JPEG, PNG (Max 10MB per file)
                                            </p>
                                        </div>

                                        {/* Action Buttons */}
                                        <div className="space-y-4">
                                            <Button
                                                type="submit"
                                                fullWidth
                                                disabled={isSubmitting || !methods.formState.isValid}
                                                className="h-12 bg-[#dc2626] text-base hover:bg-[#b91c1c]"
                                            >
                                                {isSubmitting ? 'Submitting...' : 'Submit Ticket'}
                                            </Button>
                                        </div>
                                    </div>
                                </FormProvider>
                            </>
                        )}

                        {/* Step 4: Success */}
                        {step === 'success' && (
                            <div className="text-center">
                                <div className="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-green-100">
                                    <LucideIcon name="CircleCheck" size={40} color="#16a34a" />
                                </div>

                                <h2 className="mb-3 text-2xl font-bold text-[#1e3a5f]">
                                    Ticket Submitted
                                </h2>
                                <p className="mb-6 text-base leading-relaxed text-gray-500">
                                    We've received your ticket information. You'll be contacted about service costs and next steps.
                                </p>

                                {/* Reminder */}
                                <div className="mb-6 rounded-lg border border-yellow-300 bg-amber-50 p-4 text-left">
                                    <div className="flex items-start gap-3">
                                        <LucideIcon
                                            name="TriangleAlert"
                                            size={20}
                                            color="#d97706"
                                            style={{ marginTop: 2, flexShrink: 0 }}
                                        />
                                        <div>
                                            <p className="mb-1 text-sm text-amber-900">
                                                <strong>This ticket is not covered.</strong> You will be responsible for all service fees.
                                            </p>
                                            <p className="text-xs text-amber-800">
                                                Check your email ({methods.getValues('email')}) for pricing details and payment instructions.
                                            </p>
                                        </div>
                                    </div>
                                </div>

                                {/* Upsell */}
                                <div className="mb-6 rounded-xl bg-gradient-to-br from-[#0D3E6B] to-[#1e3a5f] p-6 text-left">
                                    <div className="mb-4 flex items-center gap-3">
                                        <LucideIcon name="ShieldCheck" size={24} color="white" />
                                        <h3 className="text-lg font-semibold text-white">
                                            Protect Yourself from Future Tickets
                                        </h3>
                                    </div>
                                    <p className="mb-5 text-sm leading-relaxed text-white/90">
                                        Sign up for membership and get full coverage on all future tickets starting immediately.
                                    </p>
                                    <Button
                                        fullWidth
                                        onClick={onSignupInstead}
                                        className="h-11 bg-white text-[#1e3a5f] hover:bg-[#f0f9ff]"
                                    >
                                        Sign Up for Membership
                                    </Button>
                                </div>

                                <Button
                                    fullWidth
                                    onClick={resetAndClose}
                                    variant="secondary"
                                    className="border-slate-200 bg-white text-slate-600 shadow-none hover:bg-slate-50"
                                >
                                    Close
                                </Button>
                            </div>
                        )}
                    </div>
            </ModalContent>
        </Modal>
    );
}
