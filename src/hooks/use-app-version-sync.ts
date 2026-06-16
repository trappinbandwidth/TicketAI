import { useCallback, useEffect, useRef } from 'react';
import { CONFIG } from 'src/config-global';
import { constants } from 'src/constants.value';
import {
    AppVersionPlatform,
    DriverAppVersionResult,
    getDriverAppVersion,
} from 'src/routes/index.service';

const POLL_INTERVAL_MS = 10 * 60 * 1000; // 10 minutes
const RETRY_DELAY_MS = 30 * 1000; // 30 seconds
const RELOAD_GUARD_KEY = 'app_version_reload_guard';
const RELOAD_GUARD_WINDOW_MS = 3 * 60 * 1000; // 3 minutes

const isDev = import.meta.env.DEV;

const logDev = (...args: unknown[]) => {
    if (isDev) {
        console.log('[AppVersionSync]', ...args);
    }
};

const warnDev = (...args: unknown[]) => {
    if (isDev) {
        console.warn('[AppVersionSync]', ...args);
    }
};

const parseBuildNumber = (value: unknown): number => {
    if (typeof value === 'number') return value;
    if (typeof value === 'string') {
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : 0;
    }
    return 0;
};

const getRuntimePlatform = (): AppVersionPlatform => {
    const ua = navigator.userAgent.toLowerCase();

    if (/android/.test(ua)) return 'android';
    if (/iphone|ipad|ipod|ios/.test(ua)) return 'ios';
    return 'all';
};

const getCurrentVersionMeta = () => {
    const currentVersion = (CONFIG.appVersion || '').toString();
    const currentBuild = parseBuildNumber(CONFIG.appVersion || '');
    return { currentVersion, currentBuild };
};

const shouldRequireUpdate = (result: DriverAppVersionResult) => {
    const { currentVersion, currentBuild } = getCurrentVersionMeta();

    const latestVersion = (result?.LatestVersion || '').toString();
    const serverBuild = parseBuildNumber(result?.BuildNumber);
    const forceUpdate = Boolean(result?.ForceUpdate);

    const versionMismatch = Boolean(currentVersion && latestVersion && currentVersion !== latestVersion);
    const buildMismatch = serverBuild > 0 && currentBuild > 0 && serverBuild !== currentBuild;

    return {
        needsUpdate: forceUpdate || versionMismatch || buildMismatch,
        latestVersion,
        serverBuild,
    };
};

const setReloadGuard = (signature: string) => {
    const payload = {
        signature,
        timestamp: Date.now(),
    };
    sessionStorage.setItem(RELOAD_GUARD_KEY, JSON.stringify(payload));
};

const isReloadGuardActive = (signature: string) => {
    const raw = sessionStorage.getItem(RELOAD_GUARD_KEY);
    if (!raw) return false;

    try {
        const parsed = JSON.parse(raw) as { signature?: string; timestamp?: number };
        const timestamp = parsed?.timestamp || 0;
        const withinWindow = Date.now() - timestamp < RELOAD_GUARD_WINDOW_MS;
        return withinWindow && parsed?.signature === signature;
    } catch {
        return false;
    }
};

const ensureReloadOnControllerChange = (signature: string) => {
    let hasReloaded = false;

    const onControllerChange = () => {
        if (hasReloaded) return;
        hasReloaded = true;
        setReloadGuard(signature);
        window.location.reload();
    };

    navigator.serviceWorker.addEventListener('controllerchange', onControllerChange, { once: true });
};

const requestServiceWorkerActivation = async (signature: string) => {
    if (!('serviceWorker' in navigator)) {
        logDev('Service worker is not supported in this environment.');
        return;
    }

    const registration = await navigator.serviceWorker.getRegistration();
    if (!registration) {
        logDev('No active service worker registration found.');
        return;
    }

    await registration.update();

    if (registration.waiting) {
        ensureReloadOnControllerChange(signature);
        registration.waiting.postMessage({ type: 'SKIP_WAITING' });
        return;
    }

    if (registration.installing) {
        registration.installing.addEventListener('statechange', (event) => {
            const worker = event.target as ServiceWorker;
            if (worker.state === 'installed' && registration.waiting) {
                ensureReloadOnControllerChange(signature);
                registration.waiting.postMessage({ type: 'SKIP_WAITING' });
            }
        });
    }
};

export function useAppVersionSync() {
    const pollIntervalRef = useRef<number | null>(null);
    const retryTimeoutRef = useRef<number | null>(null);
    const inFlightRef = useRef(false);

    const clearRetryTimer = useCallback(() => {
        if (retryTimeoutRef.current) {
            window.clearTimeout(retryTimeoutRef.current);
            retryTimeoutRef.current = null;
        }
    }, []);

    const scheduleRetry = useCallback((runCheck: () => Promise<void>) => {
        clearRetryTimer();
        retryTimeoutRef.current = window.setTimeout(() => {
            runCheck();
        }, RETRY_DELAY_MS);
    }, [clearRetryTimer]);

    const runVersionCheck = useCallback(async () => {
        if (inFlightRef.current) return;
        inFlightRef.current = true;

        try {
            //   const platform = getRuntimePlatform();
            const response = await getDriverAppVersion();

            if (response?.StatusCode && response.StatusCode !== constants.RESPONSE_STATUS.SUCCESS) {
                warnDev('Version API returned non-success status.', response?.StatusCode, response?.Message);
                return;
            }

            const result = response?.Result;
            if (!result) {
                warnDev('Version API returned empty result payload.');
                return;
            }

            const { needsUpdate, latestVersion, serverBuild } = shouldRequireUpdate(result);
            if (!needsUpdate) {
                logDev('App version is up to date.');
                return;
            }

            const signature = `${latestVersion || 'unknown'}:${serverBuild || 0}:${Boolean(result.ForceUpdate)}`;
            if (isReloadGuardActive(signature)) {
                logDev('Reload guard active, skipping duplicate update reload.');
                return;
            }

            logDev('Update required. Requesting service worker activation.', {
                latestVersion: result.LatestVersion,
                minSupportedVersion: result.MinSupportedVersion,
                buildNumber: result.BuildNumber,
                forceUpdate: result.ForceUpdate,
                updatedAt: result.UpdatedAt,
            });

            await requestServiceWorkerActivation(signature);
        } catch (error) {
            warnDev('Version check failed. Scheduling retry.', error);
            scheduleRetry(runVersionCheck);
        } finally {
            inFlightRef.current = false;
        }
    }, [scheduleRetry]);

    useEffect(() => {
        runVersionCheck();

        pollIntervalRef.current = window.setInterval(() => {
            runVersionCheck();
        }, POLL_INTERVAL_MS);

        const onVisibilityChange = () => {
            if (document.visibilityState === 'visible') {
                runVersionCheck();
            }
        };

        const onOnline = () => {
            runVersionCheck();
        };

        document.addEventListener('visibilitychange', onVisibilityChange);
        window.addEventListener('online', onOnline);

        return () => {
            if (pollIntervalRef.current) {
                window.clearInterval(pollIntervalRef.current);
                pollIntervalRef.current = null;
            }
            clearRetryTimer();
            document.removeEventListener('visibilitychange', onVisibilityChange);
            window.removeEventListener('online', onOnline);
        };
    }, [clearRetryTimer, runVersionCheck]);
}
