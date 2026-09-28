import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = [
  {
    ignores: [
      ".next/",
      "out/",
      "dist/",
      "node_modules/",
      "src-tauri/target/",
    ],
  },
  ...nextVitals,
  ...nextTs,
  {
    rules: {
      // Downgrade the hyper-strict React 19 rules
      "react-hooks/refs": "off",
      "react-hooks/set-state-in-effect": "off",
      "react-hooks/immutability": "off",
    }
  }
];

export default eslintConfig;
