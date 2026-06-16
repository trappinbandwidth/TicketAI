import ReactDOM from 'react-dom/client';
import { Suspense } from 'react';
import { BrowserRouter } from 'react-router-dom';
import { HelmetProvider } from 'react-helmet-async';

import App from './app';
import { registerSW } from 'virtual:pwa-register';

// ----------------------------------------------------------------------

registerSW({ immediate: true });
// ----------------------------------------------------------------------

const root = ReactDOM.createRoot(document.getElementById('root') as HTMLElement);

root.render(
  <HelmetProvider>
    <BrowserRouter basename="/">
      <Suspense>
        <App />
      </Suspense>
    </BrowserRouter>
  </HelmetProvider>
);

