// ================== API Endpoints Interface ==================
export interface APIEndpoints {
  GET_DRIVER_PAYMENT_METHODS: string;
  GET_DRIVER_TRANSACTIONS: string;
  MANAGE_DRIVER_PAYMENT_METHOD: string;
  GET_DRIVER_PAYMENT_METHOD_STATUS: string;
  GET_DRIVER_MVRS: string;
  GET_MENU_ITEMS: string;
  GET_USER_DETAILS: string;
  GET_DRIVER_PROFILE: string;
  UPDATE_DRIVER_PROFILE: string;
  UPLOAD_PROFILE_PICTURE: string;
  GET_DRIVER_APP_VERSION: string;
  SEND_OTP: string;
  VERIFY_OTP: string;
  GET_DRIVER_TICKETS: string;
  GET_REFERRALS: string;
  UPGRADE_MEMBERSHIP: string;
  GET_CONFIG_DATA: string;
  DRIVER_USER_TICKET_REGISTRATION: string;
  DRIVER_USER_SIMPLE_REGISTRATION: string;
  REGISTRATION_PRODUCTS: string;
  CREATE_PAYMENT_INTENT: string;
  DRIVER_REGISTRATION: string;
  REGISTER_DRIVER_USER: string;
  UPLOAD_CASE_DOCUMENTS: string;
  GET_TICKET_DOCUMENTS: string;
  GET_REFERRAL_QR_LINK: string;
  CREATE_DRIVER_TICKET: string;
  GET_SESSION_STATUS: string;
  UPDATE_DRIVER_REWARDS: string;
}

// ================== S3 Document Interface ==================
export interface S3Document {
  size: string;
  lastModified: string;
  name: string;
  url: string;
}

export interface GetFilesResponse {
  Status: string;
  StatusCode: number;
  Result: {
    files: S3Document[];
  };
  Message: string;
}

// ================== Response Status Interface ==================
export interface ResponseStatus {
  SUCCESS: number;
  SUCCESS_MESSAGE: string;
}

// ================== Constants Interface ==================
export interface constantsVale {
  API_BASE: string;
  API_VERSION: string;
  API: APIEndpoints;
  PAGINATION_CURRENT_PAGE: number;
  PAGINATION_ITEM_PER_PAGE: number;
  PAGINATION_SELECTED_ITEMS: number;
  PAGINATION_MAXSIZE: number;
  RESPONSE_STATUS: ResponseStatus;
}

// ================== Pagination Params Interface ==================
export interface PaginationParams {
  pageSize?: number;
  lastId?: string;
  lastCreatedDate?: string;
}

// ================== OTP Request/Response Interfaces ==================
export interface SendOTPRequest {
  PhoneNumber: string;
  send_otp?: boolean;
}

export interface VerifyOTPRequest {
  PhoneNumber: string;
  OTPCode: string;
  verify_otp?: boolean;
}

// ================== Upgrade Membership Request/Response ==================
export interface UpgradeMembershipRequest {
  sourceTier: string;
  targetTier: string;
  billingCycle: 'monthly' | 'quarterly' | 'annually';
}

// ================== Guest Ticket Request ==================
export interface GuestTicketRequest {
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
}

// ================== Driver Registration Request ==================
export interface DriverRegistrationRequest {
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
}

export interface DriverUserSimpleRegistrationRequest {
  firstName: string;
  lastName: string;
  phone: string;
}

export interface DriverUserSimpleRegistrationData {
  ticketCase: unknown | null;
  membershipStatus: string;
  faultCase: unknown | null;
  driverId: string;
}

export interface DriverUserSimpleRegistrationResult {
  timestamp: string;
  status: string;
  message: string;
  data: DriverUserSimpleRegistrationData | null;
}

export interface DriverUserSimpleRegistrationResponse {
  Status: string;
  StatusCode: number;
  Result: DriverUserSimpleRegistrationResult | null;
  Errors?: APIErrorItem[];
  Message: string;
}

export interface DriverUserSimpleRegistrationNormalizedResult {
  statusCode: number;
  isSuccess: boolean;
  message: string;
  driverId: string | null;
  errors: APIErrorItem[];
  raw: DriverUserSimpleRegistrationResponse;
}

export interface RegisterDriverUserRequest {
  FirstName: string;
  LastName: string;
  PhoneNumber: string;
  Email: string;
  DriverId: string;
  IsMVR: boolean;
}

export interface APIErrorItem {
  Key: string;
  Message: string;
}

export interface DriverAuthTokens {
  AccessToken: string;
  RefreshToken: string;
}

export interface RegisterDriverUserResult {
  DriverId: string;
  Data: DriverAuthTokens;
  IsNewDriver: boolean;
  Message: string;
}

export interface RegisterDriverUserResponse {
  Status: string;
  StatusCode: number;
  Result: RegisterDriverUserResult | null;
  Errors?: APIErrorItem[];
  Message: string;
}

