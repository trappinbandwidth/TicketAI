import { useNavigate } from 'react-router-dom';

import { AuthPageLayout } from 'src/components/layout';
import { Logo } from 'src/components/logo';
import LucideIcon from 'src/components/lucide-icon';

export default function LandingWeb() {
  const navigate = useNavigate();

  return (
    <AuthPageLayout containerClassName="max-w-[393px]">
      <div className="relative mx-auto flex min-h-screen w-full max-w-[393px] items-center justify-center px-6 py-10">
        <div className="w-full max-w-[345px]">
          <div className="mb-[22px] flex justify-center">
            <Logo width={265} disableLink isLegalLogo />
          </div>

          <div className="mb-10 text-center">
            <p className="text-[18px] leading-7 text-[#DBEAFE]">Your CDL protection, simplified</p>
          </div>

          <div className="flex flex-col gap-4">
            <button
              type="button"
              onClick={() => navigate('/member-phone')}
              className="group w-full rounded-[24px] bg-white px-8 py-8 text-left shadow-[0px_25px_50px_rgba(0,0,0,0.25)] transition-transform duration-200 hover:scale-[1.01] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70"
            >
              <div className="flex items-center gap-5">
                <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-b from-[#0D3E6B] to-[#1E3A5F] text-white shadow-[0px_10px_15px_rgba(0,0,0,0.1),0px_4px_6px_rgba(0,0,0,0.1)]">
                  <LucideIcon name="UserCheck" size={30} strokeWidth={2.1} />
                </div>

                <div className="min-w-0 flex-1">
                  <p className="text-[20px] leading-7 text-[#0D3E6B]">Current Member</p>
                  <p className="mt-1 text-[14px] leading-5 text-[#4A5565]">Sign in to your account</p>
                </div>
              </div>
            </button>

            <button
              type="button"
              onClick={() => navigate('/sign-up')}
              className="group w-full rounded-[24px] border border-white/30 bg-white/5 px-8 py-8 text-left shadow-[0px_20px_25px_rgba(0,0,0,0.1),0px_8px_10px_rgba(0,0,0,0.1)] backdrop-blur-[10px] transition-transform duration-200 hover:scale-[1.01] hover:border-white/40 hover:bg-white/[0.08] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70"
            >
              <div className="flex items-center gap-5">
                <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl border border-white/20 bg-white/10 text-white">
                  <LucideIcon name="UserPlus" size={30} strokeWidth={2.1} />
                </div>

                <div className="min-w-0 flex-1">
                  <p className="text-[20px] leading-7 text-white">New Member</p>
                  <p className="mt-1 text-[14px] leading-5 text-[#DBEAFE]">Get started today</p>
                </div>
              </div>
            </button>
          </div>

          <div className="mt-10 text-center text-[14px] leading-5 text-[rgba(219,234,254,0.8)]">
            <span>Questions? Contact us at </span>
            <a href="mailto:protect@cdllegal.com" className="text-white underline underline-offset-2">
              protect@cdllegal.com
            </a>
          </div>
        </div>
      </div>
    </AuthPageLayout>
  );
}
