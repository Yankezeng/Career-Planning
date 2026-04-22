<template>
  <div class="capability-analysis">
    <div class="analysis-header">
      <h2>岗位能力拆解</h2>
      <el-select v-model="selectedJobId" placeholder="选择岗位" @change="loadCapabilities">
        <el-option v-for="job in jobs" :key="job.id" :label="job.name" :value="job.id" />
      </el-select>
    </div>

    <div v-if="loading" class="loading-state">加载中...</div>

    <div v-else-if="capabilityData" class="capability-content">
      <div class="capability-overview">
        <h3>{{ capabilityData.job_name }}</h3>
        <div class="difficulty-badge" :class="capabilityData.difficulty_level">
          难度: {{ capabilityData.difficulty_level }}
        </div>
      </div>

      <el-tabs v-model="activeTab" type="border-card">
        <el-tab-pane label="硬技能" name="hard-skills">
          <div class="skills-grid">
            <div v-for="(skills, category) in capabilityData.hard_skills" :key="category" class="skill-category">
              <h4>{{ category }}</h4>
              <div class="skill-tags">
                <el-tag v-for="skill in skills" :key="skill" type="primary">{{ skill }}</el-tag>
              </div>
            </div>
          </div>
          <div v-if="!capabilityData.hard_skills || Object.keys(capabilityData.hard_skills).length === 0" class="empty-tip">
            暂无硬技能数据
          </div>
        </el-tab-pane>

        <el-tab-pane label="软技能" name="soft-skills">
          <div class="skills-list">
            <div v-for="(skills, skill) in capabilityData.soft_skills" :key="skill" class="soft-skill-item">
              <span class="skill-name">{{ skill }}</span>
              <el-rate v-model="skillValues[skill]" disabled />
            </div>
          </div>
          <div v-if="!capabilityData.soft_skills || Object.keys(capabilityData.soft_skills).length === 0" class="empty-tip">
            暂无软技能数据
          </div>
        </el-tab-pane>

        <el-tab-pane label="经验要求" name="experience">
          <div class="experience-info">
            <div class="info-item">
              <span class="label">工作年限:</span>
              <span class="value">{{ capabilityData.experience_requirements.years_required || 0 }} 年</span>
            </div>
            <div class="info-item">
              <span class="label">项目数量:</span>
              <span class="value">{{ capabilityData.experience_requirements.projects_required }}</span>
            </div>
            <div class="info-item">
              <span class="label">行业经验:</span>
              <span class="value">{{ capabilityData.experience_requirements.industry_experience }}</span>
            </div>
          </div>
          <p class="experience-desc">{{ capabilityData.experience_requirements.description }}</p>
        </el-tab-pane>

        <el-tab-pane label="认证要求" name="certifications">
          <div v-if="capabilityData.certification_requirements && capabilityData.certification_requirements.length" class="cert-list">
            <div v-for="cert in capabilityData.certification_requirements" :key="cert.name" class="cert-item">
              <el-tag :type="cert.priority === '优先' ? 'danger' : 'warning'">{{ cert.priority }}</el-tag>
              <span class="cert-name">{{ cert.name }}</span>
            </div>
          </div>
          <div v-else class="empty-tip">暂无认证要求</div>
        </el-tab-pane>

        <el-tab-pane label="学习路径" name="learning-path">
          <div class="learning-path">
            <el-timeline>
              <el-timeline-item v-for="(suggestion, index) in capabilityData.learning_suggestions" :key="index" :timestamp="suggestion.category" placement="top">
                <el-card>
                  <h4>{{ suggestion.skill }}</h4>
                  <p>{{ suggestion.suggestion }}</p>
                  <div class="priority-badge" :class="suggestion.priority">优先级: {{ suggestion.priority }}</div>
                </el-card>
              </el-timeline-item>
            </el-timeline>
          </div>
        </el-tab-pane>
      </el-tabs>

      <div v-if="capabilityData.capability_gap" class="gap-analysis">
        <h3>能力差距分析</h3>
        <el-progress :percentage="capabilityData.capability_gap.match_percentage" :stroke-width="20">
          <span slot="format">{{ capabilityData.capability_gap.match_percentage }}% 匹配</span>
        </el-progress>
        <p class="gap-assessment">{{ capabilityData.capability_gap.overall_assessment }}</p>
      </div>
    </div>

    <div v-else class="empty-state">
      <p>请选择一个岗位查看能力拆解</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const activeTab = ref('hard-skills')
const selectedJobId = ref(null)
const jobs = ref([])
const capabilityData = ref(null)
const skillValues = ref({})

const loadJobs = async () => {
  try {
    const response = await fetch('/api/v1/jobs?limit=100')
    if (response.ok) {
      const data = await response.json()
      jobs.value = data.items || []
    }
  } catch (error) {
    console.error('Failed to load jobs:', error)
  }
}

const loadCapabilities = async () => {
  if (!selectedJobId.value) return

  loading.value = true
  try {
    const response = await fetch(`/api/v1/jobs/${selectedJobId.value}/capabilities`)
    if (response.ok) {
      capabilityData.value = await response.json()
      initSkillValues()
    } else {
      ElMessage.error('加载能力数据失败')
    }
  } catch (error) {
    ElMessage.error('加载能力数据失败: ' + error.message)
  } finally {
    loading.value = false
  }
}

const initSkillValues = () => {
  if (capabilityData.value && capabilityData.value.soft_skills) {
    const values = {}
    for (const skill in capabilityData.value.soft_skills) {
      values[skill] = 3
    }
    skillValues.value = values
  }
}

onMounted(() => {
  loadJobs()
})
</script>

<style scoped>
.capability-analysis {
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

.capability-overview {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.capability-overview h3 {
  margin: 0;
}

.difficulty-badge {
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  color: #fff;
}

.difficulty-badge.入门 { background: #67c23a; }
.difficulty-badge.中级 { background: #e6a23c; }
.difficulty-badge.高级 { background: #f56c6c; }

.skills-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 20px;
}

.skill-category h4 {
  margin: 0 0 10px 0;
  color: #409eff;
}

.skill-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.skills-list {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.soft-skill-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px;
  background: #f5f7fa;
  border-radius: 4px;
}

.skill-name {
  font-weight: 500;
}

.experience-info {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
  margin-bottom: 20px;
}

.info-item {
  text-align: center;
}

.info-item .label {
  display: block;
  color: #909399;
  font-size: 14px;
}

.info-item .value {
  display: block;
  font-size: 24px;
  font-weight: bold;
  color: #303133;
}

.experience-desc {
  color: #606266;
  text-align: center;
}

.cert-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.cert-item {
  display: flex;
  align-items: center;
  gap: 10px;
}

.cert-name {
  font-weight: 500;
}

.empty-tip {
  text-align: center;
  color: #909399;
  padding: 40px;
}

.learning-path {
  padding: 10px;
}

.priority-badge {
  display: inline-block;
  margin-top: 8px;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.priority-badge.高 { background: #f56c6c; color: #fff; }
.priority-badge.中 { background: #e6a23c; color: #fff; }
.priority-badge.低 { background: #67c23a; color: #fff; }

.gap-analysis {
  margin-top: 20px;
  padding: 20px;
  background: #f5f7fa;
  border-radius: 8px;
}

.gap-analysis h3 {
  margin: 0 0 15px 0;
}

.gap-assessment {
  margin-top: 10px;
  color: #606266;
}
</style>
