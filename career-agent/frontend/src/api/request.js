import axios from "axios";
import { ElMessage } from "element-plus";

const API_ORIGIN = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");

const request = axios.create({
  baseURL: `${API_ORIGIN}/api`,
  timeout: 180000,
});

request.interceptors.request.use((config) => {
  const token = localStorage.getItem("career_agent_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

request.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const silent = Boolean(error?.config?.silent);
    const status = Number(error?.response?.status || 0);
    let message = "";

    if (!error?.response) {
      if (error?.code === "ECONNABORTED") message = "请求超时，请稍后重试";
      else if (typeof navigator !== "undefined" && navigator.onLine === false) message = "网络已断开，请检查连接后重试";
      else if (String(error?.message || "").includes("Network Error")) message = "无法连接服务，请检查后端服务或代理配置";
      else message = "网络异常，请稍后重试";
    } else if (status >= 500) {
      message = "服务暂时不可用，请稍后重试";
    } else if (status >= 400) {
      message = error?.response?.data?.message || error?.response?.data?.detail || "请求参数或权限异常，请检查后重试";
    } else {
      message = error?.response?.data?.message || error?.response?.data?.detail || "请求失败";
    }

    error.friendlyMessage = message;

    if (status === 401) {
      localStorage.removeItem("career_agent_token");
      localStorage.removeItem("career_agent_user");
      if (!silent) ElMessage.error("登录状态已过期，请重新登录");
      location.href = "/?login=1";
    } else if (!silent) {
      ElMessage.error(message);
    }

    return Promise.reject(error);
  },
);

export default request;
