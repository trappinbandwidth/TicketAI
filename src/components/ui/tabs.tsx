import * as React from 'react';
import * as TabsPrimitive from '@radix-ui/react-tabs';

import { cn } from 'src/lib/utils';

export const Tabs = TabsPrimitive.Root;

export function TabsList({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.List>) {
  return (
    <TabsPrimitive.List className={cn('inline-flex rounded-pill bg-slate-100 p-1', className)} {...props} />
  );
}

export function TabsTrigger({
  className,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      className={cn(
        'inline-flex min-w-24 items-center justify-center rounded-pill px-4 py-2 text-sm font-semibold text-slate-600 transition data-[state=active]:bg-white data-[state=active]:text-brand-600 data-[state=active]:shadow-card focus:outline-none focus:ring-2 focus:ring-brand-100',
        className
      )}
      {...props}
    />
  );
}

export function TabsContent({
  className,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.Content>) {
  return <TabsPrimitive.Content className={cn('outline-none', className)} {...props} />;
}