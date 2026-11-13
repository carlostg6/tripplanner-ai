import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  define: { global: "globalThis" }, // requerido por amazon-cognito-identity-js
  server: { port: 5173 },
});
