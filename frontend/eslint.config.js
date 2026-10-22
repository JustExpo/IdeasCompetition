import js from "@eslint/js";
import jsxA11y from "eslint-plugin-jsx-a11y";
import react from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "coverage", "src/api/schema.gen.ts", ".dependency-cruiser.cjs"] },
  js.configs.recommended,
  tseslint.configs.strictTypeChecked,
  react.configs.flat.recommended,
  react.configs.flat["jsx-runtime"],
  reactHooks.configs.flat.recommended,
  jsxA11y.flatConfigs.recommended,
  {
    languageOptions: {
      globals: { ...globals.browser },
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
    },
    settings: { react: { version: "18.3" } },
    rules: {
      // CLAUDE.md §6.2: порядок состояний, кодов ошибок и типов события не должен «проваливаться».
      "@typescript-eslint/switch-exhaustiveness-check": "error",
      "@typescript-eslint/no-floating-promises": "error",
      "@typescript-eslint/restrict-template-expressions": ["error", { allowNumber: true }],
      "react/no-danger": "error",
      // Сеть — только в src/api, время — только в shared/lib/serverTime.ts (CLAUDE.md §4.2).
      "no-restricted-globals": [
        "error",
        { name: "fetch", message: "fetch разрешён только в src/api." },
        { name: "WebSocket", message: "WebSocket разрешён только в src/api." },
      ],
      "no-restricted-properties": [
        "error",
        {
          object: "Date",
          property: "now",
          message: "Время берётся из shared/lib/serverTime.ts (серверные часы).",
        },
        { object: "window", property: "fetch", message: "fetch разрешён только в src/api." },
      ],
      "no-restricted-syntax": [
        "error",
        {
          selector: "NewExpression[callee.name='Date'][arguments.length=0]",
          message: "Текущее время берётся из shared/lib/serverTime.ts.",
        },
      ],
    },
  },
  {
    files: ["src/api/**"],
    rules: { "no-restricted-globals": "off", "no-restricted-properties": "off" },
  },
  {
    files: ["src/shared/lib/serverTime.ts"],
    rules: { "no-restricted-properties": "off", "no-restricted-syntax": "off" },
  },
  {
    files: ["**/*.test.{ts,tsx}", "src/test/**"],
    rules: {
      "no-restricted-globals": "off",
      "no-restricted-properties": "off",
      "no-restricted-syntax": "off",
    },
  },
  {
    files: ["*.config.{js,ts}"],
    languageOptions: { globals: { ...globals.node } },
    ...tseslint.configs.disableTypeChecked,
  },
);
