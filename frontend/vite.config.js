import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  server: {
    // 固定监听 IPv4，避免只绑定 ::1 导致 127.0.0.1 访问被拒绝
    host: "127.0.0.1",
    port: 5173,
    // 端口被占用时直接报错，而不是悄悄换成 5174（否则浏览器打开 5173 会「拒绝访问」）
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8001",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
