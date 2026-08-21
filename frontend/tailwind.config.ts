import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        rgm: {
          orange: "#FC4C02",
          orangeLight: "#ff6a2b",
          dark: "#0a0a0a",
          card: "#121214",
          cardBorder: "rgba(255, 255, 255, 0.08)",
        }
      },
    },
  },
  plugins: [],
};
export default config;
