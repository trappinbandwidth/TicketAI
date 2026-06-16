import { useEffect, useMemo, useRef, useState } from 'react';
import { useAtom } from 'jotai';
import { yupResolver } from '@hookform/resolvers/yup';
import { useForm, Controller } from 'react-hook-form';
import * as Yup from 'yup';
import { useNavigate } from 'react-router-dom';
import { driverProfile } from 'src/store';
import { DashboardContent } from 'src/layouts/dashboard';
import { toasterService } from 'src/apiSetUp';
import { constants } from 'src/constants.value';
import { FormProvider, RHFSelectbox } from 'src/hook-form';
import { fDate, formatStr, today } from 'src/utils/format-time';
import { getUsStateCode, getUsStateName, isUsStateCode, US_STATE_SELECT_OPTIONS } from 'src/utils/us-states';
import LucideIcon from 'src/components/lucide-icon';
import { Card, Input } from 'src/components/ui';
import { formatPhoneNumber } from '../signup/components/signup-flow';
import { useUpdateDriverProfileMutation } from 'src/queries/use-profile-mutations';

interface ProfileFormValues {
    email: string;
    mobilePhone: string;
    birthdate: string;
    streetAddress: string;
    apt: string;
    city: string;
    state: string;
    stateCode?: string | null;
    zipCode: string;
}

interface GoogleAddressSuggestion {
    placeId: string;
    description: string;
    mainText: string;
    secondaryText: string;
}

function isValidBirthdateValue(value?: string | null) {
    if (!value) return false;
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;

    const parsedDate = new Date(`${value}T00:00:00`);
    if (Number.isNaN(parsedDate.getTime())) return false;

    const [year, month, day] = value.split('-').map(Number);

    return parsedDate.getFullYear() === year
        && parsedDate.getMonth() + 1 === month
        && parsedDate.getDate() === day;
}

const profileSchema = Yup.object().shape({
    email: Yup.string().email('Invalid email address').required('Email is required'),
    mobilePhone: Yup.string()
        .required('Phone is required')
        .test('phone-valid', 'Phone number must be 10 digits', (value) => (value || '').replace(/\D/g, '').length === 10),
    birthdate: Yup.string()
        .required('Date of birth is required')
        .matches(/^\d{4}-\d{2}-\d{2}$/, 'Select a valid date of birth')
        .test('birthdate-valid', 'Select a valid date of birth', (value) => isValidBirthdateValue(value))
        .test('birthdate-not-future', 'Date of birth cannot be in the future', (value) => {
            if (!value || !isValidBirthdateValue(value)) return false;

            return value <= today(formatStr.paramCase.fromYear);
        }),
    streetAddress: Yup.string().required('Street address is required'),
    apt: Yup.string().default('').defined(),
    city: Yup.string().required('City is required'),
    state: Yup.string()
        .required('State is required')
        .test('state-valid', 'Select a valid state', (value) => isUsStateCode(value)),
    stateCode: Yup.string().nullable(),
    zipCode: Yup.string().required('Zip code is required'),
});

function mapDriverDataToForm(driverData: any): ProfileFormValues {
    const rawPhone = String(driverData?.mobilePhone || '');
    const digitsPhone = rawPhone.replace(/\D/g, '');
    const stateCode = getUsStateCode(driverData?.address?.stateCode || driverData?.address?.state);

    return {
        email: String(driverData?.email || ''),
        mobilePhone: formatPhoneNumber(digitsPhone),
        birthdate: driverData?.birthdate ? fDate(driverData.birthdate as string, formatStr.paramCase.fromYear) : '',
        streetAddress: String(driverData?.address?.street || ''),
        apt: String(driverData?.address?.apt || ''),
        city: String(driverData?.address?.city || ''),
        state: stateCode,
        stateCode: stateCode || null,
        zipCode: String(driverData?.address?.zipCode || '').replace(/\D/g, '').slice(0, 5),
    };
}

