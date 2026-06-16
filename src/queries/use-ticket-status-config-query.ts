import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { constants } from 'src/constants.value';
import { getConfigData } from 'src/utils/api-service';
import { TicketStatusConfigItem } from 'src/common-service/types.interface';
import { queryKeys } from './query-keys';

export function useTicketStatusConfigQuery(enabled: boolean) {
  const query = useQuery({
    queryKey: queryKeys.ticketStatusConfig,
    queryFn: async (): Promise<TicketStatusConfigItem[]> => {
      const response = await getConfigData('ticket_status');
      if (response?.StatusCode !== constants.RESPONSE_STATUS.SUCCESS || !Array.isArray(response?.Result)) {
        throw new Error(response?.Message || 'Failed to load ticket statuses');
      }
      return response.Result as TicketStatusConfigItem[];
    },
    enabled,
    staleTime: 1000 * 60 * 60,
  });

  const sortedData = useMemo(
    () => (query.data || []).slice().sort((a: any, b: any) => a.displayOrder - b.displayOrder),
    [query.data]
  );

  return {
    ...query,
    data: sortedData,
  };
}
