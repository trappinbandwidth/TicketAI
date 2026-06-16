import { useMutation, useQueryClient } from '@tanstack/react-query';
import { CompleteDriverProfile, UpdateDriverProfile } from 'src/routes/index.service';
import { queryKeys } from './query-keys';

interface UpdateDriverProfilePayload {
  email: string;
  mobilePhone: string;
  birthdate: string;
  address: {
    street: string;
    apt?: string;
    city: string;
    state: string;
    stateCode?: string;
    zipCode: string;
  };
}

interface CompleteDriverProfilePayload {
  firstName: string;
  lastName: string;
  email: string;
  phone: string;
  mobilePhone: string;
  birthdate: string;
  address: {
    street: string;
    apt?: string;
    city: string;
    state: string;
    stateCode?: string;
    zipCode: string;
    country: string;
  };
  // licenseInformation: {
  //   cdlNumber: string;
  //   cdlState: string;
  // };
  licenseInformation?: {
    cdlNumber: string;
    cdlState: string;
  };
}

function syncDriverProfileCache(queryClient: ReturnType<typeof useQueryClient>, response: any) {
  if (!response?.Result?.data) {
    return;
  }

  queryClient.setQueryData(queryKeys.driverProfile, (oldData: any) => ({
    ...(oldData || {}),
    ...response.Result.data,
  }));
}

export function useUpdateDriverProfileMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationKey: ['mutation', 'update-driver-profile'],
    mutationFn: async (payload: UpdateDriverProfilePayload) => {
      return UpdateDriverProfile(payload);
    },
    onSuccess: (response) => {
      syncDriverProfileCache(queryClient, response);
    },
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.driverProfile });
    },
  });
}

export function useCompleteDriverProfileMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationKey: ['mutation', 'complete-driver-profile'],
    mutationFn: async (payload: CompleteDriverProfilePayload) => {
      return CompleteDriverProfile(payload);
    },
    onSuccess: (response) => {
      syncDriverProfileCache(queryClient, response);
    },
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.driverProfile });
    },
  });
}
