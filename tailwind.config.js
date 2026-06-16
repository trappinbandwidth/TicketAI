/** @type {import('tailwindcss').Config} */
// Rig Resolve — Driver App token config (portal-driver: dark · mobile-first · teal-primary)
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
        sans:    ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        display: ['"DM Serif Display"', 'Georgia', 'serif'],
        mono:    ['"JetBrains Mono"', '"Fira Code"', 'Consolas', 'monospace'],
        heading: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'], // legacy alias
      },
      colors: {
        // ── MASTER BRAND ─────────────────────────────────────────────────────
        brand: {
          teal:      '#2EC4A5', // THE bracket color — one teal element per screen max
          tealDark:  '#1E9E85',
          tealDim:   'rgba(46,196,165,0.12)',
          tealLt:    '#E8FAF6',
          ink:       '#2D3142',
          inkDeep:   '#1A1E2E',
        },

        // ── PORTAL-DRIVER (dark always, mobile-first) ─────────────────────
        driver: {
          bg:           '#0A0F1A',
          surface:      '#0F1724',
          card:         '#141E2E',
          border:       '#1A2840',
          borderHover:  '#253550',
          primary:      '#2EC4A5',   // THE only primary action — one per screen
          primaryHover: '#1E9E85',
          primaryBg:    'rgba(46,196,165,0.08)',
          primaryBorder:'rgba(46,196,165,0.20)',
          text:         '#E2E8F0',
          muted:        '#94A3B8',
          dim:          '#475569',
          faint:        '#334155',
          amber:        '#F59E0B',   // court dates · deadlines · warnings
          amberBg:      'rgba(245,158,11,0.12)',
          red:          '#EF4444',   // CDL at risk ONLY
          redBg:        'rgba(239,68,68,0.12)',
          green:        '#22C55E',   // wins · dismissals ONLY
          greenBg:      'rgba(34,197,94,0.12)',
        },

        // ── BACKWARD-COMPAT aliases (existing components still resolve) ────
        surface: {
          app:  '#0A0F1A',
          card: '#141E2E',
          muted:'#0F1724',
        },
        ink: {
          strong:   '#E2E8F0',
          body:     '#CBD5E1',
          muted:    '#94A3B8',
          subtle:   '#475569',
          inverted: '#0A0F1A',
        },
        accent: {
          red:   '#EF4444',
          green: '#22C55E',
          mint:  'rgba(34,197,94,0.12)',
          amber: '#F59E0B',
          blue:  '#60A5FA',
        },
        border: {
          DEFAULT: '#1A2840',
          strong:  '#253550',
        },
      },
      fontSize: {
        hero:         ['4rem',    { lineHeight: '1.25',      fontWeight: '800' }],
        'display-lg': ['3rem',    { lineHeight: '1.333333',  fontWeight: '800' }],
        'display-md': ['2rem',    { lineHeight: '1.333333',  fontWeight: '800' }],
        'title-xl':   ['1.5rem',  { lineHeight: '1.5',       fontWeight: '700' }],
        'title-lg':   ['1.25rem', { lineHeight: '1.5',       fontWeight: '700' }],
        'title-md':   ['1.125rem',{ lineHeight: '1.5',       fontWeight: '700' }],
      },
      spacing: {
        4.5: '1.125rem', 5.5: '1.375rem', 7.5: '1.875rem',
        13: '3.25rem',  15: '3.75rem',   18: '4.5rem',
      },
      borderRadius: {
        xl: '1rem', '2xl': '1.5rem', '3xl': '1.75rem', '4xl': '2rem', pill: '9999px',
      },
      boxShadow: {
        glass:    '0 25px 50px -12px rgba(0,0,0,0.45)',
        soft:     '0 10px 30px rgba(10,15,26,0.4)',
        card:     '0 1px 3px rgba(10,15,26,0.5), 0 1px 2px rgba(10,15,26,0.3)',
        elevated: '0 20px 60px -15px rgba(46,196,165,0.15)',
        teal:     '0 8px 28px rgba(46,196,165,0.3)',
      },
      backdropBlur: { xs: '2px' },
      screens: {
        xs: '375px', phone: '428px', tablet: '768px', laptop: '1024px', desktop: '1366px',
      },
      backgroundImage: {
        'brand-auth':      'linear-gradient(135deg, #0A0F1A 0%, #0F1724 50%, #141E2E 100%)',
        'brand-auth-soft': 'linear-gradient(180deg, #0A0F1A 0%, #141E2E 100%)',
      },
      minHeight: { touch: '44px' },
      minWidth:  { touch: '44px' },
      keyframes: {
        blob: {
          '0%, 100%': { transform: 'translate(0,0) scale(1)' },
          '33%':       { transform: 'translate(30px,-50px) scale(1.1)' },
          '66%':       { transform: 'translate(-20px,20px) scale(0.9)' },
        },
      },
      animation: {
        blob:           'blob 7s infinite',
        'blob-delay-2': 'blob 7s infinite 2s',
        'blob-delay-4': 'blob 7s infinite 4s',
      },
    },
  },
  plugins: [],
};
