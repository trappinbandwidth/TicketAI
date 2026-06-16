import { useQuery } from '@tanstack/react-query';
import { constants } from 'src/constants.value';
import { getFiles } from 'src/routes/index.service';

export function useFilesQuery(enabled: boolean, bucketName: string, folderName: string) {
  return useQuery({
    queryKey: ['files', bucketName, folderName],
    queryFn: async () => {
      const response = await getFiles({ bucketName, folderName });
      if (response?.StatusCode !== constants.RESPONSE_STATUS.SUCCESS) {
        throw new Error(response?.Message || 'Failed to load files');
      }
      return response?.Result?.files || [];
    },
    enabled,
    staleTime: 1000 * 60 * 5,
  });
}
