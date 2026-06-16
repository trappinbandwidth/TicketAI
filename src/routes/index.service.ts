import { httpService } from 'src/apiSetUp';
import { constants } from 'src/constants.value';

type UploadProfilePictureParams = {
  recordId: string;
  file: File;
  bucketName?: string;
};

type GetFilesParams = {
  bucketName: string;
  folderName: string;
};

export type AppVersionPlatform = 'android' | 'ios' | 'all';

export interface DriverAppVersionResult {
  LatestVersion?: string;
  MinSupportedVersion?: string;
  BuildNumber?: number;
  ForceUpdate?: boolean;
  ReleaseNotes?: string;
  UpdatedAt?: string;
}

export interface DriverAppVersionResponse {
  Status?: string;
  StatusCode?: number;
  Message?: string;
  Result?: DriverAppVersionResult;
}

export function GetUserDetails() {
  return httpService()
    .get(`${constants.API.GET_USER_DETAILS}`)
    .then((response) => response.data)
    .catch((error) => error.response.data);
}

export function GetDriverProfile() {
  return httpService()
    .get(`${constants.API.GET_DRIVER_PROFILE}`)
    .then((response) => response.data)
    .catch((error) => error.response.data);
}

export function UpdateDriverProfile(data: {
  email: string;
  mobilePhone: string;
  birthdate: string;
  address: {
    street: string;
    apt?: string;
    city: string;
    state: string;
    stateCode?: string;
    zipCode: string;
  };
}) {
  return httpService()
    .put(`${constants.API.UPDATE_DRIVER_PROFILE}`, data)
    .then((response) => response.data)
    .catch((error) => error.response?.data || { Status: 'ERROR', StatusCode: 500, Message: error.message });
}

export function CompleteDriverProfile(data: {
  firstName: string;
  lastName: string;
  email: string;
  phone: string;
  mobilePhone: string;
  birthdate: string;
  address: {
    street: string;
    apt?: string;
    city: string;
    state: string;
    stateCode?: string;
    zipCode: string;
    country: string;
  };
  // licenseInformation: {
  //   cdlNumber: string;
  //   cdlState: string;
  // };
  licenseInformation?: {
    cdlNumber: string;
    cdlState: string;
  };
}) {
  return httpService()
    .put(`${constants.API.UPDATE_DRIVER_PROFILE}`, data)
    .then((response) => response.data)
    .catch((error) => error.response?.data || { Status: 'ERROR', StatusCode: 500, Message: error.message });
}

export function uploadProfilePicture({ recordId, file, bucketName }: UploadProfilePictureParams) {
  const formData = new FormData();
  formData.append('RecordId', recordId);
  formData.append('File', file);

  if (bucketName) {
    formData.append('BucketName', bucketName);
  }

  return httpService(true)
    .post(constants.API.UPLOAD_PROFILE_PICTURE, formData)
    .then((response) => response.data)
    .catch((error) => error.response?.data || { Status: 'ERROR', StatusCode: 500, Message: error.message });
}

export function getFiles({ bucketName, folderName }: GetFilesParams) {
  return httpService()
    .get(`${constants.API.GET_TICKET_DOCUMENTS}?bucket=${encodeURIComponent(bucketName)}&folder=${encodeURIComponent(folderName)}`)
    .then((response) => response.data)
    .catch((error) => error.response?.data || { Status: 'ERROR', StatusCode: 500, Message: error.message });
}

export function getDriverAppVersion(platform: AppVersionPlatform = 'all'): Promise<DriverAppVersionResponse> {
  return httpService()
    .get(`${constants.API.GET_DRIVER_APP_VERSION}?platform=${encodeURIComponent(platform)}`)
    .then((response) => response.data)
    .catch((error) => error.response?.data || { Status: 'ERROR', StatusCode: 500, Message: error.message });
}