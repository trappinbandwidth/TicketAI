import axios from 'axios';
import { getDataFromSessionStorage } from '../common-service/index.service';
import { constants } from '../constants.value';
import interceptor from './interceptor';

/**
 * httpsService: function to ajax call from frontend
 * it take params formdata which is an instance of FormData class which is optional
 * if params isn't provided then it will considered as plain http request and process with application/json format
 * if called with multipart formdata then it will return an instance of multipart/form-data request
 * @param {FormData} formData Multipart form data instance
 * @returns {AxiosInstance} Axios instance
 */
const httpsService = (formData:boolean = false) => {
  const instanceUrl = axios.create({
    baseURL: `${constants.API_BASE}/${constants.API_VERSION}`,
    transformRequest: [
      (data: any, headers: any) => {
        const token: string = getDataFromSessionStorage('driver_token');
        if (token) {
          headers.Authorization = `${token}`;
        }
        if (formData) {
          headers['Content-Type'] = 'multipart/form-data';
        } else {
          headers['Content-Type'] = 'application/json';
          data = JSON.stringify(data); // Stringify for application/json
        }
        return data; // Return the transformed data
      },
    ],
  });

  // Use arrow functions consistently for better readability
  instanceUrl.interceptors.request.use((request: any) => interceptor.requestHandler(request));
  instanceUrl.interceptors.response.use(
    (response) => interceptor.successHandler(response),
    (error) => interceptor.errorHandler(error)
  );

  return instanceUrl;
};

export default httpsService;
