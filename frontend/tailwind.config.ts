import type { Config } from "tailwindcss";
import animate from "tailwindcss-animate";

const config: Config = {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      fontFamily: {
        sans: ['"DM Sans"', "system-ui", "sans-serif"],
        serif: ['"Instrument Serif"', "Georgia", "serif"],
      },
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        success: {
          DEFAULT: "#22c55e",
          dim: "rgba(34, 197, 94, 0.12)",
        },
        warning: {
          DEFAULT: "#f59e0b",
          dim: "rgba(245, 158, 11, 0.12)",
        },
        info: {
          DEFAULT: "#3b82f6",
          dim: "rgba(59, 130, 246, 0.12)",
        },
        indigo: {
          dim: "rgba(99, 102, 241, 0.12)",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      keyframes: {
        "fade-up": {
          from: { opacity: "0", transform: "translateY(12px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "slide-in": {
          from: { opacity: "0", transform: "translateX(-8px)" },
          to: { opacity: "1", transform: "translateX(0)" },
        },
        "gentle-pulse": {
          "0%, 100%": { boxShadow: "0 0 0 0 rgba(99, 102, 241, 0.15)" },
          "50%": { boxShadow: "0 0 0 6px rgba(99, 102, 241, 0)" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.4s ease-out both",
        "slide-in": "slide-in 0.3s ease-out both",
        "gentle-pulse": "gentle-pulse 2s ease-in-out infinite",
      },
    },
  },
  plugins: [animate],
};

export default config;
