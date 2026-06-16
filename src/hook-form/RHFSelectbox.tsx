import * as React from 'react';
import { Controller, useFormContext } from 'react-hook-form';

import { cn } from 'src/lib/utils';

// Type for menu items
interface MenuItemType {
  value: string | number;
  name: string;
}

type RHFSelectboxProps = Omit<React.SelectHTMLAttributes<HTMLSelectElement>, 'name'> & {
  name: string;
  label?: string;
  menus: MenuItemType[];
  cclass?: string;
  helperText?: React.ReactNode;
};

export default function RHFSelectbox({
  name,
  label,
  menus,
  cclass,
  helperText,
  onChange,
  className,
  ...other
}: RHFSelectboxProps) {
  const { control } = useFormContext();

  return (
    <Controller
      name={name}
      control={control}
      render={({ field, fieldState: { error } }) => (
        <div className={cn('my-2 w-full', cclass)}>
          {label && <label htmlFor={name} className="mb-1 block text-sm font-medium text-[#1e3a5f]">
            {label}
          </label>}
          <div className="relative">
            <select
              {...field}
              {...other}
              id={name}
              value={field.value ?? ''}
              className={cn(
                'h-11 w-full appearance-none rounded-2xl border border-slate-200 bg-white px-4 pr-10 text-sm text-ink-body shadow-card transition focus:border-brand-300 focus:outline-none focus:ring-2 focus:ring-brand-100 disabled:cursor-not-allowed disabled:opacity-50',
                !field.value && 'text-slate-400',
                error && 'border-red-500 focus:border-red-500 focus:ring-red-100',
                className
              )}
              onChange={(event) => {
                field.onChange(event.target.value);
                onChange?.(event);
              }}
            >
              <option value="" disabled>
                Please Select
              </option>
              {menus.map((item) => (
                <option key={`${item.value}-${item.name}`} value={item.value}>
                  {item.name}
                </option>
              ))}
            </select>
            <span className="pointer-events-none absolute inset-y-0 right-4 flex items-center text-slate-500">
              <svg viewBox="0 0 20 20" fill="none" className="h-4 w-4" aria-hidden="true">
                <path d="M5 7.5 10 12.5 15 7.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </span>
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
