<template>
  <div v-if="visibleCards.length" class="card-list">
    <article
      v-for="(card, index) in visibleCards"
      :key="`${card.type || 'card'}-${index}`"
      class="card-item"
      :class="{ 'profile-image-card': isProfileImageCard(card) }"
    >
      <div class="card-head">
        <span class="card-type">{{ typeLabel(card.type) }}</span>
        <span class="card-title">{{ card.title || "分析结果" }}</span>
      </div>

      <template v-if="isProfileImageCard(card)">
        <img
          v-if="cardData(card).image_url"
          class="persona-image"
          :src="assetUrl(cardData(card).image_url)"
          :alt="cardData(card).image_alt || `${cardData(card).persona?.code || ''} CBTI 人格画像图`"
        />
        <div class="persona-panel">
          <div class="persona-code">{{ cardData(card).persona?.code || cardData(card).persona_code }}</div>
          <div class="persona-name">{{ cardData(card).persona?.name || cardData(card).persona_name }}</div>
          <div class="persona-match">匹配度 {{ cardData(card).persona?.similarity_percent ?? "-" }}%</div>
        </div>
        <div v-if="mbtiProfile(card).code" class="mbti-panel">
          <span>MBTI 倾向</span>
          <strong>{{ mbtiProfile(card).code }}</strong>
          <em>{{ mbtiProfile(card).name || "职业风格参考" }}</em>
        </div>
        <p class="card-summary">{{ card.summary || cardData(card).analysis_summary }}</p>
        <div v-if="cardData(card).persona?.top_candidates?.length" class="candidate-row">
          <span v-for="item in cardData(card).persona.top_candidates" :key="item.code" class="candidate-pill">
            {{ item.code }} {{ item.similarity_percent }}%
          </span>
        </div>

        <section v-if="tableRows(card, 'ability_table').length" class="table-block">
          <div class="table-title">能力画像表格</div>
          <div class="table-row table-row-head">
            <span>维度</span>
            <span>分数</span>
            <span>证据</span>
            <span>结论</span>
          </div>
          <div v-for="row in tableRows(card, 'ability_table')" :key="row.dimension" class="table-row">
            <span>{{ row.dimension }}</span>
            <span>{{ row.score }}</span>
            <span>{{ row.evidence || "-" }}</span>
            <span>{{ row.conclusion || "-" }}</span>
          </div>
        </section>

        <section v-if="tableRows(card, 'experience_evidence_table').length" class="table-block">
          <div class="table-title">经历证据表格</div>
          <div class="table-row table-row-head three-col">
            <span>类型</span>
            <span>证据</span>
            <span>结论</span>
          </div>
          <div v-for="row in tableRows(card, 'experience_evidence_table')" :key="row.category" class="table-row three-col">
            <span>{{ row.category }}（{{ row.count }}）</span>
            <span>{{ row.evidence || "-" }}</span>
            <span>{{ row.conclusion || "-" }}</span>
          </div>
        </section>

        <section v-if="tableRows(card, 'semantic_gap_table').length" class="table-block">
          <div class="table-title">岗位语义与差距表格</div>
          <div class="table-row table-row-head three-col">
            <span>维度</span>
            <span>内容</span>
            <span>结论</span>
          </div>
          <div v-for="row in tableRows(card, 'semantic_gap_table')" :key="row.dimension" class="table-row three-col">
            <span>{{ row.dimension }}</span>
            <span>{{ row.content || row.evidence || "-" }}</span>
            <span>{{ row.conclusion || "-" }}</span>
          </div>
        </section>

        <section v-if="tableRows(card, 'growth_suggestions').length" class="table-block">
          <div class="table-title">成长建议</div>
          <div v-for="row in tableRows(card, 'growth_suggestions')" :key="row.direction" class="suggestion-row">
            <strong>{{ row.direction }}</strong>
            <span>{{ row.task }}</span>
            <small>{{ row.output }}</small>
          </div>
        </section>
      </template>

      <template v-else>
        <div class="card-summary">{{ card.summary || "查看详情" }}</div>
        <button type="button" class="detail-btn" @click="$emit('detail', card)">查看详情</button>
      </template>
    </article>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  cards: { type: Array, default: () => [] },
  backendOrigin: { type: String, default: "" },
});

defineEmits(["detail"]);

const typeLabel = (type = "") => {
  const map = {
    profile_card: "画像",
    profile_image_card: "CBTI",
    match_card: "匹配",
    gap_card: "差距",
    growth_card: "成长",
    report_card: "报告",
    resume_card: "简历",
    candidate_rank_card: "候选人",
    interview_question_card: "面试",
    metrics_card: "指标",
    action_checklist_card: "清单",
  };
  return map[type] || "结果";
};

const isProfileImageCard = (card) => card?.type === "profile_image_card";
const cardData = (card) => (card && typeof card.data === "object" ? card.data : {});
const hiddenProfileTools = new Set(["ingest_resume_attachment", "generate_profile", "profile_insight", "profile_trend_refresh"]);
const mbtiNames = {
  ISTJ: "责任执行型",
  ISFJ: "支持守护型",
  INFJ: "洞察规划型",
  INTJ: "战略分析型",
  ISTP: "实践解决型",
  ISFP: "灵活体验型",
  INFP: "理想探索型",
  INTP: "逻辑探索型",
  ESTP: "行动突破型",
  ESFP: "现场表达型",
  ENFP: "创意启发型",
  ENTP: "创新辩论型",
  ESTJ: "组织推进型",
  ESFJ: "协作服务型",
  ENFJ: "影响引导型",
  ENTJ: "目标统筹型",
};

