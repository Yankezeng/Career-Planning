<template>
  <div class="goal-recommendations">
    <div v-if="loading" class="rec-loading">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>正在生成职业目标推荐...</span>
    </div>
    <div v-else-if="recommendations.length" class="rec-list">
      <div class="rec-header">
        <h3 class="rec-title">智能推荐目标岗位</h3>
        <span class="rec-subtitle">基于您的画像、技能匹配与兴趣偏好综合分析</span>
      </div>
      <div v-for="(rec, idx) in recommendations" :key="rec.job_id" class="rec-card" :class="{ 'top-rec': idx === 0 }">
        <div v-if="idx === 0" class="top-badge">推荐</div>
        <div class="rec-main">
          <div class="rec-info">
            <div class="rec-job-name">{{ rec.job_name }}</div>
            <div class="rec-meta">
              <el-tag size="small" effect="plain">{{ rec.job_category || "-" }}</el-tag>
              <el-tag size="small" effect="plain">{{ rec.job_industry || "-" }}</el-tag>
            </div>
          </div>
          <div class="rec-scores">
            <div class="score-item">
              <span class="score-label">综合匹配</span>
              <div class="score-bar">
                <div class="score-fill" :style="{ width: rec.match_score + '%', background: scoreColor(rec.match_score) }"></div>
              </div>
              <span class="score-value">{{ rec.match_score }}分</span>
            </div>
            <div class="score-item">
              <span class="score-label">能力契合</span>
              <div class="score-bar">
                <div class="score-fill" :style="{ width: rec.ability_fit_score + '%', background: scoreColor(rec.ability_fit_score) }"></div>
              </div>
              <span class="score-value">{{ rec.ability_fit_score }}分</span>
            </div>
            <div class="score-item">
              <span class="score-label">兴趣契合</span>
              <div class="score-bar">
                <div class="score-fill" :style="{ width: rec.interest_fit_score + '%', background: scoreColor(rec.interest_fit_score) }"></div>
              </div>
              <span class="score-value">{{ rec.interest_fit_score }}分</span>
            </div>
          </div>
          <div class="rec-recommendation-score">
            <span class="rec-score-label">推荐指数</span>
            <span class="rec-score-value" :style="{ color: scoreColor(rec.recommendation_score) }">{{ rec.recommendation_score }}分</span>
          </div>
        </div>
        <div class="rec-details">
          <div v-if="rec.strengths && rec.strengths.length" class="rec-strengths">
            <div class="detail-label">您的优势</div>
            <div v-for="(s, si) in rec.strengths" :key="si" class="detail-item success">
              <el-icon><CircleCheckFilled /></el-icon>
              <span>{{ s }}</span>
            </div>
          </div>
          <div v-if="rec.gaps && rec.gaps.length" class="rec-gaps">
            <div class="detail-label">需关注</div>
            <div v-for="(g, gi) in rec.gaps" :key="gi" class="detail-item warning">
              <el-icon><WarningFilled /></el-icon>
              <span>{{ g }}</span>
            </div>
          </div>
          <div class="rec-reason">{{ rec.reason }}</div>
        </div>
        <div class="rec-actions">
          <el-button type="primary" size="small" @click="$emit('select', rec)">选为目标岗位</el-button>
        </div>
      </div>
    </div>
    <el-empty v-else description="暂无推荐，请先完善您的个人档案" />
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { Loading, CircleCheckFilled, WarningFilled } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";

const props = defineProps({
  fetchFn: { type: Function, required: true },
});

defineEmits(["select"]);

const loading = ref(false);
const recommendations = ref([]);

const scoreColor = (score) => {
  if (score >= 80) return "#22c55e";
  if (score >= 65) return "#f59e0b";
  return "#94a3b8";
};

const fetchData = async () => {
  loading.value = true;
  try {
    const res = await props.fetchFn();
    if (res?.data && Array.isArray(res.data)) {
      recommendations.value = res.data;
    }
  } catch (e) {
    ElMessage.error("获取推荐失败");
    console.error(e);
  } finally {
    loading.value = false;
  }
};

onMounted(fetchData);

defineExpose({ refresh: fetchData });
</script>

<style scoped>
.goal-recommendations {
  width: 100%;
}

.rec-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  height: 200px;
  color: #64748b;
}

.rec-loading .el-icon {
  font-size: 28px;
}

.rec-header {
  margin-bottom: 20px;
}

.rec-title {
  margin: 0 0 6px;
  font-size: 18px;
  font-weight: 700;
  color: #1e293b;
}

.rec-subtitle {
  font-size: 13px;
  color: #94a3b8;
}

.rec-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.rec-card {
  position: relative;
  padding: 20px;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #fff;
  transition: box-shadow 0.2s, border-color 0.2s;
}

.rec-card:hover {
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.06);
  border-color: #cbd5e1;
}

.rec-card.top-rec {
  border-color: #22c55e;
  background: linear-gradient(135deg, #f0fdf4 0%, #fff 100%);
}

.top-badge {
  position: absolute;
  top: -1px;
  right: 20px;
  background: #22c55e;
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  padding: 4px 12px;
  border-radius: 0 0 8px 8px;
}

.rec-main {
  display: flex;
  align-items: center;
  gap: 24px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.rec-info {
  flex: 1;
  min-width: 180px;
}

.rec-job-name {
  font-size: 17px;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 8px;
}

.rec-meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.rec-scores {
  flex: 2;
  min-width: 280px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.score-item {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
}

.score-label {
  width: 60px;
  color: #64748b;
  flex-shrink: 0;
}

.score-bar {
  flex: 1;
  height: 8px;
  background: #e2e8f0;
  border-radius: 4px;
  overflow: hidden;
}

.score-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.4s ease;
}

.score-value {
  width: 40px;
  text-align: right;
  font-weight: 600;
  color: #1e293b;
  flex-shrink: 0;
}

.rec-recommendation-score {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px 20px;
  background: #f8fafc;
  border-radius: 10px;
  flex-shrink: 0;
}

.rec-score-label {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 4px;
}

.rec-score-value {
  font-size: 24px;
  font-weight: 800;
}

.rec-details {
  margin-bottom: 12px;
}

.rec-strengths,
.rec-gaps {
  margin-bottom: 12px;
}

.detail-label {
  font-size: 13px;
  font-weight: 600;
  color: #475569;
  margin-bottom: 6px;
}

.detail-item {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 13px;
  line-height: 1.6;
  margin-bottom: 4px;
}

.detail-item.success {
  color: #166534;
}

.detail-item.success .el-icon {
  color: #22c55e;
}

.detail-item.warning {
  color: #92400e;
}

.detail-item.warning .el-icon {
  color: #f59e0b;
}

.rec-reason {
  font-size: 14px;
  color: #334155;
  line-height: 1.7;
  padding: 10px 12px;
  background: #f1f5f9;
  border-radius: 8px;
}

.rec-actions {
  display: flex;
  justify-content: flex-end;
}

@media (max-width: 768px) {
  .rec-main {
    flex-direction: column;
    align-items: flex-start;
  }

  .rec-scores {
    min-width: 100%;
  }
}
</style>
