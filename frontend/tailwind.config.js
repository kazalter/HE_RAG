/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{vue,js}"],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          '"Noto Sans SC"',
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          '"PingFang SC"',
          '"Microsoft YaHei"',
          "sans-serif",
        ],
        mono: ['"JetBrains Mono"', "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      colors: {
        paper: { 50: "#faf9f6", 100: "#f4f1ec" },
        coral: {
          50: "#fdf2ee",
          100: "#fbe3d9",
          200: "#f6c9b6",
          300: "#eda88c",
          400: "#e2855f",
          500: "#d97757",
          600: "#c25f3f",
          700: "#a04b30",
        },
      },
    },
  },
  plugins: [],
};
