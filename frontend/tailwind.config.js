/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}", "./app/**/*.{js,jsx,ts,tsx}", "./components/**/*.{js,jsx,ts,tsx}"],
  presets: [require("nativewind/preset")],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "#4F46E5",
          light: "#818CF8",
          dark: "#3730A3",
        },
        surface: "#FFFFFF",
        "surface-elevated": "#FFFFFF",
        "surface-hover": "#F3F4F6",
        background: "#F8F9FB",
        border: "#E5E7EB",
        text: {
          primary: "#111827",
          secondary: "#4B5563",
          muted: "#6B7280",
          faint: "#9CA3AF",
          inverse: "#FFFFFF",
        },
        success: "#16A34A",
        warning: "#D97706",
        danger: "#DC2626",
        info: "#2563EB",
        category: {
          blue: "#3B82F6",
          purple: "#8B5CF6",
          teal: "#14B8A6",
          indigo: "#6366F1",
        },
      },
      fontFamily: {
        sans: ["Inter_400Regular"],
        "sans-medium": ["Inter_500Medium"],
        "sans-semibold": ["Inter_600SemiBold"],
        "sans-bold": ["Inter_700Bold"],
      },
      borderRadius: {
        sm: "4px",
        DEFAULT: "8px",
        md: "8px",
        lg: "10px",
      },
    },
  },
  plugins: [],
};
