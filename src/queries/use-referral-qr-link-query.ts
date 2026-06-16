import { useQuery } from '@tanstack/react-query';
import { constants } from 'src/constants.value';
import { getReferralQrLink } from 'src/utils/api-service';
import { queryKeys } from './query-keys';

export function useReferralQrLinkQuery(enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.referralQrLink,
    queryFn: async (): Promise<string> => {
      const response = await getReferralQrLink();
      if (response?.StatusCode !== constants.RESPONSE_STATUS.SUCCESS || !response?.Result?.ReferralQrLink) {
        throw new Error(response?.Message || 'Failed to load referral QR link');
      }
      return response.Result.ReferralQrLink as string;
    },
    enabled,
    staleTime: 1000 * 60 * 30,
  });
}
