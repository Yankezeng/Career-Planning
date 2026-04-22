<template>
  <div class="action-plan">
    <div class="plan-header">
      <h2>行动计划</h2>
      <div class="header-actions">
        <el-select v-model="timeline" placeholder="时间范围" @change="generatePlan">
          <el-option label="1个月" value="1 month" />
          <el-option label="3个月" value="3 months" />
          <el-option label="6个月" value="6 months" />
          <el-option label="12个月" value="12 months" />
        </el-select>
        <el-button type="primary" @click="generatePlan">生成计划</el-button>
      </div>
    </div>

    <div v-if="loading" class="loading-state">生成中...</div>

    <div v-else-if="planData" class="plan-content">
      <div class="plan-overview">
        <div class="overview-card">
          <div class="overview-title">目标岗位</div>
          <div class="overview-value">{{ planData.target_job_name }}</div>
        </div>
        <div class="overview-card">
          <div class="overview-title">时间范围</div>
          <div class="overview-value">{{ planData.timeline }}</div>
        </div>
        <div class="overview-card">
          <div class="overview-title">计划天数</div>
          <div class="overview-value">{{ planData.days }}天</div>
        </div>
        <div class="overview-card">
          <div class="overview-title">完成率</div>
          <div class="overview-value">{{ progressStats.completion_rate || 0 }}%</div>
        </div>
      </div>

      <el-tabs v-model="activeTab" type="border-card">
        <el-tab-pane label="日计划" name="daily">
          <div class="daily-list">
            <div v-for="day in planData.daily_plans" :key="day.day" class="daily-item">
              <div class="day-header">
                <span class="day-number">第{{ day.day }}天</span>
                <span class="day-date">{{ day.date }}</span>
              </div>
              <div class="day-content">
                <div class="skill-tag">{{ day.skill }}</div>
                <div v-for="(task, idx) in day.tasks" :key="idx" class="task-item">
                  <el-checkbox v-model="day.completed" @change="updateProgress(day)">{{ task }}</el-checkbox>
                </div>
                <div class="duration">预计时长: {{ day.duration_minutes }}分钟</div>
              </div>
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="周计划" name="weekly">
          <div class="weekly-list">
            <el-timeline>
              <el-timeline-item v-for="week in planData.weekly_plans" :key="week.week" :timestamp="week.date_range" placement="top">
                <el-card>
                  <h4>第{{ week.week }}周 - {{ week.focus_skill }}</h4>
                  <div class="week-goals">
                    <div v-for="(goal, idx) in week.goals" :key="idx" class="goal-item">
                      {{ idx + 1 }}. {{ goal }}
                    </div>
                  </div>
                  <div v-if="week.milestone" class="milestone-badge">
                    <el-tag type="warning">{{ week.milestone }}</el-tag>
                  </div>
                </el-card>
              </el-timeline-item>
            </el-timeline>
          </div>
        </el-tab-pane>

        <el-tab-pane label="月计划" name="monthly">
          <div class="monthly-list">
            <div v-for="month in planData.monthly_plans" :key="month.month" class="month-card">
              <div class="month-header">
                <span class="month-number">第{{ month.month }}月</span>
                <span class="month-date">{{ month.date_range }}</span>
              </div>
              <div class="month-content">
                <h5>重点目标</h5>
                <ul>
                  <li v-for="(goal, idx) in month.primary_goals" :key="idx">{{ goal }}</li>
                </ul>
                <div v-if="month.certification_plan" class="cert-plan">
                  <el-tag type="success">{{ month.certification_plan.name }}</el-tag>
                  <span>预计 {{ month.certification_plan.target_month }} 月后报考</span>
                </div>
              </div>
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="里程碑" name="milestones">
          <div class="milestones-list">
            <el-steps :active="currentMilestoneIndex" align-center>
              <el-step v-for="milestone in planData.milestones" :key="milestone.id" :title="milestone.title" :description="milestone.date" />
            </el-steps>
          </div>
        </el-tab-pane>

        <el-tab-pane label="学习资源" name="resources">
          <div class="resources-grid">
            <div class="resource-section">
              <h4>推荐课程</h4>
              <div v-for="(course, idx) in planData.resources.courses" :key="idx" class="resource-item">
                <el-tag>{{ course.platform }}</el-tag>
                <span>{{ course.name }}</span>
                <el-tag :type="course.level === '入门' ? 'success' : 'warning'">{{ course.level }}</el-tag>
              </div>
            </div>
            <div class="resource-section">
              <h4>推荐书籍</h4>
              <div v-for="(book, idx) in planData.resources.books" :key="idx" class="resource-item">
                <span class="book-name">{{ book.name }}</span>
                <span class="book-author">{{ book.author }}</span>
              </div>
            </div>
            <div class="resource-section">
              <h4>实战项目</h4>
              <div v-for="(project, idx) in planData.resources.projects" :key="idx" class="resource-item">
                <el-tag type="primary">{{ project.name }}</el-tag>
                <p class="project-desc">{{ project.description }}</p>
              </div>
            </div>
            <div class="resource-section">
              <h4>社区论坛</h4>
              <div v-for="(community, idx) in planData.resources.communities" :key="idx" class="resource-item">
                <el-tag type="info">{{ community.name }}</el-tag>
                <span>{{ community.description }}</span>
              </div>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>

    <div v-else class="empty-state">
      <p>请选择目标岗位和时间范围生成行动计划</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
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
const activeTab = ref('daily')
const timeline = ref('3 months')
const planData = ref(null)
const progressStats = ref({})

