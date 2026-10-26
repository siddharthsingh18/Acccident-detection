/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))',
        },
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        control: {
          bg: '#090d16',
          panel: '#0f172a',
          card: '#131c31',
          border: '#1e293b',
          accent: '#06b6d4',      // Neon cyan accent
          alert: '#ef4444',       // Alert red
          highlight: '#10b981',   // Highlight green
        }
      },
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', '"Liberation Mono"', '"Courier New"', 'monospace'],
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', 'sans-serif'],
      },
      keyframes: {
        'slide-in': {
          '0%': { transform: 'translateY(-20px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        'pulse-glow': {
          '0%, 100%': { opacity: '1', filter: 'drop-shadow(0 0 10px rgba(16, 185, 129, 0.7))' },
          '50%': { opacity: '0.8', filter: 'drop-shadow(0 0 20px rgba(16, 185, 129, 0.9))' },
        },
        'pulse-alert': {
          '0%, 100%': { opacity: '1', filter: 'drop-shadow(0 0 10px rgba(239, 68, 68, 0.8))' },
          '50%': { opacity: '0.7', filter: 'drop-shadow(0 0 20px rgba(239, 68, 68, 0.9))' },
        }
      },
      animation: {
        'slide-in': 'slide-in 0.4s cubic-bezier(0.16, 1, 0.3, 1)',
        'pulse-glow': 'pulse-glow 2s infinite',
        'pulse-alert': 'pulse-alert 1.5s infinite',
      }
    },
  },
  plugins: [],
}
