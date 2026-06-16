import * as React from 'react';

import { cn } from 'src/lib/utils';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(function Input(
  { className, ...props },
  ref
) {
  return (
    <input
      ref={ref}
      className={cn(
        'flex h-11 w-full rounded-2xl border border-white/20 bg-white/10 px-4 text-sm text-white placeholder:text-blue-100/80 backdrop-blur-xs transition focus:border-white/40 focus:outline-none focus:ring-2 focus:ring-white/20 disabled:cursor-not-allowed disabled:opacity-50',
        className
      )}
      {...props}
    />
  );
});