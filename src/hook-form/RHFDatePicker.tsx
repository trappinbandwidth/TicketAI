import * as React from 'react';
import { Controller, useFormContext } from 'react-hook-form';
import { format, isValid } from 'date-fns';

import { cn } from 'src/lib/utils';

// ----------------------------------------------------------------------

type RHFDatePickerProps = Omit<React.InputHTMLAttributes<HTMLInputElement>, 'name' | 'type' | 'value' | 'onChange'> & {
  name: string;
  label?: string;
  disablePast?: boolean;
  disableFuture?: boolean;
  minDate?: string | Date;
  readOnly?: boolean;
  disabledDates?: string[]; // Array of dates in 'yyyy-MM-dd' format to disable
};

function toInputDate(value: unknown) {
  if (!value) return '';

  const dateValue = value instanceof Date ? value : new Date(value as string);

  return isValid(dateValue) ? format(dateValue, 'yyyy-MM-dd') : '';
}

export default function RHFDatePicker({
  name,
  label,
  disablePast,
  disableFuture,
  readOnly,
  minDate,
  disabledDates = [],
  ...other
}: RHFDatePickerProps) {
  const { control } = useFormContext();
  const today = format(new Date(), 'yyyy-MM-dd');
  const minDateValue = minDate ? toInputDate(minDate) : undefined;

  return (
    <Controller
      name={name}
      control={control}
      render={({ field, fieldState: { error } }) => {
        const fieldValue = toInputDate(field.value);
        const minValue = disablePast ? today : minDateValue;
        const maxValue = disableFuture ? today : undefined;

        return (
          <div className="my-2 w-full">
            {label ? <label className="mb-1 block text-sm font-medium text-[#1e3a5f]">{label}</label> : null}
            <input
              {...other}
              name={field.name}
              type="date"
              value={fieldValue}
              readOnly={readOnly}
              disabled={readOnly || other.disabled}
              min={minValue}
              max={maxValue}
              className={cn(
                'h-11 w-full rounded-2xl border border-slate-200 bg-white px-4 text-sm text-ink-body shadow-card transition focus:border-brand-300 focus:outline-none focus:ring-2 focus:ring-brand-100 disabled:cursor-not-allowed disabled:opacity-50',
                error && 'border-red-500 focus:border-red-500 focus:ring-red-100'
              )}
              onBlur={field.onBlur}
              onChange={(event) => {
                const nextValue = event.target.value;

                if (!nextValue) {
                  field.onChange(null);
                  return;
                }

                if (disabledDates.length > 0 && disabledDates.includes(nextValue)) {
                  return;
                }

                field.onChange(new Date(`${nextValue}T12:00:00`));
              }}
            />
            {error?.message && <p className="mt-1 text-sm text-red-600">{error.message}</p>}
          </div>
        );
      }}
    />
  );
}
