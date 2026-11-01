import axios from "axios"

// 响应拦截器直接返回 data，因此实例解析出的结果在调用处视为 any，
// 由各调用点按本地类型（见 ../types）自行断言，保持类型安全的同时避免 axios 泛型摩擦。
const request: any = axios.create({
  baseURL: "/api",
  timeout: 60000,
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
