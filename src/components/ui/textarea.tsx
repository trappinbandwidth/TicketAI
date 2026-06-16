import * as React from 'react';

import { cn } from 'src/lib/utils';

export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {}

export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { className, ...props },
  ref
) {
  return (
    <textarea
      ref={ref}
      className={cn(
        'flex min-h-28 w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-ink-body shadow-card transition focus:border-brand-300 focus:outline-none focus:ring-2 focus:ring-brand-100 disabled:cursor-not-allowed disabled:opacity-50',
        className
      )}
      {...props}
    />
  );
});