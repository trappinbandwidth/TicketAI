interface Plan {
    amount: number;
}

interface PlanSummaryProps {
    tierName: string;
    tierColor: string;
    planData: Plan;
    billingFrequency: 'monthly' | 'quarterly' | 'annually';
    title?: string;
}

export default function PlanSummary({
    tierName,
    tierColor,
    planData,
    billingFrequency,
    title = 'Selected Plan',
}: PlanSummaryProps) {
    const divisor = billingFrequency === 'quarterly' ? 3 : billingFrequency === 'annually' ? 12 : 1;
    const monthlyEquivalent = planData.amount / divisor;

    return (
        <div
            className="mb-3 rounded-xl p-4 text-white"
            style={{ backgroundColor: tierColor }}
        >
            <div className="flex items-center justify-between">
                <div>
                    <span className="text-xs opacity-90">{title}</span>
                    <p className="text-lg font-semibold text-white">{tierName} Membership</p>
                </div>
                <div className="text-right">
                    <div className="flex items-baseline gap-1">
                        <span className="text-2xl font-bold text-white">${monthlyEquivalent.toFixed(2)}</span>
                        <span className="text-xs opacity-90">/month</span>
                    </div>
                    {billingFrequency !== 'monthly' && (
                        <span className="text-xs opacity-90">
                            ${planData.amount.toFixed(2)} billed {billingFrequency}
                        </span>
                    )}
                </div>
            </div>
        </div>
    );
}
