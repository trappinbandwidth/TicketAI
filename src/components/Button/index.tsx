import * as React from 'react';

import { Button } from 'src/components/ui';
import { cn } from 'src/lib/utils';

type LegacyButtonVariant = 'contained' | 'outlined' | 'text';
type LegacyButtonSize = 'small' | 'medium' | 'large';
type LegacySx = Record<string, unknown>;

type ButtonAtomProps = Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'color'> & {
    children?: React.ReactNode;
    className?: string;
    component?: React.ElementType | string;
    endIcon?: React.ReactNode;
    fullWidth?: boolean;
    href?: string;
    size?: LegacyButtonSize;
    startIcon?: React.ReactNode;
    sx?: LegacySx;
    target?: string;
    rel?: string;
    variant?: LegacyButtonVariant;
};

const COLOR_TOKENS: Record<string, string> = {
    'common.white': '#ffffff',
    'divider': '#e2e8f0',
    'grey.100': '#f1f5f9',
    'grey.200': '#e2e8f0',
    'grey.300': '#cbd5e1',
    'grey.400': '#94a3b8',
    'grey.500': '#64748b',
    'text.primary': '#0f172a',
    'text.secondary': '#64748b',
    inherit: 'inherit',
};

const BREAKPOINT_KEYS = ['xs', 'sm', 'md', 'lg', 'xl'] as const;

function resolveResponsiveValue(value: unknown): unknown {
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
        return value;
    }

    const responsiveValue = value as Record<string, unknown>;
    for (const key of BREAKPOINT_KEYS) {
        if (responsiveValue[key] !== undefined) {
            return responsiveValue[key];
        }
    }

    return value;
}

function resolveColor(value: unknown): string | undefined {
    const resolvedValue = resolveResponsiveValue(value);
    if (typeof resolvedValue === 'string') {
        return COLOR_TOKENS[resolvedValue] ?? resolvedValue;
    }
    if (typeof resolvedValue === 'number') {
        return `${resolvedValue}`;
    }
    return undefined;
}

function resolveSpacing(value: unknown): string | number | undefined {
    const resolvedValue = resolveResponsiveValue(value);
    if (typeof resolvedValue === 'number') {
        return `${resolvedValue * 8}px`;
    }
    if (typeof resolvedValue === 'string') {
        return COLOR_TOKENS[resolvedValue] ?? resolvedValue;
    }
    return undefined;
}

function resolveRadius(value: unknown): string | number | undefined {
    const resolvedValue = resolveResponsiveValue(value);
    if (typeof resolvedValue === 'number') {
        return `${resolvedValue * 8}px`;
    }
    return typeof resolvedValue === 'string' ? resolvedValue : undefined;
}

function applySx(style: React.CSSProperties, sx?: LegacySx) {
    if (!sx) {
        return style;
    }

    const nextStyle = { ...style };

    if (sx.background !== undefined) nextStyle.background = resolveColor(sx.background);
    if (sx.bgcolor !== undefined) nextStyle.backgroundColor = resolveColor(sx.bgcolor);
    if (sx.color !== undefined) nextStyle.color = resolveColor(sx.color);
    if (sx.borderColor !== undefined) nextStyle.borderColor = resolveColor(sx.borderColor);
    if (sx.borderRadius !== undefined) nextStyle.borderRadius = resolveRadius(sx.borderRadius);
    if (sx.boxShadow !== undefined) nextStyle.boxShadow = String(resolveResponsiveValue(sx.boxShadow));
    if (sx.display !== undefined) nextStyle.display = String(resolveResponsiveValue(sx.display));
    if (sx.fontSize !== undefined) nextStyle.fontSize = String(resolveResponsiveValue(sx.fontSize));
    if (sx.fontWeight !== undefined) nextStyle.fontWeight = resolveResponsiveValue(sx.fontWeight) as React.CSSProperties['fontWeight'];
    if (sx.height !== undefined) nextStyle.height = resolveSpacing(sx.height);
    if (sx.justifyContent !== undefined) nextStyle.justifyContent = String(resolveResponsiveValue(sx.justifyContent));
    if (sx.marginTop !== undefined) nextStyle.marginTop = resolveSpacing(sx.marginTop);
    if (sx.mt !== undefined) nextStyle.marginTop = resolveSpacing(sx.mt);
    if (sx.marginBottom !== undefined) nextStyle.marginBottom = resolveSpacing(sx.marginBottom);
    if (sx.mb !== undefined) nextStyle.marginBottom = resolveSpacing(sx.mb);
    if (sx.marginLeft !== undefined) nextStyle.marginLeft = resolveSpacing(sx.marginLeft);
    if (sx.ml !== undefined) nextStyle.marginLeft = resolveSpacing(sx.ml);
    if (sx.marginRight !== undefined) nextStyle.marginRight = resolveSpacing(sx.marginRight);
    if (sx.mr !== undefined) nextStyle.marginRight = resolveSpacing(sx.mr);
    if (sx.minWidth !== undefined) nextStyle.minWidth = resolveSpacing(sx.minWidth);
    if (sx.padding !== undefined) nextStyle.padding = resolveSpacing(sx.padding);
    if (sx.px !== undefined) {
        nextStyle.paddingLeft = resolveSpacing(sx.px);
        nextStyle.paddingRight = resolveSpacing(sx.px);
    }
    if (sx.py !== undefined) {
        nextStyle.paddingTop = resolveSpacing(sx.py);
        nextStyle.paddingBottom = resolveSpacing(sx.py);
    }
    if (sx.textTransform !== undefined) nextStyle.textTransform = String(resolveResponsiveValue(sx.textTransform));
    if (sx.transform !== undefined) nextStyle.transform = String(resolveResponsiveValue(sx.transform));
    if (sx.whiteSpace !== undefined) nextStyle.whiteSpace = String(resolveResponsiveValue(sx.whiteSpace)) as React.CSSProperties['whiteSpace'];
    if (sx.width !== undefined) nextStyle.width = resolveSpacing(sx.width);
    if (sx.flexShrink !== undefined) nextStyle.flexShrink = Number(resolveResponsiveValue(sx.flexShrink));

    return nextStyle;
}

