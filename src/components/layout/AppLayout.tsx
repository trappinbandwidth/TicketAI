import { cn } from 'src/lib/utils';

type AppLayoutProps = {
  sidebar?: React.ReactNode;
  header?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
};

export function AppLayout({ sidebar, header, children, className }: AppLayoutProps) {
  return (
    <div className={cn('min-h-screen bg-surface-app text-ink-body', className)}>
      {header}
      <div className="mx-auto flex min-h-[calc(100vh-4rem)] w-full max-w-[1440px] gap-6 px-4 py-6 lg:px-6">
        {sidebar}
        <main className="min-w-0 flex-1">{children}</main>
      </div>
    </div>
  );
}