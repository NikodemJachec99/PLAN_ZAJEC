import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        heading: ["Bricolage Grotesque", "sans-serif"],
        body: ["Manrope", "sans-serif"],
      },
      colors: {
        ink: "#12110f",
        sand: "#f4efe3",
        linen: "#fffaf0",
        clay: "#cc5c2d",
        moss: "#355f48",
        sky: "#dfeef7",
      },
      boxShadow: {
        panel: "0 24px 60px -26px rgba(18, 17, 15, 0.35)",
      },
    },
  },
  plugins: [],
};

export default config;
