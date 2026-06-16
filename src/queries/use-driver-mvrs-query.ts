import { useInfiniteQuery } from '@tanstack/react-query';
import { constants } from 'src/constants.value';
import { getDriverMVRs } from 'src/utils/api-service';
import { queryKeys } from './query-keys';

export interface DriverMvrsResponseData {
  mvrs: any[];
  pagination?: {
    hasMore?: boolean;
    lastId?: string;
    lastCreatedDate?: string;
  };
}

export function useInfiniteDriverMvrsQuery(enabled: boolean, pageSize = 20) {
  return useInfiniteQuery({
    queryKey: queryKeys.driverMvrsInfinite(pageSize),
    initialPageParam: { lastId: undefined as string | undefined, lastCreatedDate: undefined as string | undefined },
    queryFn: async ({ pageParam }): Promise<DriverMvrsResponseData> => {
      const response = await getDriverMVRs(pageSize, pageParam.lastId, pageParam.lastCreatedDate);
      if (response?.StatusCode !== constants.RESPONSE_STATUS.SUCCESS || !response?.Result?.data) {
        throw new Error(response?.Message || 'Failed to load MVRs');
      }
      return response.Result.data as DriverMvrsResponseData;
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
