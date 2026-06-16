import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';

import { cn } from 'src/lib/utils';

const buttonVariants = cva(
  'inline-flex items-center justify-center rounded-pill text-sm font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        primary: 'bg-brand-600 text-white shadow-card hover:bg-brand-700',
        secondary: 'border border-white/20 bg-white text-brand-600 hover:bg-slate-50',
        ghost: 'bg-transparent text-white hover:bg-white/10',
        danger: 'bg-[#ec1c24] text-white hover:bg-[#c7161d]',
      },
      size: {
        sm: 'h-9 px-4',
        md: 'h-11 px-5',
        lg: 'h-12 px-6',
        icon: 'h-10 w-10',
      },
      fullWidth: {
        true: 'w-full',
        false: '',
      },
    },
    defaultVariants: {
      variant: 'primary',
      size: 'md',
      fullWidth: false,
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export function Button({
  className,
  variant,
  size,
  fullWidth,
  asChild = false,
  ...props
}: ButtonProps) {
  const Comp = asChild ? Slot : 'button';

  return (
    <Comp className={cn(buttonVariants({ variant, size, fullWidth }), className)} {...props} />
  );
}

export { buttonVariants };