import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { constants } from 'src/constants.value';
import { getConfigData } from 'src/utils/api-service';
import { queryKeys } from './query-keys';

interface ViolationType {
  value: string;
  label: string;
  displayOrder: number;
}

interface ConfigDataItem {
  value: string;
  label: string;
  displayOrder: number;
}

export interface ViolationTypeOption {
  value: string;
  Name: string;
}

export interface StateOption {
  value: string;
  Name: string;
}

export function useViolationCategoryOptionsQuery(enabled: boolean) {
  const query = useQuery({
    queryKey: queryKeys.configData('violation_category'),
    queryFn: async (): Promise<ViolationType[]> => {
      const response = await getConfigData('violation_category');
      if (response?.StatusCode !== constants.RESPONSE_STATUS.SUCCESS || !response?.Result) {
        throw new Error(response?.Message || 'Failed to load violation types');
      }
      return response.Result as ViolationType[];
    },
    enabled,
    staleTime: 1000 * 60 * 60,
  });

  const options = useMemo<ViolationTypeOption[]>(() => {
    return (query.data || [])
      .slice()
      .sort((a, b) => a.displayOrder - b.displayOrder)
      .map((item) => ({
        value: item.value,
        Name: item.label,
      }));
  }, [query.data]);

  return {
    ...query,
    data: options,
  };
}

export function useTicketStateOptionsQuery(enabled: boolean) {
  const query = useQuery({
    queryKey: queryKeys.configData('ticket_state'),
    queryFn: async (): Promise<ConfigDataItem[]> => {
      const response = await getConfigData('ticket_state');
      if (response?.StatusCode !== constants.RESPONSE_STATUS.SUCCESS || !Array.isArray(response?.Result)) {
        throw new Error(response?.Message || 'Failed to load states');
      }
      return response.Result as ConfigDataItem[];
    },
    enabled,
    staleTime: 1000 * 60 * 60,
  });

  const options = useMemo<StateOption[]>(() => {
    return (query.data || [])
      .slice()
      .sort((a, b) => a.displayOrder - b.displayOrder)
      .map((item) => ({
        value: item.value || item.label,
        Name: item.label || item.value,
      }))
      .filter((item) => item.value && item.Name);
  }, [query.data]);

  return {
    ...query,
    data: options,
  };
}
