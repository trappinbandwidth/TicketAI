import { cn } from 'src/lib/utils';

type AuthPageLayoutProps = {
  children: React.ReactNode;
  containerClassName?: string;
};

export function AuthPageLayout({ children, containerClassName }: AuthPageLayoutProps) {
  return (
    <div className="auth-background">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -right-40 -top-40 h-80 w-80 animate-blob rounded-full bg-[#dc2626] opacity-20 mix-blend-multiply blur-3xl" />
        <div className="absolute -bottom-40 -left-40 h-80 w-80 animate-blob-delay-2 rounded-full bg-blue-400 opacity-20 mix-blend-multiply blur-3xl" />
        <div className="absolute left-1/2 top-1/2 h-80 w-80 -translate-x-1/2 -translate-y-1/2 animate-blob-delay-4 rounded-full bg-purple-400 opacity-20 mix-blend-multiply blur-3xl" />
      </div>

      <div className="auth-grid-overlay pointer-events-none absolute inset-0 opacity-30" />

      <div className="relative z-10 flex min-h-screen items-start justify-center overflow-y-auto p-3 pt-6">
        <div className={cn('w-full', containerClassName)}>{children}</div>
      </div>
    </div>
  );
}