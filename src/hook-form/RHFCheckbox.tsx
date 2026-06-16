import * as React from 'react';
import { Controller, useFormContext } from 'react-hook-form';

import { cn } from 'src/lib/utils';

// ----------------------------------------------------------------------

type RHFCheckboxProps = {
  name: string;
  label?: React.ReactNode;
  className?: string;
  checkboxProps?: React.InputHTMLAttributes<HTMLInputElement>;
  helperText?: React.ReactNode;
};

export function RHFCheckbox({ name, label, className, checkboxProps, helperText }: RHFCheckboxProps) {
  const { control } = useFormContext();

  return (
    <Controller
      name={name}
      control={control}
      render={({ field, fieldState: { error } }) => (
        <div>
          <label className={cn('flex cursor-pointer items-center gap-3 select-none', className)}>
            <input
              {...field}
              {...checkboxProps}
              type="checkbox"
              checked={Boolean(field.value)}
              value={undefined}
              onChange={(event) => field.onChange(event.target.checked)}
              className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-2 focus:ring-brand-200"
            />
            {label ? <span className="text-sm text-slate-700">{label}</span> : null}
          </label>
          {(error?.message || helperText) && (
            <p className={cn('mt-1 text-sm', error ? 'text-red-600' : 'text-slate-500')}>
              {error?.message || helperText}
            </p>
          )}
        </div>
      )}
    />
  );
}

// ----------------------------------------------------------------------

interface CheckboxOption {
  value: string | number;
  label: string;
  category_url?: string;
}

type RHFMultiCheckboxProps = {
  name: string;
  options: CheckboxOption[];
  title: string;
  formControlLabelProps?: {
    className?: string;
  };
};

export function RHFMultiCheckbox({
  name,
  options,
  title,
  formControlLabelProps,
}: RHFMultiCheckboxProps) {
  const { control } = useFormContext();

  return (
    <Controller
      name={name}
      control={control}
      render={({ field, fieldState: { error } }) => {
        const onToggle = (option: CheckboxOption) => {
          const currentValue = field.value ?? [];
          const foundIndex = currentValue.findIndex(
            (item: CheckboxOption) => item.value === option.value
          );

          if (foundIndex !== -1) {
            return currentValue.filter(
              (value: CheckboxOption) => value.value !== option.value
            );
          }
          return [...currentValue, option];
        };

        return (
          <div>
            <p
              id={`${name}-label`}
              className={cn('mt-2.5 font-medium', error ? 'text-red-600' : 'text-black')}
            >
              {title}
            </p>
            <div className="mb-2.5 grid max-h-[250px] grid-cols-2 items-center gap-y-2 overflow-y-auto sm:grid-cols-4">
              {options?.map((option) => (
                <label
                  key={option.value}
                  className={cn('flex w-fit cursor-pointer items-center gap-2 select-none', formControlLabelProps?.className)}
                >
                  <input
                    type="checkbox"
                    checked={(field.value ?? []).some(
                      (item: CheckboxOption) => item.value === option.value
                    )}
                    onChange={() => field.onChange(onToggle(option))}
                    className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-2 focus:ring-brand-200"
                  />
                  <span className="flex items-center gap-1.5 text-sm text-slate-700">
                    {option.category_url && (
                      <img
                        alt={option.label}
                        src={option.category_url}
                        className="h-[30px] w-[30px] rounded-full object-cover"
                      />
                    )}
                    {option.label}
                  </span>
                </label>
              ))}
            </div>
            {error && <p className="text-sm text-red-600">{error.message}</p>}
          </div>
        );
      }}
    />
  );
}
