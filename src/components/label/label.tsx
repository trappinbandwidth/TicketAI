import { forwardRef } from 'react';

import { cn } from 'src/lib/utils';

import { getLabelClasses } from './styles';
import { labelClasses } from './classes';

import type { LabelProps } from './types';

// ----------------------------------------------------------------------

export const Label = forwardRef<HTMLSpanElement, LabelProps>(
  (
    { children, color = 'default', variant = 'soft', startIcon, endIcon, sx, className, ...other },
    ref
  ) => {
    return (
      <span
        ref={ref}
        className={cn(
          labelClasses.root,
          getLabelClasses(color, variant),
          startIcon && 'pl-2',
          endIcon && 'pr-2',
          className
        )}
        style={sx}
        {...other}
      >
        {startIcon && (
          <span className={cn(labelClasses.icon, 'mr-1.5 inline-flex h-4 w-4 items-center justify-center [&_img]:h-full [&_img]:w-full [&_img]:object-cover [&_svg]:h-full [&_svg]:w-full')}>
            {startIcon}
          </span>
        )}

        {typeof children === 'string' ? sentenceCase(children) : children}

        {endIcon && (
          <span className={cn(labelClasses.icon, 'ml-1.5 inline-flex h-4 w-4 items-center justify-center [&_img]:h-full [&_img]:w-full [&_img]:object-cover [&_svg]:h-full [&_svg]:w-full')}>
            {endIcon}
          </span>
        )}
      </span>
    );
  }
);

// ----------------------------------------------------------------------

function sentenceCase(string: string): string {
  return string.charAt(0).toUpperCase() + string.slice(1);
}
