/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        display: ["Space Grotesk", "Inter", "system-ui", "sans-serif"],
      },
      colors: {
        brand: { 50: "#e9f7f1", 100: "#cdeee2", 200: "#9fdcc6", 500: "#1f9d78", 600: "#0f8566", 700: "#0b6b52", 800: "#0a5642", 900: "#073b2d" },
      },
      borderRadius: { xl: "0.75rem", "2xl": "0.875rem" },
    },
  },
  plugins: [],
};
