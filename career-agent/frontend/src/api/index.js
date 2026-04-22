import request from "./request";

const API_ORIGIN = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");
const API_BASE_URL = `${API_ORIGIN}/api`;
const DEFAULT_ASSISTANT_CHAT_TIMEOUT_MS = Number(import.meta.env.VITE_ASSISTANT_CHAT_TIMEOUT_MS || 75000);
const ASSISTANT_GENERIC_ERROR_MESSAGE = "这次回答没有完整返回，请稍后重试，或把问题拆成几步继续问我。";
const ASSISTANT_TIMEOUT_ERROR_MESSAGE = "这次问题稍复杂，我先建议你稍后重试，或拆成“能力差距、表达话术、行动计划”分步来问。";
const ASSISTANT_STREAM_INTERRUPTED_MESSAGE = "对话连接意外中断了，请稍后重试。我也可以先按“结论 + 下一步”继续帮你整理。";

const sanitizeAssistantErrorMessage = (rawMessage, status = 0) => {
  const text = String(rawMessage || "").trim();
  if (!text) {
    if (status >= 500) return ASSISTANT_GENERIC_ERROR_MESSAGE;
    return ASSISTANT_GENERIC_ERROR_MESSAGE;
  }
  const lowered = text.toLowerCase();
  const looksInternal = [
    "traceback",
    "exception",
    "stack",
    "agent",
    "supervisor",
    "dispatch",
    "workflow",
    "runtimeerror",
    "valueerror",
    "keyerror",
    "llm",
    "ssl",
    "network error",
    "unexpected_eof",
    "unexpected eof",
    "eof occurred",
    "provider",
    "urlerror",
    "connection reset",
    "remote disconnected",
  ].some((token) => lowered.includes(token));
  if (looksInternal || text.length > 160) {
    if (status === 408 || lowered.includes("timeout") || lowered.includes("timed out")) {
      return ASSISTANT_TIMEOUT_ERROR_MESSAGE;
    }
    return ASSISTANT_GENERIC_ERROR_MESSAGE;
  }
  return text;
};

export const authApi = {
  login: (data) => request.post("/auth/login", data),
  register: (data) => request.post("/auth/register", data),
  me: () => request.get("/auth/me"),
};

