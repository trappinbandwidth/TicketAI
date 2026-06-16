import { cn } from 'src/lib/utils';

type ContentWrapperProps = React.HTMLAttributes<HTMLDivElement>;

export function ContentWrapper({ className, ...props }: ContentWrapperProps) {
  return <div className={cn('rounded-3xl bg-white p-6 shadow-card', className)} {...props} />;
}