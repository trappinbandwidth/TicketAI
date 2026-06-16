import { cn } from 'src/lib/utils';

type GridLayoutProps = React.HTMLAttributes<HTMLDivElement> & {
  columns?: '2' | '3' | '4';
};

const columnMap = {
  '2': 'md:grid-cols-2',
  '3': 'md:grid-cols-2 xl:grid-cols-3',
  '4': 'md:grid-cols-2 xl:grid-cols-4',
};

export function GridLayout({ columns = '2', className, ...props }: GridLayoutProps) {
  return <div className={cn('grid gap-4', columnMap[columns], className)} {...props} />;
}