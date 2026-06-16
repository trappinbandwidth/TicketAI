import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { constants } from 'src/constants.value';
import { getDriverTickets } from 'src/utils/api-service';
import { queryKeys } from './query-keys';

export interface DriverTicketsResponseData {
  tickets: any[];
  cases: any[];
  pagination?: {
    hasMore?: boolean;
    lastId?: string;
    lastCreatedDate?: string;
  };
}

export function useDriverTicketsQuery(enabled: boolean, pageSize = 20) {
  return useQuery({
    queryKey: queryKeys.driverTickets(pageSize),
    queryFn: async (): Promise<DriverTicketsResponseData> => {
      const response = await getDriverTickets(pageSize);
      if (response?.StatusCode !== constants.RESPONSE_STATUS.SUCCESS || !response?.Result?.data) {
        throw new Error(response?.Message || 'Failed to load tickets');
      }
      return response.Result.data as DriverTicketsResponseData;
    },
    enabled,
    staleTime: 1000 * 60 * 1, //
  });
}

export function useInfiniteDriverTicketsQuery(enabled: boolean, pageSize = 20) {
  return useInfiniteQuery({
    queryKey: queryKeys.driverTicketsInfinite(pageSize),
    initialPageParam: { lastId: undefined as string | undefined, lastCreatedDate: undefined as string | undefined },
    queryFn: async ({ pageParam }): Promise<DriverTicketsResponseData> => {
      const response = await getDriverTickets(pageSize, pageParam.lastId, pageParam.lastCreatedDate);
      if (response?.StatusCode !== constants.RESPONSE_STATUS.SUCCESS || !response?.Result?.data) {
        throw new Error(response?.Message || 'Failed to load tickets');
      }
      return response.Result.data as DriverTicketsResponseData;
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
    staleTime: 1000 * 60 * 3,
  });
}
