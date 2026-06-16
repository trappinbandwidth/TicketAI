import { cn } from 'src/lib/utils';

import { layoutClasses } from '../classes';

// ----------------------------------------------------------------------

type Breakpoint = 'xs' | 'sm' | 'md' | 'lg' | 'xl';

type HeaderSlotProps = React.HTMLAttributes<HTMLDivElement> & {
  style?: React.CSSProperties;
};

const desktopHeightClasses: Record<Breakpoint, string> = {
  xs: 'h-[var(--layout-header-desktop-height)]',
  sm: 'sm:h-[var(--layout-header-desktop-height)]',
  md: 'md:h-[var(--layout-header-desktop-height)]',
  lg: 'lg:h-[var(--layout-header-desktop-height)]',
  xl: 'xl:h-[var(--layout-header-desktop-height)]',
};

const fixedClasses: Record<Breakpoint, string> = {
  xs: 'fixed inset-x-0 top-0',
  sm: 'sm:fixed sm:inset-x-0 sm:top-0',
  md: 'md:fixed md:inset-x-0 md:top-0',
  lg: 'lg:fixed lg:inset-x-0 lg:top-0',
  xl: 'xl:fixed xl:inset-x-0 xl:top-0',
};

export type HeaderSectionProps = React.HTMLAttributes<HTMLElement> & {
  layoutQuery: Breakpoint;
  isloginScreen?: boolean;
  fixedAt?: Breakpoint;
  slots?: {
    leftArea?: React.ReactNode;
    rightArea?: React.ReactNode;
    topArea?: React.ReactNode;
    centerArea?: React.ReactNode;
    bottomArea?: React.ReactNode;
  };
  slotProps?: {
    toolbar?: HeaderSlotProps;
    container?: HeaderSlotProps & {
      maxWidth?: boolean;
    };
  };
};

const HeaderSection = ({
  style,
  className,
  slots,
  fixedAt,
  isloginScreen,
  slotProps,
  layoutQuery = 'md',
  ...other
}: HeaderSectionProps) => {
  return (
    <header
      style={{
        zIndex: 'var(--layout-header-zIndex)',
        ...style,
      }}
      className={cn(
        layoutClasses.header,
        'sticky top-0 z-[var(--layout-header-zIndex)] shadow-none',
        fixedAt ? fixedClasses[fixedAt] : '',
        className
      )}
      {...other}
    >
      {slots?.topArea}

      <div
        {...slotProps?.toolbar}
        className={cn(
          'min-h-0 h-[var(--layout-header-mobile-height)] transition-[height,background-color] duration-200 ease-in-out',
          desktopHeightClasses[layoutQuery],
          slotProps?.toolbar?.className
        )}
        style={slotProps?.toolbar?.style}
      >
        <div
          {...slotProps?.container}
          className={cn(
            'flex h-full max-w-full items-center',
            slotProps?.container?.className
          )}
          style={{
            ...(isloginScreen ? { width: 'inherit' } : null),
            ...slotProps?.container?.style,
          }}
        >
          {slots?.leftArea}

          <div className="flex flex-1 justify-center">
            {slots?.centerArea}
          </div>

          {slots?.rightArea}
        </div>
      </div>

      {slots?.bottomArea}
    </header>
  );
}
export default HeaderSection;