import { useEffect } from 'react';
import { useRegisterSW } from 'virtual:pwa-register/react';

/**
 * PWA Update Handler Component
 * 
 * Automatically detects when a new version of the app is available
 * and prompts the user to reload to get the latest version.
 * 
 * Features:
 * - Auto-detects new service worker updates
 * - Shows notification with reload button
 * - Automatically reloads on button click
 * - Skips waiting and activates new service worker immediately
 */
export default function PWAUpdateHandler() {
    const {
        needRefresh: [needRefresh, setNeedRefresh],
        updateServiceWorker,
    } = useRegisterSW({
        onRegisteredSW(swUrl, registration) {
            console.log('Service Worker registered:', swUrl);

            // Check for updates every hour
            if (registration) {
                setInterval(() => {
                    console.log('Checking for updates...');
                    registration.update();
                }, 60 * 60 * 1000); // Check every hour
            }
        },
        onRegisterError(error) {
            console.error('Service Worker registration error:', error);
        },
        onNeedRefresh() {
            console.log('New content available, please refresh!');
        },
        onOfflineReady() {
            console.log('App ready to work offline');
        },
    });

    // Auto-reload when new version is available
    useEffect(() => {
        if (needRefresh) {
            console.log('New version detected, reloading app...');
            // Auto-reload after showing notification for 2 seconds
            const timer = setTimeout(() => {
                updateServiceWorker(true);
            }, 2000);

            return () => clearTimeout(timer);
        }
    }, [needRefresh, updateServiceWorker]);

    const handleUpdate = () => {
        setNeedRefresh(false);
        updateServiceWorker(true); // This will reload the page with new content
    };

    return (
        needRefresh ? (
            <div className="pointer-events-none fixed inset-x-0 top-8 z-[9999] flex justify-center px-4">
                <div
                    className="pointer-events-auto flex w-full max-w-md items-center gap-3 rounded-2xl border border-sky-300 bg-[#0D3E6B] px-4 py-3 text-white shadow-[0_4px_12px_rgba(0,0,0,0.15)]"
                    role="status"
                    aria-live="polite"
                >
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white/15">
                        <svg className="h-4 w-4 text-white" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                            <path fillRule="evenodd" d="M18 10A8 8 0 114.928 3.443a.75.75 0 11-.856 1.232A6.5 6.5 0 1016.5 10h-2.75a.75.75 0 010-1.5H18A.75.75 0 0118.75 9v4.25a.75.75 0 01-1.5 0V10z" clipRule="evenodd" />
                        </svg>
                    </div>
                    <p className="flex-1 text-[0.95rem] font-medium">
                        New version available! Reloading...
                    </p>
                    <button
                        type="button"
                        onClick={handleUpdate}
                        className="rounded-full bg-white/15 px-3 py-1.5 text-xs font-semibold tracking-wide text-white transition-colors hover:bg-white/25"
                    >
                        RELOAD
                    </button>
                </div>
            </div>
        ) : null
    );
}
