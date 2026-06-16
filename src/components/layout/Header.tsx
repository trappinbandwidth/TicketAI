import { cn } from 'src/lib/utils';

type HeaderProps = React.HTMLAttributes<HTMLDivElement>;

export function Header({ className, ...props }: HeaderProps) {
  return <header className={cn('sticky top-0 z-40 border-b border-slate-200/80 bg-white/90', className)} {...props} />;
}