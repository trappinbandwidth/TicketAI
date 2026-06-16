import { layoutClasses } from 'src/layouts/classes';
import { cn } from 'src/lib/utils';

// ----------------------------------------------------------------------

type MainProps = React.HTMLAttributes<HTMLElement>;

export function Main({ children, className, ...other }: MainProps) {
  return (
    <main
      className={cn(layoutClasses.main, 'flex flex-1 flex-col pb-20 lg:pb-0', className)}
      {...other}
    >
      {children}
    </main>
  );
}

// ----------------------------------------------------------------------

type DashboardContentProps = React.HTMLAttributes<HTMLDivElement> & {
  disablePadding?: boolean;
  title?: string;
  maxWidth?: 'xl' | 'lg' | 'md' | 'sm' | false;
};

export function DashboardContent({
  title,
  children,
  disablePadding = true,
  maxWidth = 'xl',
  className,
  style,
  ...other
}: DashboardContentProps) {
  const maxWidthClassName = {
    xl: 'max-w-[1280px]',
    lg: 'max-w-[1024px]',
    md: 'max-w-[768px]',
    sm: 'max-w-[640px]',
    false: 'max-w-none',
  }[String(maxWidth) as 'xl' | 'lg' | 'md' | 'sm' | 'false'];

  return (
    <div
      className={layoutClasses.content}
      style={style}
      {...other}
    >
      <div
        className={cn(
          'mx-auto flex w-full flex-1 flex-col',
          maxWidthClassName,
          disablePadding ? 'px-4 py-4 sm:px-4 md:px-5 lg:px-5 xl:px-4' : 'px-4 pt-8 pb-16 lg:px-10',
          className
        )}
      >
        {title && (
          <h1 className="text-center text-3xl font-semibold text-brand-primary transition-all">
            {title}
          </h1>
        )}
        {children}
      </div>
    </div>
  );
}
