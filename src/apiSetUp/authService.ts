import { CheckIfNotEmpty } from './stringUtils';
import { persistentStorage, initPersistentStorage, hasStoredToken } from 'src/utils/persistentStorage';

// Storage key for driver token
const DRIVER_TOKEN_KEY = 'driver_token';

const authModule = {
  isAuthenticated: false,

  /**
   * Initialize auth module - call this on app startup
   * Loads data from IndexedDB into memory cache
   */
  async init(): Promise<boolean> {
    const restored = await initPersistentStorage();
    if (hasStoredToken()) {
      this.isAuthenticated = true;
    }
    return restored;
  },

  /**
   * Check if user is logged in (synchronous)
   * Works after init() has been called
   */
  isLoggedIn(): boolean {
    const token = persistentStorage.getItemSync(DRIVER_TOKEN_KEY);
    return CheckIfNotEmpty(token ?? undefined);
  },

  /**
   * Check if user is logged in (async - checks IndexedDB too)
   */
  async isLoggedInAsync(): Promise<boolean> {
    const token = await persistentStorage.getItem(DRIVER_TOKEN_KEY);
    return CheckIfNotEmpty(token ?? undefined);
  },

  /**
   * Authenticate user and store token
   */
  async authenticate(token: string): Promise<void> {
    if (CheckIfNotEmpty(token)) {
      this.isAuthenticated = true;
      await persistentStorage.setItem(DRIVER_TOKEN_KEY, token);
    }
  },

  /**
   * Synchronous authenticate - use when you can't await
   */
  authenticateSync(token: string): void {
    if (CheckIfNotEmpty(token)) {
      this.isAuthenticated = true;
      persistentStorage.setItemSync(DRIVER_TOKEN_KEY, token);
    }
  },

  /**
   * Get stored token (async)
   */
  async getToken(): Promise<string | null> {
    return persistentStorage.getItem(DRIVER_TOKEN_KEY);
  },

  /**
   * Get stored token (sync) - works after init()
   */
  getTokenSync(): string | null {
    return persistentStorage.getItemSync(DRIVER_TOKEN_KEY);
  },

  /**
   * Sign out and clear all storage
   */
  async signOut(): Promise<void> {
    this.isAuthenticated = false;
    await persistentStorage.clear();
  },

  /**
   * Synchronous sign out
   */
  signOutSync(): void {
    this.isAuthenticated = false;
    persistentStorage.clearSync();
  },

  /**
   * Restore session on app start
   * Call this when the app initializes to restore auth state from IndexedDB
   */
  async restoreSession(): Promise<boolean> {
    const token = await persistentStorage.getItem(DRIVER_TOKEN_KEY);
    if (CheckIfNotEmpty(token ?? undefined)) {
      this.isAuthenticated = true;
      return true;
    }
    return false;
  }
};

export default authModule;
