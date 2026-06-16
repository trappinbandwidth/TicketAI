import { memo } from 'react';
import { cn } from 'src/lib/utils';

import { baseVars } from '../config-vars';
import { layoutClasses } from '../classes';

// ----------------------------------------------------------------------

type CSSVarStyles = React.CSSProperties & Record<`--${string}`, string | number | undefined>;

export type LayoutSectionProps = {
  style?: React.CSSProperties;
  cssVars?: CSSVarStyles;
  contentStyle?: React.CSSProperties;
  className?: string;
  contentClassName?: string;
  children?: React.ReactNode;
  footerSection?: React.ReactNode;
  headerSection?: React.ReactNode;
  sidebarSection?: React.ReactNode;
};

const LayoutSection = ({
  style,
  cssVars,
  className,
  children,
  contentStyle,
  contentClassName,
  footerSection,
  headerSection,
  sidebarSection,
}: LayoutSectionProps) => {
  return (
    <div
      id="root__layout"
      className={cn(layoutClasses.root, className)}
      style={{ ...baseVars, ...cssVars, ...style }}
    >
      {sidebarSection}
      <div
        className={cn(layoutClasses.hasSidebar, 'flex flex-1 flex-col', contentClassName)}
        style={contentStyle}
      >
        {headerSection}
        {children}
        {footerSection}
      </div>
    </div>
  );
}
export default memo(LayoutSection);