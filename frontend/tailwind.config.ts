import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        accent: {
          50: "#E9F2F2",
          100: "#D3E6E7",
          300: "#71A8AB",
          500: "#1F6B6E",
          700: "#114448"
        },
        paper: {
          50: "#FAF8F2",
          100: "#F4F1E8",
          200: "#ECE7D7"
        },
        ink: {
          950: "#0E1217",
          900: "#161B22",
          800: "#222831",
          700: "#3B362B",
          500: "#6E6757",
          300: "#A39B86",
          100: "#DDD7C8"
        }
      },
      fontFamily: {
        display: ["Instrument Serif", "Source Serif 4", "Georgia", "serif"],
        sans: ["Geist", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"]
      }
    }
  },
  plugins: []
} satisfies Config;
