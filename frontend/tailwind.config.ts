import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        heading: ['"Bricolage Grotesque"', "sans-serif"],
        body: ["Manrope", "sans-serif"],
      },
      colors: {
        ink: "#12110f",
        sand: "#f4efe3",
        linen: "#fffaf0",
        clay: "#cc5c2d",
        moss: "#355f48",
        "moss-dark": "#2a4d3a",
        line: "#e4dccb",
        rule: "#d9cfba",
        stone: "#e9e1cf",
        track: "#efe8d8",
        muted: "#5b564c",
        subtle: "#7a7365",
        faint: "#8a8373",
        body2: "#4a463e",
        soft: "#c9bfa9",
        dusk: "#3a362f",
        coal: "#2a2722",
        remote: "#2f5f8a",
      },
    },
  },
  plugins: [],
};

export default config;
