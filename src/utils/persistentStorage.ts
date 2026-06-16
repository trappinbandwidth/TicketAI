/**
 * Persistent Storage Utility
 * 
 * This module provides a robust storage solution for PWAs that persists data
 * even when the app is removed from recent apps on mobile devices.
 * 
 * Strategy:
 * - Uses IndexedDB as primary persistent storage (survives app kills on mobile)
 * - Falls back to localStorage if IndexedDB isn't available
 * - NO sessionStorage - it gets cleared when app is killed
 */

const DB_NAME = 'cdl_driver_app_storage';
const STORE_NAME = 'persistent_data';
const DB_VERSION = 1;

let dbInstance: IDBDatabase | null = null;
let dbInitPromise: Promise<IDBDatabase | null> | null = null;
let isInitialized = false;

/**
 * Initialize IndexedDB database
 */
const initDB = (): Promise<IDBDatabase | null> => {
  if (dbInitPromise) {
    return dbInitPromise;
  }

  dbInitPromise = new Promise((resolve) => {
    // Check if IndexedDB is available
    if (typeof window === 'undefined' || !window.indexedDB) {
      console.warn('IndexedDB not available, falling back to localStorage');
      resolve(null);
      return;
    }

    try {
      const request = indexedDB.open(DB_NAME, DB_VERSION);

      request.onerror = () => {
        console.warn('IndexedDB open failed, falling back to localStorage');
        resolve(null);
      };

      request.onsuccess = () => {
        dbInstance = request.result;
        resolve(dbInstance);
      };

      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result;
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          db.createObjectStore(STORE_NAME, { keyPath: 'key' });
        }
      };
    } catch (error) {
      console.warn('IndexedDB initialization error, falling back to localStorage', error);
      resolve(null);
    }
  });

  return dbInitPromise;
};

/**
 * Get data from IndexedDB
 */
const getFromIndexedDB = async (key: string): Promise<string | null> => {
  const db = await initDB();
  if (!db) return null;

  return new Promise((resolve) => {
    try {
      const transaction = db.transaction([STORE_NAME], 'readonly');
      const store = transaction.objectStore(STORE_NAME);
      const request = store.get(key);

      request.onerror = () => {
        console.warn('IndexedDB get error for key:', key);
        resolve(null);
      };

      request.onsuccess = () => {
        const result = request.result;
        resolve(result ? result.value : null);
      };
    } catch (error) {
      console.warn('IndexedDB get error:', error);
      resolve(null);
    }
  });
};

/**
 * Set data in IndexedDB
 */
const setInIndexedDB = async (key: string, value: string): Promise<boolean> => {
  const db = await initDB();
  if (!db) return false;

  return new Promise((resolve) => {
    try {
      const transaction = db.transaction([STORE_NAME], 'readwrite');
      const store = transaction.objectStore(STORE_NAME);
      const request = store.put({ key, value, timestamp: Date.now() });

      request.onerror = () => {
        console.warn('IndexedDB set error for key:', key);
        resolve(false);
      };

      request.onsuccess = () => {
        resolve(true);
      };
    } catch (error) {
      console.warn('IndexedDB set error:', error);
      resolve(false);
    }
  });
};

/**
 * Remove data from IndexedDB
 */
const removeFromIndexedDB = async (key: string): Promise<boolean> => {
  const db = await initDB();
  if (!db) return false;

  return new Promise((resolve) => {
    try {
      const transaction = db.transaction([STORE_NAME], 'readwrite');
      const store = transaction.objectStore(STORE_NAME);
      const request = store.delete(key);

      request.onerror = () => {
        console.warn('IndexedDB delete error for key:', key);
        resolve(false);
      };

      request.onsuccess = () => {
        resolve(true);
      };
    } catch (error) {
      console.warn('IndexedDB delete error:', error);
      resolve(false);
    }
  });
};

/**
 * Clear all data from IndexedDB
 */
const clearIndexedDB = async (): Promise<boolean> => {
  const db = await initDB();
  if (!db) return false;

  return new Promise((resolve) => {
    try {
      const transaction = db.transaction([STORE_NAME], 'readwrite');
      const store = transaction.objectStore(STORE_NAME);
      const request = store.clear();

      request.onerror = () => {
        console.warn('IndexedDB clear error');
        resolve(false);
      };

      request.onsuccess = () => {
        resolve(true);
      };
    } catch (error) {
      console.warn('IndexedDB clear error:', error);
      resolve(false);
    }
  });
};

// In-memory cache for fast synchronous access after initialization
const memoryCache: Map<string, string> = new Map();

/**
 * Persistent Storage API
 * 
 * Uses IndexedDB as primary storage with localStorage as fallback.
 * Also maintains an in-memory cache for fast synchronous access.
 */
