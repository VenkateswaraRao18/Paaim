import type { Config } from 'tailwindcss'

// PAAIM "Field Ops / Pine & Amber" — see DESIGN.md
const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        pine: '#123A2E',
        'pine-2': '#1B5443',
        moss: '#7FA893',
        sage: '#D3E0D8',        // sidebar text on dark pine — clearly visible
        'sage-dim': '#93B2A4',  // sidebar secondary/labels on dark pine
        'pine-active': '#2C6E56', // selected nav item — clearly brighter than the pine sidebar
        paper: '#F3F5F2',
        card: '#FFFFFF',
        ink: '#17211C',
        dim: '#5E6B64',
        amber: '#E8A13D',
        coral: '#D8492B',
        line: '#DDE4DF',
        'surface-ok': '#EDF4EF',
        'surface-warn': '#FBF3E3',
        'surface-bad': '#FBEAE5',
        // legacy aliases → remapped onto the new system so nothing breaks mid-migration
        primary: '#1B5443',
        secondary: '#123A2E',
        danger: '#D8492B',
        warning: '#E8A13D',
        success: '#1B5443',
      },
      fontFamily: {
        mono: ['"SF Mono"', 'ui-monospace', 'Menlo', 'Consolas', 'monospace'],
      },
      letterSpacing: {
        eyebrow: '0.14em',
      },
      borderRadius: {
        card: '10px',
      },
    },
  },
  plugins: [],
}
export default config
