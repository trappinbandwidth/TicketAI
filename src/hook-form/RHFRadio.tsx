import { useFormContext, Controller } from 'react-hook-form';
import { cn } from 'src/lib/utils';

// Type for RadioOption
interface RadioOption {
  value: string | number;
  name: React.ReactNode;
}

type RHFRadioProps = {
  name: string;
  title: string;
  options: RadioOption[];
  handleChange?: (event: React.ChangeEvent<HTMLInputElement>, value: string) => void;
  disabled?: boolean;
  className?: string;
  optionClassName?: string;
  sx?: unknown;
};

export default function RHFRadio({
  name,
  title,
  options,
  handleChange,
  disabled,
  className,
  optionClassName,
}: RHFRadioProps) {
  const { control } = useFormContext();

  return (
    <Controller
      name={name}
      control={control}
      render={({ field, fieldState: { error } }) => (
        <div>
          <p
            id={`${name}-label`}
            className={cn('mt-2.5 font-medium', error ? 'text-red-600' : 'text-black')}
          >
            {title}
          </p>
          <div
            role="radiogroup"
            aria-labelledby={`${name}-label`}
            className={cn('flex flex-row gap-2 justify-start', className)}
          >
            {options.map((item) => {
              const checked = String(field.value) === String(item.value);

              return (
                <label
                  key={String(item.value)}
                  className={cn(
                    'flex cursor-pointer items-start gap-3 rounded-2xl border border-slate-200 p-4 transition-all',
                    checked && 'border-[#1a365d] bg-[rgba(26,54,93,0.02)]',
                    disabled && 'cursor-not-allowed opacity-60',
                    optionClassName
                  )}
                >
                  <input
                    type="radio"
                    name={field.name}
                    value={String(item.value)}
                    checked={checked}
                    disabled={disabled}
                    onBlur={field.onBlur}
                    onChange={(event) => {
                      field.onChange(event.target.value);
                      handleChange?.(event, event.target.value);
                    }}
                    className="mt-1 h-4 w-4 border-slate-300 text-[#1a365d] focus:ring-2 focus:ring-brand-200"
                  />
                  <span className={cn('block', checked && 'font-semibold')}>
                    {item.name}
                  </span>
                </label>
              );
            })}
          </div>
          {error && <p className="mt-1 text-sm text-red-600">{error.message}</p>}
        </div>
      )}
    />
  );
}
