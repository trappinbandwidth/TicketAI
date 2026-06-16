// ----------------------------------------------------------------------

export type ConfigValue = {
  appName: string;
  appVersion: string;
};

// ----------------------------------------------------------------------

export const CONFIG: ConfigValue = {
  appName: 'Rig Resolve | Member Portal',
  appVersion: import.meta.env.VITE_APP_VERSION || '0.0.0',
};
