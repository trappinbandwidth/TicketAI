import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { constants } from 'src/constants.value';
import { GetMenuItems } from 'src/utils/api-service';
import { queryKeys } from './query-keys';

export interface MenuItemData {
  label: string;
  route: string;
  isActive: boolean;
  title?: string;
  path?: string;
}

export function useMenuItemsQuery(enabled: boolean) {
  const query = useQuery({
    queryKey: queryKeys.menuItems,
    queryFn: async (): Promise<MenuItemData[]> => {
      const response = await GetMenuItems();
      if (response?.StatusCode !== constants.RESPONSE_STATUS.SUCCESS) {
        throw new Error(response?.Message || 'Failed to load menu');
      }
      return (response?.Result || []) as MenuItemData[];
    },
    enabled,
    staleTime: 1000 * 60 * 60,
  });

  const activeItems = useMemo(
    () => (query.data || []).filter((item) => item.isActive),
    [query.data]
  );

  return {
    ...query,
    data: activeItems,
  };
}