export const persistentStorage = {
  /**
   * Check if storage is initialized
   */
  isReady(): boolean {
    return isInitialized;
  },

  /**
   * Get an item from persistent storage (async - checks IndexedDB)
   * @param key - The key to retrieve
   * @returns Promise resolving to the value or null
   */
  async getItem(key: string): Promise<string | null> {
    // Check memory cache first
    if (memoryCache.has(key)) {
      return memoryCache.get(key) || null;
    }

    // Try IndexedDB
    const indexedDBValue = await getFromIndexedDB(key);
    if (indexedDBValue !== null) {
      memoryCache.set(key, indexedDBValue);
      return indexedDBValue;
    }

    // Fallback to localStorage
    try {
      const localValue = localStorage.getItem(key);
      if (localValue !== null) {
        memoryCache.set(key, localValue);
        // Sync to IndexedDB for future use
        await setInIndexedDB(key, localValue);
      }
      return localValue;
    } catch (error) {
      console.warn('localStorage getItem error:', error);
      return null;
    }
  },

  /**
   * Set an item in persistent storage (async - stores in IndexedDB + localStorage)
   * @param key - The key to set
   * @param value - The value to store
   */
  async setItem(key: string, value: string): Promise<void> {
    // Update memory cache
    memoryCache.set(key, value);

    // Store in IndexedDB (primary)
    await setInIndexedDB(key, value);

    // Also store in localStorage as backup
    try {
      localStorage.setItem(key, value);
    } catch (error) {
      console.warn('localStorage setItem error:', error);
    }
  },

  /**
   * Remove an item from persistent storage (async)
   * @param key - The key to remove
   */
  async removeItem(key: string): Promise<void> {
    // Remove from memory cache
    memoryCache.delete(key);

    // Remove from IndexedDB
    await removeFromIndexedDB(key);

    // Also remove from localStorage
    try {
      localStorage.removeItem(key);
    } catch (error) {
      console.warn('localStorage removeItem error:', error);
    }
  },

  /**
   * Clear all items from persistent storage (async)
   */
  async clear(): Promise<void> {
    // Clear memory cache
    memoryCache.clear();

    // Clear IndexedDB
    await clearIndexedDB();

    // Clear localStorage
    try {
      localStorage.clear();
    } catch (error) {
      console.warn('localStorage clear error:', error);
    }
  },

  /**
   * Synchronous getItem - reads from memory cache first, then localStorage
   * Use after initPersistentStorage() has been called to ensure data is loaded
   * @param key - The key to retrieve
   * @returns The value or null
   */
  getItemSync(key: string): string | null {
    // Check memory cache first (fastest)
    if (memoryCache.has(key)) {
      return memoryCache.get(key) || null;
    }

    // Fallback to localStorage
    try {
      const value = localStorage.getItem(key);
      if (value !== null) {
        memoryCache.set(key, value);
      }
      return value;
    } catch (error) {
      console.warn('getItemSync error:', error);
      return null;
    }
  },

  /**
   * Synchronous setItem - Sets in memory cache and localStorage immediately,
   * IndexedDB asynchronously
   * @param key - The key to set
   * @param value - The value to store
   */
  setItemSync(key: string, value: string): void {
    // Update memory cache
    memoryCache.set(key, value);

    // Store in localStorage (sync)
    try {
      localStorage.setItem(key, value);
    } catch (error) {
      console.warn('localStorage setItem error:', error);
    }

    // Also set in IndexedDB asynchronously (fire and forget)
    setInIndexedDB(key, value).catch(() => { });
  },

  /**
   * Synchronous removeItem
   * @param key - The key to remove
   */
  removeItemSync(key: string): void {
    // Remove from memory cache
    memoryCache.delete(key);

    // Remove from localStorage
    try {
      localStorage.removeItem(key);
    } catch (error) {
      console.warn('localStorage removeItem error:', error);
    }

    // Also remove from IndexedDB asynchronously
    removeFromIndexedDB(key).catch(() => { });
  },

  /**
   * Synchronous clear
   */
  clearSync(): void {
    // Clear memory cache
    memoryCache.clear();

    // Clear localStorage
    try {
      localStorage.clear();
    } catch (error) {
      console.warn('localStorage clear error:', error);
    }

    // Also clear IndexedDB asynchronously
    clearIndexedDB().catch(() => { });
  }
};

/**
 * Critical keys that should be loaded into memory cache on app startup
 */
const CRITICAL_KEYS = ['driver_token', 'authToken'];

/**
 * Initialize persistent storage and load critical data into memory cache
 * Call this on app startup BEFORE checking auth state
 * 
 * @returns Promise<boolean> - true if any critical data was restored
 */
export const initPersistentStorage = async (): Promise<boolean> => {
  if (isInitialized) {
    return false;
  }

  await initDB();

  let restoredAny = false;

  // Load critical keys from IndexedDB into memory cache
  for (const key of CRITICAL_KEYS) {
    try {
      // First try IndexedDB
      const indexedDBValue = await getFromIndexedDB(key);
      if (indexedDBValue !== null) {
        memoryCache.set(key, indexedDBValue);
        restoredAny = true;
        console.log(`Loaded from IndexedDB`);
        continue;
      }

      // Fallback to localStorage
      try {
        const localValue = localStorage.getItem(key);
        if (localValue !== null) {
          memoryCache.set(key, localValue);
          // Sync to IndexedDB for next time
          await setInIndexedDB(key, localValue);
          restoredAny = true;
          console.log(`Loaded localStorage`);
        }
      } catch (e) {
        console.warn(`Failed to check localStorage for ${key}`, e);
      }
    } catch (error) {
      console.warn(`Error loading ${key}:`, error);
    }
  }

  // Request persistent storage permission if available
  if (navigator.storage && navigator.storage.persist) {
    try {
      const granted = await navigator.storage.persist();
      if (granted) {
        console.log('Persistent storage granted');
      }
    } catch (e) {
      console.warn('Failed to request persistent storage', e);
    }
  }

  isInitialized = true;
  return restoredAny;
};

/**
 * Check if we have a stored token (sync check after init)
 */
export const hasStoredToken = (): boolean => {
  const token = persistentStorage.getItemSync('driver_token');
  return token !== null && token !== '';
};

export default persistentStorage;
