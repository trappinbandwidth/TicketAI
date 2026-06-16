import { useQuery } from '@tanstack/react-query';
import { constants } from 'src/constants.value';
import { getDriverTicketDetail } from 'src/utils/api-service';
import { queryKeys } from './query-keys';

export function useDriverTicketDetailQuery(ticketId?: string) {
  return useQuery({
    queryKey: queryKeys.driverTicketDetail(ticketId || ''),
    queryFn: async () => {
      const response = await getDriverTicketDetail(ticketId || '');
      if (response?.StatusCode !== constants.RESPONSE_STATUS.SUCCESS || !response?.Result?.data) {
        throw new Error(response?.Message || 'Failed to load ticket details');
      }
      return response.Result.data;
    },
    enabled: Boolean(ticketId),
    staleTime: 1000 * 60 * 2,
  });
}
