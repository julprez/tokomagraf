/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        btc: {
          orange: '#f7931a',
          dark: '#e67e22',
        },
        surface: {
          DEFAULT: '#0f172a',
          light: '#1e293b',
          lighter: '#334155',
        },
      },
    },
  },
  plugins: [],
}
