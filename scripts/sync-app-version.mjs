import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '..');
const stateFilePath = path.join(rootDir, '.app-version.json');
const packageJsonPath = path.join(rootDir, 'package.json');
const DEFAULT_VERSION = '0.0.0';

const parseVersion = (value) => {
  const match = /^(\d+)\.(\d+)\.(\d+)$/.exec(value);

  if (!match) {
    return null;
  }

  return {
    major: Number(match[1]),
    minor: Number(match[2]),
    patch: Number(match[3]),
  };
};

const formatVersion = ({ major, minor, patch }) => `${major}.${minor}.${patch}`;

const loadPackageVersion = () => {
  try {
    const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf-8'));
    return typeof packageJson.version === 'string' ? packageJson.version : DEFAULT_VERSION;
  } catch {
    return DEFAULT_VERSION;
  }
};

const loadCurrentVersion = () => {
  try {
    const fileContents = fs.readFileSync(stateFilePath, 'utf-8');
    const parsed = JSON.parse(fileContents);
    return typeof parsed.version === 'string' ? parsed.version : loadPackageVersion();
  } catch {
    return loadPackageVersion();
  }
};

const currentVersion = loadCurrentVersion();
const parsedVersion = parseVersion(currentVersion) || parseVersion(DEFAULT_VERSION);

if (!parsedVersion) {
  throw new Error('Unable to initialize app version state.');
}

const nextVersion = formatVersion({
  major: parsedVersion.major,
  minor: parsedVersion.minor,
  patch: parsedVersion.patch + 1,
});

fs.writeFileSync(
  stateFilePath,
  `${JSON.stringify({ version: nextVersion }, null, 2)}\n`,
  'utf-8'
);

console.log(`App build version updated: ${currentVersion} -> ${nextVersion}`);