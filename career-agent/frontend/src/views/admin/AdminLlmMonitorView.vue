<template>
  <div class="page-shell llm-monitor-page">
    <section class="head-row">
      <div>
        <h1>模型监控</h1>
        <p>监控系统内记录的大模型调用状态、用量和异常趋势。</p>
      </div>
      <div class="head-actions">
        <el-select v-model="trendMode" class="mode-select" @change="loadTrend">
          <el-option label="近 24 小时" value="24h" />
          <el-option label="近 7 天" value="7d" />
        </el-select>
        <el-button :loading="pinging" type="primary" @click="handlePing">立即检测连接</el-button>
        <el-button :loading="loading" @click="refreshAll">刷新</el-button>
      </div>
    </section>

    <el-alert
      v-if="overview.note"
      :title="overview.note"
      type="info"
      show-icon
      :closable="false"
      class="note-alert"
    />

    <section class="metric-grid">
      <div class="metric-card" v-for="card in overviewCards" :key="card.label">
        <div class="metric-label">{{ card.label }}</div>
        <div class="metric-value">{{ card.value }}</div>
      </div>
    </section>

    <section v-if="modelCards.length" class="model-grid">
      <div class="model-card" v-for="item in modelCards" :key="`${item.provider}-${item.model_name}`">
        <div class="model-head">
          <div class="model-title">{{ item.label || item.model_name }}</div>
          <span :class="['model-status', `status-${item.connection_status || 'degraded'}`]">{{ item.connection_status || "degraded" }}</span>
        </div>
        <div class="model-meta">{{ item.provider || "-" }} · {{ item.model_name || "-" }}</div>
        <div class="model-kv-row">
          <span>今日请求</span>
          <strong>{{ item.today_request_count || 0 }}</strong>
        </div>
        <div class="model-kv-row">
          <span>成功率</span>
          <strong>{{ Number(item.success_rate || 0).toFixed(2) }}%</strong>
        </div>
        <div class="model-kv-row">
          <span>平均耗时</span>
          <strong>{{ Number(item.avg_latency_ms || 0).toFixed(2) }} ms</strong>
        </div>
        <div class="model-kv-row">
          <span>今日 Tokens</span>
          <strong>{{ item.today_total_tokens || 0 }}</strong>
        </div>
        <div class="model-foot">
          <div>最近成功：{{ item.last_success_at || "-" }}</div>
          <div>最近失败：{{ item.last_error_at || "-" }}</div>
        </div>
      </div>
    </section>

    <section class="chart-grid">
      <el-card shadow="never">
        <template #header>请求次数趋势</template>
        <AnalysisChart :option="requestChartOption" height="280px" />
      </el-card>
      <el-card shadow="never">
        <template #header>Token 用量趋势</template>
        <AnalysisChart :option="tokenChartOption" height="280px" />
      </el-card>
      <el-card shadow="never">
        <template #header>失败次数趋势</template>
        <AnalysisChart :option="failedChartOption" height="280px" />
      </el-card>
      <el-card shadow="never">
        <template #header>平均耗时趋势</template>
        <AnalysisChart :option="latencyChartOption" height="280px" />
      </el-card>
    </section>

    <section class="table-grid">
      <el-card shadow="never">
        <template #header>最近错误</template>
        <el-table :data="recentErrors" height="260">
          <el-table-column prop="created_at" label="时间" min-width="150" />
          <el-table-column prop="scene" label="场景" min-width="120" />
          <el-table-column prop="status" label="状态" width="90" />
          <el-table-column label="Token" width="100">
            <template #default="{ row }">{{ row.total_tokens || 0 }}</template>
          </el-table-column>
          <el-table-column label="耗时(ms)" width="110">
            <template #default="{ row }">{{ Number(row.latency_ms || 0).toFixed(2) }}</template>
          </el-table-column>
          <el-table-column prop="error_message" label="错误信息" min-width="260" show-overflow-tooltip />
        </el-table>
      </el-card>

      <el-card shadow="never">
        <template #header>最近调用日志</template>
        <el-table :data="logs" height="320">
          <el-table-column prop="created_at" label="时间" min-width="150" />
          <el-table-column prop="scene" label="场景" min-width="120" />
          <el-table-column prop="status" label="状态" width="90" />
          <el-table-column label="Token" width="100">
            <template #default="{ row }">{{ row.total_tokens || 0 }}</template>
          </el-table-column>
          <el-table-column label="耗时(ms)" width="110">
            <template #default="{ row }">{{ Number(row.latency_ms || 0).toFixed(2) }}</template>
          </el-table-column>
          <el-table-column prop="provider" label="Provider" width="120" />
          <el-table-column prop="model_name" label="Model" min-width="140" />
          <el-table-column prop="error_message" label="错误信息" min-width="240" show-overflow-tooltip />
        </el-table>
      </el-card>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { adminApi } from "@/api";
