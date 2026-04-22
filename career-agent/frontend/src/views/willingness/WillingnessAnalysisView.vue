<template>
  <div class="willingness-analysis">
    <div class="analysis-header">
      <h2>就业意愿分析</h2>
      <el-button type="primary" @click="loadAnalysis">刷新分析</el-button>
    </div>

    <div v-if="loading" class="loading-state">分析中...</div>

    <div v-else-if="analysisData" class="analysis-content">
      <div class="score-overview">
        <div class="overall-score" :class="analysisData.level">
          <div class="score-value">{{ analysisData.overall_score }}</div>
          <div class="score-label">综合评分</div>
          <div class="score-level">{{ analysisData.level }}</div>
        </div>

        <div class="dimension-cards">
          <div class="dimension-card">
            <div class="card-title">求职意向强度</div>
            <div class="card-value">{{ analysisData.dimensions.intent_score }}</div>
            <div class="card-label">{{ analysisData.dimensions.intent_label }}</div>
            <el-progress :percentage="analysisData.dimensions.intent_score" :stroke-width="8" />
          </div>

          <div class="dimension-card">
            <div class="card-title">目标清晰度</div>
            <div class="card-value">{{ analysisData.dimensions.target_clarity }}</div>
            <div class="card-label">{{ analysisData.dimensions.target_clarity_label }}</div>
            <el-progress :percentage="analysisData.dimensions.target_clarity" :stroke-width="8" />
          </div>

          <div class="dimension-card">
            <div class="card-title">行动准备度</div>
            <div class="card-value">{{ analysisData.dimensions.action_readiness }}</div>
            <div class="card-label">{{ analysisData.dimensions.action_readiness_label }}</div>
            <el-progress :percentage="analysisData.dimensions.action_readiness" :stroke-width="8" />
          </div>

          <div class="dimension-card">
            <div class="card-title">竞争力认知</div>
            <div class="card-value">{{ analysisData.dimensions.competitiveness }}</div>
            <div class="card-label">{{ analysisData.dimensions.competitiveness_label }}</div>
            <el-progress :percentage="analysisData.dimensions.competitiveness" :stroke-width="8" />
          </div>
        </div>
      </div>

      <div class="radar-chart">
        <h3>四维度雷达图</h3>
        <div ref="radarChartRef" class="chart-container"></div>
      </div>

      <div class="suggestions">
        <h3>发展建议</h3>
        <ul class="suggestion-list">
          <li v-for="(suggestion, index) in analysisData.suggestions" :key="index">
            {{ suggestion }}
          </li>
        </ul>
      </div>
    </div>

    <div v-else class="empty-state">
      <p>暂无分析数据</p>
      <el-button type="primary" @click="loadAnalysis">开始分析</el-button>
    </div>

    <el-dialog v-model="surveyDialogVisible" title="就业意愿问卷" width="600px">
      <div class="survey-form">
        <p>完成问卷可获得更准确的分析结果</p>
        <el-button type="primary" @click="submitSurvey">提交问卷</el-button>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'

const props = defineProps({
  studentId: {
    type: Number,
    required: true
  }
})

const loading = ref(false)
const analysisData = ref(null)
const surveyDialogVisible = ref(false)
const radarChartRef = ref(null)
let radarChart = null

const loadAnalysis = async () => {
  loading.value = true
  try {
    const response = await fetch(`/api/v1/willingness/${props.studentId}`)
    if (response.ok) {
      analysisData.value = await response.json()
      await nextTick()
      renderRadarChart()
    } else {
      ElMessage.error('加载分析失败')
    }
  } catch (error) {
    ElMessage.error('加载分析失败: ' + error.message)
  } finally {
    loading.value = false
  }
}

const renderRadarChart = () => {
  if (!radarChartRef.value || !analysisData.value) return

  if (radarChart) {
    radarChart.dispose()
  }

  radarChart = echarts.init(radarChartRef.value)

  const option = {
    radar: {
      indicator: [
        { name: '求职意向', max: 100 },
        { name: '目标清晰度', max: 100 },
        { name: '行动准备度', max: 100 },
        { name: '竞争力认知', max: 100 }
      ],
      radius: '65%'
    },
    series: [{
      type: 'radar',
      data: [{
        value: [
          analysisData.value.dimensions.intent_score,
          analysisData.value.dimensions.target_clarity,
          analysisData.value.dimensions.action_readiness,
          analysisData.value.dimensions.competitiveness
        ],
        name: '就业意愿分析'
      }]
    }]
  }

  radarChart.setOption(option)
}

const submitSurvey = async () => {
  ElMessage.success('问卷功能开发中')
  surveyDialogVisible.value = false
}

onMounted(() => {
  loadAnalysis()
})
</script>

<style scoped>
.willingness-analysis {
  padding: 20px;
}

.analysis-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.analysis-header h2 {
  margin: 0;
}

.loading-state,
.empty-state {
  text-align: center;
  padding: 40px;
}

.score-overview {
  display: flex;
  gap: 20px;
  margin-bottom: 20px;
}

.overall-score {
  flex: 0 0 150px;
  padding: 20px;
  border-radius: 8px;
  text-align: center;
  color: #fff;
}

.overall-score.高 { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
.overall-score.中 { background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); }
.overall-score.低 { background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); }

.score-value {
  font-size: 48px;
  font-weight: bold;
}

.score-label {
  font-size: 14px;
  opacity: 0.9;
}

.score-level {
  margin-top: 10px;
  padding: 4px 12px;
  background: rgba(255,255,255,0.2);
  border-radius: 12px;
  font-size: 12px;
}

.dimension-cards {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 15px;
}

.dimension-card {
  padding: 15px;
  background: #f5f7fa;
  border-radius: 8px;
}

.card-title {
  font-size: 14px;
  color: #606266;
}

.card-value {
  font-size: 28px;
  font-weight: bold;
  color: #303133;
}

.card-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 8px;
}

.radar-chart,
.suggestions {
  background: #fff;
  padding: 20px;
  border-radius: 8px;
  margin-bottom: 20px;
}

.radar-chart h3,
.suggestions h3 {
  margin: 0 0 15px 0;
}

.chart-container {
  height: 300px;
}

.suggestion-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.suggestion-list li {
  padding: 10px 15px;
  margin-bottom: 10px;
  background: #ecf5ff;
  border-radius: 4px;
  color: #409eff;
}

.survey-form {
  text-align: center;
  padding: 20px;
}
</style>
