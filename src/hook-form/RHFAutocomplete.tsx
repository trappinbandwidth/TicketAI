import * as React from 'react';
import { Controller, useFormContext } from 'react-hook-form';

import { cn } from 'src/lib/utils';

// ----------------------------------------------------------------------

// Generic option type - can be customized based on your data
interface AutocompleteOption {
  Id?: string | number;
  Name: string;
  profilepic?: string | null;
  [key: string]: any; // Allow additional properties
}

type RHFAutocompleteProps<T extends AutocompleteOption> = {
  name: string;
  label: string;
  value?: T | T[] | string | null;
  placeholder?: boolean;
  multiple?: boolean;
  options?: T[];
  loading?: boolean;
  helperText?: string;
  disabled?: boolean;
  className?: string;
  textFieldProps?: Omit<React.InputHTMLAttributes<HTMLInputElement>, 'name' | 'label' | 'value' | 'onChange'>;
};

function getOptionKey<T extends AutocompleteOption>(option: T) {
  return String(option.Id ?? option.Name);
}

function getOptionLabel<T extends AutocompleteOption>(option: T | string | null | undefined) {
  if (!option) return '';
  return typeof option === 'string' ? option : option.Name;
}

function isSameOption<T extends AutocompleteOption>(left: T, right: T) {
  if (left.Id !== undefined && right.Id !== undefined) {
    return left.Id === right.Id;
  }

  return left.Name === right.Name;
}

export default function RHFAutocomplete<T extends AutocompleteOption = AutocompleteOption>({
  name,
  label,
  value: _value,
  placeholder = false,
  multiple = false,
  options = [],
  loading = false,
  helperText,
  disabled,
  className,
  textFieldProps,
}: RHFAutocompleteProps<T>) {
  const { control } = useFormContext();
  const [isOpen, setIsOpen] = React.useState(false);
  const [query, setQuery] = React.useState('');

  const filteredOptions = React.useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();

    if (!normalizedQuery) {
      return options;
    }

    return options.filter((option) => option.Name.toLowerCase().includes(normalizedQuery));
  }, [options, query]);

  return (
    <Controller
      name={name}
      control={control}
      render={({ field, fieldState: { error } }) => {
        const selectedValues = multiple
          ? Array.isArray(field.value)
            ? (field.value as T[])
            : []
          : [];
        const selectedOption = !multiple
          ? typeof field.value === 'string'
            ? options.find((option) => option.Name === field.value) ?? null
            : ((field.value as T | null) ?? null)
          : null;

        const visibleOptions = multiple
          ? filteredOptions.filter(
              (option) => !selectedValues.some((selectedValue) => isSameOption(selectedValue, option))
            )
          : filteredOptions;

        const inputValue = multiple
          ? query
          : query || getOptionLabel(selectedOption);

        const selectOption = (option: T) => {
          if (multiple) {
            field.onChange([...selectedValues, option]);
            setQuery('');
            setIsOpen(true);
            return;
          }

          field.onChange(option);
          setQuery('');
          setIsOpen(false);
        };

        const removeOption = (optionToRemove: T) => {
          if (!multiple) {
            field.onChange(null);
            return;
          }

          field.onChange(
            selectedValues.filter((selectedValue) => !isSameOption(selectedValue, optionToRemove))
          );
        };

        return (
          <div className={cn('relative my-2 w-full', className)}>
            <label className="mb-1 block text-sm font-medium text-[#1e3a5f]">{label}</label>

            <div
              className={cn(
                'rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-card transition focus-within:border-brand-300 focus-within:ring-2 focus-within:ring-brand-100',
                error && 'border-red-500 focus-within:border-red-500 focus-within:ring-red-100',
                disabled && 'cursor-not-allowed opacity-60'
              )}
            >
              {multiple && selectedValues.length > 0 && (
                <div className="mb-2 flex flex-wrap gap-2">
                  {selectedValues.map((option) => (
                    <button
                      key={getOptionKey(option)}
                      type="button"
                      onClick={() => removeOption(option)}
                      className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-700 transition hover:bg-slate-100"
                      disabled={disabled}
                    >
                      <span>{option.Name}</span>
                      <span aria-hidden="true">x</span>
                    </button>
                  ))}
                </div>
              )}

              <div className="flex items-center gap-2">
                <input
                  {...textFieldProps}
                  name={name}
                  disabled={disabled}
                  value={inputValue}
                  placeholder={placeholder ? label : undefined}
                  className={cn(
                    'w-full border-0 bg-transparent text-sm text-ink-body placeholder:text-slate-400 focus:outline-none',
                    textFieldProps?.className
                  )}
                  onFocus={() => setIsOpen(true)}
                  onBlur={() => {
                    window.setTimeout(() => {
                      setIsOpen(false);
                      setQuery('');
                      field.onBlur();
                    }, 120);
                  }}
                  onChange={(event) => {
                    const nextValue = event.target.value;
                    setQuery(nextValue);
                    setIsOpen(true);

                    if (!multiple && nextValue.length === 0) {
                      field.onChange(null);
                    }
                  }}
                />
                <span className="shrink-0 text-slate-500">
                  <svg viewBox="0 0 20 20" fill="none" className="h-4 w-4" aria-hidden="true">
                    <path d="M5 7.5 10 12.5 15 7.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </span>
              </div>
            </div>

            {isOpen && !disabled && (
              <div className="absolute z-20 mt-2 w-full overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xl">
                {loading ? (
                  <div className="px-4 py-3 text-sm text-slate-500">Loading...</div>
                ) : visibleOptions.length > 0 ? (
                  <ul className="max-h-64 overflow-auto py-2">
                    {visibleOptions.map((option) => {
                      const isSelected = !multiple && selectedOption ? isSameOption(selectedOption, option) : false;

                      return (
                        <li key={getOptionKey(option)}>
                          <button
                            type="button"
                            onMouseDown={(event) => {
                              event.preventDefault();
                              selectOption(option);
                            }}
                            className={cn(
                              'w-full px-4 py-3 text-left text-sm transition hover:bg-slate-50',
                              isSelected && 'bg-slate-50 font-semibold text-brand-primary'
                            )}
                          >
                            {option.Name}
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                ) : (
                  <div className="px-4 py-3 text-sm text-slate-500">No matches found</div>
                )}
              </div>
            )}

            {(error?.message || helperText) && (
              <p className={cn('mt-1 text-sm', error ? 'text-red-600' : 'text-slate-500')}>
                {error?.message || helperText}
              </p>
            )}
          </div>
        );
      }}
    />
  );
}
