import * as React from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';

import { cn } from 'src/lib/utils';

export const Modal = Dialog.Root;
export const ModalTrigger = Dialog.Trigger;
export const ModalClose = Dialog.Close;

export function ModalContent({
  className,
  children,
  hideCloseButton = false,
  ...props
}: React.ComponentProps<typeof Dialog.Content> & { hideCloseButton?: boolean }) {
  return (
    <Dialog.Portal>
      <Dialog.Overlay className="fixed inset-0 z-[10000] bg-slate-950/50 backdrop-blur-sm" />
      <Dialog.Content
        className={cn(
          'fixed left-1/2 top-1/2 z-[10001] w-[calc(100%-2rem)] max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-3xl border border-slate-200 bg-white p-6 shadow-glass outline-none max-h-[90dvh] overflow-y-auto',
          className
        )}
        {...props}
      >
        {children}
        {!hideCloseButton && (
          <Dialog.Close className="absolute right-4 top-4 inline-flex h-9 w-9 items-center justify-center rounded-full text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-100">
            <X className="h-4 w-4" />
            <span className="sr-only">Close</span>
          </Dialog.Close>
        )}
      </Dialog.Content>
    </Dialog.Portal>
  );
}

export function ModalHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('flex flex-col gap-2', className)} {...props} />;
}

export function ModalTitle({ className, ...props }: React.ComponentProps<typeof Dialog.Title>) {
  return <Dialog.Title className={cn('text-title-lg text-ink-strong', className)} {...props} />;
}

export function ModalDescription({
  className,
  ...props
}: React.ComponentProps<typeof Dialog.Description>) {
  return <Dialog.Description className={cn('text-sm text-ink-muted', className)} {...props} />;
}

export function ModalFooter({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('mt-6 flex justify-end gap-3', className)} {...props} />;
}