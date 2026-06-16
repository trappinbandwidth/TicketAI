# CDL Legal Driver Portal

A comprehensive member portal application for CDL Legal drivers, built with React, TypeScript, and Material-UI. This application provides drivers with access to their profile, billing information, MVR records, support tickets, and dashboard analytics.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Environment Configuration](#environment-configuration)
- [Development](#development)
- [Building for Production](#building-for-production)
- [Deployment](#deployment)
- [Progressive Web App (PWA)](#progressive-web-app-pwa)
- [API Integration](#api-integration)
- [Key Components](#key-components)
- [State Management](#state-management)
- [Routing](#routing)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

---

## 🎯 Overview

The **CDL Legal Driver Portal** is a modern web application designed to provide CDL drivers with a centralized platform to manage their membership, view billing information, access MVR (Motor Vehicle Record) reports, submit support requests, and track their account status.

### Key Highlights

- **Secure Authentication**: OTP-based phone verification system
- **Responsive Design**: Mobile-first approach with Material-UI components
- **Real-time Data**: React Query for efficient data fetching and caching
- **Modern Architecture**: Built with Vite for lightning-fast development
- **Type Safety**: Full TypeScript implementation
- **Progressive Web App**: Installable, works offline, and provides native app-like experience

---

## ✨ Features

### 🔐 Authentication
- Phone number-based authentication
- OTP verification system
- Secure token management
- Session persistence

### 📊 Dashboard
- Membership status overview
- Quick access to key metrics
- Recent activity tracking
- Visual analytics with charts

### 👤 Profile Management
- Personal information display
- Driver details and documentation
- Account settings
- Privacy and security controls

### 💳 Billing & Payments
- Payment method management
- Transaction history
- Billing details
- Secure payment processing

### 📄 MVR Records
- Motor Vehicle Record access
- Historical MVR data
- Status tracking
- Downloadable reports
- Pagination support

### 🎫 Support System
- Support ticket creation
- Issue tracking
- Communication history
- Multiple issue categories

---

## 🛠 Technology Stack

### Frontend
- **Framework**: React 18.3.1
- **Language**: TypeScript 5.5.4
- **Build Tool**: Vite 5.4.2
- **UI Library**: Material-UI (MUI) 5.16.7
- **State Management**: Jotai 2.10.0
- **Data Fetching**: TanStack React Query 5.64.2
- **Routing**: React Router DOM 6.26.1
- **Form Handling**: React Hook Form 7.53.0
- **Validation**: Yup 1.4.0
- **HTTP Client**: Axios 1.7.7
- **Notifications**: React Toastify 10.0.5
- **Date Handling**: date-fns 4.1.0, dayjs 1.11.13
- **Icons**: Iconify 5.0.2

### Development Tools
- **Package Manager**: Yarn 1.22.22
- **Code Formatting**: Prettier 3.3.3
- **Type Checking**: TypeScript with Vite Plugin Checker
- **Optimization**: Terser, Vite Compression Plugin
- **Code Splitting**: Vite Plugin Chunk Split

---

## 📁 Project Structure

```
cdl-driver-app/
├── public/                      # Static assets
├── src/
│   ├── apiSetUp/               # API configuration
│   │   ├── httpService.ts      # Axios instance setup
│   │   ├── interceptor.ts      # Request/response interceptors
│   │   ├── authService.ts      # Authentication utilities
│   │   ├── toasterService.ts   # Toast notification service
│   │   └── stringUtils.ts      # String utility functions
│   │
│   ├── common-service/         # Common services
│   │   ├── index.service.ts    # Session storage utilities
│   │   └── types.interface.ts  # TypeScript interfaces
│   │
│   ├── components/             # Reusable components
│   │   ├── Button/             # Custom button component
│   │   ├── Progress/           # Progress indicators
│   │   ├── iconify/            # Icon wrapper
│   │   ├── label/              # Label component
│   │   ├── loading/            # Loading screen
│   │   ├── logo/               # Logo component
│   │   ├── scrollbar/          # Custom scrollbar
│   │   └── svg-color/          # SVG color utilities
│   │
│   ├── hook-form/              # Form components
│   │   └── [form components]   # React Hook Form wrappers
│   │
│   ├── hooks/                  # Custom React hooks
│   │   └── use-scroll-to-top.ts
│   │
│   ├── layouts/                # Layout components
│   │   ├── auth/               # Authentication layout
│   │   ├── dashboard/          # Dashboard layout
│   │   ├── simple/             # Simple layout
│   │   ├── core/               # Core layout components
│   │   └── components/         # Layout-specific components
│   │
│   ├── pages/                  # Page components
│   │   ├── landing-web.tsx     # Landing/sign-in page
│   │   ├── member-phone.tsx    # Phone verification page
│   │   ├── member-verify.tsx   # OTP verification page
│   │   ├── member-dashboard.tsx # Dashboard page
│   │   ├── profile.tsx         # Profile management page
│   │   ├── support.tsx         # Support page
│   │   └── page-not-found.tsx  # 404 page
│   │
│   ├── routes/                 # Routing configuration
│   │   ├── sections.tsx        # Route definitions
│   │   ├── index.service.ts    # Route services
│   │   ├── hooks/              # Route-specific hooks
│   │   └── components/         # Route components
│   │
│   ├── sections/               # Page sections
│   │
│   ├── theme/                  # Theme configuration
│   │   └── [theme files]       # MUI theme customization
│   │
│   ├── utils/                  # Utility functions
│   │   ├── api-service.ts      # API service functions
│   │   └── format-time.ts      # Time formatting utilities
│   │
│   ├── app.tsx                 # Main App component
│   ├── main.tsx                # Application entry point
│   ├── store.ts                # Global state atoms
│   ├── config-global.ts        # Global configuration
│   ├── constants.value.ts      # Application constants
│   └── global.css              # Global styles
│
├── dist/                       # Production build output
├── .env                        # Environment variables
├── index.html                  # HTML entry point
├── package.json                # Dependencies and scripts
├── tsconfig.json               # TypeScript configuration
├── vite.config.ts              # Vite configuration
├── prettier.config.mjs         # Prettier configuration
└── README.md                   # Project documentation
```

---

## 📋 Prerequisites

Before you begin, ensure you have the following installed:

- **Node.js**: Version 20.x (as specified in package.json)
- **Yarn**: Version 1.22.22 or higher
- **Git**: For version control

---

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd cdl-driver-app
```

### 2. Install Dependencies

```bash
yarn install
```

Or using npm:

```bash
npm install
```

---

## ⚙️ Environment Configuration

Create a `.env` file in the root directory with the following variables:

```env
# API Configuration
VITE_REACT_APP_BASE_URL=<your-backend-api-url>

# Example:
# VITE_REACT_APP_BASE_URL=https://api.cdllegal.com
```

**Note**: The `.env` file is gitignored for security. Never commit sensitive credentials.

---

## 💻 Development

### Start Development Server

```bash
yarn dev
```

The application will be available at `http://localhost:3039`

### Development with Network Access

To access the dev server from other devices on your network:

```bash
yarn dev:host
```

### Code Formatting

Check code formatting:

```bash
yarn fm:check
```

Fix code formatting:

```bash
yarn fm:fix
```

### Clean Restart

Remove all dependencies and restart:

```bash
yarn re:start
```

---

## 🏗 Building for Production

### Standard Build

```bash
yarn build
```

This command will:
1. Run TypeScript type checking
2. Increment the external app version stored in `.app-version.json`
3. Build the application with Vite
4. Optimize and minify the output
5. Generate production-ready files in the `dist/` directory
6. Automatically commit and push the build (via `push-build` script)

### External App Version

The UI display version is managed outside `package.json`.

- The build counter lives in `.app-version.json`
- `.app-version.json` is gitignored, so each server can keep its own version history
- `prebuild` updates that file before every production build
- The app reads the value through `VITE_APP_VERSION`

If `.app-version.json` does not exist yet, the build script creates it automatically using the current `package.json` version as the starting point.

### Clean Build

```bash
yarn re:build
```

Or with npm:

```bash
npm run re:build-npm
```

### Build Optimizations

The production build includes:
- **Tree shaking**: Removes unused code
- **Code splitting**: Separates vendor and application code
- **Minification**: Terser minification with console removal
- **Compression**: Gzip compression for assets
- **CSS optimization**: Minified and code-split CSS
- **No source maps**: For security and smaller bundle size

---

## 🚀 Deployment

### Production Deployment Steps

#### Backend Deployment

```bash
# Navigate to backend directory
cd /path/to/backend

# Pull latest changes
git pull

# Activate virtual environment
source venv/bin/activate

# Update environment variables (if needed)
sudo nano .env

# Install/update dependencies
pip3 install -r requirements.txt

# Restart the service
sudo systemctl restart cdl-legal-carrier-guard.service

# Verify service status
sudo systemctl status cdl-legal-carrier-guard.service
```

#### Frontend Deployment

```bash
# Build the application
yarn build

# Copy build files to web server
sudo cp -r dist/* /var/www/html/web-app/

# Reload Nginx
sudo systemctl reload nginx

# Verify Nginx status
sudo systemctl status nginx
```

### Monitoring & Logs

#### Watch Service Logs

```bash
# Real-time service logs
journalctl -u cdl-legal-carrier-guard.service -f

# Last 100 lines
journalctl -u cdl-legal-carrier-guard.service -n 100

# Logs from specific time
journalctl -u cdl-legal-carrier-guard.service --since "2024-01-01"
```

#### Application Logs

```bash
# View Gunicorn access logs
tail -n 800 /var/log/gunicorn/access.log

# Follow access logs in real-time
tail -f /var/log/gunicorn/access.log

# View error logs
tail -n 800 /var/log/gunicorn/error.log
```

#### Nginx Logs

```bash
# Access logs
tail -f /var/log/nginx/access.log

# Error logs
tail -f /var/log/nginx/error.log
```

---

## 📱 Progressive Web App (PWA)

The CDL Legal Driver Portal is a fully functional Progressive Web App with offline support, installability, and optimized caching strategies.

### PWA Features

- ✅ **Installable**: Can be installed on desktop and mobile devices
- ✅ **Offline Support**: Works without internet connection
- ✅ **Auto-Updates**: Service worker updates automatically
- ✅ **Fast Loading**: Cached assets load instantly
- ✅ **Network Resilience**: Intelligent fallback strategies
- ✅ **Native-like Experience**: Standalone display mode

### Cache Strategies

| Resource Type | Strategy | Cache Duration |
|--------------|----------|----------------|
| API Calls | Network First | 24 hours |
| Images | Cache First | 30 days |
| Fonts | Cache First | 1 year |
| CSS/JS | Stale While Revalidate | 7 days |
| Google Fonts | Cache First | 1 year |

### Quick Start

#### 1. Generate PWA Icons

```bash
# Create icons directory (already created)
mkdir -p public/icons

# Generate icons using online tool:
# Visit: https://www.pwabuilder.com/imageGenerator
# Upload your logo (512x512 or larger)
# Download and extract to public/icons/
```

**Required icon sizes**: 72x72, 96x96, 128x128, 144x144, 152x152, 192x192, 384x384, 512x512

See [`PWA_ICONS_GUIDE.md`](./PWA_ICONS_GUIDE.md) for detailed instructions.

#### 2. Test PWA Locally

```bash
# Development mode (PWA enabled)
yarn dev

# Production build
yarn build
yarn start
```

#### 3. Verify Installation

1. Open Chrome DevTools (F12)
2. Go to **Application** tab
3. Check **Manifest** section
4. Verify **Service Worker** is active
5. Test **Offline** mode

### Testing Checklist

- [ ] Icons appear correctly in manifest
- [ ] Service worker registers successfully
- [ ] App works offline
- [ ] Install prompt appears
- [ ] App installs on desktop/mobile
- [ ] Cache strategies work as expected
- [ ] Updates apply automatically

### Deployment Requirements

**Production PWA requires:**
- ✅ HTTPS connection (SSL certificate)
- ✅ Valid web app manifest
- ✅ Registered service worker
- ✅ All required icons in `/public/icons/`

### Nginx Configuration for PWA

Add to your Nginx config:

```nginx
# Service Worker - No cache
location /sw.js {
    add_header Cache-Control "no-cache, no-store, must-revalidate";
}

# Manifest
location /manifest.webmanifest {
    add_header Content-Type application/manifest+json;
}
```

### Troubleshooting

**Service Worker not updating?**
```bash
# Clear and rebuild
yarn rm:all && yarn install && yarn build
```

**Icons not showing?**
- Check files exist in `/public/icons/`
- Verify file names match configuration
- Clear browser cache

**App not installable?**
- Ensure HTTPS is enabled
- Check manifest is valid
- Verify service worker is active

### Documentation

For comprehensive PWA setup, testing, and troubleshooting:
- **Setup Guide**: [`PWA_SETUP_GUIDE.md`](./PWA_SETUP_GUIDE.md)
- **Icons Guide**: [`PWA_ICONS_GUIDE.md`](./PWA_ICONS_GUIDE.md)

---

## 🔌 API Integration

### API Configuration

The application connects to the backend API configured in `src/constants.value.ts`:

```typescript
API_BASE: `${import.meta.env.VITE_REACT_APP_BASE_URL}/CDLLegalCarrierService`
API_VERSION: 'api/v1/'
```

### Available API Endpoints

- `SendOTP` - Send OTP to phone number
- `VerifyOTP` - Verify OTP and authenticate
- `GetUserDetails` - Fetch logged-in user details
- `GetDriverProfile` - Get driver profile information
- `GetMenuItems` - Fetch dynamic menu items
- `getDriverPaymentMethods` - Get payment methods
- `getDriverTransactions` - Fetch transaction history
- `getDriverMVRs` - Get MVR records

### HTTP Service

The application uses a custom Axios instance with:
- Automatic token injection
- Request/response interceptors
- Error handling
- Content-type management

---

## 🧩 Key Components

### Authentication Flow

1. **Landing Page** (`landing-web.tsx`): Initial sign-in interface
2. **Phone Verification** (`member-phone.tsx`): Phone number input
3. **OTP Verification** (`member-verify.tsx`): OTP validation
4. **Dashboard** (`member-dashboard.tsx`): Post-authentication landing

### Profile Management

The `profile.tsx` page includes multiple views:
- **Your Information**: Personal and driver details
- **Billing & Payments**: Payment methods and transactions
- **Privacy & Security**: Account security settings
- **Your MVRs**: Motor Vehicle Records with pagination

### Dashboard Features

- Membership status card
- Quick action buttons
- Recent activity feed
- Visual progress indicators
- Responsive grid layout

### Support System

- Issue type categorization
- Ticket submission form
- Support request history
- Status tracking

---

## 🗄 State Management

### Global State (Jotai)

Located in `src/store.ts`:

```typescript
- isLoading: Global loading state
- loggedInUserDetails: User information
- driverProfile: Driver profile data
```

### Data Caching (React Query)

- 24-hour stale time for queries
- Local storage persistence
- Automatic refetch disabled on window focus
- Optimized for performance

---

## 🛣 Routing

### Public Routes
- `/sign-in` - Landing/sign-in page
- `/member-phone` - Phone verification
- `/member-verify` - OTP verification
- `/404` - Not found page

### Protected Routes (Requires Authentication)
- `/dashboard` - Main dashboard
- `/profile` - User profile
- `/support` - Support page
- Dynamic routes from `GetMenuItems` API

### Route Protection

Routes are protected using token-based authentication:
```typescript
const isTokenAvailable = !!getDataFromSessionStorage('driver_token');
```

---

## 🐛 Troubleshooting

### Common Issues

#### Build Fails

```bash
# Clear cache and rebuild
yarn rm:all
yarn install
yarn build
```

#### Port Already in Use

Change the port in `vite.config.ts`:
```typescript
const PORT = 3040; // Change from 3039
```

#### API Connection Issues

1. Verify `.env` file exists and has correct `VITE_REACT_APP_BASE_URL`
2. Check backend service is running
3. Verify CORS settings on backend
4. Check browser console for specific errors

#### TypeScript Errors

```bash
# Check TypeScript errors
npx tsc --noEmit
```

#### Session/Token Issues

Clear browser session storage:
```javascript
sessionStorage.clear();
```

---

## 📝 Scripts Reference

| Script | Description |
|--------|-------------|
| `yarn dev` | Start development server on port 3039 |
| `yarn dev:host` | Start dev server with network access |
| `yarn build` | Build for production and push changes |
| `yarn start` | Preview production build |
| `yarn fm:check` | Check code formatting |
| `yarn fm:fix` | Fix code formatting issues |
| `yarn rm:all` | Remove all build artifacts and dependencies |
| `yarn re:start` | Clean install and start dev server |
| `yarn re:build` | Clean install and build |

---

## 🤝 Contributing

### Development Workflow

1. Create a feature branch
2. Make your changes
3. Run `yarn fm:fix` to format code
4. Test thoroughly
5. Commit with descriptive messages
6. Push and create a pull request

### Code Style

- Follow TypeScript best practices
- Use functional components with hooks
- Maintain consistent formatting (Prettier)
- Write meaningful component and variable names
- Add comments for complex logic

---

## 📄 License

MIT License - See package.json for details

---

## 👥 Support

For technical support or questions:
- Use the in-app support system
- Contact the development team
- Check application logs for debugging

---

## 🔄 Version

Current Version: **2.0.0**

---

**Built with ❤️ by the CDL Legal Team**