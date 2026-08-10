import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

export default defineConfig(({ mode }) => ({
  base: mode === "pages" ? "/fax-sender/" : "/faxsender/",
  plugins: [
    react(),
    {
      name: "serve-admin-entry",
      configureServer(server) {
        server.middlewares.use("/admin", (request, response, next) => {
          if (request.url !== "/" && request.url !== "" && request.url !== "/index.html") {
            next();
            return;
          }
          response.setHeader("Content-Type", "text/html; charset=utf-8");
          response.end(readFileSync(resolve(__dirname, "public/admin/index.html")));
        });
      },
    },
  ],
}));
