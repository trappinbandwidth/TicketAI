import { layoutClasses } from 'src/layouts/classes';
import { cn } from 'src/lib/utils';

// ----------------------------------------------------------------------

type MainProps = React.HTMLAttributes<HTMLElement> & {
  layoutQuery: 'xs' | 'sm' | 'md' | 'lg' | 'xl';
  disableLink?: boolean;
  sx?: React.CSSProperties;
};

export function Main({ sx, children, className, disableLink = false, layoutQuery: _layoutQuery, ...other }: MainProps) {
  const renderContent = (
    <div
      className={cn(
        'flex w-[var(--layout-auth-content-width)] max-w-[95%] flex-col rounded-2xl bg-white px-3 py-5 md:px-4',
        !disableLink && 'absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2'
      )}
    >
      {children}
    </div>
  );

  return (
    <main
      className={cn(layoutClasses.main, 'flex flex-1 flex-col items-center p-2 pb-10 pt-3 md:justify-center md:px-0 md:py-10', className)}
      style={sx}
      {...other}
    >
      {renderContent}
    </main>
  );
}
