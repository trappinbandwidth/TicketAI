import { cn } from 'src/lib/utils';

import type { LabelColor, LabelVariant } from './types';

// ----------------------------------------------------------------------

const colorStyles: Record<LabelColor, Record<LabelVariant, string>> = {
  default: {
    filled: 'bg-slate-900 text-white',
    outlined: 'border-2 border-slate-900 bg-transparent text-slate-900',
    soft: 'bg-slate-200 text-slate-600',
    inverted: 'bg-slate-300 text-slate-800',
  },
  primary: {
    filled: 'bg-brand-600 text-white',
    outlined: 'border-2 border-brand-600 bg-transparent text-brand-600',
    soft: 'bg-brand-100 text-brand-700',
    inverted: 'bg-brand-50 text-brand-800',
  },
  secondary: {
    filled: 'bg-slate-700 text-white',
    outlined: 'border-2 border-slate-700 bg-transparent text-slate-700',
    soft: 'bg-slate-100 text-slate-700',
    inverted: 'bg-slate-200 text-slate-800',
  },
  info: {
    filled: 'bg-sky-600 text-white',
    outlined: 'border-2 border-sky-600 bg-transparent text-sky-600',
    soft: 'bg-sky-100 text-sky-700',
    inverted: 'bg-sky-50 text-sky-800',
  },
  success: {
    filled: 'bg-emerald-600 text-white',
    outlined: 'border-2 border-emerald-600 bg-transparent text-emerald-600',
    soft: 'bg-emerald-100 text-emerald-700',
    inverted: 'bg-emerald-50 text-emerald-800',
  },
  warning: {
    filled: 'bg-amber-500 text-white',
    outlined: 'border-2 border-amber-500 bg-transparent text-amber-600',
    soft: 'bg-amber-100 text-amber-700',
    inverted: 'bg-amber-50 text-amber-800',
  },
  error: {
    filled: 'bg-red-600 text-white',
    outlined: 'border-2 border-red-600 bg-transparent text-red-600',
    soft: 'bg-red-100 text-red-700',
    inverted: 'bg-red-50 text-red-800',
  },
};

export function getLabelClasses(color: LabelColor, variant: LabelVariant) {
  return cn(
    'inline-flex min-h-6 min-w-6 items-center justify-center whitespace-nowrap rounded-lg px-1.5 text-xs font-bold transition-colors',
    colorStyles[color][variant]
  );
}
