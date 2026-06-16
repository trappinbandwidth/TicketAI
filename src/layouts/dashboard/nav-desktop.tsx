import { lazy } from 'react';
import { Sidebar } from 'src/components/layout';
export const NavContent = lazy(() => import('./nav'));
import { NavContentProps } from 'src/common-service/types.interface';


const NavDesktop = ({
    data,
    slots,
}: NavContentProps & { layoutQuery: string }) => {
    return (
        <Sidebar
            className="fixed left-0 top-0 z-30 hidden h-screen w-[var(--layout-nav-vertical-width)] rounded-none border-r border-slate-200/80 bg-white px-6 py-6 shadow-none lg:flex lg:flex-col"
        >
            <NavContent data={data} slots={slots} />
        </Sidebar>
    );
}
export default NavDesktop