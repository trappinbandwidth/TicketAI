import { useState } from 'react';
import { upgradeMembership } from 'src/utils/api-service';

export const useUpgradeModal = (sourceTier: string, targetTier: string) => {
  const [isOpen, setIsOpen] = useState(false);
  const [billingCycle, setBillingCycle] = useState<0 | 1 | 2>(0); // 0: monthly, 1: quarterly, 2: annually
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const openUpgradeModal = () => {
    setIsOpen(true);
    setError(null);
  };

  const closeUpgradeModal = () => {
    setIsOpen(false);
    setError(null);
    setBillingCycle(0);
  };

  const confirmUpgrade = async () => {
    setLoading(true);
    setError(null);

    try {
      const cycles = ['monthly', 'quarterly', 'annually'] as const;
      const cycle = cycles[billingCycle];
      
      const response = await upgradeMembership(sourceTier, targetTier, cycle);
      
      if (response?.Result?.success || response?.success) {
        closeUpgradeModal();
      } else {
        setError(response?.Result?.message || response?.message || 'Upgrade failed. Please try again.');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred during upgrade.');
    } finally {
      setLoading(false);
    }
  };

  return {
    isOpen,
    billingCycle,
    loading,
    error,
    openUpgradeModal,
    closeUpgradeModal,
    setBillingCycle,
    confirmUpgrade,
  };
};
