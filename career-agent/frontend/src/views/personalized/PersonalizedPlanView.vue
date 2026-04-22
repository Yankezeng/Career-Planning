<template>
  <div class="personalized-plan">
    <div class="plan-header">
      <h2>个性化发展方案</h2>
      <el-button type="primary" @click="generatePlan">重新生成</el-button>
    </div>

    <div v-if="loading" class="loading-state">生成中...</div>

    <div v-else-if="planData" class="plan-content">
      <el-tabs v-model="activeTab" type="border-card">
        <el-tab-pane label="优势分析" name="strengths">
          <div class="strengths-section">
            <div v-if="planData.strengths && planData.strengths.length" class="strengths-list">
              <div v-for="strength in planData.strengths" :key="strength.ability" class="strength-card">
                <div class="strength-header">
                  <span class="strength-name">{{ strength.ability }}</span>
                  <el-tag :type="strength.level === '强项' ? 'success' : 'warning'">{{ strength.level }}</el-tag>
                </div>
                <div class="strength-score">{{ strength.score }}分</div>
                <p class="strength-desc">{{ strength.description }}</p>
                <div class="leverage-suggestion">
                  <h5>利用建议</h5>
                  <p>{{ strength.leverage_suggestion }}</p>
                </div>
              </div>
            </div>
            <div v-else class="empty-tip">暂无优势数据</div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="短板分析" name="weaknesses">
          <div class="weaknesses-section">
            <div v-if="planData.weaknesses && planData.weaknesses.length" class="weaknesses-list">
              <div v-for="weakness in planData.weaknesses" :key="weakness.ability" class="weakness-card">
                <div class="weakness-header">
                  <span class="weakness-name">{{ weakness.ability }}</span>
                  <el-tag type="danger">{{ weakness.level }}</el-tag>
                </div>
                <div class="weakness-score">{{ weakness.score }}分</div>
                <p class="weakness-desc">{{ weakness.description }}</p>
                <div class="improvement-suggestion">
                  <h5>提升建议</h5>
                  <p>{{ weakness.improvement_suggestion }}</p>
                </div>
              </div>
            </div>
            <div v-else class="empty-tip">暂无短板数据，能力结构均衡</div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="规避提示" name="avoid">
          <div class="avoid-section">
            <div v-if="planData.avoid_suggestions" class="avoid-content">
              <div v-if="planData.avoid_suggestions.job_types_to_avoid.length" class="avoid-list">
                <h4>需规避的岗位类型</h4>
                <el-tag v-for="job in planData.avoid_suggestions.job_types_to_avoid" :key="job" type="danger" class="avoid-tag">{{ job }}</el-tag>
              </div>
              <div v-if="planData.avoid_suggestions.company_cultures_to_note.length" class="avoid-list">
                <h4>需要注意的公司文化</h4>
                <el-tag v-for="culture in planData.avoid_suggestions.company_cultures_to_note" :key="culture" type="warning" class="avoid-tag">{{ culture }}</el-tag>
              </div>
              <div v-if="planData.avoid_suggestions.risk_warnings.length" class="risk-list">
                <h4>风险提示</h4>
                <ul>
                  <li v-for="warning in planData.avoid_suggestions.risk_warnings" :key="warning">{{ warning }}</li>
                </ul>
              </div>
            </div>
            <div v-else class="empty-tip">暂无规避建议</div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="发展策略" name="strategy">
          <div class="strategy-section">
            <div v-if="planData.strengths_strategy" class="strategy-block">
              <h4>优势利用策略</h4>
              <p class="strategy-overview">{{ planData.strengths_strategy.overview }}</p>
              <div class="interview-tips">
                <h5>面试技巧</h5>
                <ul>
                  <li v-for="tip in planData.strengths_strategy.interview_tips" :key="tip">{{ tip }}</li>
                </ul>
              </div>
            </div>
            <div v-if="planData.weaknesses_strategy" class="strategy-block">
              <h4>短板提升策略</h4>
              <p class="strategy-overview">{{ planData.weaknesses_strategy.overview }}</p>
              <div v-if="planData.weaknesses_strategy.improvement_plans" class="improvement-plans">
                <div v-for="plan in planData.weaknesses_strategy.improvement_plans" :key="plan.ability" class="improvement-plan">
                  <h6>{{ plan.ability }} (当前{{ plan.current_score }}分 → 目标{{ plan.target_score }}分)</h6>
                  <p>时间周期: {{ plan.timeline }}</p>
                  <ul>
                    <li v-for="action in plan.actions" :key="action">{{ action }}</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="推荐岗位" name="jobs">
          <div class="jobs-section">
            <div v-if="planData.recommended_jobs && planData.recommended_jobs.length" class="jobs-list">
              <div v-for="job in planData.recommended_jobs" :key="job.job_id" class="job-card">
                <div class="job-header">
                  <span class="job-name">{{ job.job_name }}</span>
                  <el-tag type="success">匹配度 {{ job.match_score }}%</el-tag>
                </div>
                <div class="job-category">{{ job.category }}</div>
                <div class="job-reasons">
                  <span v-for="reason in job.match_reasons" :key="reason" class="reason-tag">{{ reason }}</span>
                </div>
                <div class="job-highlight">亮点: {{ job.highlight }}</div>
              </div>
            </div>
            <div v-else class="empty-tip">暂无推荐岗位</div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="发展报告" name="report">
          <div class="report-section">
            <div v-if="planData.personalized_report" class="report-content">
              <h3>{{ planData.personalized_report.title }}</h3>
              <div class="report-meta">{{ planData.personalized_report.summary }}</div>
              <div class="report-body">
                <pre>{{ planData.personalized_report.content }}</pre>
              </div>
            </div>
            <div v-else class="empty-tip">暂无报告数据</div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>

    <div v-else class="empty-state">
      <p>点击按钮生成个性化发展方案</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps({
  studentId: {
    type: Number,
    required: true
  },
  targetJobId: {
    type: Number,
    default: null
  }
})

