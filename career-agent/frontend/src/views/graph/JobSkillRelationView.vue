<template>
  <div class="page-shell">
    <PageHeader title="岗位技能关联页" description="展示岗位关联关系中的技能、课程与证书建议。" />
    <SectionCard>
      <el-select v-model="jobId" style="width: 260px" @change="load">
        <el-option v-for="item in jobs" :key="item.id" :label="item.name" :value="item.id" />
      </el-select>
    </SectionCard>
    <SectionCard title="关联关系明细">
      <el-table :data="relations">
        <el-table-column prop="relation_type" label="关系类型" width="120" />
        <el-table-column prop="reason" label="说明" min-width="220" />
        <el-table-column label="相关技能" min-width="180">
          <template #default="{ row }">
            <div class="tag-list"><el-tag v-for="item in row.related_skills" :key="item">{{ item }}</el-tag></div>
          </template>
        </el-table-column>
        <el-table-column label="推荐课程" min-width="180">
          <template #default="{ row }">{{ row.recommended_courses.join(" / ") }}</template>
        </el-table-column>
      </el-table>
    </SectionCard>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { jobApi } from "@/api";
import PageHeader from "@/components/PageHeader.vue";
import SectionCard from "@/components/SectionCard.vue";

const jobs = ref([]);
const jobId = ref(1);
const relations = ref([]);

const load = async () => {
  const res = await jobApi.relations(jobId.value);
  relations.value = res.data.relations || [];
};

onMounted(async () => {
  const res = await jobApi.list();
  jobs.value = res.data;
  jobId.value = jobs.value[0]?.id;
  load();
});
</script>
