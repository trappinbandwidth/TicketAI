// ----------------------------------------------------------------------

export type ConfigValue = {
  appName: string;
  appVersion: string;
};

// ----------------------------------------------------------------------

export const CONFIG: ConfigValue = {
  appName: 'Member Portal | CDL LEGAL',
  appVersion: import.meta.env.VITE_APP_VERSION || '0.0.0',
};
