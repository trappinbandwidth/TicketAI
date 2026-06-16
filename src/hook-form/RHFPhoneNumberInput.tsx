import * as React from 'react';
import { Controller, useFormContext } from 'react-hook-form';

import { cn } from 'src/lib/utils';

// ----------------------------------------------------------------------

type RHFPhoneNumberInputProps = Omit<React.InputHTMLAttributes<HTMLInputElement>, 'name' | 'size'> & {
  name: string;
  label?: React.ReactNode;
  helperText?: React.ReactNode;
  size?: 'small' | 'medium' | string;
  margin?: 'none' | 'dense' | 'normal' | string;
  variant?: string;
  fullWidth?: boolean;
  InputLabelProps?: Record<string, unknown>;
  inputProps?: React.InputHTMLAttributes<HTMLInputElement>;
  sx?: unknown;
};

export default function RHFPhoneNumberInput({
  name,
  label,
  helperText,
  type = 'number',
  size = 'medium',
  fullWidth = true,
  inputProps,
  className,
  ...other
}: RHFPhoneNumberInputProps) {
  const { control } = useFormContext();

  return (
    <Controller
      name={name}
      control={control}
      render={({ field, fieldState: { error } }) => (
        <div className={cn(fullWidth && 'w-full')}>
          {label ? <label className="mb-1 block text-sm font-medium text-[#1e3a5f]">{label}</label> : null}
          <div className={cn(
            'flex items-center rounded-2xl border border-slate-200 bg-white px-4 shadow-card transition focus-within:border-brand-300 focus-within:ring-2 focus-within:ring-brand-100',
            error && 'border-red-500 focus-within:border-red-500 focus-within:ring-red-100',
            className
          )}>
            <input
              {...field}
              value={field.value ?? ''}
              {...inputProps}
              {...other}
              type={type}
              inputMode="numeric"
              pattern="[0-9]*"
              className={cn(
                'w-full border-0 bg-transparent text-sm text-ink-body placeholder:text-slate-400 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50',
                size === 'small' ? 'h-10 py-2' : 'h-11 py-3'
              )}
              onWheel={(event) => {
                (event.target as HTMLInputElement).blur();
                other.onWheel?.(event);
              }}
              onKeyDown={(event) => {
                if (event.key === 'ArrowUp' || event.key === 'ArrowDown') {
                  event.preventDefault();
                }
                other.onKeyDown?.(event);
              }}
            />
          </div>
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
