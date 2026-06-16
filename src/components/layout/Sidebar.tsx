import { cn } from 'src/lib/utils';

type SidebarProps = React.HTMLAttributes<HTMLDivElement>;

export function Sidebar({ className, ...props }: SidebarProps) {
  return <aside className={cn('hidden w-[300px] shrink-0 rounded-3xl bg-white p-4 shadow-card lg:block', className)} {...props} />;
}