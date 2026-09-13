import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      backgroundImage: {
        "gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
        "gradient-conic":
          "conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))",
      },
      colors: {
        ink: "#1E2A4A",
        paper: "#F7F3EA",
        marigold: "#E8A33D",
        banyan: "#2F6F4E",
        rust: "#B5482A",
        sand: "#ECE3D0",
      },
      fontFamily: {
        serif: ["var(--font-fraunces)"],
        sans: ["var(--font-plex)"],
      },
    },
  },
  plugins: [],
};
export default config;