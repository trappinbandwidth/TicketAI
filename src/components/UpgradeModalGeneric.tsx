import LucideIcon from 'src/components/lucide-icon';
import { PRICING, TIER_FEATURES, TIER_STYLING } from 'src/membership-config';
import { Button, Modal, ModalContent, ModalTitle } from 'src/components/ui';

interface UpgradeModalGenericProps {
  open: boolean;
  onClose: () => void;
  sourceTier: string;
  targetTier: string;
  billingCycle: 0 | 1 | 2;
  onBillingCycleChange: (cycle: 0 | 1 | 2) => void;
  onConfirm: () => void;
  loading: boolean;
  error?: string | null;
}

export function UpgradeModalGeneric({
  open,
  onClose,
  sourceTier,
  targetTier,
  billingCycle,
  onBillingCycleChange,
  onConfirm,
  loading,
  error,
}: UpgradeModalGenericProps) {
  const planTypes = ['monthly', 'quarterly', 'annually'] as const;
  const currentPlanType = planTypes[billingCycle];
  const currentPricing = PRICING[currentPlanType];

  const getTargetTierStyled = (tier: string) => TIER_STYLING[tier as keyof typeof TIER_STYLING] || TIER_STYLING.gold;
  const getTargetFeatures = (tier: string) => TIER_FEATURES[tier as keyof typeof TIER_FEATURES] || [];
  const getSourceFeatures = (tier: string) => TIER_FEATURES[tier as keyof typeof TIER_FEATURES] || [];

  const targetTierStyle = getTargetTierStyled(targetTier);
  const targetFeatures = getTargetFeatures(targetTier);
  const sourceFeatures = getSourceFeatures(sourceTier);

  return (
    <Modal
      open={open}
      onOpenChange={(nextOpen) => !nextOpen && onClose()}
    >
      <ModalContent className="max-w-md px-2.5 pb-2.5 pt-0">
        <div className="px-0 pb-2 pt-5">
        <div className="mb-1 flex items-center justify-between">
          <p className="text-sm text-gray-500">
            Choose Your Plan
          </p>
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="rounded-full p-1 text-slate-500 transition hover:bg-slate-100 hover:text-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <LucideIcon name="CircleX" size={20} />
          </button>
        </div>
        <ModalTitle className="mb-0.5 text-xl font-bold text-[#1a365d]">
          Upgrade Your Plan
        </ModalTitle>
        <p className="text-xs text-gray-500">
          Choose the plan that best fits your needs
        </p>
        </div>

        {error && (
          <div className="mb-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Plan Tabs */}
        <div className={`mb-2 grid grid-cols-3 gap-2 ${loading ? 'pointer-events-none opacity-60' : ''}`}>
          {[
            { label: 'Monthly', value: 0 as const },
            { label: 'Quarterly', value: 1 as const, badge: 'SAVE 15%' },
            { label: 'Annually', value: 2 as const, badge: 'SAVE 17%' },
          ].map((plan) => {
            const selected = billingCycle === plan.value;

            return (
              <button
                key={plan.value}
                type="button"
                onClick={() => onBillingCycleChange(plan.value)}
                className={`relative min-h-9 rounded-lg px-2 py-2 text-[13px] font-semibold transition-colors ${selected ? 'bg-[#1a365d] text-white' : 'bg-[rgba(145,158,171,0.08)] text-gray-500'}`}
              >
                {plan.label}
                {plan.badge && (
                  <span className="absolute -right-2 -top-3 rounded-full bg-green-600 px-1.5 py-0.5 text-[9px] font-bold text-white">
                    {plan.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Target Tier Plan */}
        <div className="mb-2 overflow-visible rounded-xl border border-gray-100 bg-white shadow-sm">
          <div
            className="relative p-5 text-white"
            style={{ background: targetTierStyle.gradient }}
          >
            <span className="absolute right-2.5 top-2.5 rounded-full bg-[#ff6b35] px-2 py-0.5 text-[10px] font-bold text-white">
              Best Value
            </span>
            <div className="mb-1 flex items-center gap-1">
              <LucideIcon name={targetTierStyle.icon} size={20} />
              <p className="text-sm font-bold capitalize">
                {targetTier}
              </p>
            </div>
            <p className="text-4xl font-extrabold leading-none">
              ${currentPricing[targetTier as keyof typeof currentPricing]?.price || 0}
              <span className="ml-0.5 text-xs font-medium">
                {currentPricing[targetTier as keyof typeof currentPricing]?.billing || '/month'}
              </span>
            </p>
            {('total' in currentPricing[targetTier as keyof typeof currentPricing]) && (
              <p className="text-xs opacity-80">
                ${(currentPricing[targetTier as keyof typeof currentPricing] as any).total} billed {currentPlanType}
              </p>
            )}
          </div>
          <div className="p-4">
            <div className="space-y-2">
              {targetFeatures.map((feature, idx) => (
                <div key={idx} className="flex items-start gap-2 py-0.5">
                  <div className="min-w-7 pt-0.5">
                    <LucideIcon name="CircleCheck" size={16} color="#4caf50" />
                  </div>
                  <p className="text-xs text-gray-500">{feature}</p>
                </div>
              ))}
            </div>
            {sourceFeatures.length > 0 && (
              <div className="mt-3 rounded-lg bg-gray-50 p-3">
                <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-gray-500">
                  Current Plan Includes
                </p>
                <p className="text-xs text-gray-500">
                  {sourceFeatures.slice(0, 3).join(' • ')}
                </p>
              </div>
            )}
            <Button
              type="button"
              fullWidth
              onClick={onConfirm}
              disabled={loading}
              className="mt-1.5 bg-[#ff6b35] font-bold hover:bg-[#ff5722]"
            >
              {loading ? 'Upgrading...' : `Upgrade to ${targetTier.charAt(0).toUpperCase() + targetTier.slice(1)}`}
            </Button>
          </div>
        </div>

        {/* Info Box */}
        <div className="flex gap-1.5 rounded-xl bg-[rgba(24,144,255,0.08)] p-4">
          <LucideIcon name="Info" size={20} color="#2196f3" style={{ flexShrink: 0, marginTop: 2 }} />
          <p className="text-xs text-sky-600">
            You can upgrade your plan at any time. Your new benefits will take effect immediately, and you'll be prorated for the current billing cycle.
          </p>
        </div>
      </ModalContent>
    </Modal>
  );
}
