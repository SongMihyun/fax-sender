import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => ({
  base: mode === "pages" ? "/fax-sender/admin/" : "/faxsender/admin/",
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5791,
  },
  build: {
    outDir: "../../pages/public/admin",
    emptyOutDir: true,
  },
}));
