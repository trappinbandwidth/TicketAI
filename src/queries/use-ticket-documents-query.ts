import { useQuery } from '@tanstack/react-query';
import { constants } from 'src/constants.value';
import { getTicketDocuments } from 'src/utils/api-service';
import { queryKeys } from './query-keys';

export function useTicketDocumentsQuery(ticketName?: string) {
  return useQuery({
    queryKey: queryKeys.ticketDocuments(ticketName || ''),
    queryFn: async () => {
      const response = await getTicketDocuments(ticketName || '');
      if (response?.StatusCode !== constants.RESPONSE_STATUS.SUCCESS) {
        throw new Error(response?.Message || 'Failed to load ticket documents');
      }
      return response?.Result?.files || [];
    },
    enabled: Boolean(ticketName),
    staleTime: 1000 * 60 * 2,
  });
}
