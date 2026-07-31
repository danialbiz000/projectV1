import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef7ff",
          100: "#d9edff",
          500: "#2a7de1",
          600: "#1c64c4",
          700: "#174f9c",
        },
      },
    },
  },
  plugins: [],
};

export default config;
