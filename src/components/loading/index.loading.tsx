import { memo } from 'react';
import { LoadingScreen } from '../loading-screen';

interface LoadingScreenPros {
  loading: boolean;
}
const Loader = ({ loading }: LoadingScreenPros) => {
  return (
    <>
      {loading && <LoadingScreen />}
    </>
  );
};
export default memo(Loader);
