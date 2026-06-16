import { useState, useCallback } from 'react';
import { useAtom } from 'jotai';

import { useRouter } from 'src/routes/hooks';
import { driverProfile } from 'src/store';
import { cn } from 'src/lib/utils';
// ----------------------------------------------------------------------

type AccountPopoverButtonProps = Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'children'>;

export type AccountPopoverProps = AccountPopoverButtonProps & {
  data?: {
    label: string;
    href: string;
    icon?: React.ReactNode;
    info?: React.ReactNode;
  }[];
  sx?: React.CSSProperties;
};

export default function AccountPopover({ data = [], sx, ...other }: AccountPopoverProps) {
  const router = useRouter();
  const [_driverProfile] = useAtom(driverProfile);

  const handleOpenPopover = useCallback((event: React.MouseEvent<HTMLButtonElement>) => {
    router.push('/profile');
  }, []);

  return (
    <button
      type="button"
      onClick={handleOpenPopover}
      className={cn(
        'inline-flex h-10 w-10 items-center justify-center rounded-full p-0.5 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/40'
      )}
      style={sx}
      {...other}
    >
      {_driverProfile.profilePicture ? (
        <img
          alt={_driverProfile?.fullName || _driverProfile?.FullName || 'Profile avatar'}
          src={_driverProfile.profilePicture}
          className="block h-full w-full rounded-full bg-transparent object-cover object-center shadow-[0_4px_12px_rgba(0,0,0,0.1)]"
        />
      ) : (
        <span className="flex h-full w-full items-center justify-center rounded-full bg-brand-600 text-sm font-semibold text-white shadow-[0_4px_12px_rgba(0,0,0,0.1)]">
          {_driverProfile?.fullName?.[0] || _driverProfile?.FullName?.[0] || ''}
        </span>
      )}
    </button>
  );
}
