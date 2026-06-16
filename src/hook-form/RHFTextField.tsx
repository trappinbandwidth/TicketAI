import * as React from 'react';
import { Controller, useFormContext } from 'react-hook-form';

import { cn } from 'src/lib/utils';

// ----------------------------------------------------------------------

type RHFTextFieldProps = Omit<React.InputHTMLAttributes<HTMLInputElement>, 'name' | 'size'> & {
  name: string;
  label?: React.ReactNode;
  helperText?: React.ReactNode;
  handleChange?: (event: React.ChangeEvent<HTMLInputElement>) => void;
  maxLength?: number;
  multiline?: boolean;
  rows?: number;
  size?: 'small' | 'medium' | string;
  margin?: 'none' | 'dense' | 'normal' | string;
  variant?: string;
  fullWidth?: boolean;
  sx?: unknown;
  InputLabelProps?: Record<string, unknown>;
  InputProps?: {
    startAdornment?: React.ReactNode;
    endAdornment?: React.ReactNode;
  };
  inputProps?: React.InputHTMLAttributes<HTMLInputElement> &
    React.TextareaHTMLAttributes<HTMLTextAreaElement> & {
      startAdornment?: React.ReactNode;
      startadornment?: React.ReactNode;
      endAdornment?: React.ReactNode;
      endadornment?: React.ReactNode;
    };
};

// ----------------------------------------------------------------------

export default function RHFTextField({
  name,
  handleChange,
  maxLength,
  label,
  helperText,
  type = 'text',
  size = 'medium',
  fullWidth = true,
  InputProps,
  inputProps,
  multiline = false,
  rows = 4,
  className,
  onBlur,
  onChange,
  ...other
}: RHFTextFieldProps) {
  const { control } = useFormContext();
  const startAdornment = InputProps?.startAdornment ?? inputProps?.startAdornment ?? inputProps?.startadornment;
  const endAdornment = InputProps?.endAdornment ?? inputProps?.endAdornment ?? inputProps?.endadornment;
  const inputClassName = cn(
    'rhf-text-field-input min-w-0 flex-1 border-0 bg-transparent text-sm text-ink-body placeholder:text-slate-400 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50',
    multiline ? 'min-h-[112px] resize-y py-3' : size === 'small' ? 'h-10 py-2' : 'h-11 py-3'
  );
  const wrapperClassName = cn(
    'rhf-text-field-control flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-4 text-ink-body shadow-card transition focus-within:border-brand-300 focus-within:ring-2 focus-within:ring-brand-100',
    multiline && 'items-start',
    !fullWidth && 'w-auto',
    className
  );

  return (
    <Controller
      name={name}
      control={control}
      render={({ field, fieldState: { error } }) => (
        <div className={cn(fullWidth && 'w-full')}>
          {label ? <label className="mb-1 block text-sm font-medium text-[#1e3a5f]">{label}</label> : null}
          <div className={cn(wrapperClassName, error && 'border-red-500 focus-within:border-red-500 focus-within:ring-red-100')}>
            {startAdornment ? <div className="shrink-0 text-slate-500">{startAdornment}</div> : null}
            {multiline ? (
              <textarea
                name={field.name}
                value={field.value ?? ''}
                rows={rows}
                onBlur={(event) => {
                  field.onBlur();
                    onBlur?.(event as unknown as React.FocusEvent<HTMLInputElement>);
                }}
                onChange={(event) => {
                  field.onChange(event.target.value);
                  onChange?.(event as unknown as React.ChangeEvent<HTMLInputElement>);
                  handleChange?.(event as unknown as React.ChangeEvent<HTMLInputElement>);
                }}
                className={inputClassName}
                maxLength={maxLength}
                autoComplete={type === 'password' ? 'new-password' : inputProps?.autoComplete}
                {...(inputProps as Omit<React.TextareaHTMLAttributes<HTMLTextAreaElement>, 'startAdornment' | 'startadornment' | 'endAdornment' | 'endadornment'>)}
                {...(other as React.TextareaHTMLAttributes<HTMLTextAreaElement>)}
              />
            ) : (
              <input
                {...field}
                value={field.value ?? ''}
                type={type}
                onBlur={(event) => {
                  field.onBlur();
                  onBlur?.(event);
                }}
                onChange={(event) => {
                  field.onChange(event.target.value);
                  onChange?.(event);
                  handleChange?.(event);
                }}
                className={inputClassName}
                maxLength={maxLength}
                autoComplete={type === 'password' ? 'new-password' : inputProps?.autoComplete}
                {...(inputProps as Omit<React.InputHTMLAttributes<HTMLInputElement>, 'startAdornment' | 'startadornment' | 'endAdornment' | 'endadornment'>)}
                {...other}
              />
            )}
            {endAdornment ? <div className="shrink-0 text-slate-500">{endAdornment}</div> : null}
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
