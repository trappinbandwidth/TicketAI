import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';

// ----------------------------------------------------------------------

export function useRouter() {
  const navigate = useNavigate();

  const router = useMemo(
    () => ({
      back: () => navigate(-1),
      forward: () => navigate(1),
      refresh: () => navigate(0),
      push: (href: string) => navigate(href),
      replace: (href: string) => navigate(href, { replace: true }),
      newWindow: (href: string) => {
        window.open(href, '_blank');
      }
    }),
    [navigate]
  );

  return router;
}