export const assistantApi = {
  welcome: () => request.get("/assistant/welcome"),
  summary: () => request.get("/assistant/summary"),
  search: (q) => request.get("/assistant/search", { params: { q } }),
  assets: () => request.get("/assistant/assets"),
  gallery: () => request.get("/assistant/gallery"),
  skills: () => request.get("/assistant/skills"),
  sessions: () => request.get("/assistant/sessions"),
  createSession: (data) => request.post("/assistant/sessions", data),
  updateSession: (id, data) => request.patch(`/assistant/sessions/${id}`, data),
  deleteSession: (id) => request.delete(`/assistant/sessions/${id}`),
  sessionMessages: (id) => request.get(`/assistant/sessions/${id}/messages`),
  downloadArtifact: async (attachmentId) => {
    const token = localStorage.getItem("career_agent_token");
    const response = await fetch(`${API_BASE_URL}/assistant/artifacts/${attachmentId}/download`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!response.ok) {
      let message = "文件下载失败";
      try {
        const errorData = await response.json();
        message = errorData?.message || errorData?.detail || message;
      } catch (_) {
        // Ignore JSON parsing failure and keep default message.
      }
      throw new Error(message);
    }
    return response.blob();
  },
  chat: async (data, handlers = {}) => {
    const token = localStorage.getItem("career_agent_token");
    const controller = new AbortController();
    const timeoutMs = Number(handlers.timeoutMs || DEFAULT_ASSISTANT_CHAT_TIMEOUT_MS);
    const timeoutMessage = handlers.timeoutMessage || ASSISTANT_TIMEOUT_ERROR_MESSAGE;
    let didTimeout = false;
    let timeoutId = null;
    const clearChatTimeout = () => {
      if (timeoutId) window.clearTimeout(timeoutId);
      timeoutId = null;
    };
    const refreshChatTimeout = () => {
      clearChatTimeout();
      if (timeoutMs > 0) {
        timeoutId = window.setTimeout(() => {
          didTimeout = true;
          controller.abort();
        }, timeoutMs);
      }
    };
    refreshChatTimeout();
    let response;
    try {
      response = await fetch(`${API_BASE_URL}/assistant/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(data || {}),
        signal: controller.signal,
      });
    } catch (error) {
      clearChatTimeout();
      if (didTimeout || error?.name === "AbortError") {
        const timeoutError = new Error(timeoutMessage);
        timeoutError.code = "ASSISTANT_CHAT_TIMEOUT";
        timeoutError.friendlyMessage = timeoutMessage;
        throw timeoutError;
      }
      throw error;
    }
    if (!response.ok) {
      clearChatTimeout();
      let backendMessage = "";
      try {
        const raw = await response.text();
        if (raw) {
          try {
            const parsed = JSON.parse(raw);
            backendMessage = parsed?.message || parsed?.detail || "";
          } catch (_) {
            backendMessage = raw;
          }
        }
      } catch (_) {
        // Ignore response body read failures and keep fallback message.
      }
      const message = sanitizeAssistantErrorMessage(backendMessage || `聊天请求失败(${response.status})`, response.status);
      const error = new Error(message);
      error.status = response.status;
      error.backendMessage = backendMessage;
      error.friendlyMessage = message;
      throw error;
    }
    const reader = response.body?.getReader();
    if (!reader) {
      clearChatTimeout();
      const error = new Error(ASSISTANT_STREAM_INTERRUPTED_MESSAGE);
      error.code = "ASSISTANT_STREAM_UNAVAILABLE";
      error.friendlyMessage = ASSISTANT_STREAM_INTERRUPTED_MESSAGE;
      throw error;
    }
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    let donePayload = null;

    const emitEvent = (eventName, payload) => {
      refreshChatTimeout();
      if (eventName === "meta" && typeof handlers.onMeta === "function") handlers.onMeta(payload || {});
      if (eventName === "progress" && typeof handlers.onProgress === "function") handlers.onProgress(payload || {});
      if (eventName === "error" && typeof handlers.onError === "function") handlers.onError(payload || {});
      if (eventName === "delta" && typeof handlers.onDelta === "function") handlers.onDelta(payload || {});
      if (eventName === "done" && typeof handlers.onDone === "function") handlers.onDone(payload || {});
      if (eventName === "done") donePayload = payload || {};
    };

    try {
      while (true) {
        const { value, done } = await reader.read();
        if (value?.length) refreshChatTimeout();
        buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
        const chunks = buffer.split("\n\n");
        buffer = chunks.pop() || "";
        for (const chunk of chunks) {
          const lines = chunk.split("\n").map((line) => line.trim()).filter(Boolean);
          const eventLine = lines.find((line) => line.startsWith("event:"));
          const dataLines = lines.filter((line) => line.startsWith("data:"));
          if (!eventLine || !dataLines.length) continue;
          const eventName = eventLine.replace("event:", "").trim();
          const payloadText = dataLines.map((line) => line.slice(5).trim()).join("");
          let payload = {};
          try {
            payload = payloadText ? JSON.parse(payloadText) : {};
          } catch (error) {
            const parseError = new Error(ASSISTANT_STREAM_INTERRUPTED_MESSAGE);
            parseError.code = "ASSISTANT_STREAM_PARSE_ERROR";
            parseError.friendlyMessage = ASSISTANT_STREAM_INTERRUPTED_MESSAGE;
            parseError.cause = error;
            throw parseError;
          }
          emitEvent(eventName, payload);
        }
        if (done) break;
      }
    } catch (error) {
      if (didTimeout || error?.name === "AbortError") {
        const timeoutError = new Error(timeoutMessage);
        timeoutError.code = "ASSISTANT_CHAT_TIMEOUT";
        timeoutError.friendlyMessage = timeoutMessage;
        throw timeoutError;
      }
      throw error;
    } finally {
      clearChatTimeout();
    }
    if (!donePayload) {
      const streamError = new Error(ASSISTANT_STREAM_INTERRUPTED_MESSAGE);
      streamError.code = "ASSISTANT_STREAM_INTERRUPTED";
      streamError.friendlyMessage = ASSISTANT_STREAM_INTERRUPTED_MESSAGE;
      throw streamError;
    }
    return donePayload || {};
  },
};

export const jobApi = {
  list: () => request.get("/jobs"),
  knowledgePostings: (params = {}) => request.get("/jobs/knowledge-postings", { params }),
  detail: (id) => request.get(`/jobs/${id}`),
  create: (data) => request.post("/jobs", data),
  update: (id, data) => request.put(`/jobs/${id}`, data),
  remove: (id) => request.delete(`/jobs/${id}`),
  generateProfile: (id) => request.post(`/jobs/${id}/generate-profile`),
  relations: (id) => request.get(`/jobs/${id}/relations`),
  transfer: (sourceId, targetId) => request.get(`/jobs/relations/transfer/${sourceId}/${targetId}`),
};

export const studentApi = {
  me: () => request.get("/students/me"),
  updateMe: (data) => request.put("/students/me", data),
  listResource: (resource) => request.get(`/students/me/${resource}`),
  createResource: (resource, data) => request.post(`/students/me/${resource}`, data),
  updateResource: (resource, id, data) => request.put(`/students/me/${resource}/${id}`, data),
  deleteResource: (resource, id) => request.delete(`/students/me/${resource}/${id}`),
  uploadAttachment: (formData) => request.post("/students/me/attachments", formData, { headers: { "Content-Type": "multipart/form-data" } }),
  listAttachments: () => request.get("/students/me/attachments"),
  deleteAttachment: (id) => request.delete(`/students/me/attachments/${id}`),
  listResumes: () => request.get("/students/me/resumes"),
  createResume: (data) => request.post("/students/me/resumes", data),
  updateResume: (id, data) => request.put(`/students/me/resumes/${id}`, data),
  deleteResume: (id) => request.delete(`/students/me/resumes/${id}`),
  listResumeVersions: (resumeId) => request.get(`/students/me/resumes/${resumeId}/versions`),
  createResumeVersion: (resumeId, data) => request.post(`/students/me/resumes/${resumeId}/versions`, data),
  cloneResume: (resumeId, data = {}) => request.post(`/students/me/resumes/${resumeId}/clone`, data),
  setDefaultResume: (resumeId) => request.post(`/students/me/resumes/${resumeId}/set-default`),
  createResumeFromAttachment: (attachmentId, data = {}) => request.post(`/students/me/resumes/from-attachment/${attachmentId}`, data),
  optimizeResumeByResume: (resumeId, data = {}) => request.post(`/students/me/resumes/${resumeId}/optimize`, data),
  deliverResumeByResume: (resumeId, data) => request.post(`/students/me/resumes/${resumeId}/deliver`, data),
  parseResume: (attachmentId) => request.post(`/students/me/resume/parse/${attachmentId}`),
  ingestResume: (attachmentId) => request.post(`/students/me/resume/ingest/${attachmentId}`),
  listResumeDeliveryTargets: () => request.get("/students/me/resume-delivery/targets"),
  listResumeDeliveries: () => request.get("/students/me/resume-deliveries"),
  deliverResume: (data) => request.post("/students/me/resume-deliveries", data),
  optimizeResume: (attachmentId, options = {}) => {
    const params = {};
    if (options.targetRole) params.target_role = options.targetRole;
    if (options.targetJobId != null) params.target_job_id = options.targetJobId;
    if (options.jobDescription) params.job_description = options.jobDescription;
    return request.post(`/students/me/resume/optimize/${attachmentId}`, null, { params });
  },
  previewResumePdf: (attachmentId) => request.get(`/students/me/resume/preview/${attachmentId}`),
  downloadResumeWord: async (attachmentId, options = {}) => {
    const token = localStorage.getItem("career_agent_token");
    const params = new URLSearchParams();
    if (options.resumeId != null) params.set("resume_id", String(options.resumeId));
    if (options.resumeVersionId != null) params.set("resume_version_id", String(options.resumeVersionId));
    if (options.targetRole) params.set("target_role", String(options.targetRole));
    if (options.targetJobId != null) params.set("target_job_id", String(options.targetJobId));
    if (options.jobDescription) params.set("job_description", String(options.jobDescription));
    const query = params.toString();

    const response = await fetch(`${API_BASE_URL}/students/me/resume/export/word/${attachmentId}${query ? `?${query}` : ""}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) {
      let message = "简历 Word 导出失败";
      try {
        const errorData = await response.json();
        message = errorData?.message || errorData?.detail || message;
      } catch (_) {
        // Ignore JSON parsing failure and keep default message.
      }
      throw new Error(message);
    }
    return response.blob();
  },
  downloadResumePdf: async (attachmentId, options = {}) => {
    const token = localStorage.getItem("career_agent_token");
    const params = new URLSearchParams();
    if (options.resumeId != null) params.set("resume_id", String(options.resumeId));
    if (options.resumeVersionId != null) params.set("resume_version_id", String(options.resumeVersionId));
    if (options.targetRole) params.set("target_role", String(options.targetRole));
    if (options.targetJobId != null) params.set("target_job_id", String(options.targetJobId));
    if (options.jobDescription) params.set("job_description", String(options.jobDescription));
    const query = params.toString();

    const response = await fetch(`${API_BASE_URL}/students/me/resume/export/pdf/${attachmentId}${query ? `?${query}` : ""}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) {
      let message = "简历 PDF 导出失败";
      try {
        const errorData = await response.json();
        message = errorData?.message || errorData?.detail || message;
      } catch (_) {
        // Ignore JSON parsing failure and keep default message.
      }
      throw new Error(message);
    }
    return response.blob();
  },
  generateProfile: () => request.post("/students/me/profile/generate"),
  getProfile: () => request.get("/students/me/profile", { silent: true }),
  generateProfileImage: () => request.post("/students/me/profile/image/generate"),
  getProfileImage: () => request.get("/students/me/profile/image", { silent: true }),
  generateMatches: () => request.post("/students/me/matches/generate"),
  getMatches: () => request.get("/students/me/matches"),
  getMatch: (jobId) => request.get(`/students/me/matches/${jobId}`),
  saveGoal: (data) => request.post("/students/me/career-goals", data),
  getGoal: () => request.get("/students/me/career-goals"),
  getGoalRecommendations: () => request.get("/students/me/career-goals/recommendations"),
  generatePath: (data) => request.post("/students/me/career-path/generate", data),
  getPath: () => request.get("/students/me/career-path"),
  generateReport: (data) => request.post("/students/me/report/generate", data),
  latestReport: () => request.get("/students/me/report/latest"),
  previewReport: (id) => request.get(`/students/reports/${id}/preview`),
  updateReport: (id, data) => request.put(`/students/reports/${id}`, data),
  polishReport: (id) => request.post(`/students/reports/${id}/polish`),
  checkReport: (id) => request.get(`/students/reports/${id}/check`),
  reportVersions: (id) => request.get(`/students/reports/${id}/versions`),
  restoreReportVersion: (id, data) => request.post(`/students/reports/${id}/restore`, data),
  downloadReportPdf: async (id) => {
    const token = localStorage.getItem("career_agent_token");
    const response = await fetch(`${API_BASE_URL}/students/reports/${id}/export/pdf`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return response.blob();
  },
  growthRecords: () => request.get("/students/me/growth-records"),
  createGrowthRecord: (data) => request.post("/students/me/growth-records", data),
  reviews: () => request.get("/students/me/reviews"),
  latestOptimization: () => request.get("/students/me/re-optimization/latest"),
  reOptimize: () => request.post("/students/me/re-optimization"),
};

export const enterpriseApi = {
  dashboard: () => request.get("/enterprise/dashboard"),
  students: () => request.get("/enterprise/students", { silent: true }),
  studentProfile: (id) => request.get(`/enterprise/students/${id}/profile`, { silent: true }),
  studentReport: (id) => request.get(`/enterprise/students/${id}/report`),
  studentMatches: (id) => request.get(`/enterprise/students/${id}/matches`),
  studentMatchDetail: (id, jobId) => request.get(`/enterprise/students/${id}/matches/${jobId}`),
  studentCareerPath: (id) => request.get(`/enterprise/students/${id}/career-path`),
  studentGrowthRecords: (id) => request.get(`/enterprise/students/${id}/growth-records`),
  studentLatestOptimization: (id) => request.get(`/enterprise/students/${id}/optimization/latest`),
  review: (id, data) => request.post(`/enterprise/students/${id}/review`, data),
  deliveries: () => request.get("/enterprise/deliveries"),
  deliveryDetail: (id) => request.get(`/enterprise/deliveries/${id}`),
  resumeAnalysis: (id) => request.get(`/enterprise/deliveries/${id}/resume-analysis`),
};

export const adminApi = {
  users: () => request.get("/admin/users"),
  createUser: (data) => request.post("/admin/users", data),
  stats: () => request.get("/admin/stats/dashboard"),
  controlCenter: () => request.get("/admin/stats/control-center"),
  llmOverview: () => request.get("/admin/llm/overview"),
  llmUsageTrend: (mode = "24h") => request.get("/admin/llm/usage/trend", { params: { mode } }),
  llmLogs: (params = {}) => request.get("/admin/llm/logs", { params }),
  llmPing: () => request.post("/admin/llm/ping"),
  configs: () => request.get("/admin/configs"),
  updateConfigs: (data) => request.put("/admin/configs", data),
  departments: () => request.get("/admin/departments"),
  classes: () => request.get("/admin/classes"),
};

export const graphApi = {
  getJobGraph: (params = {}) => request.get("/graph/job-graph", { params }),
  checkJobGraph: () => request.get("/graph/job-graph/check"),
  getJobDetail: (jobId) => request.get(`/graph/job-graph/detail/${jobId}`),
};
