<template>
  <div class="job-graph-wrapper">
    <div v-if="loading" class="graph-loading">
      <div class="loading-spinner"></div>
      <span>加载岗位图谱数据...</span>
    </div>
    <div v-else-if="error" class="graph-error">
      <span class="error-icon">!</span>
      <span>{{ error }}</span>
      <el-button type="primary" @click="fetchData">重试</el-button>
    </div>
    <template v-else>
      <div class="graph-header">
        <div class="graph-stats">
          <el-tag type="info">岗位 {{ stats.job_count }}</el-tag>
          <el-tag type="info">关联 {{ stats.relation_count }}</el-tag>
          <el-tag type="info">分类 {{ stats.category_count }}</el-tag>
          <el-tag v-if="stats.company_count > 0" type="info">企业 {{ stats.company_count }}</el-tag>
          <el-tag :type="dataSource === 'milvus' ? 'warning' : dataSource === 'database' ? 'primary' : 'success'" effect="plain">
            数据来源: {{ dataSourceLabel }}
          </el-tag>
        </div>
        <div class="graph-filters">
          <el-select v-model="selectedCategory" placeholder="按分类筛选" clearable @change="handleCategoryChange">
            <el-option v-for="cat in categories" :key="cat" :label="cat" :value="cat" />
          </el-select>
          <el-select v-model="selectedRelationType" placeholder="关系类型" clearable>
            <el-option label="全部关系" value="" />
            <el-option label="技能关联" value="技能关联" />
            <el-option label="同类型" value="同类型" />
            <el-option label="同企业" value="同企业" />
            <el-option label="垂直晋升" value="垂直晋升" />
            <el-option label="换岗路径" value="换岗路径" />
          </el-select>
          <el-select v-model="densityMode" placeholder="密度模式">
            <el-option label="自动" value="auto" />
            <el-option label="全部显示" value="all" />
            <el-option label="精简模式" value="compact" />
          </el-select>
          <el-switch v-model="focusMode" active-text="聚焦模式" inactive-text="" />
        </div>
      </div>
      <div class="relation-legend">
        <span class="legend-title">关系类型：</span>
        <span class="legend-item"><span class="legend-dot skill"></span>技能关联</span>
        <span class="legend-item"><span class="legend-dot same-type"></span>同类型</span>
        <span v-if="showCompanyRelation" class="legend-item"><span class="legend-dot same-company"></span>同企业</span>
        <span class="legend-item"><span class="legend-dot promotion"></span>垂直晋升</span>
        <span class="legend-item"><span class="legend-dot transfer"></span>换岗路径</span>
      </div>
      <GraphView :graph="graphData" :focus-id="focusNodeId" :focus-mode="focusMode" @node-click="handleNodeClick" />
    </template>

    <el-dialog v-model="detailVisible" :title="selectedNode?.label || '岗位详情'" width="560px">
      <div v-if="selectedNode" class="job-detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="岗位名称">{{ selectedNode.label }}</el-descriptions-item>
          <el-descriptions-item label="分类">{{ selectedNode.category }}</el-descriptions-item>
          <el-descriptions-item label="企业">{{ selectedNode.company_name || '未知企业' }}</el-descriptions-item>
          <el-descriptions-item label="薪资范围">{{ selectedNode.salary_range }}</el-descriptions-item>
          <el-descriptions-item label="工作地点">{{ selectedNode.location }}</el-descriptions-item>
        </el-descriptions>
        <div v-if="selectedNode.description" class="job-desc">
          <div class="desc-label">岗位描述</div>
          <div class="desc-content">{{ selectedNode.description }}</div>
        </div>
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
        <el-button type="primary" @click="handleViewDetails">查看详情</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import GraphView from "./GraphView.vue";
import { graphApi } from "@/api";

const props = defineProps({
  enterpriseId: {
    type: Number,
    default: null
  }
});

const router = useRouter();

const loading = ref(false);
const error = ref("");
const rawData = ref(null);
const selectedCategory = ref("");
const selectedRelationType = ref("");
const densityMode = ref("auto");
const focusMode = ref(false);
const focusNodeId = ref(null);
const detailVisible = ref(false);
const selectedNode = ref(null);

const stats = computed(() => rawData.value?.stats || {
  job_count: 0,
  relation_count: 0,
  category_count: 0,
  company_count: 0
});
const dataSource = computed(() => rawData.value?.source || "unknown");
const dataSourceLabel = computed(() => {
  if (dataSource.value === "milvus") return "Milvus";
  if (dataSource.value === "database") return "数据库";
  if (dataSource.value === "neo4j") return "Neo4j";
  return "未知";
});

const showCompanyRelation = computed(() => {
  return (rawData.value?.edges || []).some(e => e.relation_type === "同企业");
});

const categories = computed(() => {
  const cats = new Set(rawData.value?.nodes?.map((n) => n.category) || []);
  return Array.from(cats).filter(Boolean).sort();
});

const companies = computed(() => {
  const corps = new Set(rawData.value?.nodes?.map((n) => n.company_name).filter(Boolean) || []);
  return Array.from(corps).sort();
});

const companyColors = computed(() => {
  const colors = {};
  const colorPalette = [
    "#5470c6", "#91cc75", "#fac858", "#ee6666", "#73c0de",
    "#3ba272", "#fc8452", "#9a60b4", "#ea7ccc", "#5470c6"
  ];
  companies.value.forEach((company, index) => {
    colors[company] = colorPalette[index % colorPalette.length];
  });
  return colors;
});

