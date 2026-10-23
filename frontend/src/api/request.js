import axios from "axios";

const request = axios.create({
  baseURL: "/api",
  timeout: 60000,
});

// 请求拦截器：直接从 localStorage 拿 token，避免引入 Pinia 报错
request.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截器
request.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("token");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  },
);

// 🚨 必须要有这一行，否则 Home.vue 导入就会报错！
export default request;
