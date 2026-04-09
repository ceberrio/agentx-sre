/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // SoftServe brand colors — source: Brandfetch + logo.com (AC-01, BR-01, BR-03)
        // Primary: #454494 (Victoria purple) — confirmed via Brandfetch & logo.com
        brand: {
          primary: '#454494',
          dark: '#333278',
          light: '#5D5CB0',
          lighter: '#EEEDF8',
        },
        // Neutral palette — aligned with HU-P031 design tokens
        neutral: {
          900: '#1A1A2E',
          800: '#2D2D44',
          700: '#4A4A6A',
          600: '#6B6B8A',
          500: '#8E8EAA',
          400: '#ADADC4',
          300: '#CACAD9',
          200: '#E2E2ED',
          100: '#F1F1F8',
          50: '#F8F8FC',
        },
        // Semantic colors — standard palette for success/warning/error/info states
        semantic: {
          success: '#22C55E',
          warning: '#F59E0B',
          error: '#EF4444',
          info: '#3B82F6',
          'success-light': '#DCFCE7',
          'warning-light': '#FEF3C7',
          'error-light': '#FEE2E2',
          'info-light': '#DBEAFE',
        },
      },
      fontFamily: {
        // Montserrat: primary brand font (confirmed via SoftServe public materials)
        sans: ['Montserrat', 'Inter', 'system-ui', 'sans-serif'],
        montserrat: ['Montserrat', 'Inter', 'sans-serif'],
        inter: ['Inter', 'Open Sans', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Courier New', 'monospace'],
      },
      // Spacing tokens aligned with HU-P031
      spacing: {
        '1': '4px',
        '2': '8px',
        '3': '12px',
        '4': '16px',
        '6': '24px',
        '8': '32px',
      },
      borderRadius: {
        sm: '4px',
        md: '8px',
        lg: '12px',
        full: '9999px',
      },
      boxShadow: {
        sm: '0 1px 3px rgba(0, 0, 0, 0.10)',
        md: '0 4px 12px rgba(0, 0, 0, 0.15)',
        lg: '0 8px 24px rgba(0, 0, 0, 0.20)',
      },
      // BR-05: Only transition-colors and transition-shadow — no complex animations
      transitionProperty: {
        colors: 'color, background-color, border-color, text-decoration-color, fill, stroke',
        shadow: 'box-shadow',
      },
      transitionDuration: {
        '150': '150ms',
      },
    },
  },
  plugins: [],
}
