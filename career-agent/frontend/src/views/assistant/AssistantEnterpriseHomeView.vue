<template>
  <div class="assistant-enterprise-redirect">正在跳转到统一 Agent 首页...</div>
</template>

<script setup>
import { onMounted } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();

onMounted(() => {
  router.replace("/assistant");
});
</script>

<style scoped>
.assistant-enterprise-redirect {
  min-height: 240px;
  display: grid;
  place-items: center;
  color: #475569;
  font-size: 14px;
}
</style>
