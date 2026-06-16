import { lazy, Suspense, useEffect, useMemo, useState } from 'react';
import { Outlet, Navigate, useRoutes } from 'react-router-dom';

import {
  isLoading,
  driverProfile,
  ticketStatusConfig,
  ticketList,
  ticketLoading,
} from 'src/store';
import { useAtom } from 'jotai';
import { LoadingScreen } from 'src/components/loading-screen';
import authModule from 'src/apiSetUp/authService';
import { TicketStatusConfigItem } from 'src/common-service/types.interface';
import LucideIcon from 'src/components/lucide-icon';
import InactiveMembershipOverlay from 'src/components/InactiveMembershipOverlay';
import { useDriverProfileQuery } from 'src/queries/use-driver-profile-query';
import { useMenuItemsQuery } from 'src/queries/use-menu-items-query';
import { useTicketStatusConfigQuery } from 'src/queries/use-ticket-status-config-query';
import { useDriverTicketsQuery } from 'src/queries/use-driver-tickets-query';
// Lazy-loaded routes
export const DashboardLayout = lazy(() => import('src/layouts/dashboard/layout'));
export const LandingWebPage = lazy(() => import('src/pages/landing-web'));
export const MemberPhonePage = lazy(() => import('src/pages/member-phone'));
export const MemberVerifyPage = lazy(() => import('src/pages/member-verify'));
export const MemberDashboardPage = lazy(() => import('src/pages/member-dashboard'));
export const SupportPage = lazy(() => import('src/pages/support'));
export const TicketsPage = lazy(() => import('src/pages/ticket/tickets-list'));
export const TicketDetailPage = lazy(() => import('src/pages/ticket/ticket-modal-route'));
export const PaymentReturnPage = lazy(() => import('src/pages/ticket/PaymentReturnPage'));
export const RewardsPage = lazy(() => import('src/pages/rewards'));
export const ReferralPage = lazy(() => import('src/pages/referral'));
export const Page404 = lazy(() => import('src/pages/page-not-found'));
export const SignUpPage = lazy(() => import('src/pages/signup'));

// Profile Pages
export const ProfileHomePage = lazy(() => import('src/pages/profile/home'));
export const ProfileUserInfoPage = lazy(() => import('src/pages/profile/your-information'));
export const ProfileBillingPage = lazy(() => import('src/pages/profile/billing-payments'));
export const ProfilePrivacyPage = lazy(() => import('src/pages/profile/privacy-security'));
export const ProfileMVRsPage = lazy(() => import('src/pages/profile/mvrs'));

