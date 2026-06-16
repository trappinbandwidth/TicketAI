import { forwardRef } from 'react';
import SimpleBar from 'simplebar-react';

import { scrollbarClasses } from './classes';

import type { ScrollbarProps } from './types';

// ----------------------------------------------------------------------

export const Scrollbar = forwardRef<HTMLDivElement, ScrollbarProps>(
  ({ slotProps, children, fillContent, style, ...other }, ref) => (
    <SimpleBar
      scrollableNodeProps={{ ref }}
      clickOnTrack={false}
      className={scrollbarClasses.root}
      style={{
        minWidth: 0,
        minHeight: 0,
        flexGrow: 1,
        display: 'flex',
        flexDirection: 'column',
        ...style,
      }}
      {...other}
    >
      <style>{`
        .${scrollbarClasses.root} .simplebar-wrapper {
          ${toCssBlock(slotProps?.wrapper)}
        }
        .${scrollbarClasses.root} .simplebar-content-wrapper {
          ${toCssBlock(slotProps?.contentWrapper)}
        }
        .${scrollbarClasses.root} .simplebar-content {
          ${fillContent ? 'min-height: 100%; display: flex; flex: 1 1 auto; flex-direction: column;' : ''}
          ${toCssBlock(slotProps?.content)}
        }
      `}</style>
      {children}
    </SimpleBar>
  )
);

function toCssBlock(style?: React.CSSProperties) {
  if (!style) return '';

  return Object.entries(style)
    .filter(([, value]) => value !== undefined && value !== null)
    .map(([key, value]) => `${toKebabCase(key)}: ${String(value)};`)
    .join(' ');
}

function toKebabCase(value: string) {
  return value.replace(/[A-Z]/g, (match) => `-${match.toLowerCase()}`);
}
