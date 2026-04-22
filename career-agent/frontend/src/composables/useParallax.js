import { onMounted, onUnmounted, ref } from 'vue';

export function useParallax(options = {}) {
  const {
    speed = 0.5,
    minOffset = -100,
    maxOffset = 100
  } = options;

  const offsetY = ref(0);
  let ticking = false;

  const onScroll = () => {
    if (!ticking) {
      requestAnimationFrame(() => {
        offsetY.value = Math.min(maxOffset, Math.max(minOffset, window.scrollY * speed));
        ticking = false;
      });
      ticking = true;
    }
  };

  onMounted(() => {
    window.addEventListener('scroll', onScroll, { passive: true });
  });

  onUnmounted(() => {
    window.removeEventListener('scroll', onScroll);
  });

  return { offsetY };
}
