/**
 * 统一的 API 基地址，整个前端只从这里取，避免各处硬编码 /api。
 *
 * - 默认 "/api"：本地由 Vite 代理转发到 127.0.0.1:8001，线上由 Nginx 反代到后端；
 * - 前后端分域名部署时，在 `frontend/.env.production` 写
 *   `VITE_API_BASE=https://api.your-domain.com` 即可切换，无需改代码。
 */
export const API_BASE: string = (import.meta.env.VITE_API_BASE || "/api").replace(/\/+$/, "")

export default API_BASE
