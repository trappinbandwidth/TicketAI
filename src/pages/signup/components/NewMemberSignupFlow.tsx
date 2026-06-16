import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { toasterService } from 'src/apiSetUp';
import { setDataIntoStorage } from 'src/common-service/index.service';
import { AuthPageLayout } from 'src/components/layout';
import LucideIcon from 'src/components/lucide-icon';
import { Logo } from 'src/components/logo';
import { Button } from 'src/components/ui';
import { constants } from 'src/constants.value';
import { VerifyOTP, SendOTP, driverUserSimpleRegistration, registerDriverUser } from 'src/utils/api-service';

import { formatPhoneNumber } from './signup-flow/formatters';

type SignupStep = 'basic' | 'otp';

const OTP_LENGTH = 6;
const OTP_COOLDOWN_SECONDS = 60;

export default function NewMemberSignupFlow() {
  const navigate = useNavigate();
  const otpInputRefs = useRef<Array<HTMLInputElement | null>>([]);

  const [step, setStep] = useState<SignupStep>('basic');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [phone, setPhone] = useState('');
  const [otpDigits, setOtpDigits] = useState<string[]>(Array(OTP_LENGTH).fill(''));
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [isSendingOtp, setIsSendingOtp] = useState(false);
  const [isVerifyingOtp, setIsVerifyingOtp] = useState(false);
  const [otpErrorMessage, setOtpErrorMessage] = useState('');

  const cleanPhone = phone.replace(/\D/g, '');
  const otpCode = otpDigits.join('');
  const isBasicValid = firstName.trim().length > 0 && lastName.trim().length > 0 && cleanPhone.length === 10;
  const isOtpValid = otpCode.length === OTP_LENGTH;

  useEffect(() => {
    if (secondsLeft <= 0) return;

    const timer = window.setTimeout(() => {
      setSecondsLeft((currentSeconds) => currentSeconds - 1);
    }, 1000);

    return () => window.clearTimeout(timer);
  }, [secondsLeft]);

  useEffect(() => {
    if (step !== 'otp') return;

    const firstEmptyIndex = otpDigits.findIndex((digit) => !digit);
    const nextIndex = firstEmptyIndex === -1 ? OTP_LENGTH - 1 : firstEmptyIndex;
    otpInputRefs.current[nextIndex]?.focus();
  }, [step, otpDigits]);

  const handleExit = () => {
    navigate('/sign-in');
  };

  const handleBack = () => {
    if (step === 'otp') {
      setStep('basic');
      setOtpDigits(Array(OTP_LENGTH).fill(''));
      setOtpErrorMessage('');
      return;
    }

    handleExit();
  };

  const sendOtp = async () => {
    if (!isBasicValid || isSendingOtp) return;
    // Local test mode: skip API, go straight to OTP step
    setOtpDigits(Array(OTP_LENGTH).fill(''));
    setOtpErrorMessage('');
    setStep('otp');
  };

  const verifyOtp = async () => {
    if (!isOtpValid || isVerifyingOtp) return;

    // Local test mode: accept hardcoded OTP 123456
    if (otpCode !== '123456') {
      setOtpErrorMessage('Incorrect code. Use 123456 for local testing.');
      setOtpDigits(Array(OTP_LENGTH).fill(''));
      otpInputRefs.current[0]?.focus();
      return;
    }

    setIsVerifyingOtp(true);
    try {
      await setDataIntoStorage('driver_token', `local-test-${cleanPhone}`);
      await setDataIntoStorage('driver_refresh_token', `local-refresh-${cleanPhone}`);
      navigate('/dashboard', { replace: true });
    } finally {
      setIsVerifyingOtp(false);
    }
  };

  const resendOtp = async () => {
    if (secondsLeft > 0 || isSendingOtp) return;
    await sendOtp();
  };

  const handleOtpChange = (index: number, value: string) => {
    const sanitizedValue = value.replace(/\D/g, '');
    if (otpErrorMessage) {
      setOtpErrorMessage('');
    }

    if (!sanitizedValue) {
      const updatedDigits = [...otpDigits];
      updatedDigits[index] = '';
      setOtpDigits(updatedDigits);
      return;
    }

    const characters = sanitizedValue.slice(0, OTP_LENGTH).split('');
    const updatedDigits = [...otpDigits];

    characters.forEach((character, characterIndex) => {
      const nextIndex = index + characterIndex;
      if (nextIndex < OTP_LENGTH) {
        updatedDigits[nextIndex] = character;
      }
    });

    setOtpDigits(updatedDigits);

    const focusIndex = Math.min(index + characters.length, OTP_LENGTH - 1);
    otpInputRefs.current[focusIndex]?.focus();
  };

  const handleOtpKeyDown = (index: number, event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Backspace' && !otpDigits[index] && index > 0) {
      otpInputRefs.current[index - 1]?.focus();
    }

    if (event.key === 'ArrowLeft' && index > 0) {
      otpInputRefs.current[index - 1]?.focus();
    }

    if (event.key === 'ArrowRight' && index < OTP_LENGTH - 1) {
      otpInputRefs.current[index + 1]?.focus();
    }
  };

  return (
    <AuthPageLayout containerClassName="max-w-[393px]">
      <div className="relative mx-auto w-full max-w-[393px]">
        <div className="px-6 pb-6 pt-[60px] text-center">
          <div className="mb-6 flex justify-center">
            <Logo width={265} disableLink />
          </div>
          <p className="text-[18px] leading-7 text-[#DBEAFE]">Your road protection, simplified</p>
        </div>

        <div className="rounded-t-[32px] bg-white shadow-[0px_-12px_32px_rgba(15,23,42,0.18)]">
          <div className="flex items-center justify-between border-b border-[#E5E7EB] px-6 py-4">
            <button
              type="button"
              onClick={handleBack}
              className="inline-flex h-8 w-8 items-center justify-center rounded-full text-[#4B5563] transition hover:bg-slate-100"
            >
              <LucideIcon name="ArrowLeft" size={20} />
            </button>

            <h1 className="text-[24px] leading-6 text-[#0D3E6B]">
              {step === 'basic' ? 'Create Account' : 'Verify Phone'}
            </h1>

            <button
              type="button"
              onClick={handleExit}
              className="inline-flex h-8 w-8 items-center justify-center rounded-full text-[#6B7280] transition hover:bg-slate-100"
            >
              <LucideIcon name="X" size={20} />
            </button>
          </div>

          {step === 'basic' ? (
            <div className="px-6 pb-[max(24px,env(safe-area-inset-bottom))] pt-6">
              <p className="mb-6 text-[16px] leading-6 text-[#4B5563]">
                Enter your basic information to get started. We&apos;ll send you a verification code.
              </p>

              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <label className="block">
                    <span className="mb-2 block text-[14px] leading-5 text-[#4B5563]">First Name</span>
                    <div className="relative">
                      <LucideIcon name="User" size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#9CA3AF]" />
                      <input
                        type="text"
                        value={firstName}
                        onChange={(event) => setFirstName(event.target.value)}
                        placeholder="John"
                        className="h-[45px] w-full rounded-[14px] border border-[#D1D5DB] bg-white pl-10 pr-3 text-[16px] text-[#111827] outline-none transition placeholder:text-[#9CA3AF] focus:border-[#0D3E6B] focus:ring-2 focus:ring-[#0D3E6B]/10"
                      />
                    </div>
                  </label>

                  <label className="block">
                    <span className="mb-2 block text-[14px] leading-5 text-[#4B5563]">Last Name</span>
                    <input
                      type="text"
                      value={lastName}
                      onChange={(event) => setLastName(event.target.value)}
                      placeholder="Smith"
                      className="h-[45px] w-full rounded-[14px] border border-[#D1D5DB] bg-white px-3 text-[16px] text-[#111827] outline-none transition placeholder:text-[#9CA3AF] focus:border-[#0D3E6B] focus:ring-2 focus:ring-[#0D3E6B]/10"
                    />
                  </label>
                </div>

                <label className="block">
                  <span className="mb-2 block text-[14px] leading-5 text-[#4B5563]">Phone Number</span>
                  <div className="relative">
                    <LucideIcon name="Phone" size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#9CA3AF]" />
                    <input
                      type="tel"
                      value={phone}
                      onChange={(event) => setPhone(formatPhoneNumber(event.target.value))}
                      placeholder="(555) 555-5555"
                      maxLength={14}
                      className="h-[45px] w-full rounded-[14px] border border-[#D1D5DB] bg-white pl-10 pr-3 text-[16px] text-[#111827] outline-none transition placeholder:text-[#9CA3AF] focus:border-[#0D3E6B] focus:ring-2 focus:ring-[#0D3E6B]/10"
                    />
                  </div>
                  <span className="mt-2 block text-[12px] leading-4 text-[#6B7280]">
                    We&apos;ll send a verification code to this number
                  </span>
                </label>
              </div>

              <Button
                type="button"
                onClick={sendOtp}
                disabled={!isBasicValid || isSendingOtp}
                fullWidth
                className="mt-6 h-12 rounded-full bg-[#0D3E6B] text-[16px] font-semibold text-white hover:bg-[#123d67] disabled:bg-[#E5E7EB] disabled:text-[#9CA3AF]"
              >
                {isSendingOtp ? 'Sending Code...' : 'Send Verification Code'}
              </Button>

              <p className="mt-4 text-center text-[12px] leading-4 text-[#6B7280]">
                By continuing, you agree to our Terms of Service and Privacy Policy
              </p>
            </div>
          ) : (
            <div className="px-6 pb-[max(24px,env(safe-area-inset-bottom))] pt-6">
              <p className="text-[16px] leading-6 text-[#4B5563]">We sent a 6-digit code to</p>
              <p className="mt-2 text-[16px] leading-6 text-[#0D3E6B]">{phone}</p>

              <div className="mt-6 flex justify-between gap-2">
                {otpDigits.map((digit, index) => (
                  <input
                    key={`otp-digit-${index}`}
                    ref={(element) => {
                      otpInputRefs.current[index] = element;
                    }}
                    type="text"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    maxLength={OTP_LENGTH}
                    value={digit}
                    onChange={(event) => handleOtpChange(index, event.target.value)}
                    onKeyDown={(event) => handleOtpKeyDown(index, event)}
                    className={`h-14 w-12 rounded-[14px] border-2 text-center text-[24px] font-normal text-[#111827] outline-none transition ${
                      otpErrorMessage
                        ? 'border-red-300 bg-red-50 focus:border-red-400 focus:ring-2 focus:ring-red-100'
                        : 'border-[#D1D5DB] focus:border-[#0D3E6B] focus:ring-2 focus:ring-[#0D3E6B]/10'
                    }`}
                  />
                ))}
              </div>

              {otpErrorMessage ? (
                <p className="mt-3 text-sm text-red-600">{otpErrorMessage}</p>
              ) : null}

              <Button
                type="button"
                onClick={verifyOtp}
                disabled={!isOtpValid || isVerifyingOtp}
                fullWidth
                className="mt-6 h-12 rounded-full bg-[#0D3E6B] text-[16px] font-semibold text-white hover:bg-[#123d67] disabled:bg-[#E5E7EB] disabled:text-[#9CA3AF]"
              >
                {isVerifyingOtp ? 'Verifying & Creating Account...' : 'Verify & Continue'}
              </Button>

              <div className="mt-4 text-center">
                <button
                  type="button"
                  onClick={resendOtp}
                  disabled={secondsLeft > 0 || isSendingOtp}
                  className="text-[14px] leading-5 text-[#0D3E6B] underline underline-offset-2 disabled:cursor-not-allowed disabled:text-[#9CA3AF]"
                >
                  {secondsLeft > 0 ? `Didn\'t receive code? Resend in ${secondsLeft}s` : "Didn't receive code? Resend"}
                </button>
              </div>

              <div className="mt-6 rounded-[16px] border border-[#BFDBFE] bg-[#E8F4F8] px-4 py-4 text-center">
                <p className="text-[14px] leading-5 text-[#4B5563]">
                  <span className="text-[#0D3E6B]">Demo:</span> Enter the 6-digit verification code we texted to you
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </AuthPageLayout>
  );
}