const graphData = computed(() => {
  const nodes = (rawData.value?.nodes || [])
    .filter((n) => !selectedCategory.value || n.category === selectedCategory.value)
    .map((n) => ({
      id: n.id,
      name: n.label,
      category: n.category,
      company_name: n.company_name,
      symbolColor: companyColors.value[n.company_name] || "#999"
    }));

  const nodeIds = new Set(nodes.map((n) => n.id));
  let links = (rawData.value?.edges || [])
    .filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target))
    .map((e) => ({
      source: e.source,
      target: e.target,
      relation_type: e.relation_type,
      relation_label: e.relation_label || e.relation_type,
      reason: e.shared_skill || e.company_name || e.relation_type,
      weight: e.weight || 0.5,
    }));

  if (selectedRelationType.value) {
    links = links.filter(l => l.relation_type === selectedRelationType.value);
  }

  if (densityMode.value === "compact" || (densityMode.value === "auto" && nodes.length > 60)) {
    links = filterLinksByDensity(links, focusNodeId.value, 5);
  }

  if (focusMode.value) {
    links = links.map(l => ({
      ...l,
      visible: focusNodeId.value ? (l.source === focusNodeId.value || l.target === focusNodeId.value) : false
    }));
  } else {
    links = links.map(l => ({
      ...l,
      visible: true
    }));
  }

  return { nodes, links };
});

function filterLinksByDensity(links, focusId, maxEdgesPerNode) {
  const nodeEdgeCount = new Map();
  const result = [];
  const sorted = [...links].sort((a, b) => (b.weight || 0) - (a.weight || 0));

  for (const link of sorted) {
    const src = link.source, tgt = link.target;
    const srcCount = nodeEdgeCount.get(src) || 0;
    const tgtCount = nodeEdgeCount.get(tgt) || 0;
    const isFocusRelated = focusId && (src === focusId || tgt === focusId);
    const canAdd = isFocusRelated || (srcCount < maxEdgesPerNode && tgtCount < maxEdgesPerNode);

    if (canAdd) {
      result.push(link);
      nodeEdgeCount.set(src, srcCount + 1);
      nodeEdgeCount.set(tgt, tgtCount + 1);
    }
  }
  return result;
}

const fetchData = async () => {
  loading.value = true;
  error.value = "";
  try {
    const params = { limit: 150 };
    if (props.enterpriseId) {
      params.enterprise_id = props.enterpriseId;
    }
    const res = await graphApi.getJobGraph(params);
    if (res?.data) {
      rawData.value = res.data;
      ElMessage.success(`已加载 ${res.data.stats?.job_count || 0} 个岗位的图谱数据`);
    } else {
      error.value = "图谱数据为空";
    }
  } catch (e) {
    error.value = e?.message || "获取图谱数据失败";
    console.error("Job graph fetch error:", e);
  } finally {
    loading.value = false;
  }
};

const handleCategoryChange = () => {
  focusNodeId.value = null;
};

const handleNodeClick = (params) => {
  if (params?.dataType === "node") {
    const nodeData = params.data || {};
    const rawNode = rawData.value?.nodes?.find((n) => n.id === nodeData.id);
    selectedNode.value = rawNode || nodeData;
    detailVisible.value = true;
    focusNodeId.value = nodeData.id;
  }
};

const handleViewDetails = () => {
  detailVisible.value = false;
  const nodeId = Number(selectedNode.value?.id);
  if (Number.isFinite(nodeId) && nodeId > 0) {
    router.push({ path: "/jobs/detail", query: { id: nodeId } });
    return;
  }
  ElMessage.info("该节点为岗位路径节点，可在岗位卡片中查看路径详情");
};

onMounted(fetchData);

watch(() => props.enterpriseId, () => {
  selectedCategory.value = "";
  focusNodeId.value = null;
  fetchData();
});

watch(selectedCategory, () => {
  focusNodeId.value = null;
});
</script>

<style scoped>
.job-graph-wrapper {
  width: 100%;
}

.graph-loading,
.graph-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  height: 400px;
  color: #64748b;
}

.graph-error {
  color: #ef4444;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #e2e8f0;
  border-top-color: #5470c6;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error-icon {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: #fef2f2;
  color: #ef4444;
  font-size: 20px;
  font-weight: bold;
  display: flex;
  align-items: center;
  justify-content: center;
}

.graph-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  flex-wrap: wrap;
  gap: 12px;
}

.graph-stats {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.graph-filters {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.graph-filters .el-select {
  width: 130px;
}

.graph-filters .el-switch {
  --el-switch-off-color: #dcdfe6;
  height: 32px;
  line-height: 32px;
}

.relation-legend {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
  padding: 8px 12px;
  background: #f8fafc;
  border-radius: 8px;
  font-size: 13px;
  color: #64748b;
}

.legend-title {
  font-weight: 500;
  color: #475569;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.legend-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
}

.legend-dot.skill {
  background: #5470c6;
}

.legend-dot.same-type {
  background: #91cc75;
}

.legend-dot.same-company {
  background: #fac858;
}

.legend-dot.promotion {
  background: #22c55e;
}

.legend-dot.transfer {
  background: #f97316;
}

.job-detail {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.job-desc {
  margin-top: 8px;
}

.desc-label {
  font-size: 14px;
  font-weight: 600;
  color: #374151;
  margin-bottom: 8px;
}

.desc-content {
  font-size: 14px;
  color: #6b7280;
  line-height: 1.8;
}
</style>