export function Router() {
  // Use sync check - works because App.tsx has already initialized persistent storage
  const isTokenAvailable = authModule.isLoggedIn();
  const [, setTickets] = useAtom(ticketList);
  const [driverData, setDriverProfileData] = useAtom(driverProfile);
  const [, setLoading] = useAtom(isLoading);
  const [, setTicketLoading] = useAtom(ticketLoading);
  const [, setStatusData] = useAtom(ticketStatusConfig) as [TicketStatusConfigItem[], any];
  const [isInitialLoading, setIsInitialLoading] = useState(true);
  const isLoginDisabled = driverData?.loginEnabled === false;

  const profileQuery = useDriverProfileQuery(isTokenAvailable);
  const menuQuery = useMenuItemsQuery(isTokenAvailable && profileQuery.isSuccess);
  const ticketStatusQuery = useTicketStatusConfigQuery(isTokenAvailable && menuQuery.isSuccess);
  const ticketsQuery = useDriverTicketsQuery(isTokenAvailable && menuQuery.isSuccess, 20);

  const menuList = useMemo(() => {
    return (menuQuery.data || []).map((element: any) => {
      const mapped = {
        ...element,
        title: element.label || '',
        path: element.route,
      } as any;

      if (mapped.label === 'Home') mapped.icon = <LucideIcon name="House" />;
      else if (mapped.label === 'Tickets') mapped.icon = <LucideIcon name="FileText" />;
      else if (mapped.label === 'Referral') mapped.icon = <LucideIcon name="UserPlus" />;
      else if (mapped.label === 'Rewards') mapped.icon = <LucideIcon name="Gift" />;
      else if (mapped.label === 'Profile') mapped.icon = <LucideIcon name="User" />;
      else if (mapped.label === 'Support') mapped.icon = <LucideIcon name="ALargeSmall" />;

      return mapped;
    });
  }, [menuQuery.data]);

  const handleReactivate = () => {
    window.location.href = 'mailto:protect@cdllegal.com?subject=Membership%20Reactivation';
  };

  useEffect(() => {
    if (!isTokenAvailable) {
      setIsInitialLoading(false);
      return;
    }

    if (profileQuery.isPending || menuQuery.isPending) {
      setIsInitialLoading(true);
      return;
    }

    setIsInitialLoading(false);
  }, [isTokenAvailable, profileQuery.isPending, menuQuery.isPending]);

  useEffect(() => {
    setLoading(profileQuery.isLoading || profileQuery.isFetching);
    if (profileQuery.isSuccess) {
      setDriverProfileData(profileQuery.data || {});
    }
    if (profileQuery.isError) {
      setDriverProfileData({});
    }
  }, [profileQuery.isLoading, profileQuery.isFetching, profileQuery.isSuccess, profileQuery.isError, profileQuery.data, setDriverProfileData, setLoading]);

  useEffect(() => {
    const sortedTickets = (ticketsQuery.data?.tickets || []).slice().sort((a: any, b: any) => new Date(b.createdDate).getTime() - new Date(a.createdDate).getTime());
    setTickets({ tickets: sortedTickets, cases: ticketsQuery.data?.cases || [] });
    setTicketLoading(ticketsQuery.isLoading || ticketsQuery.isFetching);
  }, [ticketsQuery.data, ticketsQuery.isLoading, ticketsQuery.isFetching, setTickets, setTicketLoading]);

  useEffect(() => {
    setStatusData(ticketStatusQuery.data || []);
  }, [ticketStatusQuery.data, setStatusData]);

  const routeConfig = [
    {
      path: '/',
      element: isTokenAvailable ? (
        isLoginDisabled ? (
          <InactiveMembershipOverlay onReactivate={handleReactivate} />
        ) : (
          <DashboardLayout navData={menuList}>
            <Suspense fallback={<LoadingScreen />}>
              <Outlet />
            </Suspense>
          </DashboardLayout>
        )
      ) : (
        <Navigate to="/sign-in" />
      ),
      children: [
        {
          path: 'profile',
          children: [
            { path: '', element: <ProfileHomePage /> },
            { path: 'user-info', element: <ProfileUserInfoPage /> },
            { path: 'billing', element: <ProfileBillingPage /> },
            { path: 'privacy', element: <ProfilePrivacyPage /> },
            { path: 'mvrs', element: driverData?.mvrEnabled ? <ProfileMVRsPage /> : <Navigate to="/profile" replace /> },
          ]
        },
        {
          path: '',
          element: <Navigate to="dashboard" />,
        },
        {
          path: 'dashboard',
          element: (<MemberDashboardPage />),
        },
        {
          path: 'support',
          element: (<SupportPage />),
        },
        {
          path: 'tickets',
          children: [
            { path: '', element: (<TicketsPage />) },
            { path: ':id', element: (<TicketDetailPage />) }
          ]
        },
        {
          path: 'return',
          element: (<PaymentReturnPage />),
        },
        {
          path: 'rewards',
          element: (<RewardsPage />),
        },
        {
          path: 'referral',
          element: (<ReferralPage />),
        },
      ],
    },
    {
      path: '/',
      element: !isTokenAvailable ? (
        <Suspense fallback={<LoadingScreen />}>
          <Outlet />
        </Suspense>
      ) : (
        <Navigate to="/" />
      ),
      children: [
        {
          path: 'sign-in',
          element: (<LandingWebPage />)
        },
        {
          path: 'member-phone',
          element: <MemberPhonePage />,
        },
        {
          path: 'member-verify',
          element: <MemberVerifyPage />,
        },
        {
          path: 'sign-up',
          element: <SignUpPage />,
        },
        { path: '/', element: <Navigate to="/sign-in" /> }
      ],
    },
    {
      path: '404',
      element: <Page404 />,
    },
    {
      path: '*',
      element: <Navigate to="/404" replace />,
    },
  ];

  const routeResult = useRoutes(routeConfig);
  return isTokenAvailable ? (isInitialLoading ? <LoadingScreen /> : routeResult) : routeResult;
}
