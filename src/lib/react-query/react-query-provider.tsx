import { ReactNode } from 'react';
import { PersistQueryClientProvider } from '@tanstack/react-query-persist-client';
import { queryClient, reactQueryPersistOptions } from './query-client';

interface ReactQueryProviderProps {
  children: ReactNode;
}

export function ReactQueryProvider({ children }: ReactQueryProviderProps) {
  return (
    <PersistQueryClientProvider client={queryClient} persistOptions={reactQueryPersistOptions}>
      {children}
    </PersistQueryClientProvider>
  );
}