const loading = ref(false)
const activeTab = ref('strengths')
const planData = ref(null)

const generatePlan = async () => {
  loading.value = true
  try {
    const url = `/api/v1/personalized-plans/generate?student_id=${props.studentId}${props.targetJobId ? `&target_job_id=${props.targetJobId}` : ''}`
    const response = await fetch(url, { method: 'POST' })

    if (response.ok) {
      planData.value = await response.json()
    } else {
      ElMessage.error('生成方案失败')
    }
  } catch (error) {
    ElMessage.error('生成方案失败: ' + error.message)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  generatePlan()
})
</script>

<style scoped>
.personalized-plan {
  padding: 20px;
}

.plan-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.plan-header h2 {
  margin: 0;
}

.loading-state,
.empty-state {
  text-align: center;
  padding: 40px;
}

.empty-tip {
  text-align: center;
  color: #909399;
  padding: 40px;
}

.strengths-list,
.weaknesses-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 15px;
}

.strength-card,
.weakness-card {
  padding: 20px;
  border-radius: 8px;
  border: 1px solid #ebeef5;
}

.strength-card {
  background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
}

.weakness-card {
  background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
}

.strength-header,
.weakness-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.strength-name,
.weakness-name {
  font-size: 18px;
  font-weight: bold;
}

.strength-score,
.weakness-score {
  font-size: 32px;
  font-weight: bold;
  color: #409eff;
  margin-bottom: 10px;
}

.strength-desc,
.weakness-desc {
  color: #606266;
  margin-bottom: 15px;
}

.leverage-suggestion h5,
.improvement-suggestion h5 {
  margin: 0 0 5px 0;
  color: #303133;
  font-size: 14px;
}

.leverage-suggestion p,
.improvement-suggestion p {
  margin: 0;
  font-size: 14px;
  color: #409eff;
}

.avoid-content {
  padding: 10px;
}

.avoid-list,
.risk-list {
  margin-bottom: 20px;
}

.avoid-list h4,
.risk-list h4 {
  margin: 0 0 15px 0;
}

.avoid-tag {
  margin: 5px;
}

.risk-list ul {
  padding-left: 20px;
}

.risk-list li {
  padding: 5px 0;
  color: #f56c6c;
}

.strategy-block {
  padding: 20px;
  background: #f5f7fa;
  border-radius: 8px;
  margin-bottom: 15px;
}

.strategy-block h4 {
  margin: 0 0 10px 0;
}

.strategy-overview {
  color: #606266;
  margin-bottom: 15px;
}

.interview-tips h5,
.improvement-plans h6 {
  margin: 10px 0;
  font-size: 14px;
}

.interview-tips ul,
.improvement-plans ul {
  padding-left: 20px;
  color: #606266;
}

.improvement-plans p {
  font-size: 12px;
  color: #909399;
  margin: 5px 0;
}

.jobs-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 15px;
}

.job-card {
  padding: 15px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
}

.job-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.job-name {
  font-weight: bold;
  font-size: 16px;
}

.job-category {
  color: #909399;
  font-size: 12px;
  margin-bottom: 10px;
}

.job-reasons {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-bottom: 10px;
}

.reason-tag {
  padding: 2px 8px;
  background: #ecf5ff;
  color: #409eff;
  border-radius: 4px;
  font-size: 12px;
}

.job-highlight {
  font-size: 12px;
  color: #67c23a;
}

.report-content {
  padding: 20px;
  background: #fafafa;
  border-radius: 8px;
}

.report-content h3 {
  text-align: center;
  margin-bottom: 10px;
}

.report-meta {
  text-align: center;
  color: #909399;
  margin-bottom: 20px;
  padding-bottom: 20px;
  border-bottom: 1px solid #ebeef5;
}

.report-body pre {
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: 'Microsoft YaHei', sans-serif;
  font-size: 14px;
  line-height: 1.8;
}
</style>
