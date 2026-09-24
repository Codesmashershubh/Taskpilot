/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#FAFAFA",
        surface: "#FFFFFF",
        ink: "#1D1D1F",
        muted: "#6E6E73",
        hairline: "#E7E7EA",
        accent: {
          DEFAULT: "#2F5EFF",
          soft: "#EEF2FF",
        },
        state: {
          idle: "#8A8A90",
          working: "#2F5EFF",
          approval: "#E5A031",
          success: "#1FAE7A",
          danger: "#E14F4F",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "sans-serif"],
        mono: ["'JetBrains Mono'", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      borderRadius: {
        card: "20px",
        pill: "999px",
      },
      boxShadow: {
        soft: "0 1px 2px rgba(20,20,25,0.04), 0 8px 24px rgba(20,20,25,0.06)",
        lift: "0 2px 4px rgba(20,20,25,0.06), 0 16px 40px rgba(20,20,25,0.10)",
      },
      spacing: {
        18: "4.5rem",
      },
      keyframes: {
        breathe: {
          "0%, 100%": { transform: "scale(1)", opacity: "1" },
          "50%": { transform: "scale(1.35)", opacity: "0.55" },
        },
        "fade-up": {
          from: { opacity: "0", transform: "translateY(14px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        breathe: "breathe 2.2s ease-in-out infinite",
        "fade-up": "fade-up 0.5s ease-out both",
      },
    },
  },
  plugins: [],
};
