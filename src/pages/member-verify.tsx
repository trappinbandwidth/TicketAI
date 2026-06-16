import { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { useAtom } from 'jotai';
import { signInAnonymously } from 'firebase/auth';

import { toasterService } from 'src/apiSetUp';
import { setDataIntoStorage } from 'src/common-service/index.service';
import { AuthPageLayout } from 'src/components/layout';
import LucideIcon from 'src/components/lucide-icon';
import { Logo } from 'src/components/logo';
import { Button } from 'src/components/ui';
import { VerifyOTP, SendOTP } from 'src/utils/api-service';
import { isLoading, firebaseUid } from 'src/store';
import { auth } from 'src/lib/firebase';
import { constants } from 'src/constants.value';

const OTP_LENGTH = 6;
const OTP_COOLDOWN = 60;
const STORAGE_KEY_PREFIX = 'otp_last_sent_';

export default function MemberVerify() {
  const [searchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [loading, setIsLoading] = useAtom(isLoading);
  const [, setFirebaseUid] = useAtom(firebaseUid);

  const formattedPhoneFromState = (location.state as any)?.phoneNumber || '';

  const phone = useMemo(() => {
    const token = searchParams.get('token');
    if (!token) return '';
    try {
      const decoded = atob(atob(token));
      const [, reversed] = decoded.split(':');
      return reversed ? reversed.split('').reverse().join('') : '';
    } catch {
      return '';
    }
  }, [searchParams]);

  const [secondsLeft, setSecondsLeft] = useState(0);
  const [lastSentTime, setLastSentTime] = useState<number>(0);
  const [otpCode, setOtpCode] = useState('');
  const [hasCodeError, setHasCodeError] = useState(false);

  const isOtpValid = otpCode.length === OTP_LENGTH;

  const displayPhone = useMemo(() => {
    if (formattedPhoneFromState) return formattedPhoneFromState;

    const digits = phone.replace(/\D/g, '');
    if (digits.length !== 10) return phone;

    return `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6)}`;
  }, [formattedPhoneFromState, phone]);

  useEffect(() => {
    if (!phone) {
      navigate('/member-phone');
      return;
    }

    const storageKey = `${STORAGE_KEY_PREFIX}${phone}`;
    const stored = localStorage.getItem(storageKey);
    let timestamp = 0;

    if (stored) {
      timestamp = parseInt(stored, 10);
    } else {
      // If no timestamp for this specific phone, set it now
      timestamp = Date.now();
      localStorage.setItem(storageKey, timestamp.toString());
    }
    setLastSentTime(timestamp);
  }, [phone, navigate]);

  useEffect(() => {
    if (!lastSentTime) return;

    const updateTimer = () => {
      const now = Date.now();
      const elapsed = Math.floor((now - lastSentTime) / 1000);
      const remaining = Math.max(OTP_COOLDOWN - elapsed, 0);
      setSecondsLeft(remaining);
      return remaining;
    };

    const initialRemaining = updateTimer();

    if (initialRemaining > 0) {
      const interval = window.setInterval(() => {
        const remaining = updateTimer();
        if (remaining <= 0) {
          window.clearInterval(interval);
        }
      }, 1000);

      return () => window.clearInterval(interval);
    }
  }, [lastSentTime]);

  const handleOtpChange = (value: string) => {
    const sanitizedValue = value.replace(/\D/g, '').slice(0, OTP_LENGTH);

    setOtpCode(sanitizedValue);

    if (hasCodeError) {
      setHasCodeError(false);
    }
  };

  const handleVerify = async () => {
    if (!isOtpValid || loading) return;

    setIsLoading(true);
    try {
      const response = await VerifyOTP({
        PhoneNumber: phone,
        OTPCode: otpCode,
      } as any);

      if (response.StatusCode === constants.RESPONSE_STATUS.SUCCESS) {
        await setDataIntoStorage('driver_token', response.Result.Data.AccessToken);
        await setDataIntoStorage('driver_refresh_token', response.Result.Data.RefreshToken);

        // Sign into Firebase anonymously to get a stable UID for Firestore
        try {
          const fbResult = await signInAnonymously(auth);
          const uid = fbResult.user.uid;
          setFirebaseUid(uid);
          await setDataIntoStorage('firebase_uid', uid);
        } catch (fbErr) {
          console.warn('[firebase] anonymous sign-in failed (offline or not configured):', fbErr);
        }

        navigate('/dashboard');
      } else {
        setHasCodeError(true);
        setOtpCode('');
      }
    } catch (error) {
      setHasCodeError(true);
      setOtpCode('');
      toasterService('Failed to verify code.', 4, error);
    } finally {
      setIsLoading(false);
    }
  };

  const resend = async () => {
    if (secondsLeft > 0 || loading) return;

    setIsLoading(true);
    try {
      const response = await SendOTP({ PhoneNumber: phone } as any);

      if (response.StatusCode === constants.RESPONSE_STATUS.SUCCESS) {
        const now = Date.now();
        const storageKey = `${STORAGE_KEY_PREFIX}${phone}`;
        localStorage.setItem(storageKey, now.toString());
        setLastSentTime(now);
        setOtpCode('');
        setHasCodeError(false);
      } else {
        toasterService(response.Message, 4, response.Message);
      }
    } catch (error) {
      toasterService('Failed to send verification code.', 4, error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleBack = () => {
    navigate('/member-phone', {
      state: { phoneNumber: displayPhone },
    });
  };

  return (
    <AuthPageLayout containerClassName="max-w-[400px]">
      <Button
        type="button"
        variant="ghost"
        size="sm"
        onClick={handleBack}
        className="mb-4 inline-flex border border-white/20 bg-white/10 px-4 text-white hover:bg-white/15"
      >
        <LucideIcon name="ArrowLeft" size={20} color="#fff" />
        <span>Back</span>
      </Button>

      <div className="mb-10 flex justify-center">
        <div className="relative">
          <div className="absolute inset-0 rounded-3xl bg-white/30 blur-[32px]" />
          <div className="relative rounded-3xl border border-white/20 bg-white/10 p-6 shadow-[0_24px_64px_rgba(15,23,42,0.3)] backdrop-blur-xl">
            <Logo width={180} disableLink isLegalLogo />
          </div>
        </div>
      </div>

      <div className="mb-10 text-center">
        <h1 className="mb-3 text-3xl text-white">Enter Verification Code</h1>
        <p className="text-base text-blue-100">We sent a code to {displayPhone}</p>
      </div>

      <div
        className={`mb-6 rounded-3xl border bg-white/10 p-8 shadow-[0_24px_64px_rgba(15,23,42,0.3)] backdrop-blur-xl ${
          hasCodeError ? 'border-2 border-red-400' : 'border-white/20'
        }`}
      >
        <label className="mb-3 block text-sm text-blue-100">6-Digit Code</label>
        <div className="relative">
          <LucideIcon
            name="MessageSquare"
            size={24}
            className={`pointer-events-none absolute left-5 top-1/2 -translate-y-1/2 ${
              hasCodeError ? 'text-red-300' : 'text-white/60'
            }`}
          />

          <input
            type="text"
            name="one-time-code"
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={OTP_LENGTH}
            value={otpCode}
            onChange={(event) => handleOtpChange(event.target.value)}
            spellCheck={false}
            className={`w-full rounded-2xl border-2 bg-white/10 py-4 pl-14 pr-5 text-center text-2xl font-normal tracking-[0.45em] text-white outline-none transition placeholder:text-white/40 focus:ring-2 focus:ring-white/50 ${
              hasCodeError ? 'auth-input-autofill border-red-400 focus:border-red-400' : 'auth-input-autofill border-white/20 focus:border-white/40'
            }`}
            placeholder="123456"
          />
        </div>

        {hasCodeError && <p className="mt-3 text-sm text-red-300">Incorrect code. Please try again.</p>}
      </div>

      <Button
        type="button"
        onClick={handleVerify}
        disabled={!isOtpValid || loading}
        fullWidth
        className="mb-4 h-14 rounded-3xl bg-white text-lg text-[#0D3E6B] shadow-[0_24px_64px_rgba(255,255,255,0.18)] hover:scale-[1.02] hover:bg-slate-50 disabled:border-2 disabled:border-white/10 disabled:bg-white/20 disabled:text-white/40"
      >
        {loading ? 'Verifying...' : 'Verify Code'}
      </Button>

      <div className="text-center">
        {secondsLeft > 0 ? (
          <p className="text-sm text-blue-100">Resend code in {secondsLeft}s</p>
        ) : (
          <button type="button" onClick={resend} disabled={loading} className="text-sm text-white hover:underline">
            Didn&apos;t receive a code? Resend
          </button>
        )}
      </div>
    </AuthPageLayout>
  );
}
