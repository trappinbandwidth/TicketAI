import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';

import { cn } from 'src/lib/utils';

const badgeVariants = cva('inline-flex items-center rounded-pill px-2.5 py-1 text-xs font-semibold', {
  variants: {
    variant: {
      default: 'bg-brand-50 text-brand-600',
      success: 'bg-green-50 text-green-700',
      warning: 'bg-amber-50 text-amber-700',
      danger: 'bg-red-50 text-red-700',
      outline: 'border border-slate-200 bg-white text-slate-600',
    },
  },
  defaultVariants: {
    variant: 'default',
  },
});

export function Badge({
  className,
  variant,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}