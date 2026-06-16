import PlanCard from './PlanCard';
import FrequencySelector from './FrequencySelector';

type PlanType = 'silver' | 'gold' | 'platinum';
type BillingFrequency = 'monthly' | 'quarterly' | 'annually';

interface Plan {
    amount: number;
    benefits: string[];
}

interface PlanDetails {
    [key: string]: {
        name: string;
        color: string;
        icon: string;
        badge?: string;
        plans: {
            monthly?: Plan;
            quarterly?: Plan;
            annually?: Plan;
        };
    };
}

interface Frequency {
    savingsPercent: number | null;
    savingsBadge: string | null;
    label: string;
    key: string;
}

interface PlanSelectionStepProps {
    planDetails: PlanDetails;
    frequencies: Frequency[];
    billingFrequency: BillingFrequency;
    isLoadingPlans: boolean;
    plansError: string | null;
    onFrequencyChange: (frequency: BillingFrequency) => void;
    onPlanSelect: (plan: PlanType) => void;
}

export default function PlanSelectionStep({
    planDetails,
    frequencies,
    billingFrequency,
    isLoadingPlans,
    plansError,
    onFrequencyChange,
    onPlanSelect,
}: PlanSelectionStepProps) {
    return (
        <>
            <FrequencySelector
                frequencies={frequencies}
                selectedFrequency={billingFrequency}
                onFrequencyChange={(key) => onFrequencyChange(key as BillingFrequency)}
            />

            {/* Loading State */}
            {isLoadingPlans && (
                <div className="flex justify-center p-8">
                    <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-200 border-t-[#0D3E6B]" />
                </div>
            )}

            {/* Error State */}
            {plansError && !isLoadingPlans && (
                <p className="text-center text-red-500">{plansError}</p>
            )}

            {/* Plan Cards */}
            {!isLoadingPlans && !plansError && (
                <div className="space-y-4">
                    {(Object.keys(planDetails) as PlanType[]).map((tierKey) => {
                        const tier = planDetails[tierKey];
                        const currentPlan = tier.plans[billingFrequency];

                        if (!currentPlan) return null;

                        return (
                            <PlanCard
                                key={tierKey}
                                tierKey={tierKey}
                                tierName={tier.name}
                                tierColor={tier.color}
                                tierIcon={tier.icon}
                                tierBadge={tier.badge}
                                currentPlan={currentPlan}
                                billingFrequency={billingFrequency}
                                onSelect={() => onPlanSelect(tierKey)}
                            />
                        );
                    })}
                </div>
            )}
        </>
    );
}
