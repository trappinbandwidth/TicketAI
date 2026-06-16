import 'src/global.css';
import { useEffect, useState } from 'react';
import { useAtom } from 'jotai';
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import { Router } from 'src/routes/sections';
import { ReactQueryProvider } from 'src/lib/react-query/react-query-provider';
import { useScrollToTop } from 'src/hooks/use-scroll-to-top';
import Loader from 'src/components/loading/index.loading';
import { useAppVersionSync } from 'src/hooks/use-app-version-sync';
import { isLoading, firebaseUid } from './store';
import authModule from './apiSetUp/authService';
import { getDataFromStorage } from 'src/common-service/index.service';

// ----------------------------------------------------------------------

export default function App() {
  const [loading] = useAtom(isLoading);
  const [, setFbUid] = useAtom(firebaseUid);
  const [isInitialized, setIsInitialized] = useState(false);

  useAppVersionSync();

  useScrollToTop();

  // Initialize persistent storage and restore session on app start
  useEffect(() => {
    const initApp = async () => {
      try {
        // Initialize auth module - loads tokens from IndexedDB into memory cache
        const restored = await authModule.init();

        if (restored) {
          console.log('Session restored from persistent storage');
        }

        // Restore Firebase UID from storage (set on OTP verify)
        const storedFbUid = await getDataFromStorage('firebase_uid');
        if (storedFbUid) {
          setFbUid(storedFbUid);
        }
      } catch (error) {
        console.warn('Error initializing app:', error);
      } finally {
        setIsInitialized(true);
      }
    };

    initApp();
  }, []);

  // Show loader while initializing (restoring session from IndexedDB)
  if (!isInitialized) {
    return <Loader loading={true} />;
  }

  return (
    <ReactQueryProvider>
      <Loader loading={loading} />
      <ToastContainer
        position="top-right"
        autoClose={1500}
        hideProgressBar={false}
        newestOnTop={false}
        rtl={false}
        pauseOnFocusLoss
        draggable
        pauseOnHover
        style={{ zIndex: 99999 }}
      />
      <Router />
    </ReactQueryProvider>
  );
}