import AnalysisChart from "@/components/AnalysisChart.vue";

const loading = ref(false);
const pinging = ref(false);
const trendMode = ref("24h");
const overview = reactive({
  provider: "-",
  model_name: "-",
  api_base_url: "-",
  connection_status: "unknown",
  last_success_at: "",
  last_error_at: "",
  last_error_message: "",
  today_request_count: 0,
  today_success_count: 0,
  today_failed_count: 0,
  today_total_tokens: 0,
  avg_latency_ms: 0,
  success_rate: 0,
  models: [],
  note: "",
});
const trend = reactive({ labels: [], request_counts: [], total_tokens: [], failed_counts: [], avg_latency_ms: [], models: [] });
const logs = ref([]);

const overviewCards = computed(() => [
  { label: "Provider", value: overview.provider || "-" },
  { label: "Model", value: overview.model_name || "-" },
  { label: "连接状态", value: overview.connection_status || "unknown" },
  { label: "最近成功时间", value: overview.last_success_at || "-" },
  { label: "最近失败时间", value: overview.last_error_at || "-" },
  { label: "平均耗时", value: `${Number(overview.avg_latency_ms || 0).toFixed(2)} ms` },
  { label: "今日请求数", value: overview.today_request_count || 0 },
  { label: "今日总 Tokens", value: overview.today_total_tokens || 0 },
  { label: "成功率", value: `${Number(overview.success_rate || 0).toFixed(2)}%` },
  { label: "监控模型数", value: Array.isArray(overview.models) ? overview.models.length : 0 },
]);

const modelCards = computed(() => (Array.isArray(overview.models) ? overview.models : []));
const modelPalette = ["#2563eb", "#0ea5e9", "#8b5cf6", "#10b981", "#f59e0b", "#ef4444"];

const buildLineOption = (title, totalSeries, key) => {
  const modelSeries = (trend.models || []).map((item, index) => {
    const color = modelPalette[index % modelPalette.length];
    return {
      name: item.label || item.model_name || `模型${index + 1}`,
      type: "line",
      smooth: true,
      data: item[key] || [],
      lineStyle: { color, width: 2 },
      itemStyle: { color },
      areaStyle: { color: `${color}1A` },
    };
  });

  const totalLine = {
    name: "总计",
    type: "line",
    smooth: true,
    data: totalSeries || [],
    lineStyle: { color: "#334155", width: 2, type: "dashed" },
    itemStyle: { color: "#334155" },
  };

  const series = modelSeries.length ? [totalLine, ...modelSeries] : [totalLine];

  return {
  tooltip: { trigger: "axis" },
  legend: { top: 0 },
  grid: { left: 40, right: 16, top: 30, bottom: 30 },
  xAxis: { type: "category", data: trend.labels || [] },
  yAxis: { type: "value", name: title },
  series,
};
};

