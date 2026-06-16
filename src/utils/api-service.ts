import { httpService } from 'src/apiSetUp';
import {
  DriverUserSimpleRegistrationNormalizedResult,
  DriverUserSimpleRegistrationRequest,
  DriverUserSimpleRegistrationResponse,
  ManagePaymentMethodRequest,
  PaymentMethodStatusResponse,
  RegisterDriverUserNormalizedResult,
  RegisterDriverUserRequest,
  RegisterDriverUserResponse,
  SendOTPRequest,
  VerifyOTPRequest,
} from 'src/common-service/types.interface';
import { constants } from 'src/constants.value';


export function getDriverPaymentMethods() {
  return httpService()
    .get(`${constants.API.GET_DRIVER_PAYMENT_METHODS}`)
    .then((response) => response.data)
    .catch((error) => error.response.data);
}
export function getDriverTransactions() {
  return httpService()
    .get(`${constants.API.GET_DRIVER_TRANSACTIONS}`)
    .then((response) => response.data)
    .catch((error) => error.response.data);
}

export function manageDriverPaymentMethod(data: ManagePaymentMethodRequest) {
  return httpService()
    .post(constants.API.MANAGE_DRIVER_PAYMENT_METHOD, data)
    .then((response) => response.data)
    .catch((error) => error.response?.data || { Status: 'ERROR', StatusCode: 500, Message: error.message });
}

export function getDriverPaymentMethodStatus(paymentMethodId: string, operationType: string): Promise<PaymentMethodStatusResponse> {
  return httpService()
    .get(`${constants.API.GET_DRIVER_PAYMENT_METHOD_STATUS}?paymentMethodId=${encodeURIComponent(paymentMethodId)}&operationType=${encodeURIComponent(operationType)}`)
    .then((response) => response.data)
    .catch((error) => error.response?.data || { Status: 'ERROR', StatusCode: 500, Message: error.message });
}
export function getDriverMVRs(pageSize: number = 20, lastId?: string, lastCreatedDate?: string) {
  const params: any = { pageSize };
  if (lastId) params.lastId = lastId;
  if (lastCreatedDate) params.lastCreatedDate = lastCreatedDate;

  return httpService()
    .get(`${constants.API.GET_DRIVER_MVRS}`, { params })
    .then((response) => response.data)
    .catch((error) => error.response.data);
}

export function getDriverTickets(pageSize: number = 20, lastId?: string, lastCreatedDate?: string) {
  const params: any = { pageSize };
  if (lastId) params.lastId = lastId;
  if (lastCreatedDate) params.lastCreatedDate = lastCreatedDate;

  return httpService()
    .get(`${constants.API.GET_DRIVER_TICKETS}`, { params })
    .then((response) => response.data)
    .catch((error) => error.response.data);
}

export function getDriverTicketDetail(ticketId: string) {
  return httpService()
    .get(`${constants.API.GET_DRIVER_TICKETS}/${ticketId}`)
    .then((response) => response.data)
    .catch((error) => error.response.data);
}

export function getReferrals(pageSize: number = 20, lastId?: string, lastCreatedDate?: string) {
  const params: any = { pageSize };
  if (lastId) params.lastId = lastId;
  if (lastCreatedDate) params.lastCreatedDate = lastCreatedDate;

  return httpService()
    .get(`${constants.API.GET_REFERRALS}`, { params })
    .then((response) => response.data)
    .catch((error) => error.response.data);
}
export function SendOTP(data: SendOTPRequest) {
  return httpService()
    .post(constants.API.SEND_OTP, data)
    .then((response) => response.data)
    .catch((error) => error.response.data);
}

export function VerifyOTP(data: VerifyOTPRequest) {
  return httpService()
    .post(constants.API.VERIFY_OTP, data)
    .then((response) => response.data)
    .catch((error) => error.response.data);
}

export function GetMenuItems() {
  return httpService()
    .get(constants.API.GET_MENU_ITEMS)
    .then((response) => response.data)
    .catch((error) => error.response.data);
}

export function upgradeMembership(
  sourceTier: string,
  targetTier: string,
  billingCycle: 'monthly' | 'quarterly' | 'annually'
) {
  return httpService()
    .post(constants.API.UPGRADE_MEMBERSHIP, {
      sourceTier,
      targetTier,
      billingCycle,
    })
    .then((response) => response.data)
    .catch((error) => error.response.data);
}

export function getConfigData(dataType: string) {
  return httpService()
    .get(`${constants.API.GET_CONFIG_DATA}?data_type=${dataType}`)
    .then((response) => response.data)
    .catch((error) => error.response.data);
}

export function submitGuestTicket(data: {
  firstName: string;
  lastName: string;
  email: string;
  phone: string;
  ticket: {
    violationType: string;
    ticketDate: string;
    courtDate: string;
    location: string;
    description?: string;
  };
}) {
  return httpService()
    .post(constants.API.DRIVER_USER_TICKET_REGISTRATION, data)
    .then((response) => response.data)
    .catch((error) => error.response.data);
}

