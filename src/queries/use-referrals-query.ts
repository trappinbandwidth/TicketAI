import { useInfiniteQuery } from '@tanstack/react-query';
import { constants } from 'src/constants.value';
import { getReferrals } from 'src/utils/api-service';
import { queryKeys } from './query-keys';

export interface ReferralsResponseData {
  referrals: any[];
  pagination?: {
    hasMore?: boolean;
    lastId?: string;
    lastCreatedDate?: string;
    totalCount?: number;
  };
}

export function useInfiniteReferralsQuery(enabled: boolean, pageSize = 20) {
  return useInfiniteQuery({
    queryKey: queryKeys.referralsInfinite(pageSize),
    initialPageParam: { lastId: undefined as string | undefined, lastCreatedDate: undefined as string | undefined },
    queryFn: async ({ pageParam }): Promise<ReferralsResponseData> => {
      const response = await getReferrals(pageSize, pageParam.lastId, pageParam.lastCreatedDate);
      if (response?.StatusCode !== constants.RESPONSE_STATUS.SUCCESS || !response?.Result?.data) {
        throw new Error(response?.Message || 'Failed to load referrals');
      }
      return response.Result.data as ReferralsResponseData;
    },
    getNextPageParam: (lastPage) => {
      if (!lastPage?.pagination?.hasMore) {
        return undefined;
      }
      return {
        lastId: lastPage.pagination?.lastId,
        lastCreatedDate: lastPage.pagination?.lastCreatedDate,
      };
    },
    enabled,
    staleTime: 1000 * 60 * 5,
  });
}
