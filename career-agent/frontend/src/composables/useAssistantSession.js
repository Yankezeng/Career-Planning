import { legacySkillMap } from "@/constants/assistantSkills";

const ASSISTANT_CLIENT_CONTEXT_KEY = "career_agent_assistant_client_context";

const normalizeToken = (value = "") => String(value || "").trim().toLowerCase().replaceAll("_", "-");

export const normalizeSkillCode = (value = "") => {
  const token = normalizeToken(value);
  if (!token) return "";
  return legacySkillMap[token] || token;
};

export const normalizeSessionTitle = (value = "") => {
  const text = String(value || "").trim();
  return (text || "新任务").slice(0, 40);
};

export const normalizeSessionItem = (item = {}) => ({
  id: String(item.id || item.session_id || ""),
  title: normalizeSessionTitle(item.title || "新任务"),
  messages: Array.isArray(item.messages) ? item.messages : [],
  lastMessage: item.lastMessage || item.last_message || "",
  updatedAt: item.updatedAt || item.updated_at || "",
  lastSkill: normalizeSkillCode(item.lastSkill || item.last_skill || ""),
  pinned: !!item.pinned,
  state: item.state || item.state_json || {},
});

const toIntOrNull = (value) => {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : null;
};

export const normalizeAssistantClientContext = (value = {}) => {
  const payload = typeof value === "object" && value ? value : {};
  const attachment = payload.attachment && typeof payload.attachment === "object" ? payload.attachment : {};
  const attachmentId = toIntOrNull(payload.attachment_id || attachment.id);
  return {
    resume_id: toIntOrNull(payload.resume_id),
    resume_version_id: toIntOrNull(payload.resume_version_id),
    attachment_id: attachmentId,
    attachment: attachmentId
      ? {
          id: attachmentId,
          file_name: String(attachment.file_name || "").trim(),
          file_type: String(attachment.file_type || "").trim(),
        }
      : {},
    target_job: String(payload.target_job || "").trim(),
    target_city: String(payload.target_city || "").trim(),
    target_industry: String(payload.target_industry || "").trim(),
    selected_skill: normalizeSkillCode(payload.selected_skill || ""),
    current_focus: String(payload.current_focus || "").trim(),
    updated_at: payload.updated_at || new Date().toISOString(),
  };
};

export const getAssistantClientContext = () => {
  try {
    const raw = localStorage.getItem(ASSISTANT_CLIENT_CONTEXT_KEY);
    if (!raw) return normalizeAssistantClientContext({});
    return normalizeAssistantClientContext(JSON.parse(raw));
  } catch (_) {
    return normalizeAssistantClientContext({});
  }
};

export const setAssistantClientContext = (value = {}) => {
  const normalized = normalizeAssistantClientContext(value);
  localStorage.setItem(ASSISTANT_CLIENT_CONTEXT_KEY, JSON.stringify(normalized));
  return normalized;
};

export const patchAssistantClientContext = (patch = {}) => {
  const current = getAssistantClientContext();
  return setAssistantClientContext({ ...current, ...patch, updated_at: new Date().toISOString() });
};

export const clearAssistantClientContext = () => {
  localStorage.removeItem(ASSISTANT_CLIENT_CONTEXT_KEY);
};
