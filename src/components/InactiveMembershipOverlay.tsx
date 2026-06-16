import LucideIcon from 'src/components/lucide-icon';

interface InactiveMembershipOverlayProps {
    onReactivate: () => void;
}

export function InactiveMembershipOverlay({ onReactivate }: InactiveMembershipOverlayProps) {
    return (
        <div className="flex min-h-screen items-center justify-center bg-gray-100 px-2 py-4">
            <div className="w-full max-w-[520px] rounded-[2rem] border-2 border-gray-200 bg-white p-6 text-center shadow-lg sm:p-8">
                <div className="flex items-center justify-center gap-2.5">
                    <div className="flex h-20 w-20 items-center justify-center rounded-full bg-gray-100 text-gray-400">
                        <LucideIcon name="CircleAlert" size={38} color="#99a1af" />
                    </div>

                    <div className="hidden sm:block" />
                </div>

                <div className="mt-2.5 flex flex-col items-center gap-2.5">
                    <h1 className="text-3xl font-medium text-[rgba(30,58,95,0.4)]">
                        Membership Inactive
                    </h1>

                    <p className="max-w-[430px] text-base text-[#99a1af]">
                        Your membership has expired. Reactivate your account to continue accessing Rig Resolve services and manage your citations.
                    </p>

                    <button
                        type="button"
                        onClick={onReactivate}
                        className="mt-1 flex w-full items-center justify-center gap-2 rounded-2xl bg-[#dc2626] px-4 py-3 text-base font-bold text-white transition-colors hover:bg-[#b91c1c]"
                    >
                        <LucideIcon name="CreditCard" size={20} color="white" />
                        Reactivate Membership
                    </button>

                    <p className="text-sm text-gray-500">
                        Questions? Contact us at protect@cdllegal.com
                    </p>
                </div>
            </div>
        </div>
    );
}

export default InactiveMembershipOverlay;