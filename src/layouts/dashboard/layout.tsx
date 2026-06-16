import { lazy, useEffect } from 'react';

import { Logo } from 'src/components/logo';
import { Header } from 'src/components/layout';
import { useAtom } from 'jotai';
import { driverProfile } from 'src/store';
import { useFilesQuery } from 'src/queries/use-files-query';
import { cn } from 'src/lib/utils';
import { Main } from './main';
export const BottomBar = lazy(() => import('./bottombar'));
export const NavMobileBottom = lazy(() => import('./nav-mobile-bottom'));
export const NavDesktop = lazy(() => import('./nav-desktop'));
export const AccountPopover = lazy(() => import('../components/account-popover'));
// ----------------------------------------------------------------------

export type DashboardLayoutProps = {
  sx?: React.CSSProperties;
  children: React.ReactNode;
  header?: {
    sx?: React.CSSProperties;
  };
  navData: any[];
};

const DashboardLayout = ({ sx, children, header, navData }: DashboardLayoutProps) => {
  const [_driverProfile, setDriverProfileData] = useAtom(driverProfile);
  const bucketName = import.meta.env.VITE_S3_BUCKET_NAME || '';
  const folderName = _driverProfile.id ? `profile_picture/001${_driverProfile.id}` : '';

  const profilePictureFilesQuery = useFilesQuery(
    Boolean(_driverProfile.id && !_driverProfile.profilePicture && bucketName && folderName),
    bucketName,
    folderName
  );

  useEffect(() => {
    if (_driverProfile.profilePicture) return;
    const files = profilePictureFilesQuery.data || [];
    if (!files.length) return;

    const latestFile = [...files]
      .sort((a: any, b: any) => {
        const aTime = new Date(a?.lastModified || a?.LastModified || 0).getTime();
        const bTime = new Date(b?.lastModified || b?.LastModified || 0).getTime();
        return bTime - aTime;
      })[0];

    if (!latestFile?.url) return;

    setDriverProfileData((prev: any) => ({
      ...prev,
      profilePicture: latestFile.url,
    }));
  }, [_driverProfile.profilePicture, profilePictureFilesQuery.data, setDriverProfileData]);

  return (
    <>
      <div
        className="min-h-screen bg-surface-app text-ink-body"
        style={{
          '--layout-nav-vertical-width': '300px',
          ...sx,
        } as React.CSSProperties}
      >
        <Header
          className="border-slate-200/80 bg-white/90 shadow-sm"
          style={header?.sx}
        >
          <div className={cn(
            'flex items-center justify-between px-4 py-3 sm:px-6 lg:px-[54px] lg:py-[18px]'
          )}>
            <div className={cn('flex items-center')}>
              <Logo width={149} height="auto" className="mt-0" />
            </div>
            <div className="ml-auto flex items-center gap-2">
              <AccountPopover />
            </div>
          </div>
        </Header>

        <Main>{children}</Main>
      </div>
      <NavMobileBottom data={navData} forceDesktop dashboardDesktopMode />
    </>
  );
};
export default DashboardLayout;