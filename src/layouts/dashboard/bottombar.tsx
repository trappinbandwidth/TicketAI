import { memo } from 'react';
import LucideIcon from 'src/components/lucide-icon';

const BottomBar = () => {
    return (
        <>
            <div className="mb-2 flex h-[30px] w-full items-center justify-between">
                {/* <LucideIcon name="Chrome" /> */}
                <LucideIcon name="Facebook" size={24} color="#1877F2" style={{ cursor: 'pointer' }} onClick={() => window.open('https://www.facebook.com/Cdllegalplan/', '_blank')} />
                {/* <LucideIcon name="Instagram" /> */}
                <LucideIcon name="Linkedin" size={24} color="#0A66C2" style={{ cursor: 'pointer' }} onClick={() => window.open('https://www.linkedin.com/company/cdllegal', '_blank')} />
                <LucideIcon name="Music" size={24} color="#000000" style={{ cursor: 'pointer' }} onClick={() => window.open('https://www.tiktok.com/@cdl_legal', '_blank')} />
            </div>
            <div className="mb-2 flex w-full items-center justify-start gap-2">
                <LucideIcon name="Star" size={24} />
                <p className="select-none text-base font-normal leading-[10px]">
                    <span style={{ color: '#EC1C24', fontWeight: 'bolder' }} className='hightlighted'>VETERAN</span> OWNED BUSINESS
                </p>
            </div>
        </>

    )
}

export default memo(BottomBar)