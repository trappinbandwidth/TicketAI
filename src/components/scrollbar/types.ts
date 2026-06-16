import type { Props as SimplebarProps } from 'simplebar-react';

// ----------------------------------------------------------------------

export type ScrollbarProps = SimplebarProps & {
  style?: React.CSSProperties;
  children?: React.ReactNode;
  fillContent?: boolean;
  slotProps?: {
    wrapper?: React.CSSProperties;
    contentWrapper?: React.CSSProperties;
    content?: React.CSSProperties;
  };
};
