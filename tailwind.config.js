/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./index.html', './src/**/*.{ts,tsx,js,jsx}'],
  theme: {
    container: {
      center: true,
      padding: {
        DEFAULT: '1rem',
        sm: '1.25rem',
        lg: '1.5rem',
        xl: '2rem',
      },
    },
    extend: {
      fontFamily: {
        sans: ['Open Sans', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        heading: ['Barlow', 'Open Sans', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      colors: {
        brand: {
          50: '#eef6ff',
          100: '#d7e9ff',
          200: '#b6d8ff',
          300: '#84bbff',
          400: '#4b95ff',
          500: '#236ef5',
          600: '#0d3e6b',
          700: '#0a2847',
          800: '#071f38',
          900: '#051528',
        },
        accent: {
          red: '#dc2626',
          green: '#008236',
          mint: '#dcfce7',
          amber: '#f2ae2e',
          blue: '#60a5fa',
        },
        surface: {
          app: '#fbf9fa',
          card: '#ffffff',
          muted: '#f3f4f6',
        },
        ink: {
          strong: '#003e6b',
          body: '#1f2937',
          muted: '#64748b',
          subtle: '#94a3b8',
          inverted: '#ffffff',
        },
        border: {
          DEFAULT: 'rgba(15, 23, 42, 0.12)',
          strong: 'rgba(15, 23, 42, 0.2)',
        },
      },
      fontSize: {
        hero: ['4rem', { lineHeight: '1.25', fontWeight: '800' }],
        'display-lg': ['3rem', { lineHeight: '1.333333', fontWeight: '800' }],
        'display-md': ['2rem', { lineHeight: '1.333333', fontWeight: '800' }],
        'title-xl': ['1.5rem', { lineHeight: '1.5', fontWeight: '700' }],
        'title-lg': ['1.25rem', { lineHeight: '1.5', fontWeight: '700' }],
        'title-md': ['1.125rem', { lineHeight: '1.5', fontWeight: '700' }],
      },
      spacing: {
        4.5: '1.125rem',
        5.5: '1.375rem',
        7.5: '1.875rem',
        13: '3.25rem',
        15: '3.75rem',
        18: '4.5rem',
      },
      borderRadius: {
        xl: '1rem',
        '2xl': '1.5rem',
        '3xl': '1.75rem',
        '4xl': '2rem',
        pill: '9999px',
      },
      boxShadow: {
        glass: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
        soft: '0 10px 30px rgba(15, 23, 42, 0.08)',
        card: '0 1px 3px rgba(15, 23, 42, 0.1), 0 1px 2px rgba(15, 23, 42, 0.08)',
        elevated: '0 20px 60px -15px rgba(255, 255, 255, 0.3)',
      },
      backdropBlur: {
        xs: '2px',
      },
      screens: {
        xs: '375px',
        phone: '428px',
        tablet: '768px',
        laptop: '1024px',
        desktop: '1366px',
      },
      backgroundImage: {
        'brand-auth': 'linear-gradient(135deg, #0D3E6B 0%, #1e3a5f 50%, #0a2847 100%)',
        'brand-auth-soft': 'linear-gradient(180deg, #0D3E6B 0%, #1e3a5f 100%)',
      },
      keyframes: {
        blob: {
          '0%, 100%': { transform: 'translate(0, 0) scale(1)' },
          '33%': { transform: 'translate(30px, -50px) scale(1.1)' },
          '66%': { transform: 'translate(-20px, 20px) scale(0.9)' },
        },
      },
      animation: {
        blob: 'blob 7s infinite',
        'blob-delay-2': 'blob 7s infinite 2s',
        'blob-delay-4': 'blob 7s infinite 4s',
      },
    },
  },
  plugins: [],
};