const requestChartOption = computed(() => buildLineOption("请求", trend.request_counts || [], "request_counts"));
const tokenChartOption = computed(() => buildLineOption("Token", trend.total_tokens || [], "total_tokens"));
const failedChartOption = computed(() => buildLineOption("失败", trend.failed_counts || [], "failed_counts"));
const latencyChartOption = computed(() => buildLineOption("ms", trend.avg_latency_ms || [], "avg_latency_ms"));

const recentErrors = computed(() => (logs.value || []).filter((item) => item.status === "failed").slice(0, 8));

const loadOverview = async () => {
  const res = await adminApi.llmOverview();
  Object.assign(overview, { ...res?.data, models: res?.data?.models || [] });
};

const loadTrend = async () => {
  const res = await adminApi.llmUsageTrend(trendMode.value);
  Object.assign(trend, {
    labels: res?.data?.labels || [],
    request_counts: res?.data?.request_counts || [],
    total_tokens: res?.data?.total_tokens || [],
    failed_counts: res?.data?.failed_counts || [],
    avg_latency_ms: res?.data?.avg_latency_ms || [],
    models: res?.data?.models || [],
  });
};

const loadLogs = async () => {
  const res = await adminApi.llmLogs({ limit: 30 });
  logs.value = res?.data?.items || [];
};

const refreshAll = async () => {
  loading.value = true;
  try {
    await Promise.all([loadOverview(), loadTrend(), loadLogs()]);
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || "加载模型监控数据失败");
  } finally {
    loading.value = false;
  }
};

const handlePing = async () => {
  pinging.value = true;
  try {
    const res = await adminApi.llmPing();
    const status = res?.data?.connection_status || "degraded";
    if (status === "online") ElMessage.success("连接检测成功");
    else ElMessage.warning(res?.data?.error_message || "连接检测完成，状态异常");
    await refreshAll();
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || "连接检测失败");
  } finally {
    pinging.value = false;
  }
};

onMounted(async () => {
  await refreshAll();
});
</script>

<style scoped>
.llm-monitor-page {
  display: grid;
  gap: 16px;
}

.head-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.head-row h1 {
  margin: 0;
  font-size: 28px;
  color: #0f172a;
}

.head-row p {
  margin: 8px 0 0;
  color: #64748b;
}

.head-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.mode-select {
  width: 140px;
}

.note-alert {
  margin-top: -4px;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.metric-card {
  border: 1px solid #dbe4f1;
  border-radius: 14px;
  background: #fff;
  padding: 14px;
}

.metric-label {
  color: #64748b;
  font-size: 12px;
}

.metric-value {
  margin-top: 6px;
  color: #0f172a;
  font-size: 18px;
  font-weight: 700;
  line-height: 1.4;
  word-break: break-word;
}

.chart-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.model-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.model-card {
  border: 1px solid #dbe4f1;
  border-radius: 14px;
  background: #fff;
  padding: 14px;
  display: grid;
  gap: 8px;
}

.model-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.model-title {
  color: #0f172a;
  font-size: 16px;
  font-weight: 700;
}

.model-status {
  min-height: 24px;
  padding: 0 8px;
  border-radius: 999px;
  font-size: 12px;
  display: inline-flex;
  align-items: center;
  font-weight: 700;
}

.status-online {
  background: #dcfce7;
  color: #166534;
}

.status-degraded {
  background: #fef3c7;
  color: #92400e;
}

.status-offline {
  background: #fee2e2;
  color: #991b1b;
}

.model-meta {
  color: #64748b;
  font-size: 12px;
}

.model-kv-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #334155;
  font-size: 13px;
}

.model-kv-row strong {
  color: #0f172a;
}

.model-foot {
  border-top: 1px solid #e2e8f0;
  padding-top: 8px;
  color: #64748b;
  font-size: 12px;
  display: grid;
  gap: 4px;
}

.table-grid {
  display: grid;
  gap: 12px;
}

@media (max-width: 960px) {
  .metric-grid,
  .model-grid,
  .chart-grid {
    grid-template-columns: 1fr;
  }

  .head-row {
    flex-direction: column;
  }
}
</style>
