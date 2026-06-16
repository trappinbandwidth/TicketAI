import { persistentStorage } from 'src/utils/persistentStorage';

let debounceTimeout: NodeJS.Timeout | null = null;

/**
 * Store data in persistent storage (IndexedDB + localStorage)
 * Async version for maximum reliability on mobile PWAs
 */
export const setDataIntoStorage = async (key: string, data: any): Promise<void> => {
  const stringifyData = typeof data === 'string' ? data : JSON.stringify(data);
  await persistentStorage.setItem(key, stringifyData);
};

/**
 * Get data from persistent storage (async version)
 * Checks memory cache -> IndexedDB -> localStorage
 */
export const getDataFromStorage = async (key: string): Promise<any> => {
  const getData = await persistentStorage.getItem(key);
  if (getData && getData !== null && getData !== undefined) {
    try {
      return JSON.parse(getData);
    } catch {
      return getData;
    }
  }
  return null;
};

/**
 * Remove data from persistent storage (async)
 */
export const removeDataFromStorage = async (key: string): Promise<void> => {
  await persistentStorage.removeItem(key);
};

/**
 * Clear all persistent storage (async)
 */
export const clearStorage = async (): Promise<void> => {
  await persistentStorage.clear();
};

// ============================================================
// Synchronous methods - Use these for places that can't use async
// (e.g., axios interceptors, render functions)
// Note: These work best AFTER initPersistentStorage() has been called
// ============================================================

/**
 * Store data synchronously
 * Stores in memory cache + localStorage immediately, IndexedDB async
 */
export const setDataIntoSessionStorage = (key: string, data: any): void => {
  const stringifyData = typeof data === 'string' ? data : JSON.stringify(data);
  persistentStorage.setItemSync(key, stringifyData);
};

/**
 * Get data synchronously from memory cache/localStorage
 * For this to have IndexedDB data, initPersistentStorage() must have been called
 */
export const getDataFromSessionStorage = (key: string): any => {
  const getData = persistentStorage.getItemSync(key);
  if (getData && getData !== null && getData !== undefined) {
    try {
      return JSON.parse(getData);
    } catch {
      return getData;
    }
  }
  return null;
};

/**
 * Remove data synchronously
 */
export const removeDataFromSessionStorage = (key: string): void => {
  persistentStorage.removeItemSync(key);
};

/**
 * Clear all storage synchronously
 */
export const clearSessionStorage = (): void => {
  persistentStorage.clearSync();
};

// ============================================================
// Utility functions
// ============================================================

export const stringifyJsonData = (data: Array<any>): string => {
  if (!data) return '';
  return JSON.stringify(data);
};

export const parseJsonData = (data: string): any => {
  if (!data?.length) return [];
  return JSON.parse(data);
};

export const debounce =
  (func: Function, delay: number) =>
    (...args: any[]) => {
      if (debounceTimeout) {
        clearTimeout(debounceTimeout);
      }
      debounceTimeout = setTimeout(() => {
        func(...args);
      }, delay);
    };
