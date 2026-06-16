import axios from 'axios';
import { constants } from '../constants.value';
import { getDataFromSessionStorage, setDataIntoSessionStorage } from '../common-service/index.service';
import { persistentStorage } from 'src/utils/persistentStorage';

let isRefreshing = false;
let failedQueue: Array<{ resolve: Function; reject: Function }> = [];

const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

const axiosMiddleware = {
  requestHandler(request: any): any {
    return request;
  },
  errorHandler(error: any): Promise<any> {
    const originalRequest = error.config;

    if (
      error?.response?.status === 401 &&
      error.response?.data?.Message === 'Token has been expired!' &&
      !originalRequest._retry
    ) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then((token) => {
          originalRequest.headers.Authorization = token;
          return axios(originalRequest);
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      const refreshToken = getDataFromSessionStorage('driver_refresh_token');
      if (!refreshToken) {
        persistentStorage.clearSync();
        window.location.replace('/');
        return Promise.reject(error);
      }

      return new Promise((resolve, reject) => {
        axios
          .post(`${constants.API_BASE}/${constants.API_VERSION}RefreshToken`, {
            RefreshToken: refreshToken,
          })
          .then(({ data }) => {
            const newAccessToken = data.Result.Data.AccessToken;
            const newRefreshToken = data.Result.Data.RefreshToken;
            setDataIntoSessionStorage('driver_token', newAccessToken);
            setDataIntoSessionStorage('driver_refresh_token', newRefreshToken);
            originalRequest.headers.Authorization = newAccessToken;
            processQueue(null, newAccessToken);
            resolve(axios(originalRequest));
          })
          .catch((err) => {
            processQueue(err, null);
            persistentStorage.clearSync();
            window.location.replace('/');
            reject(err);
          })
          .finally(() => {
            isRefreshing = false;
          });
      });
    }

    // If refresh token itself expired, force logout
    if (
      error?.response?.status === 401 &&
      ['Refresh token has been expired!', 'Invalid refresh token!'].includes(
        error.response?.data?.Message
      )
    ) {
      persistentStorage.clearSync();
      window.location.replace('/');
    }

    return Promise.reject(error);
  },
  successHandler(response: any): any {
    const { data } = response;
    return {
      status: true,
      data,
      ...(data.message && { message: data.message }),
    };
  },
};

export default axiosMiddleware;
