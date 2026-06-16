import { memo } from 'react';
import { usePathname, useRouter } from 'src/routes/hooks';
import { cn } from 'src/lib/utils';

// ----------------------------------------------------------------------

interface NavMobileBottomProps {
    data: any[];
    forceDesktop?: boolean;
    dashboardDesktopMode?: boolean;
}

const NavMobileBottom = ({ data, forceDesktop = false, dashboardDesktopMode = false }: NavMobileBottomProps) => {
    const pathname = usePathname();
    const router = useRouter();

    // Filter out items that shouldn't appear in bottom nav
    const filteredItems = data.filter(
        (item) => !item?.children && !item?.isRedirect
    );

    const desktopDashboardItems = dashboardDesktopMode
        ? filteredItems
            .filter((item) => ['Home', 'Rewards', 'Tickets'].includes(item.title))
            .map((item) => ({
                ...item,
                isPrimary: item.title === 'Rewards',
            }))
            .sort((a, b) => {
                const order = ['Home', 'Rewards', 'Tickets'];
                return order.indexOf(a.title) - order.indexOf(b.title);
            })
        : filteredItems;

    // Mobile nav keeps the original item ordering/primary behavior.
    const mobilePrimaryItem = filteredItems.find((item) => item.isPrimary);
    const mobileOtherItems = filteredItems.filter((item) => !item.isPrimary);

    const mobileMidPoint = Math.ceil(mobileOtherItems.length / 2);
    const mobileLeftItems = mobileOtherItems.slice(0, mobileMidPoint);
    const mobileRightItems = mobileOtherItems.slice(mobileMidPoint);

    const mobileOrderedItems = mobilePrimaryItem
        ? [...mobileLeftItems, mobilePrimaryItem, ...mobileRightItems]
        : filteredItems;

    const mobileCenterIndex = mobilePrimaryItem ? mobileLeftItems.length : -1;

    // Desktop dashboard nav uses the Figma-specific three-item arrangement.
    const primaryItem = desktopDashboardItems.find((item) => item.isPrimary);
    const otherItems = desktopDashboardItems.filter((item) => !item.isPrimary);

    // Split other items into left and right groups
    // If odd number, put extra item on left
    const midPoint = Math.ceil(otherItems.length / 2);
    const leftItems = otherItems.slice(0, midPoint);
    const rightItems = otherItems.slice(midPoint);

    // Combine: left items + primary item (center) + right items
    const orderedItems = primaryItem
        ? [...leftItems, primaryItem, ...rightItems]
        : filteredItems;

    // Find the new center index (where primary item is)
    const centerIndex = primaryItem ? leftItems.length : -1;

    const handleNavigation = (path: string) => {
        router.push(path);
    };

    return (
        <>
            <nav className={cn(
                'fixed inset-x-0 bottom-0 z-[9999] flex border-t border-slate-200 bg-white/95 px-2 pb-[env(safe-area-inset-bottom)] shadow-[0_-2px_10px_rgba(0,0,0,0.1)] backdrop-blur',
                forceDesktop ? 'lg:hidden' : 'lg:hidden'
            )}>
                {mobileOrderedItems.map((item, index) => {
                    const isActive = pathname === item.path || pathname.startsWith(`${item.path}/`);
                    const isCenter = index === mobileCenterIndex;

                    return (
                        <div key={item.title} className="relative flex flex-1 items-center justify-center">
                            <button
                                onClick={() => handleNavigation(item.path)}
                                className={`flex w-full flex-col items-center justify-center px-2 py-3 transition-transform active:scale-95 ${isCenter ? '-mt-5' : ''}`}
                            >
                                <span
                                    className={`mb-1 flex items-center justify-center rounded-full transition-colors ${isCenter
                                        ? 'h-14 w-14 bg-red-600 text-white shadow-[0_4px_12px_rgba(220,38,38,0.3)]'
                                        : isActive
                                            ? 'h-10 w-10 text-red-600'
                                            : 'h-10 w-10 text-slate-400'
                                        }`}
                                >
                                    {item.icon}
                                </span>
                                <span className={`text-center ${isCenter ? 'mt-1 text-[13px]' : 'text-xs'} ${isActive ? 'font-semibold text-red-600' : 'font-normal text-slate-500'}`}>
                                    {item.title}
                                </span>
                            </button>
                        </div>
                    );
                })}
            </nav>

            {forceDesktop ? (
                <nav className={cn(
                    'fixed inset-x-0 bottom-0 z-[9999] hidden border-t border-slate-200 bg-white/95 shadow-[0_-2px_10px_rgba(0,0,0,0.1)] backdrop-blur lg:flex lg:h-[109px] lg:px-[54px] lg:pb-0 lg:pt-[12px]'
                )}>
                    {orderedItems.map((item, index) => {
                        const isActive = pathname === item.path || pathname.startsWith(`${item.path}/`);
                        const isCenter = index === centerIndex;

                        return (
                            <div key={item.title} className="relative flex flex-1 items-center justify-center">
                                <button
                                    onClick={() => handleNavigation(item.path)}
                                    className={cn(
                                        'flex w-full flex-col items-center justify-center px-2 py-3 transition-transform active:scale-95',
                                        isCenter ? '-mt-5' : '',
                                        'lg:py-[18px]'
                                    )}
                                >
                                    <span
                                        className={cn(
                                            'mb-1 flex items-center justify-center rounded-full transition-colors',
                                            isCenter
                                                ? 'h-14 w-14 bg-red-600 text-white shadow-[0_4px_12px_rgba(220,38,38,0.3)]'
                                                : isActive
                                                    ? 'h-10 w-10 text-red-600'
                                                    : 'h-10 w-10 text-slate-400',
                                            isCenter
                                                ? 'lg:h-[72px] lg:w-[72px] lg:shadow-[0_10px_15px_rgba(0,0,0,0.1),0_4px_6px_rgba(0,0,0,0.1)]'
                                                : 'lg:h-[27px] lg:w-[27px]'
                                        )}
                                    >
                                        {item.icon}
                                    </span>
                                    <span className={cn(
                                        'text-center',
                                        isCenter ? 'mt-1 text-[13px]' : 'text-xs',
                                        isActive ? 'font-semibold text-red-600' : 'font-normal text-slate-500',
                                        'lg:text-[13.5px] lg:leading-[18px]'
                                    )}>
                                        {item.title}
                                    </span>
                                </button>
                            </div>
                        );
                    })}
                </nav>
            ) : null}
        </>
    );
};

export default memo(NavMobileBottom);
