import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAtom } from 'jotai';

import { AuthPageLayout } from 'src/components/layout';
import LucideIcon from 'src/components/lucide-icon';
import { Logo } from 'src/components/logo';
import { Button } from 'src/components/ui';
import { constants } from 'src/constants.value';
import { isLoading } from 'src/store';
import { SendOTP } from 'src/utils/api-service';

import { formatPhoneNumber } from './signup/components/signup-flow';

export default function MemberPhone() {
  const navigate = useNavigate();
  const location = useLocation();
  const [loading, setIsLoading] = useAtom(isLoading);

  const returnedPhone = (location.state as any)?.phoneNumber || '';

  const [phoneNumber, setPhoneNumber] = useState(returnedPhone);
  const [showErrorState, setShowErrorState] = useState(false);

  const cleanPhoneNumber = phoneNumber.replace(/\D/g, '');
  const isPhoneValid = cleanPhoneNumber.length === 10;

  useEffect(() => {
    if (returnedPhone) {
      setPhoneNumber(returnedPhone);
    }
  }, [returnedPhone]);

  const handleSubmit = async () => {
    if (!isPhoneValid || loading) return;

    // Local test mode: skip API, navigate directly to verify with hardcoded OTP 123456
    const reversed = cleanPhoneNumber.split('').reverse().join('');
    const salt = 'local';
    const obfuscated = btoa(btoa(`${salt}:${reversed}`));
    navigate(`/member-verify?token=${encodeURIComponent(obfuscated)}`, {
      state: { phoneNumber },
    });
  };

  return (
    <AuthPageLayout containerClassName="max-w-[400px]">
      <Button
        type="button"
        variant="ghost"
        size="sm"
        onClick={() => navigate('/sign-in')}
        className="mb-4 inline-flex border border-white/20 bg-white/10 px-4 text-white hover:bg-white/15"
      >
        <LucideIcon name="ArrowLeft" size={20} color="#fff" />
        <span>Back</span>
      </Button>

      <div className="mb-10 flex justify-center">
        <div className="relative">
          <div className="absolute inset-0 rounded-3xl bg-white/30 blur-[32px]" />
          <div className="relative rounded-3xl border-2 border-white/40 bg-white/20 p-6 shadow-[0_24px_64px_rgba(15,23,42,0.3)] backdrop-blur-xl">
            <Logo width={180} disableLink />
          </div>
        </div>
      </div>

      <div className="mb-10 text-center">
        <h1 className="mb-3 text-3xl text-white">Enter Your Phone</h1>
        <p className="text-base text-blue-100">We&apos;ll send you a secure login code</p>
      </div>

      <div className="mb-6 rounded-3xl border border-white/20 bg-white/10 p-8 shadow-[0_24px_64px_rgba(15,23,42,0.3)] backdrop-blur-xl">
        <label className="mb-3 block text-sm text-blue-100">Phone Number</label>
        <div className="relative">
          <LucideIcon
            name="Phone"
            size={24}
            className="pointer-events-none absolute left-5 top-1/2 -translate-y-1/2 text-white/60"
          />
          <input
            type="tel"
            name="phone"
            autoComplete="tel"
            value={phoneNumber}
            onChange={(event) => {
              setPhoneNumber(formatPhoneNumber(event.target.value));
              if (showErrorState) {
                setShowErrorState(false);
              }
            }}
            placeholder="(555) 555-5555"
            maxLength={14}
            className="auth-input-autofill w-full rounded-2xl border-2 border-white/20 bg-white/10 py-4 pl-14 pr-5 text-lg text-white outline-none transition placeholder:text-white/40 focus:border-white/40 focus:ring-2 focus:ring-white/50"
          />
        </div>
      </div>

      {showErrorState && (
        <div className="mb-6 rounded-3xl border-2 border-red-400 bg-white/10 p-6 backdrop-blur-xl">
          <div className="flex items-start gap-3">
            <LucideIcon name="CircleAlert" size={20} className="mt-0.5 shrink-0 text-red-300" />
            <div>
              <p className="mb-2 text-base text-white">
                We couldn&apos;t find an account associated with this phone number.
              </p>
              <button
                type="button"
                onClick={() => navigate('/sign-up')}
                className="text-sm text-white underline hover:no-underline"
              >
                Click here to sign up as a new member
              </button>
            </div>
          </div>
        </div>
      )}

      <Button
        type="button"
        onClick={handleSubmit}
        disabled={!isPhoneValid || loading}
        fullWidth
        className="h-14 rounded-3xl bg-white text-lg text-[#0D3E6B] shadow-[0_24px_64px_rgba(255,255,255,0.18)] hover:scale-[1.02] hover:bg-slate-50 disabled:border-2 disabled:border-white/10 disabled:bg-white/20 disabled:text-white/40"
      >
        {loading ? 'Sending...' : 'Send Login Code'}
      </Button>

      <div className="mt-8 text-center">
        <p className="text-sm text-blue-100/80">Standard messaging rates may apply</p>
      </div>
    </AuthPageLayout>
  );
}