const visibleCards = computed(() =>
  props.cards.filter((card) => {
    if (!card || typeof card !== "object") return false;
    if (card.type === "profile_card" || card.type === "profile_image_card" || hiddenProfileTools.has(card.tool)) return false;
    return true;
  }),
);

const mbtiProfile = (card) => {
  const data = cardData(card);
  const direct = data.mbti && typeof data.mbti === "object" ? data.mbti : {};
  const nested = data.persona?.mbti && typeof data.persona.mbti === "object" ? data.persona.mbti : {};
  const fallback = deriveMbtiFromCbti(data.persona?.code || data.persona_code || "");
  return {
    code: direct.code || nested.code || data.mbti_code || data.persona?.mbti_code || fallback.code,
    name: direct.name || nested.name || data.mbti_name || data.persona?.mbti_name || fallback.name,
    summary: direct.summary || nested.summary || "",
  };
};

const deriveMbtiFromCbti = (code) => {
  const text = String(code || "").trim().toUpperCase();
  if (!text) return { code: "", name: "" };
  const mbtiCode = `${text.includes("C") ? "E" : "I"}${text.startsWith("T") ? "N" : "S"}${text.startsWith("T") ? "T" : "F"}${text.includes("S") ? "J" : "P"}`;
  return { code: mbtiCode, name: mbtiNames[mbtiCode] || "职业风格参考" };
};

const assetUrl = (url) => {
  const text = String(url || "").trim();
  if (!text) return "";
  if (text.startsWith("http://") || text.startsWith("https://")) return text;
  const origin = String(props.backendOrigin || import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");
  return `${origin}${text.startsWith("/") ? "" : "/"}${text}`;
};

const tableRows = (card, key) => {
  const data = cardData(card);
  const direct = data[key];
  if (Array.isArray(direct)) return direct;
  const reportRows = data.profile_report?.[key];
  return Array.isArray(reportRows) ? reportRows : [];
};
</script>

<style scoped>
.card-list {
  margin-top: 10px;
  display: grid;
  gap: 10px;
}

.card-item {
  border: 1px solid #dce5f2;
  border-radius: 8px;
  background: #f8fbff;
  text-align: left;
  padding: 10px 12px;
}

.profile-image-card {
  background: #ffffff;
}

.card-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.card-type {
  border: 1px solid #c7d7f4;
  border-radius: 8px;
  min-height: 20px;
  padding: 0 8px;
  display: inline-flex;
  align-items: center;
  color: #1d4ed8;
  font-size: 11px;
  font-weight: 700;
}

.card-title {
  color: #0f172a;
  font-size: 13px;
  font-weight: 700;
}

.card-summary {
  margin: 8px 0 0;
  color: #475569;
  font-size: 12px;
  line-height: 1.6;
}

.detail-btn {
  margin-top: 8px;
  min-height: 28px;
  border: 1px solid #c7d7f4;
  border-radius: 8px;
  background: #ffffff;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.persona-image {
  width: 100%;
  max-height: 420px;
  object-fit: contain;
  border: 1px solid #dbe5f2;
  border-radius: 8px;
  background: #ffffff;
  display: block;
}

.persona-panel {
  margin-top: 10px;
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 8px;
  align-items: center;
}

.persona-code {
  color: #0f172a;
  font-size: 20px;
  font-weight: 800;
}

.persona-name {
  color: #1e293b;
  font-size: 14px;
  font-weight: 700;
}

.persona-match {
  color: #166534;
  font-size: 12px;
  font-weight: 700;
}

.mbti-panel {
  margin-top: 8px;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  background: #eff6ff;
  padding: 8px 10px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  color: #1e3a8a;
}

.mbti-panel span {
  font-size: 12px;
  font-weight: 700;
}

.mbti-panel strong {
  color: #0f62fe;
  font-size: 18px;
  line-height: 1;
}

.mbti-panel em {
  color: #334155;
  font-size: 12px;
  font-style: normal;
  font-weight: 700;
}

.candidate-row {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.candidate-pill {
  min-height: 24px;
  padding: 0 8px;
  border: 1px solid #bbf7d0;
  border-radius: 8px;
  background: #f0fdf4;
  color: #166534;
  display: inline-flex;
  align-items: center;
  font-size: 12px;
  font-weight: 700;
}

.table-block {
  margin-top: 10px;
  display: grid;
  gap: 4px;
}

.table-title {
  color: #0f172a;
  font-size: 13px;
  font-weight: 800;
}

.table-row {
  display: grid;
  grid-template-columns: 82px 48px minmax(0, 1.1fr) minmax(0, 1fr);
  gap: 6px;
  align-items: start;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 6px 8px;
  color: #334155;
  font-size: 12px;
  line-height: 1.45;
}

.table-row.three-col {
  grid-template-columns: 92px minmax(0, 1.2fr) minmax(0, 1fr);
}

.table-row-head {
  background: #f1f6ff;
  color: #1e3a8a;
  font-weight: 800;
}

.suggestion-row {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 8px;
  display: grid;
  gap: 3px;
  color: #334155;
  font-size: 12px;
}

.suggestion-row strong {
  color: #0f172a;
}

.suggestion-row small {
  color: #64748b;
}

@media (max-width: 720px) {
  .persona-panel,
  .table-row,
  .table-row.three-col {
    grid-template-columns: 1fr;
  }
}
</style>