const currentMilestoneIndex = computed(() => {
  if (!planData.value || !planData.value.milestones) return 0
  const completedCount = planData.value.milestones.filter(m => m.status === 'completed').length
  return completedCount
})

const generatePlan = async () => {
  if (!props.targetJobId) {
    ElMessage.warning('请先选择目标岗位')
    return
  }

  loading.value = true
  try {
    const response = await fetch(
      `/api/v1/action-plans/generate?student_id=${props.studentId}&target_job_id=${props.targetJobId}&timeline=${timeline.value}`,
      { method: 'POST' }
    )

    if (response.ok) {
      planData.value = await response.json()
      await loadProgressStats()
    } else {
      ElMessage.error('生成计划失败')
    }
  } catch (error) {
    ElMessage.error('生成计划失败: ' + error.message)
  } finally {
    loading.value = false
  }
}

const loadProgressStats = async () => {
  if (!planData.value || !planData.value.id) return

  try {
    const response = await fetch(`/api/v1/action-plans/${planData.value.id}/stats`)
    if (response.ok) {
      progressStats.value = await response.json()
    }
  } catch (error) {
    console.error('Failed to load progress stats:', error)
  }
}

const updateProgress = async (day) => {
  if (!planData.value || !planData.value.id) return

  const taskId = `day_${day.day}`
  try {
    await fetch(
      `/api/v1/action-plans/${planData.value.id}/progress?task_id=${taskId}&completed=${day.completed || false}`,
      { method: 'PUT' }
    )
    await loadProgressStats()
  } catch (error) {
    console.error('Failed to update progress:', error)
  }
}

onMounted(() => {
  if (props.targetJobId) {
    generatePlan()
  }
})
</script>

<style scoped>
.action-plan {
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

.header-actions {
  display: flex;
  gap: 10px;
}

.loading-state,
.empty-state {
  text-align: center;
  padding: 40px;
}

.plan-overview {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 15px;
  margin-bottom: 20px;
}

.overview-card {
  padding: 15px;
  background: #f5f7fa;
  border-radius: 8px;
  text-align: center;
}

.overview-title {
  font-size: 14px;
  color: #909399;
}

.overview-value {
  font-size: 24px;
  font-weight: bold;
  color: #303133;
  margin-top: 5px;
}

.daily-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 15px;
}

.daily-item {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 15px;
}

.day-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
  padding-bottom: 10px;
  border-bottom: 1px solid #ebeef5;
}

.day-number {
  font-weight: bold;
  color: #409eff;
}

.day-date {
  color: #909399;
  font-size: 12px;
}

.day-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.skill-tag {
  display: inline-block;
  padding: 2px 8px;
  background: #ecf5ff;
  color: #409eff;
  border-radius: 4px;
  font-size: 12px;
}

.task-item {
  padding: 5px 0;
}

.duration {
  font-size: 12px;
  color: #909399;
  margin-top: 5px;
}

.weekly-list {
  padding: 10px;
}

.week-goals {
  margin: 10px 0;
}

.goal-item {
  padding: 5px 0;
  color: #606266;
}

.milestone-badge {
  margin-top: 10px;
}

.monthly-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 15px;
}

.month-card {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 15px;
}

.month-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 15px;
  padding-bottom: 10px;
  border-bottom: 1px solid #ebeef5;
}

.month-number {
  font-weight: bold;
  color: #409eff;
}

.month-content h5 {
  margin: 0 0 10px 0;
  color: #303133;
}

.month-content ul {
  padding-left: 20px;
  margin: 10px 0;
}

.month-content li {
  padding: 3px 0;
  color: #606266;
}

.cert-plan {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid #ebeef5;
  font-size: 12px;
  color: #909399;
}

.milestones-list {
  padding: 30px 0;
}

.resources-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
}

.resource-section {
  padding: 15px;
  background: #f5f7fa;
  border-radius: 8px;
}

.resource-section h4 {
  margin: 0 0 15px 0;
  color: #303133;
}

.resource-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid #ebeef5;
}

.resource-item:last-child {
  border-bottom: none;
}

.book-name {
  font-weight: 500;
}

.book-author {
  color: #909399;
  font-size: 12px;
}

.project-desc {
  margin: 5px 0 0 0;
  font-size: 12px;
  color: #909399;
}
</style>
