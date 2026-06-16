import * as Yup from 'yup';
import { useState, useCallback, useMemo, memo, useEffect } from 'react';

import LucideIcon from 'src/components/lucide-icon';
import { FormProvider, RHFTextField } from 'src/hook-form';
import { Button } from 'src/components/ui';
import { useForm } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import { usePathname, useRouter } from 'src/routes/hooks';
import { cn } from 'src/lib/utils';

// ----------------------------------------------------------------------

interface SearchbarProps extends React.HTMLAttributes<HTMLDivElement> {
  isOpen?: boolean;
  sx?: React.CSSProperties;
}

const Searchbar = ({ sx, isOpen, className, ...other }: SearchbarProps) => {
  const router = useRouter();
  const path = usePathname();
  const [open, setOpen] = useState(isOpen || false);

  const handleOpen = useCallback(() => {
    setOpen((prev) => !prev);
  }, []);

  const formSchema = Yup.object().shape({
    Search: Yup.string(),
  });
  const defaultValues = {
    Search: '',
  };
  const methods = useForm({
    resolver: yupResolver(formSchema),
    defaultValues,
    mode: 'onChange',
  });

  const {
    handleSubmit,
    reset,
    watch,
    formState: { isValid, isLoading: _isLoading },
  } = methods;

  useEffect(() => {
    if (path.includes('global-search')) {
      reset({ Search: decodeURIComponent(path.split('/').pop() || '') });
    } else {
      reset({ Search: '' });
    }
  }, [path]);

  const handleClose = useCallback(() => {
    reset();
    setOpen(false);
  }, []);

  const onSubmit = (values: any) => {
    // router.push(`/customerportal/global-search/${values.Search}`);
    handleClose();
  };
  const memoizedSearchField = useMemo(
    () => (
      <RHFTextField
        required
        name="Search"
        autoFocus={!isOpen}
        placeholder="Search…"
        label=""
        type="text"
        inputProps={{
          startadornment: (
            <span className="flex items-center">
              <LucideIcon name="Search" size={20} color="#9e9e9e" />
            </span>
          ),
        }}
      />
    ),
    [isOpen]
  );

  return (
    <div className={className}>
      {!open && !isOpen && (
        <button
          type="button"
          onClick={handleOpen}
          className="inline-flex h-10 w-10 items-center justify-center rounded-full transition hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/40"
        >
          <LucideIcon name="Search" size={24} />
        </button>
      )}

      {!isOpen ? (
        <FormProvider onSubmit={handleSubmit(onSubmit)} methods={methods}>
          {open ? (
            <div
              className={cn(
                'absolute left-0 top-0 z-[99] flex w-full items-center gap-3 border-b border-slate-200 bg-white/90 px-3 py-3 shadow-lg backdrop-blur md:px-5',
                className
              )}
              style={sx}
              {...other}
            >
              {memoizedSearchField}
              <Button type="submit" disabled={!isValid || watch('Search') === ''}>
                Search
              </Button>
              <button
                type="button"
                onClick={handleOpen}
                className="inline-flex h-10 w-10 items-center justify-center rounded-full transition hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/40"
              >
                <LucideIcon name="CircleX" size={24} />
              </button>
            </div>
          ) : null}
        </FormProvider>
      ) : (
        <FormProvider onSubmit={handleSubmit(onSubmit)} methods={methods}>
          {memoizedSearchField}
        </FormProvider>
      )}
    </div>
  );
};
export default memo(Searchbar);
