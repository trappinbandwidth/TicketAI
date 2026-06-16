import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useAtom } from 'jotai';
import { Helmet } from 'react-helmet-async';
import { useNavigate } from 'react-router-dom';
import Cropper, { Area } from 'react-easy-crop';
import 'react-easy-crop/react-easy-crop.css';
import { CONFIG } from 'src/config-global';
import { driverProfile, isLoading } from 'src/store';
import { DashboardContent } from 'src/layouts/dashboard';
import LucideIcon from 'src/components/lucide-icon';
import { Avatar, AvatarFallback, AvatarImage, Button, Card, Modal, ModalContent, ModalTitle } from 'src/components/ui';
import authModule from 'src/apiSetUp/authService';
import { toasterService } from 'src/apiSetUp';
import { constants } from 'src/constants.value';
import { getFiles, uploadProfilePicture } from 'src/routes/index.service';

const createImage = (imageUrl: string): Promise<HTMLImageElement> =>
    new Promise((resolve, reject) => {
        const image = new Image();
        image.crossOrigin = 'anonymous';
        image.onload = () => resolve(image);
        image.onerror = reject;
        image.src = imageUrl;
    });

const getCroppedImageBlob = async (imageSrc: string, cropArea: Area): Promise<Blob> => {
    const image = await createImage(imageSrc);
    const outputSize = 720;
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');

    if (!context) {
        throw new Error('Failed to prepare image crop.');
    }

    canvas.width = outputSize;
    canvas.height = outputSize;

    context.drawImage(
        image,
        cropArea.x,
        cropArea.y,
        cropArea.width,
        cropArea.height,
        0,
        0,
        outputSize,
        outputSize
    );

    const blob = await new Promise<Blob | null>((resolve) => {
        canvas.toBlob(resolve, 'image/jpeg', 0.92);
    });

    if (!blob) {
        throw new Error('Failed to generate cropped image.');
    }

    return blob;
};

