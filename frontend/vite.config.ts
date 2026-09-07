import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  envDir: "..",
  plugins: [react()],
  // MapLibre creates its rendering worker from the distributed ESM file.
  // Vite's dependency optimizer can rewrite that reference to a stale
  // node_modules/.vite path, leaving the controls visible but no map tiles.
  optimizeDeps: {
    exclude: ["maplibre-gl"],
  },
  server: {
    port: 5173,
  },
});
