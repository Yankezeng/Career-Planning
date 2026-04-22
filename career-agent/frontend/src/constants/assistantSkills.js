export const legacySkillMap = {
  resume_optimize: "resume-workbench",
  ability_profile: "profile-insight",
  job_match: "match-center",
  career_path: "growth-planner",
  report_generate: "report-builder",
  candidate_screen: "candidate-screening",
  "candidate-screen": "candidate-screening",
  review_feedback: "review-advice",
  "review-feedback": "review-advice",
  system_monitor: "admin-metrics",
  "metrics-analysis": "admin-metrics",
  "job-recommend": "match-center",
  job_recommend: "match-center",
  match_center: "match-center",
  growth_planner: "growth-planner",
  profile_insight: "profile-insight",
  profile_image: "profile-image",
  "profile-image": "profile-image",
  persona_image: "profile-image",
  mbti: "profile-image",
  cbti: "profile-image",
  report_builder: "report-builder",
};

const normalizeToken = (value = "") => String(value || "").trim().toLowerCase().replaceAll("_", "-");

export const normalizeSkillCode = (code = "") => {
  const normalized = normalizeToken(code);
  if (!normalized) return "";
  return legacySkillMap[normalized] || normalized;
};

export const getRolePromptTemplates = (role = "student") => {
  const map = {
    student: [
      { label: "🌊 随便聊聊", prompt: "", mode: "free-chat" },
      { label: "📋 开始职业规划", prompt: "我想开始职业规划，请帮我走完完整流程", mode: "match-center" },
    ],
    enterprise: [
      { label: "🌊 随便聊聊", prompt: "", mode: "free-chat" },
      { label: "📋 候选人筛选", prompt: "筛出最适合的前三个候选人，并说明理由。", mode: "candidate-screening" },
    ],
    admin: [
      { label: "🌊 随便聊聊", prompt: "", mode: "free-chat" },
      { label: "📋 运营复盘", prompt: "输出本周运营复盘和下周优先动作。", mode: "ops-review" },
    ],
  };
  return map[role] || map.student;
};
