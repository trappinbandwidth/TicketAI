import { memo, useEffect } from "react";
import { usePathname } from "src/routes/hooks";
import { NavContentProps } from "src/common-service/types.interface";
import NavContent from './nav';
import { cn } from 'src/lib/utils';

const NavMobile = ({
    sx,
    data,
    open,
    slots,
    onClose,
}: NavContentProps & { open: boolean; onClose: () => void }) => {
    const pathname = usePathname();

    useEffect(() => {
        if (open) {
            onClose();
        }
    }, [pathname]);

    return (
        <>
            <div
                className={cn(
                    'fixed inset-0 z-40 bg-slate-950/40 transition-opacity lg:hidden',
                    open ? 'pointer-events-auto opacity-100' : 'pointer-events-none opacity-0'
                )}
                onClick={onClose}
                aria-hidden="true"
            />
            <aside
                aria-hidden={!open}
                className={cn(
                    'fixed left-0 top-0 z-50 h-screen w-[var(--layout-nav-mobile-width)] max-w-[90vw] overflow-visible bg-[var(--layout-nav-bg)] px-2.5 pt-2.5 shadow-2xl transition-transform duration-200 ease-out lg:hidden',
                    open ? 'translate-x-0' : '-translate-x-full'
                )}
                style={sx}
            >
                <NavContent data={data} slots={slots} />
            </aside>
        </>
    );
}
export default memo(NavMobile)