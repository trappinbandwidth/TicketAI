import { cn } from 'src/lib/utils';

type PageContainerProps = React.HTMLAttributes<HTMLDivElement>;

export function PageContainer({ className, ...props }: PageContainerProps) {
  return <section className={cn('mx-auto w-full max-w-6xl px-4', className)} {...props} />;
}