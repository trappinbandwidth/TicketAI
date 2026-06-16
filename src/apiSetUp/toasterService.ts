import { toast } from 'react-toastify';
import { CheckIfNotEmpty } from './stringUtils';

interface ToastOptions {
  toastId?: any;
  position: any;
  autoClose: number;
  hideProgressBar: boolean;
  closeOnClick: boolean;
  pauseOnHover: boolean;
  draggable: boolean;
  maxOpened: number;
  preventDuplicates: number;
}

/**
 * Display toaster notification.
 * @param message Message to show on toaster
 * @param type Type of notification:
 *             1: info
 *             2: success
 *             3: warning
 *             4: error
 * @param id Toast ID
 */
export default function displayToast(message: string, type: number, id: any): void {
  const options: ToastOptions = {
    toastId: id,
    position: 'top-right',
    autoClose: 3000,
    hideProgressBar: false,
    closeOnClick: true,
    pauseOnHover: true,
    draggable: false,
    maxOpened: 1,
    preventDuplicates: 1,
  };

  if (CheckIfNotEmpty(message)) {
    switch (type) {
      case 1:
        toast.info(message, options);
        break;
      case 2:
        toast.success(message, options);
        break;
      case 3:
        toast.warn(message, options);
        break;
      case 4:
        toast.error(message, options);
        break;
      default:
        toast(message, options);
        break;
    }
  }
}