function getVariantClasses(variant: LegacyButtonVariant) {
    if (variant === 'outlined') {
        return 'border border-[#003366] bg-transparent text-[#003366] shadow-none hover:bg-slate-50';
    }

    if (variant === 'text') {
        return 'bg-transparent text-[#003366] shadow-none hover:bg-slate-50';
    }

    return 'bg-[#003366] text-white hover:bg-[#002244]';
}

function getSize(size: LegacyButtonSize) {
    if (size === 'small') return 'sm';
    if (size === 'large') return 'lg';
    return 'md';
}

function ButtonAtom({
    children,
    className,
    disabled,
    endIcon,
    fullWidth,
    href,
    component,
    onMouseEnter,
    onMouseLeave,
    size = 'medium',
    startIcon,
    sx,
    target,
    rel,
    type = 'button',
    variant = 'contained',
    ...buttonProps
}: ButtonAtomProps) {
    const [isHovered, setIsHovered] = React.useState(false);
    const isError = className?.split(' ').includes('error') ?? false;

    const mergedSx = React.useMemo(() => {
        const defaultSx: LegacySx = {
            justifyContent: 'center',
            bgcolor: '#003366',
            color: '#FFFFFF',
            borderRadius: '9999px',
            textTransform: 'none',
            px: 2,
            py: 1,
            '&:hover': {
                bgcolor: '#002244',
            },
            '&.error': {
                bgcolor: '#EC1C24',
                '&:hover': {
                    bgcolor: '#CC0000',
                },
            },
            '&.Mui-disabled': {
                bgcolor: 'grey.200',
            },
        };

        const nextSx: LegacySx = {
            ...defaultSx,
            ...sx,
        };

        if (isError) {
            Object.assign(nextSx, (defaultSx['&.error'] as LegacySx) ?? {}, (sx?.['&.error'] as LegacySx) ?? {});
        }

        return nextSx;
    }, [isError, sx]);

    const baseStyle = applySx({}, mergedSx);
    const hoverStyle = applySx({}, ((mergedSx['&:hover'] as LegacySx) ?? {}));
    const disabledStyle = applySx({}, (((mergedSx['&.Mui-disabled'] as LegacySx) ?? (mergedSx['&:disabled'] as LegacySx) ?? {})));
    const style = {
        ...baseStyle,
        ...(isHovered && !disabled ? hoverStyle : {}),
        ...(disabled ? disabledStyle : {}),
    } as React.CSSProperties;

    const content = (
        <>
            {startIcon ? <span className="inline-flex shrink-0 items-center">{startIcon}</span> : null}
            <span className="inline-flex items-center gap-1">{children}</span>
            {endIcon ? <span className="inline-flex shrink-0 items-center">{endIcon}</span> : null}
        </>
    );

    const sharedProps = {
        className: cn(getVariantClasses(variant), className),
        disabled,
        fullWidth,
        onMouseEnter: (event: React.MouseEvent<HTMLButtonElement | HTMLAnchorElement>) => {
            setIsHovered(true);
            onMouseEnter?.(event as React.MouseEvent<HTMLButtonElement>);
        },
        onMouseLeave: (event: React.MouseEvent<HTMLButtonElement | HTMLAnchorElement>) => {
            setIsHovered(false);
            onMouseLeave?.(event as React.MouseEvent<HTMLButtonElement>);
        },
        size: getSize(size) as 'sm' | 'md' | 'lg',
        style,
    };

    if ((href || component === 'a') && !disabled) {
        return (
            <Button asChild {...sharedProps}>
                <a href={href} target={target} rel={rel}>
                    {content}
                </a>
            </Button>
        );
    }

    return (
        <Button type={type} {...sharedProps} {...buttonProps}>
            {content}
        </Button>
    );
}

export default ButtonAtom;
