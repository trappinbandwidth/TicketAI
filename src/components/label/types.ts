// ----------------------------------------------------------------------

export type LabelColor =
  | 'default'
  | 'primary'
  | 'secondary'
  | 'info'
  | 'success'
  | 'warning'
  | 'error';

export type LabelVariant = 'filled' | 'outlined' | 'soft' | 'inverted';

export interface LabelProps extends React.HTMLAttributes<HTMLSpanElement> {
  color?: LabelColor;
  variant?: LabelVariant;
  endIcon?: React.ReactElement | null;
  startIcon?: React.ReactElement | null;
  sx?: React.CSSProperties;
}
