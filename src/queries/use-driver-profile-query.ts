import { useQuery } from '@tanstack/react-query';
import { constants } from 'src/constants.value';
import { GetDriverProfile } from 'src/routes/index.service';
import { queryKeys } from './query-keys';

export function useDriverProfileQuery(enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.driverProfile,
    queryFn: async () => {
      const response = await GetDriverProfile();
      if (response?.StatusCode !== constants.RESPONSE_STATUS.SUCCESS || !response?.Result?.data) {
        throw new Error(response?.Message || 'Failed to load profile');
      }
      return response.Result.data;
    },
    enabled,
    staleTime: 1000 * 60 * 10,
  });
}
