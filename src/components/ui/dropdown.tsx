import * as React from 'react';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { Check, ChevronRight } from 'lucide-react';

import { cn } from 'src/lib/utils';

export const Dropdown = DropdownMenu.Root;
export const DropdownTrigger = DropdownMenu.Trigger;

export function DropdownContent({
  className,
  sideOffset = 6,
  ...props
}: React.ComponentProps<typeof DropdownMenu.Content>) {
  return (
    <DropdownMenu.Portal>
      <DropdownMenu.Content
        sideOffset={sideOffset}
        className={cn(
          'z-50 min-w-48 rounded-2xl border border-slate-200 bg-white p-1 shadow-glass outline-none',
          className
        )}
        {...props}
      />
    </DropdownMenu.Portal>
  );
}

export function DropdownItem({
  className,
  inset,
  ...props
}: React.ComponentProps<typeof DropdownMenu.Item> & { inset?: boolean }) {
  return (
    <DropdownMenu.Item
      className={cn(
        'relative flex cursor-default select-none items-center rounded-xl px-3 py-2 text-sm text-ink-body outline-none transition hover:bg-slate-50 focus:bg-slate-50 data-[disabled]:pointer-events-none data-[disabled]:opacity-50',
        inset && 'pl-8',
        className
      )}
      {...props}
    />
  );
}

export function DropdownCheckboxItem({
  className,
  children,
  checked,
  ...props
}: React.ComponentProps<typeof DropdownMenu.CheckboxItem>) {
  return (
    <DropdownMenu.CheckboxItem
      checked={checked}
      className={cn(
        'relative flex cursor-default select-none items-center rounded-xl py-2 pl-8 pr-3 text-sm text-ink-body outline-none transition hover:bg-slate-50 focus:bg-slate-50',
        className
      )}
      {...props}
    >
      <span className="absolute left-3 flex h-4 w-4 items-center justify-center">
        <DropdownMenu.ItemIndicator>
          <Check className="h-4 w-4 text-brand-600" />
        </DropdownMenu.ItemIndicator>
      </span>
      {children}
    </DropdownMenu.CheckboxItem>
  );
}

export function DropdownSubTrigger({
  className,
  inset,
  children,
  ...props
}: React.ComponentProps<typeof DropdownMenu.SubTrigger> & { inset?: boolean }) {
  return (
    <DropdownMenu.SubTrigger
      className={cn(
        'flex cursor-default select-none items-center rounded-xl px-3 py-2 text-sm text-ink-body outline-none transition hover:bg-slate-50 focus:bg-slate-50',
        inset && 'pl-8',
        className
      )}
      {...props}
    >
      {children}
      <ChevronRight className="ml-auto h-4 w-4" />
    </DropdownMenu.SubTrigger>
  );
}