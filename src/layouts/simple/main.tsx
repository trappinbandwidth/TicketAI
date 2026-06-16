import { layoutClasses } from '../classes';
import { cn } from 'src/lib/utils';

// ----------------------------------------------------------------------

type SimpleMainProps = React.HTMLAttributes<HTMLElement> & {
  sx?: React.CSSProperties;
};

export function Main({ children, sx, className, ...other }: SimpleMainProps) {
  return (
    <main
      className={cn(layoutClasses.main, 'flex flex-1 flex-col', className)}
      style={sx}
      {...other}
    >
      {children}
    </main>
  );
}

// ----------------------------------------------------------------------

export function CompactContent({
  sx,
  layoutQuery: _layoutQuery,
  children,
  className,
  ...other
}: React.HTMLAttributes<HTMLDivElement> & { layoutQuery: 'xs' | 'sm' | 'md' | 'lg' | 'xl'; sx?: React.CSSProperties }) {

  return (
    <div
      className={cn(
        layoutClasses.content,
        'mx-auto flex w-full max-w-[var(--layout-simple-content-compact-width)] flex-1 flex-col px-1 pb-10 pt-3 text-center md:justify-center md:px-0 md:py-10',
        className
      )}
      style={sx}
      {...other}
    >
      {children}
    </div>
  );
}
