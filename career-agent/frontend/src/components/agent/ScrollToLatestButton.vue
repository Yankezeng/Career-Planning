<template>
  <transition name="scroll-latest-fade">
    <button v-if="visible" type="button" class="scroll-latest-btn" @click="$emit('click')">
      <span v-if="unreadCount > 0">↓ {{ unreadCount }} 条新消息</span>
      <span v-else>回到最新</span>
    </button>
  </transition>
</template>

<script setup>
defineProps({
  visible: { type: Boolean, default: false },
  unreadCount: { type: Number, default: 0 },
});

defineEmits(["click"]);
</script>

<style scoped>
.scroll-latest-btn {
  position: absolute;
  right: 20px;
  bottom: 16px;
  border: 1px solid #bfdbfe;
  background: #2563eb;
  color: #fff;
  border-radius: 999px;
  min-height: 36px;
  padding: 0 14px;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 8px 20px rgba(37, 99, 235, 0.28);
  z-index: 4;
}

.scroll-latest-fade-enter-active,
.scroll-latest-fade-leave-active {
  transition: all 0.18s ease;
}

.scroll-latest-fade-enter-from,
.scroll-latest-fade-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
</style>
