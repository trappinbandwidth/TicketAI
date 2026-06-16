/// <reference types="vite/client" />
/// <reference types="vite-plugin-pwa/client" />

// Environment variables
declare module '*.env' {
    export const VITE_APP_VERSION: string;
    export const VITE_REACT_APP_BASE_URL: string;
    export const VITE_STRIPE_PUBLISHABLE_KEY: string;
}

interface ImportMetaEnv {
    readonly VITE_APP_VERSION: string;
    readonly VITE_REACT_APP_BASE_URL: string;
    readonly VITE_STRIPE_PUBLISHABLE_KEY: string;
}

interface ImportMeta {
    readonly env: ImportMetaEnv;
}

// PWA Virtual Module
declare module 'virtual:pwa-register' {
    export interface RegisterSWOptions {
        immediate?: boolean;
        onNeedRefresh?: () => void;
        onOfflineReady?: () => void;
        onRegistered?: (registration: ServiceWorkerRegistration | undefined) => void;
        onRegisterError?: (error: Error) => void;
    }

    export function registerSW(options?: RegisterSWOptions): (reloadPage?: boolean) => Promise<void>;
}