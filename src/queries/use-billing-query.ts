import { useQuery } from '@tanstack/react-query';
import { constants } from 'src/constants.value';
import { getDriverPaymentMethodStatus, getDriverPaymentMethods, getDriverTransactions, GetSessionStatus } from 'src/utils/api-service';
import { queryKeys } from './query-keys';

export function useDriverPaymentMethodsQuery(enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.driverPaymentMethods,
    queryFn: async () => {
      const response = await getDriverPaymentMethods();
      if (response?.StatusCode !== constants.RESPONSE_STATUS.SUCCESS) {
        throw new Error(response?.Message || 'Failed to load payment methods');
      }
      return response;
    },
    enabled,
    staleTime: 1000 * 60 * 2,
  });
}

export function useDriverTransactionsQuery(enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.driverTransactions,
    queryFn: async () => {
      const response = await getDriverTransactions();
      if (response?.StatusCode !== constants.RESPONSE_STATUS.SUCCESS) {
        throw new Error(response?.Message || 'Failed to load transactions');
      }
      return response;
    },
    enabled,
    staleTime: 1000 * 60 * 2,
  });
}

export async function fetchDriverPaymentMethodStatusQuery(paymentMethodId: string, operationType: string) {
  const response = await getDriverPaymentMethodStatus(paymentMethodId, operationType);
  if (response?.StatusCode !== constants.RESPONSE_STATUS.SUCCESS) {
    throw new Error(response?.Message || 'Failed to check payment method status');
  }
  return response?.Result?.data;
}

export function useSessionStatusQuery(sessionId?: string) {
  return useQuery({
    queryKey: queryKeys.sessionStatus(sessionId || ''),
    queryFn: async () => {
      const response = await GetSessionStatus(sessionId || '');
      return response;
    },
    enabled: Boolean(sessionId),
    staleTime: 1000 * 30,
  });
}
