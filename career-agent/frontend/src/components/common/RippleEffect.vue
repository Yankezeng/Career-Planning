<template>
  <div class="ripple-container" ref="containerRef">
    <slot></slot>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue';

const containerRef = ref(null);

const createRipple = (event) => {
  const target = event.currentTarget;
  const rect = target.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const y = event.clientY - rect.top;

  const ripple = document.createElement('span');
  ripple.className = 'ripple-effect';
  ripple.style.left = `${x}px`;
  ripple.style.top = `${y}px`;

  target.appendChild(ripple);

  ripple.addEventListener('animationend', () => {
    ripple.remove();
  });
};

onMounted(() => {
  if (containerRef.value) {
    containerRef.value.addEventListener('click', createRipple);
  }
});

onUnmounted(() => {
  if (containerRef.value) {
    containerRef.value.removeEventListener('click', createRipple);
  }
});
</script>

<style scoped>
.ripple-container {
  position: relative;
  overflow: hidden;
}

.ripple-effect {
  position: absolute;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(255, 255, 255, 0.6) 0%, rgba(255, 255, 255, 0.2) 50%, transparent 70%);
  transform: scale(0);
  animation: ripple-animation 0.6s ease-out forwards;
  pointer-events: none;
}

@keyframes ripple-animation {
  0% {
    transform: scale(0);
    opacity: 1;
  }
  100% {
    transform: scale(4);
    opacity: 0;
  }
}
</style>
