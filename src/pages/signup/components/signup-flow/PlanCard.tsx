import LucideIcon from 'src/components/lucide-icon';

interface Plan {
    amount: number;
    benefits: string[];
}

interface PlanCardProps {
    tierKey: string;
    tierName: string;
    tierColor: string;
    tierIcon: string;
    tierBadge?: string;
    currentPlan: Plan;
    billingFrequency: 'monthly' | 'quarterly' | 'annually';
    onSelect: () => void;
}

export default function PlanCard({
    tierKey,
    tierName,
    tierColor,
    tierIcon,
    tierBadge,
    currentPlan,
    billingFrequency,
    onSelect,
}: PlanCardProps) {
    // Calculate monthly equivalent for display
    const divisor = billingFrequency === 'quarterly' ? 3 : billingFrequency === 'annually' ? 12 : 1;
    const monthlyEquivalent = currentPlan.amount / divisor;

    return (
        <div
            onClick={onSelect}
            className="cursor-pointer rounded-xl border-2 border-gray-200 bg-white p-5 transition-all hover:-translate-y-0.5 hover:border-[#0D3E6B] hover:shadow-lg"
        >
            <div className="mb-4 flex items-start gap-4">
                <div
                    className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl"
                    style={{ backgroundColor: tierColor }}
                >
                    <LucideIcon name={tierIcon} size={24} color="#fff" />
                </div>
                <div className="flex-1">
                    <div className="flex items-center gap-2">
                        <p className="text-base font-bold text-[#1e3a5f]">
                            {tierName} Membership
                        </p>
                        {tierBadge && (
                            <span className="rounded bg-orange-500 px-2 py-0.5 text-[0.65rem] font-semibold text-white">
                                {tierBadge}
                            </span>
                        )}
                    </div>
                    <div className="flex items-baseline gap-1">
                        <span className="text-2xl font-bold text-gray-900">
                            ${monthlyEquivalent.toFixed(2)}
                        </span>
                        <span className="text-xs text-gray-500">/month</span>
                    </div>
                    {billingFrequency !== 'monthly' && (
                        <p className="text-xs text-gray-500">
                            ${currentPlan.amount.toFixed(2)} billed {billingFrequency}
                        </p>
                    )}
                </div>
            </div>

            <div className="space-y-2">
                {currentPlan.benefits.map((benefit: string, idx: number) => (
                    <div key={idx} className="flex items-start gap-2">
                        <LucideIcon
                            name="CircleCheck"
                            size={18}
                            color="#16a34a"
                            style={{ marginTop: 2 }}
                        />
                        <p className="text-sm text-gray-500">{benefit}</p>
                    </div>
                ))}
            </div>
        </div>
    );
}