export interface RegisterDriverUserNormalizedResult {
  statusCode: number;
  message: string;
  accessToken: string | null;
  refreshToken: string | null;
  driverId: string | null;
  isNewDriver: boolean;
  errors: APIErrorItem[];
  raw: RegisterDriverUserResponse;
}

// ================== Payment Intent Request/Response ==================
export interface CreatePaymentIntentRequest {
  amount: number;
  currency?: string;
  customerId?: string;
}

// ================== Payment Method Interface ==================
export interface PaymentMethod {
  id: string;
  cardOwnerType?: string;
  cardBrand?: string;
  last4?: string;
  expiryMonth?: number;
  expiryYear?: number;
  isDefault?: boolean;
}

export type ManagePaymentMethodAction = 'create' | 'setDefault' | 'delete';

export interface ManagePaymentMethodRequest {
  action: ManagePaymentMethodAction;
  cardHolderName?: string;
  cardNumber?: string;
  expirationMonth?: string;
  expirationYear?: string;
  cvv?: string;
  billingPostalCode?: string;
  isDefault?: boolean;
  paymentMethodId?: string;
}

export interface PaymentMethodStatusResponse {
  Status: string;
  StatusCode: number;
  Result?: {
    timestamp?: string;
    status?: string;
    message?: string;
    data?: {
      state: string;
      id?: string;
      status?: string | null;
      isProcessed?: boolean;
    };
  };
  Errors?: Array<{ Key: string; Message: string }>;
  Message?: string;
}

// ================== Transaction Interface ==================
export interface Transaction {
  id: string;
  amount: number;
  currency: string;
  status: string;
  createdAt: string;
  description?: string;
  type?: string;
}

// ================== MVR Record Interface ==================
export interface MVRRecord {
  id: string;
  createdDate: string;
  status: string;
  reportDate?: string;
  driverName?: string;
}

// ================== Referral Interface ==================
export interface Referral {
  id: string;
  referredName: string;
  referredEmail?: string;
  status: string;
  createdDate: string;
  reward?: number;
}

// ================== Driver Profile Interface ==================
export interface DriverProfile {
  id: string;
  firstName: string;
  lastName: string;
  email: string;
  phone: string;
  city?: string;
  state?: string;
  zipCode?: string;
  cdlNumber?: string;
  cdlState?: string;
  membershipTier?: string;
  billingCycle?: string;
}

// ================== Menu Item Interface ==================
export interface MenuItem {
  id: string;
  title: string;
  path: string;
  icon?: string;
  children?: MenuItem[];
}

// ================== Registration Product Interface ==================
export interface RegistrationProduct {
  id: string;
  name: string;
  description?: string;
  price: number;
  billingFrequency: string;
  features?: string[];
}

export type NavContentProps = {
  data: {
    path: string;
    title: string;
    children?: Array<any>;
    isRedirect?: boolean;
    isActive?: boolean;
    icon: React.ReactNode;
    info?: React.ReactNode;
  }[];
  slots?: {
    topArea?: React.ReactNode;
    bottomArea?: React.ReactNode;
  };
  sx?: React.CSSProperties;
};
export interface TicketStatusConfigItem {
  value?: undefined;
  pathPercent: number;
  label: string;
  inPath: boolean;
  displayOrder: number;
  rawValues: Array<{
    value: string;
  }>; // Optional array of raw values that can also match this status
}

// ================== Driver Ticket Interface ==================
export interface TicketPaymentItem {
  transactionId: string;
  reason: string;
  payNow: number;
  payLater: number;
  dueDate: string;
  tinyUrl: string;
  ticketName: string;
  ticketId: string;
  stripeKey: string;
  opportunityId: string;
  contactName: string;
  contactId: string;
  contactEmail: string;
  accountName: string;
  accountId: string;
  accountEmail: string;
}

export interface TicketActions {
  payment?: {
    priority: number;
    label: string;
    items: TicketPaymentItem[];
  };
}
export interface DriverTicketCases {
  tickets: DriverTicketItem[];
  cases: CasesItem[];
}
export interface CasesItem {
  caseNumber: string;
  createdDate: string;
  description: string;
  id: string;
  priority: string;
  status: string;
  subject: string;
}
export interface DriverTicketItem {
  id: string;
  name?: string;
  stateCodeCitation: string;
  createdDate?: string;
  courtDate?: string;
  courtName?: string | null;
  violationCategory: string;
  violationDescription: string;
  violationLocation: string;
  ticketOutcome: string;
  paymentRequired: boolean | null;
  fineAmount: number | null;
  attorneyStatus: string;
  ticketStatus: string;
  attorney?: {
    name?: string;
    email?: string;
    phone?: string;
  } | null;
  actionRequired?: boolean;
  actions?: TicketActions;
}