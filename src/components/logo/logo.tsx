import { forwardRef } from 'react';

import { RouterLink } from 'src/routes/components';
import { cn } from 'src/lib/utils';

import { logoClasses } from './classes';

// ----------------------------------------------------------------------

type ResponsiveValue<T> = T | { xs?: T; sm?: T; md?: T; lg?: T; xl?: T };

type LogoSx = {
  width?: ResponsiveValue<string | number>;
  height?: ResponsiveValue<string | number>;
  marginTop?: ResponsiveValue<string | number>;
};

export type LogoProps = React.HTMLAttributes<HTMLDivElement> & {
  href?: string;
  disableLink?: boolean;
  width?: string | number;
  height?: string | number;
  sx?: LogoSx;
};

function resolveResponsiveValue<T>(value?: ResponsiveValue<T>): T | undefined {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return value as T | undefined;
  }

  const responsiveValue = value as { xs?: T; sm?: T; md?: T; lg?: T; xl?: T };

  return responsiveValue.xs ?? responsiveValue.sm ?? responsiveValue.md ?? responsiveValue.lg ?? responsiveValue.xl;
}

function resolveDimension(value?: string | number) {
  return typeof value === 'number' ? `${value}px` : value;
}

export const Logo = forwardRef<HTMLDivElement, LogoProps>(
  (
    { width, href = '/', height, disableLink = false, className, sx, ...other },
    ref
  ) => {
    const resolvedWidth = resolveDimension(width ?? resolveResponsiveValue(sx?.width) ?? '100%');
    const resolvedHeight = resolveDimension(height ?? resolveResponsiveValue(sx?.height));
    const resolvedMarginTop = resolveDimension(resolveResponsiveValue(sx?.marginTop));
    const sharedClassName = cn(logoClasses.root, 'flex max-w-full shrink-0 items-start', className);
    const sharedStyle = {
      width: resolvedWidth,
      height: resolvedHeight,
      marginTop: resolvedMarginTop,
      pointerEvents: disableLink ? 'none' : undefined,
    } as React.CSSProperties;

    const image = (
      <img
        alt="Full logo"
        src="/assets/logo.png"
        width="100%"
        height="100%"
        className="block h-full w-full object-contain"
      />
    );

    if (disableLink) {
      return (
        <div ref={ref} className={sharedClassName} aria-label="Logo" style={sharedStyle} {...other}>
          {image}
        </div>
      );
    }

    return (
      <RouterLink
        ref={ref as React.ForwardedRef<HTMLAnchorElement>}
        href={href}
        className={sharedClassName}
        aria-label="Logo"
        style={sharedStyle}
      >
        {image}
      </RouterLink>
    );
  }
);
