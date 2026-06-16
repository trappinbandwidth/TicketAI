import { lazy, useEffect, useState } from 'react';

import { Logo } from 'src/components/logo';

import { Main } from './main';
export const LayoutSection = lazy(() => import('../core/layout-section'));
export const HeaderSection = lazy(() => import('../core/header-section'));
import { layoutClasses } from '../classes';

// ----------------------------------------------------------------------

type Breakpoint = 'xs' | 'sm' | 'md' | 'lg' | 'xl';

type SxProp = React.CSSProperties;

export type AuthLayoutProps = {
  sx?: SxProp;
  children: React.ReactNode;
  disableLink?: boolean;
  style?: any;
  header?: {
    sx?: SxProp;
  };
};

const AuthLayout = ({ sx, children, header, style, disableLink = false }: AuthLayoutProps) => {
  const layoutQuery: Breakpoint = 'md';
  const [isBigScreen, setIsBigScreen] = useState(() =>
    typeof window !== 'undefined' ? window.matchMedia('(min-width: 768px)').matches : false
  );

  useEffect(() => {
    if (typeof window === 'undefined') {
      return undefined;
    }

    const mediaQuery = window.matchMedia('(min-width: 768px)');
    const handleChange = (event: MediaQueryListEvent) => setIsBigScreen(event.matches);

    setIsBigScreen(mediaQuery.matches);
    mediaQuery.addEventListener('change', handleChange);

    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);

  return (
    <LayoutSection
      /** **************************************
       * Header
       *************************************** */
      headerSection={
        <HeaderSection
          isloginScreen={true}
          layoutQuery={layoutQuery}
          fixedAt={layoutQuery}
          slotProps={{
            container: { maxWidth: false },
            toolbar: { style: { backgroundColor: 'transparent', backdropFilter: 'unset' } },
          }}
          style={header?.sx}
          slots={{
            leftArea: (!disableLink && <Logo width={isBigScreen ? '950px' : '700px'} disableLink={disableLink} />),
          }}
        />
      }
      /** **************************************
       * Footer
       *************************************** */
      footerSection={null}
      /** **************************************
       * Style
       *************************************** */
      cssVars={{ '--layout-auth-content-width': '420px', ...style }}
      style={sx}
      contentStyle={{
        backgroundImage: "url('/assets/bg_cdl_legal.jpeg')",
        boxShadow: 'rgb(121 119 119 / 30%) 0px 0px 0px 1016px inset',
        backgroundPosition: 'center center',
      }}
    >
      <Main disableLink={disableLink} layoutQuery={layoutQuery}>{children}</Main>
    </LayoutSection>
  );
}
export default AuthLayout;