export default function ProfileHomePage() {
    const navigate = useNavigate();
    const [_driverProfile, setDriverProfileData] = useAtom(driverProfile);
    const [, setLoading] = useAtom(isLoading);
    const [isUploadingProfilePicture, setIsUploadingProfilePicture] = useState(false);
    const [isPreparingCropImage, setIsPreparingCropImage] = useState(false);
    const [localPreviewUrl, setLocalPreviewUrl] = useState('');
    const [imageForCrop, setImageForCrop] = useState('');
    const [isCropDialogOpen, setIsCropDialogOpen] = useState(false);
    const [cropPosition, setCropPosition] = useState({ x: 0, y: 0 });
    const [cropZoom, setCropZoom] = useState(1.2);
    const [croppedAreaPixels, setCroppedAreaPixels] = useState<Area | null>(null);
    const [isPhotoDragActive, setIsPhotoDragActive] = useState(false);
    const [isUpgradeModalOpen, setIsUpgradeModalOpen] = useState(false);
    const fileInputRef = useRef<HTMLInputElement | null>(null);
    const profileImageUrl = useMemo(
        () => localPreviewUrl || _driverProfile.profilePicture,
        [localPreviewUrl, _driverProfile]
    );

    const membershipSince = _driverProfile?.membershipInfo?.sinceYear || new Date().getFullYear();
    const initials = `${(_driverProfile?.firstName?.[0] || '').toUpperCase()}${(_driverProfile?.lastName?.[0] || '').toUpperCase()}` || 'JD';
    const carrierLabel = useMemo(() => {
        const candidates = [
            _driverProfile?.carrierFromDriver,
            _driverProfile?.carrierName,
            _driverProfile?.companyName,
            _driverProfile?.organizationName,
            _driverProfile?.employerName,
        ];

        return candidates.find((value): value is string => typeof value === 'string' && value.trim().length > 0) || '';
    }, [_driverProfile]);

    useEffect(() => () => {
        if (localPreviewUrl.startsWith('blob:')) {
            URL.revokeObjectURL(localPreviewUrl);
        }
    }, [localPreviewUrl]);

    useEffect(() => () => {
        if (imageForCrop.startsWith('blob:')) {
            URL.revokeObjectURL(imageForCrop);
        }
    }, [imageForCrop]);

    const handleLogout = () => {
        setLoading(true);
        // Clear all persistent storage (IndexedDB + localStorage)
        authModule.signOutSync();
        setTimeout(() => {
            window.location.reload();
        }, 0);
        setLoading(false);
    };

    interface MenuItem {
        id: string;
        label: string;
        sublabel: string;
        icon: string;
        onClick: () => void;
    }
    const MENU_ITEMS: MenuItem[] = [
        {
            id: 'info',
            label: 'Your Information',
            sublabel: 'Manage your contact details',
            icon: 'User',
            onClick: () => navigate('/profile/user-info'),
        },
        {
            id: 'billing',
            label: 'Billing & Payments',
            sublabel: 'Payment methods & transaction history',
            icon: 'CreditCard',
            onClick: () => navigate('/profile/billing'),
        },
    ];


    const handleProfilePictureUpload = useCallback(async (selectedFile: File) => {
        if (!selectedFile) return;

        if (!navigator.onLine) {
            toasterService('You are offline. Please reconnect and try again.', 4, 'profile-picture-offline');
            return;
        }

        const driverId = _driverProfile?.id;
        if (!driverId) {
            toasterService('Unable to identify your profile. Please refresh and try again.', 4, 'profile-picture-driver-id-missing');
            return;
        }

        const bucketName = import.meta.env.VITE_S3_BUCKET_NAME || 'cdl-salesforce-uat';
        const recordId = `001${driverId}`;
        const folderName = `profile_picture/${recordId}`;

        setIsUploadingProfilePicture(true);
        const previewUrl = URL.createObjectURL(selectedFile);
        setLocalPreviewUrl(previewUrl);

        try {
            const response = await uploadProfilePicture({
                recordId,
                file: selectedFile,
                bucketName,
            });

            if (response.StatusCode !== constants.RESPONSE_STATUS.SUCCESS) {
                toasterService(response?.Message || 'Failed to upload profile picture.', 4, 'profile-picture-upload-failed');
                if (previewUrl.startsWith('blob:')) {
                    URL.revokeObjectURL(previewUrl);
                }
                setLocalPreviewUrl('');
                return;
            }
            const _responseProfilePic = await getFiles({ bucketName, folderName });

            const files = _responseProfilePic?.Result?.files || _responseProfilePic?.files || [];
            if (!Array.isArray(files) || files.length === 0) {
                return;
            }

            const latestFile = [...files].sort((first: any, second: any) => {
                const firstTime = new Date(first?.lastModified || first?.LastModified || 0).getTime();
                const secondTime = new Date(second?.lastModified || second?.LastModified || 0).getTime();
                return secondTime - firstTime;
            })[0];

            const imageUrl = latestFile?.url || latestFile?.Url;
            if (!imageUrl) {
                return;
            }

            setDriverProfileData((prev: any) => ({
                ...prev,
                profilePicture: imageUrl
            }));

            setLocalPreviewUrl('');
            toasterService('Profile picture uploaded successfully', 2, 'profile-picture-upload-success');
        } catch (error: any) {
            toasterService(error?.message || 'Failed to upload profile picture.', 4, 'profile-picture-upload-error');
            if (previewUrl.startsWith('blob:')) {
                URL.revokeObjectURL(previewUrl);
            }
            setLocalPreviewUrl('');
        } finally {
            setIsUploadingProfilePicture(false);
            if (fileInputRef.current) {
                fileInputRef.current.value = '';
            }
        }
    }, [_driverProfile, setDriverProfileData]);

    const handleOpenCropDialog = useCallback((selectedFile: File) => {
        if (!selectedFile.type.startsWith('image/')) {
            toasterService('Please select a valid image file.', 4, 'profile-picture-invalid-file');
            return;
        }

        if (selectedFile.size > 10 * 1024 * 1024) {
            toasterService('Please select an image smaller than 10 MB.', 4, 'profile-picture-size-limit');
            return;
        }

        const sourceUrl = URL.createObjectURL(selectedFile);
        setImageForCrop(sourceUrl);
        setCropPosition({ x: 0, y: 0 });
        setCropZoom(1.2);
        setCroppedAreaPixels(null);
        setIsCropDialogOpen(true);
    }, []);

    const handleCropComplete = useCallback((_croppedArea: Area, nextCroppedAreaPixels: Area) => {
        setCroppedAreaPixels(nextCroppedAreaPixels);
    }, []);

    const handleCloseCropDialog = useCallback(() => {
        if (isPreparingCropImage || isUploadingProfilePicture) return;
        setIsCropDialogOpen(false);
        setImageForCrop('');
        setCroppedAreaPixels(null);
        if (fileInputRef.current) {
            fileInputRef.current.value = '';
        }
    }, [isPreparingCropImage, isUploadingProfilePicture]);

    const handleConfirmCrop = useCallback(async () => {
        if (!imageForCrop || !croppedAreaPixels) {
            toasterService('Please adjust your photo before continuing.', 4, 'profile-picture-crop-missing');
            return;
        }

        setIsPreparingCropImage(true);
        try {
            const croppedBlob = await getCroppedImageBlob(imageForCrop, croppedAreaPixels);
            const croppedFile = new File([croppedBlob], `profile-picture-${Date.now()}.jpg`, {
                type: 'image/jpeg',
                lastModified: Date.now(),
            });

            setIsCropDialogOpen(false);
            setImageForCrop('');
            setCroppedAreaPixels(null);

            await handleProfilePictureUpload(croppedFile);
        } catch (error: any) {
            toasterService(error?.message || 'Failed to crop image. Please try again.', 4, 'profile-picture-crop-fail');
        } finally {
            setIsPreparingCropImage(false);
        }
    }, [croppedAreaPixels, handleProfilePictureUpload, imageForCrop]);

    const handleProfilePictureInput = useCallback(async (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file) return;
        handleOpenCropDialog(file);
    }, [handleOpenCropDialog]);

    const handlePhotoDrop = useCallback(async (event: React.DragEvent<HTMLDivElement>) => {
        event.preventDefault();
        event.stopPropagation();
        setIsPhotoDragActive(false);

        const droppedFile = event.dataTransfer.files?.[0];
        if (!droppedFile) return;
        handleOpenCropDialog(droppedFile);
    }, [handleOpenCropDialog]);

    return (
        <>
            <Helmet>
                <title> {`Profile - ${CONFIG.appName}`}</title>
            </Helmet>

            <DashboardContent>
                <div className="mvp-page-shell">
                    <div className="relative">
                        <Card className="mb-6 rounded-3xl border-0 p-4 shadow-lg">
                            <div className="flex items-center gap-4">
                                <div
                                    title="Tap or drop an image to update your photo"
                                    className="relative"
                                >
                                    <div
                                        onClick={() => {
                                            if (!isUploadingProfilePicture && !isPreparingCropImage) {
                                                fileInputRef.current?.click();
                                            }
                                        }}
                                        onDragOver={(event) => {
                                            event.preventDefault();
                                            event.stopPropagation();
                                            setIsPhotoDragActive(true);
                                        }}
                                        onDragLeave={(event) => {
                                            event.preventDefault();
                                            event.stopPropagation();
                                            setIsPhotoDragActive(false);
                                        }}
                                        onDrop={handlePhotoDrop}
                                        className={`rounded-full border-2 border-dashed p-0.5 transition-all ${isPhotoDragActive ? 'border-[#1e3a5f]' : 'border-transparent'
                                            } ${isUploadingProfilePicture || isPreparingCropImage
                                                ? 'cursor-not-allowed opacity-70'
                                                : 'cursor-pointer'
                                            }`}
                                    >
                                        <input
                                            ref={fileInputRef}
                                            type="file"
                                            accept="image/*"
                                            onChange={handleProfilePictureInput}
                                            style={{ display: 'none' }}
                                            disabled={isUploadingProfilePicture || isPreparingCropImage}
                                        />

                                        <div className="relative">
                                            <Avatar className="h-20 w-20 border-2 border-gray-200 text-2xl shadow-[0_4px_12px_rgba(0,0,0,0.1)]">
                                                <AvatarImage src={profileImageUrl} alt={_driverProfile?.fullName} />
                                                <AvatarFallback className="bg-[#dc2626] text-2xl text-white">
                                                    {initials}
                                                </AvatarFallback>
                                            </Avatar>
                                            <span className="absolute bottom-0 right-0 flex h-7 w-7 items-center justify-center rounded-full bg-white shadow-[0_4px_12px_rgba(0,0,0,0.1)]">
                                                {isUploadingProfilePicture ? (
                                                    <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-slate-300 border-t-[#1e3a5f]" />
                                                ) : (
                                                    <LucideIcon name="Camera" size={18} color="#1e3a5f" />
                                                )}
                                            </span>
                                        </div>
                                    </div>
                                </div>

                                <div className="min-w-0 flex-1">
                                    <h1 className="mb-1 text-xl font-medium text-[#1e3a5f]">{_driverProfile?.fullName || 'Driver'}</h1>
                                    <p className="mb-2 text-base text-gray-600">Member since {membershipSince}</p>
                                    {carrierLabel && (
                                        <div className="inline-flex items-center gap-1.5 rounded-full border border-[#0D3E6B]/20 bg-[#0D3E6B]/10 px-3 py-1.5">
                                            <LucideIcon name="Truck" size={14} color="#0D3E6B" />
                                            <span className="truncate text-sm text-[#0D3E6B]">{carrierLabel}</span>
                                        </div>
                                    )}
                                </div>
                            </div>
                        </Card>

                        <div className="mb-6 space-y-3">
                            {MENU_ITEMS.map((item) => (
                                <button
                                    key={item.id}
                                    type="button"
                                    className="flex w-full items-center justify-between rounded-2xl border border-gray-200 bg-white p-4 text-left transition-shadow hover:shadow-md"
                                    onClick={item.onClick}
                                >
                                    <div className="flex items-center gap-3">
                                        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gray-100">
                                            <LucideIcon name={item.icon} size={20} color="#1e3a5f" />
                                        </div>
                                        <div className="text-left">
                                            <div className="text-lg text-[#1e3a5f]">{item.label}</div>
                                            <div className="text-base text-gray-500">{item.sublabel}</div>
                                        </div>
                                    </div>
                                    <LucideIcon name="ChevronRight" size={20} color="#9ca3af" />
                                </button>
                            ))}
                        </div>

                        <div className="mb-6 rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
                            <div className="mb-3 flex items-center gap-3">
                                <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-[#0D3E6B]/10">
                                    <LucideIcon name="Phone" size={20} color="#0D3E6B" />
                                </div>
                                <div className="flex-1">
                                    <div className="text-[#1e3a5f]">Need Support?</div>
                                    <div className="text-sm text-gray-500">Mon-Fri, 8AM-5PM CT</div>
                                </div>
                            </div>

                            <a
                                href="tel:+19133611575"
                                className="block w-full rounded-xl bg-[#0D3E6B] py-3 text-center text-lg text-white transition-colors hover:bg-[#1e3a5f]"
                            >
                                <span>(913) 361-1575</span>
                            </a>
                        </div>

                        <button
                            type="button"
                            className="mb-3 flex w-full items-center justify-center gap-2 rounded-2xl border border-gray-200 bg-white p-4 text-[#0D3E6B] transition-colors hover:bg-blue-50"
                            onClick={() => setIsUpgradeModalOpen(true)}
                        >
                            <LucideIcon name="TrendingUp" size={20} color="#0D3E6B" />
                            Upgrade Plan
                        </button>

                        <button
                            type="button"
                            onClick={handleLogout}
                            className="mb-6 flex w-full items-center justify-center gap-2 rounded-2xl border border-gray-200 bg-white p-4 text-[#dc2626] transition-colors hover:bg-red-50"
                        >
                            <LucideIcon name="LogOut" size={20} color="#dc2626" />
                            Sign Out
                        </button>

                        <div className="mt-8 text-center opacity-50">
                            <div className="text-sm text-gray-400">
                                Powered by Rig Resolve {new Date().getFullYear()} - V{CONFIG.appVersion}
                            </div>
                        </div>
                    </div>
                </div>

                <Modal open={isUpgradeModalOpen} onOpenChange={setIsUpgradeModalOpen}>
                    <ModalContent
                        hideCloseButton
                        className="bottom-0 top-auto w-full max-w-md -translate-y-0 overflow-hidden rounded-t-3xl border-0 p-0 sm:bottom-auto sm:top-1/2 sm:rounded-3xl sm:-translate-y-1/2"
                    >
                        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-gray-200 bg-white px-6 py-4">
                            <h3 className="text-xl text-[#1e3a5f]">Upgrade Your Plan</h3>
                            <button
                                type="button"
                                onClick={() => setIsUpgradeModalOpen(false)}
                                className="flex h-8 w-8 items-center justify-center rounded-full transition-colors hover:bg-gray-100"
                            >
                                <LucideIcon name="X" size={20} color="#6b7280" />
                            </button>
                        </div>

                        <div className="space-y-6 p-6">
                            <div className="py-4 text-center">
                                <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-[#1e3a5f]/10">
                                    <LucideIcon name="ArrowUpCircle" size={32} color="#1e3a5f" />
                                </div>
                                <h4 className="mb-2 text-xl text-[#1e3a5f]">Ready to Upgrade?</h4>
                                <p className="text-base text-gray-600">
                                    Contact our support team to upgrade your membership plan.
                                </p>
                            </div>

                            <div className="space-y-3">
                                <a
                                    href="tel:+19133611575"
                                    className="group flex items-center justify-between rounded-2xl bg-[#1e3a5f] p-5 text-white transition-colors hover:bg-[#152d47]"
                                >
                                    <div className="flex items-center gap-4">
                                        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-white/20">
                                            <LucideIcon name="Phone" size={24} color="#ffffff" />
                                        </div>
                                        <div className="text-left">
                                            <p className="mb-0.5 text-sm text-white">Call Support</p>
                                            <p className="text-lg text-white">(913) 361-1575</p>
                                        </div>
                                    </div>
                                    <LucideIcon name="ArrowRight" size={20} color="#ffffff" className="transition-transform group-hover:translate-x-1" />
                                </a>

                                <div className="flex items-start gap-3 rounded-2xl border border-[#1e3a5f]/20 bg-[#1e3a5f]/5 p-4">
                                    <LucideIcon name="Clock" size={20} color="#1e3a5f" className="mt-0.5 shrink-0" />
                                    <div>
                                        <p className="mb-1 text-sm text-[#1e3a5f]">Support Hours</p>
                                        <p className="text-sm text-[#1e3a5f]/80">Monday - Friday: 8am - 5pm CST</p>
                                    </div>
                                </div>
                            </div>

                            <button
                                type="button"
                                onClick={() => setIsUpgradeModalOpen(false)}
                                className="w-full rounded-xl bg-gray-100 py-3.5 text-base text-gray-700 transition-colors hover:bg-gray-200"
                            >
                                Close
                            </button>
                        </div>
                    </ModalContent>
                </Modal>

                <Modal open={isCropDialogOpen} onOpenChange={(nextOpen) => !nextOpen && handleCloseCropDialog()}>
                    <ModalContent className="max-w-2xl" hideCloseButton>
                        <div className="mb-4 flex items-start justify-between gap-4">
                            <div>
                                <ModalTitle>Adjust profile photo</ModalTitle>
                                <p className="mt-1 text-sm text-slate-500">
                                    Drag to center your face and use zoom for a perfect fit.
                                </p>
                            </div>
                        </div>
                        <div className="relative h-[280px] w-full overflow-hidden rounded-2xl bg-slate-900 sm:h-[340px]">
                            {imageForCrop && (
                                <Cropper
                                    objectFit="cover"
                                    image={imageForCrop}
                                    crop={cropPosition}
                                    zoom={cropZoom}
                                    aspect={1}
                                    cropShape="round"
                                    showGrid={false}
                                    onCropChange={setCropPosition}
                                    onCropComplete={handleCropComplete}
                                    onZoomChange={setCropZoom}
                                />
                            )}
                        </div>
                        <div className="px-1 pt-4">
                            <label htmlFor="profile-photo-zoom" className="text-xs text-slate-500">
                                Zoom
                            </label>
                            <input
                                id="profile-photo-zoom"
                                type="range"
                                min={1}
                                max={3}
                                step={0.05}
                                value={cropZoom}
                                onChange={(event) => setCropZoom(Number(event.target.value))}
                                disabled={isPreparingCropImage || isUploadingProfilePicture}
                                className="mt-2 h-2 w-full cursor-pointer appearance-none rounded-full bg-slate-200 accent-[#1a365d]"
                            />
                        </div>
                        <div className="mt-6 flex justify-end gap-3">
                            <Button
                                type="button"
                                variant="secondary"
                                onClick={handleCloseCropDialog}
                                disabled={isPreparingCropImage || isUploadingProfilePicture}
                                className="border border-slate-200 bg-white text-slate-700"
                            >
                                Cancel
                            </Button>
                            <Button
                                type="button"
                                onClick={handleConfirmCrop}
                                disabled={isPreparingCropImage || isUploadingProfilePicture}
                                className="gap-2"
                            >
                                {isPreparingCropImage && (
                                    <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/40 border-t-white" />
                                )}
                                {isPreparingCropImage ? 'Preparing...' : 'Save & Upload'}
                            </Button>
                        </div>
                    </ModalContent>
                </Modal>
            </DashboardContent>
        </>
    );
}
