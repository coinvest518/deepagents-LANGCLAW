/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./app/**/*.{js,ts,jsx,tsx}', './components/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        hud: {
          bg: '#040d18',
          panel: '#071628',
          border: '#0a2540',
          cyan: '#00d4ff',
          blue: '#0066ff',
          amber: '#ff6b00',
          green: '#00ff88',
          red: '#ff2d55',
          text: '#a8c4d4',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      animation: {
        pulse2: 'pulse 2s cubic-bezier(0.4,0,0.6,1) infinite',
        scan: 'scan 3s linear infinite',
        glow: 'glow 2s ease-in-out infinite alternate',
      },
      keyframes: {
        scan: {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(100vh)' },
        },
        glow: {
          from: { boxShadow: '0 0 5px #00d4ff33' },
          to: { boxShadow: '0 0 20px #00d4ff88, 0 0 40px #00d4ff33' },
        },
      },
    },
  },
  plugins: [],
}
