import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import compression from "vite-plugin-compression";
import checker from 'vite-plugin-checker';
import { defineConfig } from 'vite';
import { chunkSplitPlugin } from 'vite-plugin-chunk-split';
import react from '@vitejs/plugin-react-swc';
import { VitePWA } from 'vite-plugin-pwa';

// ----------------------------------------------------------------------

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const PORT = 3039;
const APP_VERSION_STATE_PATH = path.resolve(__dirname, '.app-version.json');

const getAppVersion = () => {
  try {
    const rawState = fs.readFileSync(APP_VERSION_STATE_PATH, 'utf-8');
    const parsedState = JSON.parse(rawState) as { version?: string };
    return parsedState.version || '0.0.0';
  } catch {
    return '0.0.0';
  }
};

export default defineConfig({
  base: '/',
  define: {
    'import.meta.env.VITE_APP_VERSION': JSON.stringify(getAppVersion()),
  },
  plugins: [
    compression(),
    chunkSplitPlugin(),
    react(),
    checker({
      typescript: true,
      // eslint: {
      //   lintCommand: 'eslint "./src/**/*.{js,jsx,ts,tsx}"',
      //   dev: { logLevel: ['error'] },
      // },
      overlay: {
        position: 'tl',
        initialIsOpen: false,
      },
    }),
    VitePWA({
      registerType: 'autoUpdate',
      injectRegister: 'auto',
      includeAssets: ['favicon.ico', 'robots.txt', 'apple-touch-icon.png'],
      manifest: {
        name: 'CDL Legal Driver Portal',
        short_name: 'CDL Portal',
        description: 'Member portal for CDL Legal drivers to manage their profile, billing, MVR records, and support tickets.',
        theme_color: '#1976d2',
        background_color: '#ffffff',
        display: 'standalone',
        display_override: ['standalone', 'fullscreen'],
        orientation: 'portrait',
        scope: '/',
        start_url: '/',
        id: '/',
        categories: ['business', 'productivity'],
        prefer_related_applications: false,
        icons: [
          // Android Icons - Standard
          {
            src: '/icons/android/android-launchericon-48-48.png',
            sizes: '48x48',
            type: 'image/png',
            purpose: 'any'
          },
          {
            src: '/icons/android/android-launchericon-72-72.png',
            sizes: '72x72',
            type: 'image/png',
            purpose: 'any'
          },
          {
            src: '/icons/android/android-launchericon-96-96.png',
            sizes: '96x96',
            type: 'image/png',
            purpose: 'any'
          },
          {
            src: '/icons/android/android-launchericon-144-144.png',
            sizes: '144x144',
            type: 'image/png',
            purpose: 'any'
          },
          {
            src: '/icons/android/android-launchericon-192-192.png',
            sizes: '192x192',
            type: 'image/png',
            purpose: 'any'
          },
          {
            src: '/icons/android/android-launchericon-512-512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'any'
          },
          // Android Icons - Maskable (for adaptive icons)
          {
            src: '/icons/android/android-launchericon-192-192.png',
            sizes: '192x192',
            type: 'image/png',
            purpose: 'maskable'
          },
          {
            src: '/icons/android/android-launchericon-512-512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable'
          },
          // iOS Icons
          {
            src: '/icons/ios/128.png',
            sizes: '128x128',
            type: 'image/png',
            purpose: 'any'
          },
          {
            src: '/icons/ios/144.png',
            sizes: '144x144',
            type: 'image/png',
            purpose: 'any'
          },
          {
            src: '/icons/ios/152.png',
            sizes: '152x152',
            type: 'image/png',
            purpose: 'any'
          },
          {
            src: '/icons/ios/167.png',
            sizes: '167x167',
            type: 'image/png',
            purpose: 'any'
          },
          {
            src: '/icons/ios/180.png',
            sizes: '180x180',
            type: 'image/png',
            purpose: 'any'
          },
          {
            src: '/icons/ios/192.png',
            sizes: '192x192',
            type: 'image/png',
            purpose: 'any'
          },
          {
            src: '/icons/ios/256.png',
            sizes: '256x256',
            type: 'image/png',
            purpose: 'any'
          },
          {
            src: '/icons/ios/512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'any'
          },
          {
            src: '/icons/ios/1024.png',
            sizes: '1024x1024',
            type: 'image/png',
            purpose: 'any'
          }
        ],
        screenshots: [
          {
            src: '/icons/android/android-launchericon-512-512.png',
            sizes: '512x512',
            type: 'image/png',
            form_factor: 'wide',
            label: 'CDL Legal Driver Portal - Desktop View'
          },
          {
            src: '/icons/android/android-launchericon-512-512.png',
            sizes: '512x512',
            type: 'image/png',
            form_factor: 'narrow',
            label: 'CDL Legal Driver Portal - Mobile View'
          }
        ]
      },
      workbox: {
        navigateFallback: undefined,
        // Cache strategies
        runtimeCaching: [
          {
            urlPattern: ({ request }) => request.mode === 'navigate',
            handler: 'NetworkFirst',
            options: {
              cacheName: 'html-cache',
              networkTimeoutSeconds: 3,
            },
          },
          {
            // Static assets - Cache First strategy
            urlPattern: /\.(?:png|jpg|jpeg|svg|gif|webp|ico)$/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'images-cache',
              expiration: {
                maxEntries: 100,
                maxAgeSeconds: 60 * 60 * 24 * 30, // 30 days
              },
            },
          },
          {
            // Fonts - Cache First strategy
            urlPattern: /\.(?:woff|woff2|ttf|eot)$/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'fonts-cache',
              expiration: {
                maxEntries: 20,
                maxAgeSeconds: 60 * 60 * 24 * 365, // 1 year
              },
            },
          },
          {
            // CSS and JS - Stale While Revalidate
            urlPattern: /\.(?:css|js)$/i,
            handler: 'StaleWhileRevalidate',
            options: {
              cacheName: 'static-resources',
              expiration: {
                maxEntries: 60,
                maxAgeSeconds: 60 * 60 * 24 * 7, // 7 days
              },
            },
          },
          {
            // Google Fonts - Cache First
            urlPattern: /^https:\/\/fonts\.googleapis\.com\/.*/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'google-fonts-cache',
              expiration: {
                maxEntries: 10,
                maxAgeSeconds: 60 * 60 * 24 * 365, // 1 year
              },
              cacheableResponse: {
                statuses: [0, 200],
              },
            },
          },
        ],
        // Clean up old caches
        cleanupOutdatedCaches: true,
        // Skip waiting and claim clients immediately
        skipWaiting: true,
        clientsClaim: true,
      },
      devOptions: {
        enabled: false, // Disable PWA in development mode to avoid warnings
        type: 'module',
      },
    }),
  ],
  resolve: {
    alias: [
      {
        find: /^~(.+)/,
        replacement: path.join(process.cwd(), 'node_modules/$1'),
      },
      {
        find: /^src(.+)/,
        replacement: path.join(process.cwd(), 'src/$1'),
      },
    ],
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("node_modules")) {
            if (id.includes('/react/') || id.includes('/react-dom/') || id.includes('/react-router-dom/') || id.includes('/react-helmet-async/')) {
              return 'framework';
            }

            if (id.includes('/@tanstack/')) {
              return 'query';
            }

            if (id.includes('/@stripe/') || id.includes('/react-stripe-js/')) {
              return 'stripe';
            }

            if (id.includes('/react-hook-form/') || id.includes('/@hookform/') || id.includes('/yup/')) {
              return 'forms';
            }

            if (id.includes('/lucide-react/') || id.includes('/@iconify/react/')) {
              return 'icons';
            }

            if (id.includes('/jotai/') || id.includes('/axios/') || id.includes('/date-fns/') || id.includes('/dayjs/')) {
              return 'data';
            }

            return 'vendor';
          }
        },
      }
    },
    minify: 'terser',
    terserOptions: {
      maxWorkers: 3,
      compress: {
        drop_console: true, // Example: Removes console logs
      },
    },
    cssMinify: true,
    cssCodeSplit: true,
    sourcemap: false,
  },
  server: { port: PORT, host: true },
  preview: { port: PORT, host: true },
});
