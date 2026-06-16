import { useMutation, useQueryClient } from '@tanstack/react-query';
import { ManagePaymentMethodRequest } from 'src/common-service/types.interface';
import { manageDriverPaymentMethod } from 'src/utils/api-service';
import { queryKeys } from './query-keys';

function updatePaymentMethodsCache(
  previousData: any,
  updater: (methods: any[]) => any[]
) {
  if (!previousData?.Result?.data?.paymentMethods) {
    return previousData;
  }

  const nextMethods = updater(previousData.Result.data.paymentMethods);

  return {
    ...previousData,
    Result: {
      ...previousData.Result,
      data: {
        ...previousData.Result.data,
        paymentMethods: nextMethods,
      },
    },
  };
}

export function useSetDefaultPaymentMethodMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationKey: ['mutation', 'set-default-payment-method'],
    mutationFn: async (paymentMethodId: string) => {
      return manageDriverPaymentMethod({ action: 'setDefault', paymentMethodId });
    },
    onMutate: async (paymentMethodId) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.driverPaymentMethods });
      const previousData = queryClient.getQueryData(queryKeys.driverPaymentMethods);

      queryClient.setQueryData(queryKeys.driverPaymentMethods, (old: any) =>
        updatePaymentMethodsCache(old, (methods) =>
          methods.map((method) => ({
            ...method,
            isDefault: method.id === paymentMethodId,
          }))
        )
      );

      return { previousData };
    },
    onError: (_error, _variables, context) => {
      if (context?.previousData) {
        queryClient.setQueryData(queryKeys.driverPaymentMethods, context.previousData);
      }
    },
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.driverPaymentMethods });
    },
  });
}

export function useDeletePaymentMethodMutation() {
  return useMutation({
    mutationKey: ['mutation', 'delete-payment-method'],
    mutationFn: async (paymentMethodId: string) => {
      return manageDriverPaymentMethod({ action: 'delete', paymentMethodId });
    },
  });
}

export function useCreatePaymentMethodMutation() {
  return useMutation({
    mutationKey: ['mutation', 'create-payment-method'],
    mutationFn: async (payload: ManagePaymentMethodRequest) => {
      return manageDriverPaymentMethod(payload);
    },
  });
}
