<template>
  <div ref="rootRef" class="thinking-indicator" :class="`state-${state}`">
    <span class="thinking-label">{{ label || defaultLabel }}</span>
    <span ref="dotsRef" class="thinking-dots" aria-hidden="true">
      <i class="dot"></i>
      <i class="dot"></i>
      <i class="dot"></i>
    </span>
    <span v-if="state === 'streaming'" ref="cursorRef" class="thinking-cursor">▍</span>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import { gsap } from "gsap";

const props = defineProps({
  state: { type: String, default: "waiting" },
  label: { type: String, default: "" },
});

const defaultLabel = computed(() => {
  if (props.state === "error") return "请求异常";
  if (props.state === "streaming") return "正在生成回复...";
  return "正在思考...";
});

const rootRef = ref(null);
const dotsRef = ref(null);
const cursorRef = ref(null);

let dotsTl = null;
let pulseTl = null;
let cursorTl = null;
let exitTl = null;
let errorTl = null;

const dotNodes = () => Array.from(dotsRef.value?.querySelectorAll(".dot") || []);

const stopAll = () => {
  dotsTl?.kill();
  pulseTl?.kill();
  cursorTl?.kill();
  exitTl?.kill();
  errorTl?.kill();
  dotsTl = null;
  pulseTl = null;
  cursorTl = null;
  exitTl = null;
  errorTl = null;
};

const playWaiting = () => {
  stopAll();
  const root = rootRef.value;
  const dots = dotNodes();
  if (!root || !dots.length) return;
  gsap.set(root, { opacity: 1, x: 0, color: "#64748b" });
  gsap.set(dots, { y: 0, opacity: 0.45 });

  dotsTl = gsap.timeline({ repeat: -1 });
  dotsTl
    .to(dots, { y: -3, opacity: 1, duration: 0.3, stagger: 0.12, ease: "sine.out" })
    .to(dots, { y: 0, opacity: 0.45, duration: 0.3, stagger: 0.12, ease: "sine.in" });

  pulseTl = gsap.timeline({ repeat: -1, yoyo: true }).to(root, { opacity: 0.72, duration: 0.45, ease: "sine.inOut" });
};

const playStreaming = () => {
  stopAll();
  const root = rootRef.value;
  const dots = dotNodes();
  if (!root || !dots.length) return;
  gsap.set(root, { opacity: 1, x: 0, color: "#64748b" });
  gsap.set(dots, { y: 0, opacity: 0.35 });

  dotsTl = gsap.timeline({ repeat: -1 });
  dotsTl
    .to(dots, { y: -2, opacity: 0.85, duration: 0.22, stagger: 0.1, ease: "sine.out" })
    .to(dots, { y: 0, opacity: 0.35, duration: 0.22, stagger: 0.1, ease: "sine.in" });

  if (cursorRef.value) {
    gsap.set(cursorRef.value, { opacity: 1 });
    cursorTl = gsap.timeline({ repeat: -1 });
    cursorTl.to(cursorRef.value, { opacity: 0, duration: 0.45, ease: "none" }).to(cursorRef.value, { opacity: 1, duration: 0.45, ease: "none" });
  }
};

const playDone = () => {
  stopAll();
  if (!rootRef.value) return;
  exitTl = gsap.timeline();
  exitTl.to(rootRef.value, { opacity: 0, duration: 0.2, ease: "power1.out" });
};

const playError = () => {
  stopAll();
  if (!rootRef.value) return;
  gsap.set(rootRef.value, { opacity: 1, color: "#dc2626" });
  errorTl = gsap.timeline();
  errorTl
    .to(rootRef.value, { x: 4, duration: 0.06, yoyo: true, repeat: 3, ease: "power1.inOut" })
    .set(rootRef.value, { x: 0 });
};

watch(
  () => props.state,
  async (state) => {
    await nextTick();
    if (state === "waiting") playWaiting();
    if (state === "streaming") playStreaming();
    if (state === "done") playDone();
    if (state === "error") playError();
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  stopAll();
});
</script>

<style scoped>
.thinking-indicator {
  margin-top: 8px;
  min-height: 18px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #64748b;
  font-size: 12px;
  line-height: 1;
  user-select: none;
}

.thinking-label {
  font-weight: 600;
}

.thinking-dots {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
  opacity: 0.45;
}

.thinking-cursor {
  font-size: 13px;
  font-weight: 700;
  line-height: 1;
}
</style>