function parseGoogleAddress(addressComponents: Array<{ longText?: string; shortText?: string; types?: string[] }>) {
    const findComponent = (type: string) => addressComponents.find((component) => component.types?.includes(type));

    const streetNumber = findComponent('street_number')?.longText || '';
    const route = findComponent('route')?.longText || '';
    const stateCode = getUsStateCode(findComponent('administrative_area_level_1')?.shortText || findComponent('administrative_area_level_1')?.longText);

    return {
        streetAddress: [streetNumber, route].filter(Boolean).join(' ').trim(),
        apt: findComponent('subpremise')?.longText || '',
        city: findComponent('locality')?.longText || findComponent('sublocality')?.longText || '',
        state: stateCode,
        stateCode,
        zipCode: (findComponent('postal_code')?.longText || '').replace(/\D/g, '').slice(0, 5),
    };
}

const profileInputClassName =
    'max-w-[100%] h-11 rounded-lg border border-gray-300 bg-white px-3 py-2 text-base text-[#1e3a5f] placeholder:text-gray-400 focus:border-[#dc2626] focus:outline-none focus:ring-2 focus:ring-[#dc2626]/20';

export default function YourInformationPage() {
    const navigate = useNavigate();
    const [driverData, setDriverData] = useAtom(driverProfile);
    const [isEditing, setIsEditing] = useState<boolean>(false);
    const [isSaving, setIsSaving] = useState<boolean>(false);
    const [isAddressLoading, setIsAddressLoading] = useState<boolean>(false);
    const [isAddressMenuOpen, setIsAddressMenuOpen] = useState<boolean>(false);
    const [addressOptions, setAddressOptions] = useState<GoogleAddressSuggestion[]>([]);
    const updateDriverProfileMutation = useUpdateDriverProfileMutation();
    const addressFieldRef = useRef<HTMLDivElement | null>(null);

    const googleApiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY as string | undefined;

    const methods = useForm<ProfileFormValues>({
        resolver: yupResolver(profileSchema),
        defaultValues: mapDriverDataToForm(driverData),
    });

    const {
        handleSubmit,
        reset,
        setValue,
        watch,
        control,
    } = methods;
    const streetAddress = watch('streetAddress');
    const shouldShowAddressOptions = isEditing && isAddressMenuOpen && (streetAddress || '').trim().length >= 3;

    /*
    const licenseExpirationDate = useMemo(() => {
        if (!driverData?.licenseExpirationDate) return null;

        const parsedDate = new Date(driverData.licenseExpirationDate);
        return Number.isNaN(parsedDate.getTime()) ? null : parsedDate;
    }, [driverData?.licenseExpirationDate]);

    const isLicenseActive = useMemo(() => {
        if (!licenseExpirationDate) return false;
        return licenseExpirationDate.getTime() >= new Date().setHours(0, 0, 0, 0);
    }, [licenseExpirationDate]);
    */

    useEffect(() => {
        if (!isEditing) {
            reset(mapDriverDataToForm(driverData));
        }
    }, [driverData, isEditing, reset]);

    useEffect(() => {
        if (!isEditing) {
            setIsAddressMenuOpen(false);
            return;
        }

        const handlePointerDown = (event: MouseEvent) => {
            if (!addressFieldRef.current?.contains(event.target as Node)) {
                setIsAddressMenuOpen(false);
            }
        };

        document.addEventListener('mousedown', handlePointerDown);

        return () => {
            document.removeEventListener('mousedown', handlePointerDown);
        };
    }, [isEditing]);

    useEffect(() => {
        if (!isEditing || !googleApiKey) return;

        const query = (streetAddress || '').trim();
        if (query.length < 3) {
            setAddressOptions([]);
            return;
        }

        const controller = new AbortController();
        const debounceTimer = setTimeout(async () => {
            try {
                setIsAddressLoading(true);
                const response = await fetch('https://places.googleapis.com/v1/places:autocomplete', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Goog-Api-Key': googleApiKey,
                        'X-Goog-FieldMask': 'suggestions.placePrediction.placeId,suggestions.placePrediction.text.text,suggestions.placePrediction.structuredFormat.mainText.text,suggestions.placePrediction.structuredFormat.secondaryText.text',
                    },
                    signal: controller.signal,
                    body: JSON.stringify({
                        input: query,
                        languageCode: 'en-US',
                        regionCode: 'US',
                        includedRegionCodes: ['us']
                    }),
                });

                if (!response.ok) {
                    setAddressOptions([]);
                    return;
                }

                const result = await response.json();
                const suggestions = (result?.suggestions || [])
                    .map((suggestion: any) => {
                        const prediction = suggestion?.placePrediction;
                        if (!prediction?.placeId) return null;

                        return {
                            placeId: prediction.placeId,
                            description: prediction?.text?.text || '',
                            mainText: prediction?.structuredFormat?.mainText?.text || prediction?.text?.text || '',
                            secondaryText: prediction?.structuredFormat?.secondaryText?.text || '',
                        } as GoogleAddressSuggestion;
                    })
                    .filter(Boolean) as GoogleAddressSuggestion[];

                setAddressOptions(suggestions);
            } catch {
                setAddressOptions([]);
            } finally {
                setIsAddressLoading(false);
            }
        }, 350);

        return () => {
            controller.abort();
            clearTimeout(debounceTimer);
        };
    }, [isEditing, streetAddress, googleApiKey]);

    const contactDetails = useMemo(
        () => [
            { label: 'Email', value: driverData?.email || '-', icon: 'Mail' },
            { label: 'Phone', value: formatPhoneNumber(String(driverData?.mobilePhone || '')) || '-', icon: 'Phone' },
            { label: 'Date of Birth', value: driverData?.birthdate ? fDate(driverData.birthdate, formatStr.split.date) : '-', icon: 'Calendar' },
            { label: 'Street Address', value: driverData?.address?.street || '-', icon: 'House' },
            { label: 'Apt / Unit', value: driverData?.address?.apt || '-', icon: 'Building2' },
            {
                label: 'City, State, ZIP',
                value:
                    [driverData?.address?.city, driverData?.address?.state].filter(Boolean).join(', ') +
                    `${driverData?.address?.zipCode ? ` ${driverData.address.zipCode}` : ''}` ||
                    '-',
                icon: 'MapPin',
            },
        ],
        [driverData]
    );

    /*
    const licenseInformation = [
        { label: 'License Number', value: driverData?.licenseNumber || '-', icon: 'FileText' },
        { label: 'State', value: driverData?.cdlState || '-', icon: 'MapPin' },
        { label: 'Expiration Date', value: driverData?.licenseExpirationDate ? fDate(driverData.licenseExpirationDate) : '-', icon: 'Calendar' },
    ];
    */

    const handleEdit = () => {
        reset(mapDriverDataToForm(driverData));
        setAddressOptions([]);
        setIsAddressMenuOpen(false);
        setIsEditing(true);
    };

    const handleCancel = () => {
        reset(mapDriverDataToForm(driverData));
        setAddressOptions([]);
        setIsAddressMenuOpen(false);
        setIsEditing(false);
    };

    const handleAddressSelect = async (selectedOption: GoogleAddressSuggestion | null) => {
        if (!selectedOption || !googleApiKey) return;
        setIsAddressLoading(true);
        try {
            const response = await fetch(
                `https://places.googleapis.com/v1/places/${selectedOption.placeId}?fields=addressComponents,formattedAddress`,
                {
                    method: 'GET',
                    headers: {
                        'X-Goog-Api-Key': googleApiKey,

                    }
                }
            );

            if (!response.ok) return;

            const place = await response.json();
            const parsed = parseGoogleAddress(place?.addressComponents || []);

            setValue('streetAddress', parsed.streetAddress || selectedOption.mainText || selectedOption.description, {
                shouldDirty: true,
                shouldValidate: true,
            });
            setValue('apt', parsed.apt, { shouldDirty: true });
            setValue('city', parsed.city, { shouldDirty: true, shouldValidate: true });
            setValue('state', parsed.state, { shouldDirty: true, shouldValidate: true });
            setValue('stateCode', parsed.stateCode, { shouldDirty: true, shouldValidate: true });
            setValue('zipCode', parsed.zipCode, { shouldDirty: true, shouldValidate: true });
            setIsAddressMenuOpen(false);
        } finally {
            setIsAddressLoading(false);
        }
    };

    const onSubmit = handleSubmit(async (formData) => {
        const payload = {
            email: formData.email.trim(),
            mobilePhone: formData.mobilePhone.replace(/\D/g, '').slice(0, 10),
            birthdate: fDate(formData.birthdate, formatStr.paramCase.date),
            address: {
                street: formData.streetAddress.trim(),
                apt: formData.apt.trim() || undefined,
                city: formData.city.trim(),
                state: getUsStateName(formData.state) || formData.state.trim(),
                stateCode: formData.state.trim().toUpperCase() || undefined,
                zipCode: formData.zipCode.replace(/\D/g, '').slice(0, 5),
            }
        };
        try {
            setIsSaving(true);
            const response = await updateDriverProfileMutation.mutateAsync(payload);
            if (response?.StatusCode === constants.RESPONSE_STATUS.SUCCESS) {
                setDriverData((prev: any) => ({
                    ...prev,
                    ...response?.Result.data,
                    mobilePhone: formatPhoneNumber(response?.Result.data?.mobilePhone),
                }));
                setIsEditing(false);
                toasterService('Profile updated successfully.', 2, 'update-profile-success');
                return;
            }

            toasterService(response?.Message || 'Unable to update profile right now.', 4, 'update-profile-fail');
        } catch (error: any) {
            toasterService(error?.message || 'Unable to update profile right now.', 4, 'update-profile-catch');
        } finally {
            setIsSaving(false);
        }
    });

    return (
        <DashboardContent>
            <div className="p-2">
                <div className="mb-6 flex items-center gap-3">
                    <button
                        type="button"
                        onClick={() => navigate('/profile')}
                        className="flex h-10 w-10 items-center justify-center rounded-full bg-gray-100 transition-colors hover:bg-gray-200"
                    >
                        <LucideIcon name="ChevronLeft" size={20} color="#1e3a5f" />
                    </button>
                    <div>
                        <h1 className="mb-1 text-2xl text-[#1e3a5f]">
                            Your Information
                        </h1>
                        <p className="text-base text-gray-600">
                            Manage your contact details
                        </p>
                    </div>
                </div>

                <Card className="mb-6 rounded-2xl border border-gray-200 p-6 shadow-none">
                    <div className="mb-4 flex items-center justify-between">
                        <h2 className="text-xl text-[#1e3a5f]">
                            Contact Details
                        </h2>
                        {!isEditing && (
                            <button
                                type="button"
                                onClick={handleEdit}
                                className="flex items-center gap-1 text-[#dc2626] transition-colors hover:text-[#b91c1c]"
                            >
                                <LucideIcon name="Pen" size={16} />
                                <span className="text-base">Edit</span>
                            </button>
                        )}
                    </div>

                    {!isEditing && (
                        <div className="space-y-4">
                            {contactDetails.map((item) => (
                                <div key={item.label} className="flex items-center gap-3">
                                    <LucideIcon name={item.icon} size={20} color="#9ca3af" className="shrink-0" />
                                    <div className="flex-1">
                                        <div className="mb-1 text-sm text-gray-500">{item.label}</div>
                                        <div className="text-base text-[#1e3a5f]">{item.value}</div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}

                    {isEditing && (
                        <FormProvider methods={methods} onSubmit={onSubmit}>
                            <div className="space-y-4">
                            <div className="flex items-start gap-3">
                                <LucideIcon name="Mail" size={20} color="#9ca3af" className="mt-9 shrink-0" />
                                <Controller
                                    name="email"
                                    control={control}
                                    render={({ field, fieldState: { error } }) => (
                                        <div className="flex-1">
                                            <label className="mb-1 block text-sm text-gray-500">Email</label>
                                            <Input
                                                {...field}
                                                type="email"
                                                value={field.value || ''}
                                                className={`${profileInputClassName} ${error ? 'border-red-500 focus:border-red-500 focus:ring-red-500/20' : ''}`}
                                            />
                                            {error?.message && <p className="mt-1 text-sm text-red-600">{error.message}</p>}
                                        </div>
                                    )}
                                />
                            </div>

                            <div className="flex items-start gap-3">
                                <LucideIcon name="Phone" size={20} color="#9ca3af" className="mt-9 shrink-0" />
                                <Controller
                                    name="mobilePhone"
                                    control={control}
                                    render={({ field, fieldState: { error } }) => (
                                        <div className="flex-1">
                                            <label className="mb-1 block text-sm text-gray-500">Phone</label>
                                            <Input
                                                {...field}
                                                value={field.value || ''}
                                                placeholder="(555) 123-4567"
                                                className={`${profileInputClassName} ${error ? 'border-red-500 focus:border-red-500 focus:ring-red-500/20' : ''}`}
                                                onChange={(event) => {
                                                    field.onChange(formatPhoneNumber(event.target.value));
                                                }}
                                            />
                                            {error?.message && <p className="mt-1 text-sm text-red-600">{error.message}</p>}
                                        </div>
                                    )}
                                />
                            </div>

                            <div className="flex items-start gap-3">
                                <LucideIcon name="Calendar" size={20} color="#9ca3af" className="mt-9 shrink-0" />
                                <Controller
                                    name="birthdate"
                                    control={control}
                                    render={({ field, fieldState: { error } }) => (
                                        <div className="flex-1">
                                            <label className="mb-1 block text-sm text-gray-500">Date of Birth</label>
                                            <Input
                                                {...field}
                                                type="date"
                                                value={field.value || ''}
                                                max={today(formatStr.paramCase.fromYear)}
                                                className={`${profileInputClassName} ${error ? 'border-red-500 focus:border-red-500 focus:ring-red-500/20' : ''}`}
                                            />
                                            {error?.message && <p className="mt-1 text-sm text-red-600">{error.message}</p>}
                                        </div>
                                    )}
                                />
                            </div>

                            <div className="flex items-start gap-3">
                                <LucideIcon name="House" size={20} color="#9ca3af" className="mt-9 shrink-0" />
                                <Controller
                                    name="streetAddress"
                                    control={control}
                                    render={({ field, fieldState: { error } }) => (
                                        <div ref={addressFieldRef} className="relative z-30 flex-1">
                                            <label className="mb-1 block text-sm text-gray-500">Street Address</label>
                                            <div className="relative">
                                                <Input
                                                    {...field}
                                                    value={field.value || ''}
                                                    onFocus={() => setIsAddressMenuOpen(true)}
                                                    onBlur={(event) => {
                                                        field.onBlur();
                                                    }}
                                                    className={`${profileInputClassName} ${error ? 'border-red-500 focus:border-red-500 focus:ring-red-500/20' : ''}`}
                                                    onChange={(event) => {
                                                        field.onChange(event.target.value);
                                                        setIsAddressMenuOpen(true);
                                                    }}
                                                />
                                                {isAddressLoading && (
                                                    <div className="absolute right-4 top-1/2 -translate-y-1/2">
                                                        <div className="h-[18px] w-[18px] animate-spin rounded-full border-2 border-slate-300 border-t-[#dc2626]" />
                                                    </div>
                                                )}
                                            </div>
                                            {error?.message ? (
                                                <p className="mt-1 text-sm text-red-600">{error.message}</p>
                                            ) : !googleApiKey ? (
                                                <p className="mt-1 text-sm text-slate-500">
                                                    Set VITE_GOOGLE_MAPS_API_KEY in your .env to enable address search
                                                </p>
                                            ) : null}

                                            {shouldShowAddressOptions && (
                                                <div className="absolute left-0 right-0 top-full z-[100] mt-2 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl ring-1 ring-black/5">
                                                    {addressOptions.length > 0 ? (
                                                        <ul className="max-h-64 overflow-auto py-2">
                                                            {addressOptions.map((option) => (
                                                                <li key={option.placeId}>
                                                                    <button
                                                                        type="button"
                                                                        onMouseDown={(event) => {
                                                                            event.preventDefault();
                                                                            handleAddressSelect(option);
                                                                        }}
                                                                        className="w-full px-4 py-3 text-left transition hover:bg-slate-50"
                                                                    >
                                                                        <p className="text-sm font-semibold text-slate-900">
                                                                            {option.mainText}
                                                                        </p>
                                                                        <p className="text-xs text-slate-500">
                                                                            {option.secondaryText || option.description}
                                                                        </p>
                                                                    </button>
                                                                </li>
                                                            ))}
                                                        </ul>
                                                    ) : isAddressLoading ? (
                                                        <div className="px-4 py-3 text-sm text-slate-500">
                                                            Searching addresses...
                                                        </div>
                                                    ) : !isAddressLoading ? (
                                                        <div className="px-4 py-3 text-sm text-slate-500">
                                                            No address matches found
                                                        </div>
                                                    ) : null}
                                                </div>
                                            )}
                                        </div>
                                    )}
                                />
                            </div>

                            <div className="flex items-start gap-3">
                                <LucideIcon name="Building2" size={20} color="#9ca3af" className="mt-9 shrink-0" />
                                <Controller
                                    name="apt"
                                    control={control}
                                    render={({ field, fieldState: { error } }) => (
                                        <div className="flex-1">
                                            <label className="mb-1 block text-sm text-gray-500">Apt / Unit</label>
                                            <Input
                                                {...field}
                                                value={field.value || ''}
                                                placeholder="Apt, suite, unit"
                                                className={`${profileInputClassName} ${error ? 'border-red-500 focus:border-red-500 focus:ring-red-500/20' : ''}`}
                                            />
                                            {error?.message && <p className="mt-1 text-sm text-red-600">{error.message}</p>}
                                        </div>
                                    )}
                                />
                            </div>

                            <div className="flex items-start gap-3">
                                <LucideIcon name="MapPin" size={20} color="#9ca3af" className="mt-9 shrink-0" />
                                <div className="flex-1">
                                    <label className="mb-1 block text-sm text-gray-500">City, State, ZIP</label>
                                    <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
                                        <Controller
                                            name="city"
                                            control={control}
                                            render={({ field, fieldState: { error } }) => (
                                                <div className="col-span-2 min-w-0 sm:col-span-2">
                                                    <Input
                                                        {...field}
                                                        value={field.value || ''}
                                                        placeholder="City"
                                                        className={`${profileInputClassName} ${error ? 'border-red-500 focus:border-red-500 focus:ring-red-500/20' : ''}`}
                                                    />
                                                </div>
                                            )}
                                        />
                                        <RHFSelectbox
                                            label=''
                                            name="state"
                                            menus={US_STATE_SELECT_OPTIONS}
                                            cclass="min-w-0 sm:col-span-1 my-0"
                                            className="max-w-[100%] h-11 rounded-lg border border-gray-300 bg-white px-3 py-2 pr-10 text-base text-[#1e3a5f] shadow-none focus:border-[#dc2626] focus:ring-[#dc2626]/20"
                                            onChange={(event) => {
                                                setValue('stateCode', event.target.value || null, {
                                                    shouldDirty: true,
                                                    shouldValidate: true,
                                                });
                                            }}
                                        />
                                        <Controller
                                            name="zipCode"
                                            control={control}
                                            render={({ field, fieldState: { error } }) => (
                                                <div className="min-w-0 sm:col-span-2">
                                                    <Input
                                                        {...field}
                                                        value={field.value || ''}
                                                        placeholder="ZIP"
                                                        maxLength={5}
                                                        inputMode="numeric"
                                                        className={`${profileInputClassName} ${error ? 'border-red-500 focus:border-red-500 focus:ring-red-500/20' : ''}`}
                                                        onChange={(event) => {
                                                            field.onChange(event.target.value.replace(/\D/g, '').slice(0, 5));
                                                        }}
                                                    />
                                                </div>
                                            )}
                                        />
                                    </div>
                                    {(methods.formState.errors.city?.message || methods.formState.errors.zipCode?.message) && (
                                        <p className="mt-1 text-sm text-red-600">
                                            {methods.formState.errors.city?.message || methods.formState.errors.zipCode?.message}
                                        </p>
                                    )}
                                </div>
                            </div>

                            <div className="mt-4 flex gap-2">
                                <button
                                    type="button"
                                    onClick={handleCancel}
                                    disabled={isSaving}
                                    className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-gray-100 px-4 py-2 text-base text-gray-700 transition-colors hover:bg-gray-200 disabled:cursor-not-allowed disabled:opacity-60"
                                >
                                    <LucideIcon name="X" size={16} color="currentColor" />
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    disabled={isSaving}
                                    className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-[#1e3a5f] px-4 py-2 text-base text-white transition-colors hover:bg-[#2d4a70] disabled:cursor-not-allowed disabled:opacity-60"
                                >
                                    {isSaving ? (
                                        <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
                                    ) : (
                                        <LucideIcon name="Check" size={16} color="#ffffff" />
                                    )}
                                    {isSaving ? 'Saving...' : 'Save'}
                                </button>
                            </div>
                            </div>
                        </FormProvider>
                    )}
                </Card>

                {/*
                <Card className="mb-6 rounded-2xl border border-gray-200 p-6 shadow-none">
                    <h2 className="mb-4 text-xl text-[#1e3a5f]">
                        License Information
                    </h2>

                    <div className="space-y-4">
                        {licenseInformation.map((item) => (
                            <div key={item.label} className="flex items-center gap-3">
                                <LucideIcon name={item.icon} size={20} color="#9ca3af" className="shrink-0" />
                                <div className="flex-1">
                                    <div className="mb-1 text-sm text-gray-500">{item.label}</div>
                                    <div className="text-base text-[#1e3a5f]">{item.value}</div>
                                </div>
                            </div>
                        ))}
                    </div>

                    <div className={`${
                        isLicenseActive
                            ? 'mt-4 flex items-start gap-3 rounded-2xl border border-green-200 bg-green-50 p-4'
                            : 'mt-4 flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 p-4'
                    }`}>
                        <LucideIcon
                            name={isLicenseActive ? 'CircleCheckBig' : 'TriangleAlert'}
                            size={20}
                            color={isLicenseActive ? '#16a34a' : '#dc2626'}
                            className="mt-0.5 shrink-0"
                        />
                        <div>
                            <div className={isLicenseActive ? 'text-base text-green-900' : 'text-base text-red-900'}>
                                {isLicenseActive ? 'License Active' : 'License Expired'}
                            </div>
                            <div className={isLicenseActive ? 'mt-1 text-base text-green-700' : 'mt-1 text-base text-red-700'}>
                                {isLicenseActive ? 'Your CDL is valid and in good standing' : 'Your CDL has expired. Please renew your license.'}
                            </div>
                        </div>
                    </div>
                </Card>
                */}
            </div>
        </DashboardContent >
    );
}