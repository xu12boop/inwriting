import axios from "axios"
import { API_BASE } from "./base"

// 响应拦截器直接返回 data，因此实例解析出的结果在调用处视为 any，
// 由各调用点按本地类型（见 ../types）自行断言，保持类型安全的同时避免 axios 泛型摩擦。
const request: any = axios.create({
  baseURL: API_BASE,
  // 报告生成要等模型吐出完整 JSON，实测 40-90 秒，必须留足余量。
  // 后端长文本调用读超时为 120 秒，这里取 150 秒，保证「后端先超时、前端后超时」，
  // 否则前端会先断，用户看到的是无信息的「生成失败」。
  timeout: 150000,
})

// 请求拦截器：直接从 localStorage 拿 token，避免引入 Pinia 报错
request.interceptors.request.use((config: any) => {
  const token = localStorage.getItem("token")
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器：直接返回 data；401 时清空登录态并跳回登录页
request.interceptors.response.use(
  (response: any) => response.data,
  (error: any) => {
    if (error?.response?.status === 401) {
      localStorage.removeItem("token")
      window.location.href = "/login"
    }
    return Promise.reject(error)
  },
)

// 必须要有这一行，否则 Home.vue 等导入时会因类型缺失而报错
export default request