export function driverUserSimpleRegistration(
  data: DriverUserSimpleRegistrationRequest
): Promise<DriverUserSimpleRegistrationNormalizedResult> {
  return httpService()
    .post(constants.API.DRIVER_USER_SIMPLE_REGISTRATION, data)
    .then((response) => response.data as DriverUserSimpleRegistrationResponse)
    .catch(
      (error) =>
        ({
          Status: 'FAILURE',
          StatusCode: error.response?.status || 500,
          Result: error.response?.data?.Result || null,
          Errors: error.response?.data?.Errors || [],
          Message: error.response?.data?.Message || error.response?.data?.message || error.message,
        }) as DriverUserSimpleRegistrationResponse
    )
    .then((response) => ({
      statusCode: response.StatusCode,
      isSuccess:
        response.StatusCode === constants.RESPONSE_STATUS.SUCCESS &&
        response.Status?.toUpperCase() === 'SUCCESS' &&
        response.Result?.status?.toLowerCase() === 'success',
      message:
        response.Result?.message ||
        response.Message ||
        response.Errors?.[0]?.Message ||
        'Failed to create driver registration.',
      driverId: response.Result?.data?.driverId || null,
      errors: response.Errors || [],
      raw: response,
    }));
}

export function registerDriverUser(data: RegisterDriverUserRequest): Promise<RegisterDriverUserNormalizedResult> {
  return httpService()
    .post(constants.API.REGISTER_DRIVER_USER, data)
    .then((response) => response.data as RegisterDriverUserResponse)
    .catch(
      (error) =>
        ({
          Status: 'FAILURE',
          StatusCode: error.response?.status || 500,
          Result: null,
          Errors: error.response?.data?.Errors || [],
          Message: error.response?.data?.Message || error.message,
        }) as RegisterDriverUserResponse
    )
    .then((response) => ({
      statusCode: response.StatusCode,
      message: response.Message || response.Errors?.[0]?.Message || 'Driver registration failed.',
      accessToken: response.Result?.Data?.AccessToken || null,
      refreshToken: response.Result?.Data?.RefreshToken || null,
      driverId: response.Result?.DriverId || null,
      isNewDriver: response.Result?.IsNewDriver ?? false,
      errors: response.Errors || [],
      raw: response,
    }));
}

export function getRegistrationProducts() {
  return httpService()
    .get(constants.API.REGISTRATION_PRODUCTS)
    .then((response) => response.data)
    .catch((error) => error.response.data);
}
export function driverRegistration(data: {
  firstName: string;
  lastName: string;
  email: string;
  phone: string;
  city: string;
  state: string;
  zipCode: string;
  cdlNumber?: string;
  cdlState?: string;
  product: string;
  billingFrequency: string;
  amount: string;
}) {
  return httpService()
    .post(constants.API.DRIVER_REGISTRATION, data)
    .then((response) => response.data)
    .catch((error) => error.response.data);
}

export function uploadCaseDocuments(formData: FormData) {
  return httpService(true)
    .post(constants.API.UPLOAD_CASE_DOCUMENTS, formData)
    .then((response) => response.data)
    .catch((error) => error.response.data);
}
export function driverRegistraction(data: any) {
  return httpService()
    .post(constants.API.REGISTER_DRIVER_USER, data)
    .then((response) => response.data)
    .catch((error) => error.response.data);
}

/**
 * Fetches documents from S3 for a specific ticket
 * @param ticketName - The ticket name/ID (e.g., 'Tckt-00003863')
 * @param bucket - Optional S3 bucket name, defaults to env variable
 * @returns Promise with the API response containing files list
 */
export function getTicketDocuments(folderPath: string) {
  const bucketName = import.meta.env.VITE_S3_BUCKET_NAME;

  return httpService()
    .get(`${constants.API.GET_TICKET_DOCUMENTS}?bucket=${bucketName}&folder=${encodeURIComponent(folderPath)}`)
    .then((response) => response.data)
    .catch((error) => error.response?.data || { Status: 'ERROR', StatusCode: 500, Message: error.message });
}

/**
 * Fetches the referral QR link for the current user
 * @returns Promise with the API response containing ReferralQrLink
 */
export function getReferralQrLink() {
  return httpService()
    .get(constants.API.GET_REFERRAL_QR_LINK)
    .then((response) => response.data)
    .catch((error) => error.response?.data || { Status: 'ERROR', StatusCode: 500, Message: error.message });
}

export function createDriverTicket(data: any) {
  return httpService()
    .post(constants.API.CREATE_DRIVER_TICKET, data)
    .then((response) => response.data)
    .catch((error) => error.response?.data || { Status: 'ERROR', StatusCode: 500, Message: error.message });
}

/**
 * Checks the status of a Stripe checkout session
 * @param sessionId - The Stripe checkout session ID
 * @returns Promise with the session status response
 */
export function GetSessionStatus(sessionId: string) {
  return httpService()
    .get(`${constants.API.GET_SESSION_STATUS}/${sessionId}`)
    .then((response) => response.data)
    .catch((error) => error.response?.data || { Status: 'ERROR', StatusCode: 500, Message: error.message });
}

export interface UpdateDriverRewardsRequest {
  driverPhone: string;
  driverEmail: string;
  requestInfo: {
    email: string;
    phone: string;
    amount: number;
  };
}

export function updateDriverRewards(data: UpdateDriverRewardsRequest) {
  return httpService()
    .put(constants.API.UPDATE_DRIVER_REWARDS, data)
    .then((response) => response.data)
    .catch((error) => error.response?.data || { Status: 'ERROR', StatusCode: 500, Message: error.message });
}
