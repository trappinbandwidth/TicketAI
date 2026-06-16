import { QueryClient } from '@tanstack/react-query';
import { createSyncStoragePersister } from '@tanstack/query-sync-storage-persister';
import { persistentStorage } from 'src/utils/persistentStorage';

const ONE_HOUR = 1000 * 60 * 60;
const ONE_DAY = ONE_HOUR * 24;

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: ONE_HOUR,
      gcTime: ONE_DAY,
      retry: 1,
      refetchOnWindowFocus: false,
      refetchOnReconnect: true,
    },
  },
});

export const reactQueryPersister = createSyncStoragePersister({
  storage: {
    getItem: (key: string) => persistentStorage.getItemSync(key),
    setItem: (key: string, value: string) => persistentStorage.setItemSync(key, value),
    removeItem: (key: string) => persistentStorage.removeItemSync(key),
  },
});

export const reactQueryPersistOptions = {
  persister: reactQueryPersister,
  maxAge: ONE_HOUR,
  buster: 'v1',
};
