import { defineStore } from "pinia";
import { authApi } from "@/api";

const TOKEN_KEY = "career_agent_token";
const USER_KEY = "career_agent_user";
const FIRST_VISIT_KEY = "career_agent_first_visit_initialized";

const initAuthState = () => {
  if (!localStorage.getItem(FIRST_VISIT_KEY)) {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    localStorage.setItem(FIRST_VISIT_KEY, "1");
    return { token: "", user: null };
  }

  return {
    token: localStorage.getItem(TOKEN_KEY) || "",
    user: JSON.parse(localStorage.getItem(USER_KEY) || "null"),
  };
};

export const useAuthStore = defineStore("auth", {
  state: () => initAuthState(),
  getters: {
    isLoggedIn: (state) => !!state.token,
    role: (state) => state.user?.role || "",
  },
  actions: {
    async login(payload) {
      const res = await authApi.login(payload);
      this.token = res.data.access_token;
      this.user = res.data.user;
      localStorage.setItem(TOKEN_KEY, this.token);
      localStorage.setItem(USER_KEY, JSON.stringify(this.user));
    },
    async register(payload) {
      const res = await authApi.register(payload);
      this.token = res.data.access_token;
      this.user = res.data.user;
      localStorage.setItem(TOKEN_KEY, this.token);
      localStorage.setItem(USER_KEY, JSON.stringify(this.user));
    },
    async fetchMe() {
      const res = await authApi.me();
      this.user = res.data;
      localStorage.setItem(USER_KEY, JSON.stringify(this.user));
    },
    logout() {
      this.token = "";
      this.user = null;
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
    },
  },
});
