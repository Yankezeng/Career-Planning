<template>
  <span ref="textRef" class="typewriter"></span>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue';

const props = defineProps({
  text: { type: String, default: '' },
  speed: { type: Number, default: 50 },
  startDelay: { type: Number, default: 0 }
});

const textRef = ref(null);
let timeoutId = null;

const type = (index = 0) => {
  if (!textRef.value) return;

  if (index < props.text.length) {
    textRef.value.innerHTML = props.text.substring(0, index + 1);
    timeoutId = setTimeout(() => type(index + 1), props.speed);
  }
};

const start = () => {
  if (timeoutId) clearTimeout(timeoutId);
  if (textRef.value) textRef.value.innerHTML = '';
  setTimeout(() => type(0), props.startDelay);
};

onMounted(() => {
  if (props.text) start();
});

watch(() => props.text, () => {
  start();
});
</script>

<style scoped>
.typewriter {
  display: inline-block;
  overflow: hidden;
  white-space: nowrap;
  border-right: 2px solid currentColor;
  animation: blink-caret 0.75s step-end infinite;
}

.typewriter:not(:empty) {
  border-right-color: transparent;
}

@keyframes blink-caret {
  from, to { border-color: transparent; }
  50% { border-color: currentColor; }
}
</style>
