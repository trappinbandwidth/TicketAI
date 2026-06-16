import * as React from 'react';
import * as AvatarPrimitive from '@radix-ui/react-avatar';

import { cn } from 'src/lib/utils';

export function Avatar({ className, ...props }: React.ComponentProps<typeof AvatarPrimitive.Root>) {
  return (
    <AvatarPrimitive.Root className={cn('relative inline-flex h-10 w-10 shrink-0 overflow-hidden rounded-full', className)} {...props} />
  );
}

export function AvatarImage({ className, ...props }: React.ComponentProps<typeof AvatarPrimitive.Image>) {
  return <AvatarPrimitive.Image className={cn('h-full w-full object-cover', className)} {...props} />;
}

export function AvatarFallback({ className, ...props }: React.ComponentProps<typeof AvatarPrimitive.Fallback>) {
  return <AvatarPrimitive.Fallback className={cn('flex h-full w-full items-center justify-center bg-brand-600 text-sm font-semibold text-white', className)} {...props} />;
}