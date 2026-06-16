import { lazy } from 'react';

import { RouterLink } from 'src/routes/components';

import { Logo } from 'src/components/logo';

import { Main, CompactContent } from './main';
export const LayoutSection = lazy(() => import('../core/layout-section'));
export const HeaderSection = lazy(() => import('../core/header-section'));

// ----------------------------------------------------------------------

type Breakpoint = 'xs' | 'sm' | 'md' | 'lg' | 'xl';

type SxProp = React.CSSProperties;

export type SimpleLayoutProps = {
  sx?: SxProp;
  children: React.ReactNode;
  header?: {
    sx?: SxProp;
  };
  content?: {
    compact?: boolean;
  };
};

export function SimpleLayout({ sx, children, header, content }: SimpleLayoutProps) {
  const layoutQuery: Breakpoint = 'md';

  return (
    <LayoutSection
      /** **************************************
       * Header
       *************************************** */
      headerSection={
        <HeaderSection
          layoutQuery={layoutQuery}
          slotProps={{ container: { maxWidth: false } }}
          style={header?.sx}
          slots={{
            topArea: (
              <div className="hidden rounded-none border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-900">
                This is an info Alert.
              </div>
            ),
            leftArea: <Logo width={102} />,
            rightArea: (
              <RouterLink
                href="#"
                className="text-sm font-semibold text-inherit"
              >
                Need help?
              </RouterLink>
            ),
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
      cssVars={{
        '--layout-simple-content-compact-width': '448px',
      }}
      style={sx}
    >
      <Main>
        {content?.compact ? (
          <CompactContent layoutQuery={layoutQuery}>{children}</CompactContent>
        ) : (
          children
        )}
      </Main>
    </LayoutSection>
  );
}
