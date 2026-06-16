import * as jotai from 'jotai';
import { DriverTicketCases, DriverTicketItem } from './common-service/types.interface';

export const isLoading = jotai.atom<boolean>(false);
export const ticketLoading = jotai.atom<boolean>(false);
export const driverProfile = jotai.atom<any>({});
export const ticketStatusConfig = jotai.atom<any[]>([]);
export const ticketList = jotai.atom<DriverTicketCases>({ tickets: [], cases: [] });

// Firebase Auth UID — set after anonymous sign-in on successful OTP verify.
// Used as the Firestore driverId for all ticket reads/writes.
export const firebaseUid = jotai.atom<string>('');