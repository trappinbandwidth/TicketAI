import { useForm } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import * as Yup from 'yup';

import LucideIcon from 'src/components/lucide-icon';
import { Button } from 'src/components/ui';
import { DashboardContent } from 'src/layouts/dashboard/main';
import { FormProvider, RHFTextField, RHFSelectbox, RHFRadio } from 'src/hook-form';
import { toasterService } from 'src/apiSetUp';

const ISSUE_TYPES = [
    { name: 'Billing Issue', value: 'Billing Issue' },
    { name: 'Technical Support', value: 'Technical Support' },
    { name: 'Legal Question', value: 'Legal Question' },
    { name: 'Membership Inquiry', value: 'Membership Inquiry' },
    { name: 'Other', value: 'Other' }
];

const supportSchema = Yup.object().shape({
    issueType: Yup.string().required('Issue type is required'),
    relatedTicket: Yup.string().optional(),
    subject: Yup.string().required('Subject is required'),
    description: Yup.string().required('Description is required').min(10, 'Description must be at least 10 characters'),
    contactMethod: Yup.string().required('Contact method is required'),
});

type SupportFormData = Yup.InferType<typeof supportSchema>;


export default function SupportPage() {
    const methods = useForm<SupportFormData>({
        resolver: yupResolver(supportSchema) as any,
        defaultValues: {
            issueType: '',
            relatedTicket: '',
            subject: '',
            description: '',
            contactMethod: 'phone',
        },
    });

    const {
        handleSubmit,
        reset,
        watch,
        formState: { isSubmitting },
    } = methods;

    const contactMethod = watch('contactMethod');

    const onSubmit = handleSubmit(async (data) => {
        try {
            console.log('Support Request Data:', data);
            // Simulate API call
            await new Promise((resolve) => setTimeout(resolve, 1500));
            toasterService('Support request submitted successfully!', 1, 'Success');
            reset();
        } catch (error) {
            console.error(error);
            toasterService('Failed to submit support request.', 4, 'Error');
        }
    });


    return (
        <DashboardContent>
            <div className="mvp-page-shell max-w-none lg:max-w-none">
            {/* Header */}
            <div className="mb-4 text-left md:text-center">
                <h1 className="mb-1 text-3xl font-extrabold text-[#1a365d]">
                    Support
                </h1>
                <p className="text-lg font-medium text-gray-500">
                    We're here to help you get the most out of Rig Resolve
                </p>
            </div>

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
                {/* Left Side: Help & History */}
                <div className="lg:col-span-4">
                    <div className="space-y-4">
                        {/* Need Immediate Help Card */}
                        <div
                            className="relative overflow-hidden rounded-lg bg-[#1a365d] p-6 text-white"
                            style={{ boxShadow: '0 8px 16px rgba(26, 54, 93, 0.2)' }}
                        >
                            <div className="absolute -right-5 -top-5 h-[100px] w-[100px] rounded-full bg-white/5" />
                            <div className="mb-4 flex items-center gap-2">
                                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-white/15">
                                    <LucideIcon name="PhoneCall" size={28} />
                                </div>
                                <div>
                                    <p className="font-extrabold">
                                        Need Immediate Help?
                                    </p>
                                    <p className="text-[13px] opacity-80">
                                        Available Mon - Fri, 8AM - 5PM CT
                                    </p>
                                </div>
                            </div>

                            <Button
                                asChild
                                fullWidth
                                size="lg"
                                variant="secondary"
                                className="mb-2 h-14 justify-center gap-2 rounded-xl border-white bg-white font-extrabold text-[#1a365d] hover:-translate-y-0.5 hover:bg-slate-100"
                            >
                                <a href="tel:9133611575">
                                    <LucideIcon name="Phone" size={20} />
                                    <span>(913) 361-1575</span>
                                </a>
                            </Button>

                            <div className="mt-2 flex items-center justify-center gap-1 opacity-80">
                                <LucideIcon name="Clock" size={16} />
                                <p className="text-xs font-semibold">
                                    Average wait time: &lt; 2 minutes
                                </p>
                            </div>
                        </div>

                        {/* Recent Support Requests */}
                        <div className="hidden lg:block">
                            <div className="mb-2 flex items-center gap-1.5">
                                <LucideIcon name="History" size={22} color="#1a365d" />
                                <p className="text-base font-extrabold text-[#1a365d]">
                                    Recent Requests
                                </p>
                            </div>

                            <div className="space-y-2">
                                <SupportRequestItem
                                    title="Question about court date"
                                    id="SUP-001"
                                    ticket="CDL-2024-001"
                                    status="Resolved"
                                    date="11/15/2024"
                                />
                                <SupportRequestItem
                                    title="Document upload issue"
                                    id="SUP-002"
                                    ticket="CDL-2024-003"
                                    status="Resolved"
                                    date="10/28/2024"
                                />
                            </div>
                        </div>
                    </div>
                </div>

                {/* Right Side: Form & Mobile Requests */}
                <div className="lg:col-span-8">
                    <div className="space-y-4">
                        {/* Submit Support Request Form */}
                        <div className="rounded-lg bg-white p-6 shadow-[0_4px_20px_rgba(0,0,0,0.05)] md:p-10">
                            <div className="mb-4 flex items-center gap-2">
                                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[rgba(26,54,93,0.08)] text-[#1a365d]">
                                    <LucideIcon name="Mail" size={24} />
                                </div>
                                <div>
                                    <h2 className="text-2xl font-extrabold text-[#1a365d]">
                                        Submit a Support Request
                                    </h2>
                                    <p className="text-sm text-gray-500">
                                        Complete the form below and we'll be in touch shortly.
                                    </p>
                                </div>
                            </div>

                            <FormProvider methods={methods} onSubmit={onSubmit}>
                                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                                    <div>
                                        <RHFSelectbox
                                            name="issueType"
                                            label="Issue Type *"
                                            menus={ISSUE_TYPES}
                                        />
                                    </div>

                                    <div>
                                        <RHFTextField
                                            name="relatedTicket"
                                            label="Related Ticket (Optional)"
                                            placeholder="e.g., CDL-2024-001"
                                        />
                                    </div>


                                    <div className="md:col-span-2">
                                        <RHFTextField
                                            name="subject"
                                            label="Subject *"
                                            placeholder="Brief description of your issue"
                                        />
                                    </div>

                                    <div className="md:col-span-2">
                                        <RHFTextField
                                            name="description"
                                            multiline
                                            rows={6}
                                            label="Description *"
                                            placeholder="Please provide as much detail as possible so we can better assist you..."
                                        />
                                    </div>


                                    <div className="md:col-span-2">
                                        <RHFRadio
                                            name="contactMethod"
                                            title="Preferred Contact Method *"
                                            className="mt-1 flex flex-col gap-4 sm:flex-row"
                                            optionClassName="mr-0 flex-1"
                                            options={[
                                                {
                                                    value: 'phone',
                                                    name: (
                                                        <div className="flex items-center gap-1.5">
                                                            <LucideIcon
                                                                name="Phone"
                                                                size={22}
                                                                color={contactMethod === 'phone' ? '#1a365d' : '#6b7280'}
                                                            />
                                                            <div>
                                                                <p className="text-sm font-bold">Phone Call</p>
                                                                <p className="text-xs text-gray-500">Quickest for complex issues</p>
                                                            </div>
                                                        </div>
                                                    ),
                                                },
                                                {
                                                    value: 'email',
                                                    name: (
                                                        <div className="flex items-center gap-1.5">
                                                            <LucideIcon
                                                                name="Mail"
                                                                size={22}
                                                                color={contactMethod === 'email' ? '#1a365d' : '#6b7280'}
                                                            />
                                                            <div>
                                                                <p className="text-sm font-bold">Email</p>
                                                                <p className="text-xs text-gray-500">Best for non-urgent tasks</p>
                                                            </div>
                                                        </div>
                                                    ),
                                                },
                                            ]}
                                        />
                                    </div>




                                    <div className="md:col-span-2">
                                        <Button
                                            fullWidth
                                            size="lg"
                                            type="submit"
                                            disabled={isSubmitting}
                                            className="mt-2 h-14 justify-center gap-2 rounded-xl bg-[#1a365d] font-extrabold hover:-translate-y-0.5 hover:bg-[#0d2139]"
                                        >
                                            {isSubmitting ? <LucideIcon name="LoaderCircle" size={24} className="animate-spin" /> : <LucideIcon name="Send" size={20} />}
                                            <span>{isSubmitting ? 'Submitting...' : 'Submit Support Request'}</span>
                                        </Button>
                                    </div>
                                </div>
                            </FormProvider>

                        </div>

                        {/* Mobile-only Recent Requests */}
                        <div className="block lg:hidden">
                            <div className="mb-2.5 flex items-center gap-1.5">
                                <LucideIcon name="History" size={24} color="#1a365d" />
                                <p className="text-xl font-extrabold text-[#1a365d]">
                                    Recent Support Requests
                                </p>
                            </div>
                            <div className="space-y-2">
                                {/* ... truncated for simplicity in the diff or just repeat ... */}
                                <SupportRequestItem
                                    title="Question about court date"
                                    id="SUP-001"
                                    ticket="CDL-2024-001"
                                    status="Resolved"
                                    date="11/15/2024"
                                />
                            </div>
                        </div>

                        {/* Common Questions */}
                        <div>
                            <h2 className="mb-3 text-xl font-extrabold text-[#1a365d]">
                                Frequently Asked Questions
                            </h2>
                            <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                                {[
                                    'How do I upload my citation documents?',
                                    'When will I hear back from my assigned attorney?',
                                    'How do I earn and redeem referral rewards?',
                                    'What should I do if my court date changes?',
                                ].map((q) => (
                                    <div key={q}>
                                        <div className="flex h-full cursor-pointer items-center justify-between rounded-lg border border-transparent bg-white p-2.5 transition-all duration-200 hover:border-[rgba(26,54,93,0.1)] hover:translate-x-1 hover:shadow-lg">
                                            <p className="text-sm font-bold">
                                                {q}
                                            </p>
                                            <LucideIcon name="ChevronRight" size={20} color="#6b7280" style={{ marginLeft: 16 }} />
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            </div>
        </DashboardContent>
    );
}

function SupportRequestItem({ title, id, ticket, status, date }: any) {
    return (
        <div className="rounded-lg bg-white p-2.5 shadow-sm">
            <div className="mb-1.5 flex items-start justify-between gap-2">
                <div>
                    <p className="mb-0.5 text-sm font-bold">
                        {title}
                    </p>
                    <div className="flex items-center gap-1">
                        <span className="rounded border border-gray-300 px-1.5 py-0.5 text-[10px]">
                            {id}
                        </span>
                        <span className="rounded bg-[rgba(26,54,93,0.08)] px-1.5 py-0.5 text-[10px] text-[#1a365d]">
                            {`Ticket: ${ticket}`}
                        </span>
                    </div>
                </div>
                <span className="rounded bg-[rgba(34,197,94,0.1)] px-2 py-1 text-[11px] font-bold text-[#15803d]">
                    {status}
                </span>
            </div>
            <div className="flex items-center gap-0.5 text-gray-500">
                <LucideIcon name="Clock" size={14} />
                <p className="text-xs">Submitted {date}</p>
            </div>
        </div>
    );
}
