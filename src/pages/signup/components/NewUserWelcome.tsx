import { Modal, ModalContent } from 'src/components/ui';
import { Button } from 'src/components/ui';
import LucideIcon from 'src/components/lucide-icon';

interface NewUserWelcomeProps {
    isOpen: boolean;
    onClose: () => void;
    onSelectSignup: () => void;
    onSelectTicketSubmission: () => void;
}

/**
 * NewUserWelcome Modal - First screen for new users
 * Optimized for mobile devices (iOS & Android)
 * Presents two paths: Sign up for membership (recommended) or Submit a ticket
 */
export default function NewUserWelcome({
    isOpen,
    onClose,
    onSelectSignup,
    onSelectTicketSubmission,
}: NewUserWelcomeProps) {
    return (
        <Modal open={isOpen} onOpenChange={(open) => !open && onClose()}>
            <ModalContent
                hideCloseButton
                className="left-0 right-0 top-auto mx-0 w-full max-w-none translate-x-0 translate-y-0 rounded-t-[20px] rounded-b-none border-0 p-0 sm:left-1/2 sm:right-auto sm:top-1/2 sm:w-[calc(100%-2rem)] sm:max-w-[440px] sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-3xl sm:border sm:border-slate-200"
            >
                <div className="max-h-[80vh] overflow-auto pb-[env(safe-area-inset-bottom,0px)] sm:pb-0">
                    <div className="mx-auto mb-1 mt-3 block h-1 w-10 rounded-full bg-gray-300 sm:hidden" />

                    <div className="px-5 pb-3 pt-4 text-center sm:px-6 sm:pb-4 sm:pt-6">
                        <h2 className="mb-1 text-xl font-bold text-[#1e3a5f] sm:text-2xl">
                            Welcome to Rig Resolve!
                        </h2>
                        <p className="text-sm text-gray-500">Choose your path to get started</p>
                    </div>

                    <div className="px-5 sm:px-6">
                        <div className="relative overflow-visible rounded-xl bg-gradient-to-br from-[#0D3E6B] to-[#1e3a5f] p-4 text-white sm:p-5">
                            <span className="absolute -top-2.5 right-3 rounded-full bg-[#F2AE26] px-2.5 py-1 text-[0.7rem] font-semibold text-[#1e3a5f] shadow-md sm:right-4 sm:text-xs">
                                Recommended
                            </span>

                            <div className="mb-3 flex items-start gap-3 sm:mb-4 sm:gap-4">
                                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-white/20 sm:h-12 sm:w-12">
                                    <LucideIcon name="ShieldCheck" size={22} />
                                </div>
                                <div className="flex-1">
                                    <h3 className="mb-1 text-base font-semibold text-white sm:text-lg">
                                        Get Protected First
                                    </h3>
                                    <p className="text-[0.8125rem] leading-snug text-white/95 sm:text-sm">
                                        Sign up for membership and all future tickets will be covered starting today
                                    </p>
                                </div>
                            </div>

                            <div className="mb-4 ml-1 space-y-1.5 sm:mb-5 sm:space-y-2">
                                {['Future tickets covered', 'Member rewards & referral program', 'Full app access & benefits'].map((benefit) => (
                                    <div key={benefit} className="flex items-center gap-2">
                                        <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-[#F2AE26]" />
                                        <span className="text-[0.8125rem] text-white/90 sm:text-sm">{benefit}</span>
                                    </div>
                                ))}
                            </div>

                            <Button
                                fullWidth
                                onClick={onSelectSignup}
                                className="h-11 bg-white text-[#1e3a5f] hover:bg-white/95 sm:h-10"
                            >
                                <span>Sign Up for Membership</span>
                                <LucideIcon name="ArrowRight" size={20} />
                            </Button>
                        </div>
                    </div>

                    <div className="flex items-center justify-center py-3 sm:py-4">
                        <span className="text-sm text-gray-500">or</span>
                    </div>

                    <div className="px-5 pb-3 sm:px-6 sm:pb-4">
                        <div className="rounded-xl border-2 border-gray-200 p-4 sm:p-5">
                            <div className="mb-2 flex items-start gap-3 sm:gap-4">
                                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-gray-100 sm:h-12 sm:w-12">
                                    <LucideIcon name="FileText" size={22} color="#1e3a5f" />
                                </div>
                                <div className="flex-1">
                                    <h3 className="mb-1 text-base font-semibold text-[#1e3a5f] sm:text-lg">
                                        Submit a Ticket Now
                                    </h3>
                                    <p className="text-[0.8125rem] leading-snug text-gray-500 sm:text-sm">
                                        Get help with a current ticket you already have
                                    </p>
                                </div>
                            </div>

                            <div className="mb-3 flex items-start justify-center gap-2 rounded-lg border border-amber-200 bg-amber-50 p-2.5 sm:mb-4 sm:rounded-xl sm:p-3">
                                <LucideIcon name="TriangleAlert" size={18} color="#d97706" style={{ marginTop: 1 }} />
                                <p className="text-[0.8125rem] text-amber-600 sm:text-sm">
                                    <strong>Not covered:</strong> You&apos;ll pay for services on this ticket
                                </p>
                            </div>

                            <Button
                                fullWidth
                                onClick={onSelectTicketSubmission}
                                className="h-11 bg-gray-100 text-[#1e3a5f] shadow-none hover:bg-gray-200 sm:h-10"
                            >
                                <span>Continue Anyway</span>
                                <LucideIcon name="ArrowRight" size={20} />
                            </Button>
                        </div>
                    </div>

                    <div className="px-5 pb-4 sm:px-6 sm:pb-6">
                        <Button
                            fullWidth
                            variant="secondary"
                            onClick={onClose}
                            className="h-11 border-slate-200 bg-white text-[#1e3a5f] hover:bg-slate-50 sm:h-10"
                        >
                            Go Back
                        </Button>
                    </div>
                </div>
            </ModalContent>
        </Modal>
    );
}
