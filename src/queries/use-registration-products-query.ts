import { useQuery } from '@tanstack/react-query';
import { constants } from 'src/constants.value';
import { getRegistrationProducts } from 'src/utils/api-service';
import { queryKeys } from './query-keys';

export interface RegistrationPlan {
  tierCode: string;
  tier: string;
  name: string;
  id: string;
  frequency: string;
  displayOrder: number;
  discountPercent: number;
  discountAmount: number;
  benefits: string[];
  amount: number;
}

export interface RegistrationFrequency {
  savingsPercent: number | null;
  savingsBadge: string | null;
  label: string;
  key: string;
}

export interface RegistrationProductsResult {
  plans: RegistrationPlan[];
  frequencies: RegistrationFrequency[];
}

export function useRegistrationProductsQuery(enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.registrationProducts,
    queryFn: async (): Promise<RegistrationProductsResult> => {
      const response = await getRegistrationProducts();
      if (response?.StatusCode !== constants.RESPONSE_STATUS.SUCCESS || !response?.Result) {
        throw new Error(response?.Message || 'Failed to load plans');
      }
      return response.Result as RegistrationProductsResult;
    },
    enabled,
    staleTime: 1000 * 60 * 30,
  });
}
