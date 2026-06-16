/** @type {import('tailwindcss').Config} */
// Rig Resolve — QA Dashboard token config (portal-attorney: warm stone · amber-primary · desktop)
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans:    ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        display: ['"DM Serif Display"', 'Georgia', 'serif'],
        mono:    ['"JetBrains Mono"', '"Fira Code"', 'Consolas', 'monospace'],
      },
      colors: {
        // ── MASTER BRAND ─────────────────────────────────────────────────────
        brand: {
          teal:      '#2EC4A5',
          tealDark:  '#1E9E85',
          tealDim:   'rgba(46,196,165,0.10)',
          ink:       '#2D3142',
          inkDeep:   '#1A1E2E',
        },

        // ── PORTAL-ATTORNEY (warm stone · amber-primary · desktop) ─────────
        attorney: {
          bg:           '#FAFAF9',
          surface:      '#FFFFFF',
          card:         '#FFFFFF',
          border:       '#E7E5E4',
          borderHover:  '#D6D3D1',
          primary:      '#D97706',
          primaryHover: '#B45309',
          primaryBg:    'rgba(217,119,6,0.08)',
          primaryBorder:'rgba(217,119,6,0.24)',
          text:         '#1C1917',
          muted:        '#78716C',
          dim:          '#A8A29E',
          amber:        '#D97706',
          amberBg:      'rgba(217,119,6,0.08)',
          red:          '#DC2626',
          redBg:        'rgba(220,38,38,0.08)',
          green:        '#16A34A',
          greenBg:      'rgba(22,163,74,0.08)',
          teal:         '#2EC4A5',
          tealBg:       'rgba(46,196,165,0.08)',
        },

        // ── PORTAL-DRIVER (backward compat for any shared components) ──────
        driver: {
          bg:      '#0A0F1A',
          surface: '#0F1724',
          primary: '#2EC4A5',
          text:    '#E2E8F0',
          muted:   '#94A3B8',
          amber:   '#F59E0B',
          red:     '#EF4444',
          green:   '#22C55E',
        },
      },
      boxShadow: {
        card:     '0 1px 3px rgba(28,25,23,0.08), 0 1px 2px rgba(28,25,23,0.06)',
        elevated: '0 10px 30px rgba(28,25,23,0.10)',
        amber:    '0 8px 28px rgba(217,119,6,0.25)',
        teal:     '0 8px 28px rgba(46,196,165,0.25)',
      },
    },
  },
  plugins: [],
}
