export const queryKeys = {
  registrationProducts: ['registration-products'] as const,
  configData: (type: string) => ['config-data', type] as const,
  driverProfile: ['driver-profile'] as const,
  menuItems: ['menu-items'] as const,
  ticketStatusConfig: ['ticket-status-config'] as const,
  driverTickets: (pageSize: number, lastId?: string, lastCreatedDate?: string) =>
    ['driver-tickets', pageSize, lastId || null, lastCreatedDate || null] as const,
  driverTicketsInfinite: (pageSize: number) => ['driver-tickets-infinite', pageSize] as const,
  referralsInfinite: (pageSize: number) => ['referrals-infinite', pageSize] as const,
  driverMvrsInfinite: (pageSize: number) => ['driver-mvrs-infinite', pageSize] as const,
  driverTicketDetail: (ticketId: string) => ['driver-ticket-detail', ticketId] as const,
  ticketDocuments: (ticketName: string) => ['ticket-documents', ticketName] as const,
  referralQrLink: ['referral-qr-link'] as const,
  driverPaymentMethods: ['driver-payment-methods'] as const,
  driverTransactions: ['driver-transactions'] as const,
  driverPaymentMethodStatus: (paymentMethodId: string, operationType: string) =>
    ['driver-payment-method-status', paymentMethodId, operationType] as const,
  sessionStatus: (sessionId: string) => ['session-status', sessionId] as const,
};
