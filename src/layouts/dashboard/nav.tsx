import { Fragment } from 'react';

import { usePathname, useRouter } from 'src/routes/hooks';
import { Logo } from 'src/components/logo';
import { Scrollbar } from 'src/components/scrollbar';


import { NavContentProps } from 'src/common-service/types.interface';

const NavContent = ({
  data,
  slots,
}: NavContentProps) => {
  const pathname = usePathname();
  const router = useRouter();

  const handleClickNavigate = (path: string) => {
    router.push(path);
  };

  return (
    <>
      <Logo width={170} />

      {slots?.topArea}
      <Scrollbar fillContent>
        <nav className="mt-10 flex flex-1 flex-col">
          <ul className="flex flex-col gap-2">
            {data.map((item: any) => {
              const isActived = pathname === item.path || pathname.startsWith(`${item.path}/`);
              return (
                <Fragment key={item.title}>
                  <li>
                    <button
                      onClick={() => handleClickNavigate(item.path)}
                      className={`flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left text-sm transition-colors ${isActived
                        ? 'bg-brand-primary/10 font-semibold text-brand-primary'
                        : 'font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                        }`}
                    >
                      <span className="flex h-6 w-6 shrink-0 items-center justify-center">
                        {item.icon}
                      </span>
                      <span className="flex-1 truncate">
                        {item.title}
                      </span>
                    </button>
                  </li>
                </Fragment>
              );
            })}
          </ul>
        </nav>
      </Scrollbar>

      {slots?.bottomArea}
    </>
  );
}
export default NavContent