<template>
  <div ref="containerRef" class="dynamic-bg"></div>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue';
import * as THREE from 'three';

const props = defineProps({
  particleCount: { type: Number, default: 200 },
  speed: { type: Number, default: 0.5 },
  primaryColor: { type: String, default: '#00d4ff' },
  secondaryColor: { type: String, default: '#0066ff' },
  interactive: { type: Boolean, default: true },
  mouseRadius: { type: Number, default: 120 }
});

const containerRef = ref(null);
let animId = null;
let renderer, scene, camera, particles;
const mouse = { x: -9999, y: -9999 };
let clickParticles = [];

const init = () => {
  if (!containerRef.value) return;

  const w = window.innerWidth;
  const h = window.innerHeight;

  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(75, w / h, 0.1, 1000);
  camera.position.z = 30;

  renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
  renderer.setSize(w, h);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  containerRef.value.appendChild(renderer.domElement);

  const geo = new THREE.BufferGeometry();
  const positions = new Float32Array(props.particleCount * 3);
  const colors = new Float32Array(props.particleCount * 3);
  const velocities = new Float32Array(props.particleCount * 3);

  const col1 = new THREE.Color(props.primaryColor);
  const col2 = new THREE.Color(props.secondaryColor);

  for (let i = 0; i < props.particleCount; i++) {
    positions[i * 3] = (Math.random() - 0.5) * 100;
    positions[i * 3 + 1] = (Math.random() - 0.5) * 100;
    positions[i * 3 + 2] = (Math.random() - 0.5) * 50;

    const c = col1.clone().lerp(col2, Math.random());
    colors[i * 3] = c.r;
    colors[i * 3 + 1] = c.g;
    colors[i * 3 + 2] = c.b;

    velocities[i * 3] = (Math.random() - 0.5) * 0.1 * props.speed;
    velocities[i * 3 + 1] = (Math.random() - 0.5) * 0.1 * props.speed;
    velocities[i * 3 + 2] = (Math.random() - 0.5) * 0.05 * props.speed;
  }

  geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  geo.userData.velocities = velocities;

  const mat = new THREE.PointsMaterial({
    size: 2.5,
    vertexColors: true,
    transparent: true,
    opacity: 0.9,
    sizeAttenuation: true
  });

  particles = new THREE.Points(geo, mat);
  scene.add(particles);

  animate();
};

const animate = () => {
  animId = requestAnimationFrame(animate);
  if (!particles || !renderer || !scene || !camera) return;

  const pos = particles.geometry.attributes.position.array;
  const vel = particles.geometry.userData.velocities;

  for (let i = 0; i < props.particleCount; i++) {
    const px = pos[i * 3];
    const py = pos[i * 3 + 1];
    const pz = pos[i * 3 + 2];

    if (props.interactive) {
      const screenPos = toScreen(px, py, pz);
      const dx = screenPos.x - mouse.x;
      const dy = screenPos.y - mouse.y;
      const dist = Math.sqrt(dx * dx + dy * dy);

      if (dist < props.mouseRadius && dist > 0) {
        const force = (props.mouseRadius - dist) / props.mouseRadius * 0.02;
        vel[i * 3] -= dx * force;
        vel[i * 3 + 1] -= dy * force;
      }
    }

    vel[i * 3] *= 0.99;
    vel[i * 3 + 1] *= 0.99;
    vel[i * 3 + 2] *= 0.99;

    pos[i * 3] += vel[i * 3];
    pos[i * 3 + 1] += vel[i * 3 + 1];
    pos[i * 3 + 2] += vel[i * 3 + 2];

    if (Math.abs(pos[i * 3]) > 50) vel[i * 3] *= -0.9;
    if (Math.abs(pos[i * 3 + 1]) > 50) vel[i * 3 + 1] *= -0.9;
    if (Math.abs(pos[i * 3 + 2]) > 25) vel[i * 3 + 2] *= -0.9;
  }

  for (let i = clickParticles.length - 1; i >= 0; i--) {
    const cp = clickParticles[i];
    cp.life -= 0.02;
    cp.mesh.position.x += cp.vx;
    cp.mesh.position.y += cp.vy;
    cp.mesh.material.opacity = cp.life;
    cp.mesh.scale.multiplyScalar(0.96);

    if (cp.life <= 0) {
      scene.remove(cp.mesh);
      cp.mesh.geometry.dispose();
      cp.mesh.material.dispose();
      clickParticles.splice(i, 1);
    }
  }

  particles.geometry.attributes.position.needsUpdate = true;
  particles.rotation.y += 0.0002;
  renderer.render(scene, camera);
};

const toScreen = (x, y, z) => {
  const vector = new THREE.Vector3(x, y, z);
  vector.project(camera);
  return {
    x: (vector.x + 1) / 2 * window.innerWidth,
    y: -(vector.y - 1) / 2 * window.innerHeight
  };
};

const onMouseMove = (e) => {
  mouse.x = e.clientX;
  mouse.y = e.clientY;
};

const onMouseLeave = () => {
  mouse.x = -9999;
  mouse.y = -9999;
};

const onClick = (e) => {
  if (!props.interactive || !particles) return;

  const col1 = new THREE.Color(props.primaryColor);
  const col2 = new THREE.Color(props.secondaryColor);

  for (let i = 0; i < 15; i++) {
    const geo = new THREE.BufferGeometry();
    const positions = new Float32Array([0, 0, 0]);
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));

    const mat = new THREE.PointsMaterial({
      size: 4,
      color: col1.clone().lerp(col2, Math.random()),
      transparent: true,
      opacity: 1
    });

    const particle = new THREE.Points(geo, mat);
    particle.position.set(
      (e.clientX / window.innerWidth - 0.5) * 50,
      -(e.clientY / window.innerHeight - 0.5) * 50,
      0
    );

    const angle = Math.random() * Math.PI * 2;
    const speed = 0.5 + Math.random() * 1;
    clickParticles.push({
      mesh: particle,
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed,
      life: 1
    });

    scene.add(particle);
  }
};

const onResize = () => {
  if (!camera || !renderer) return;
  const w = window.innerWidth;
  const h = window.innerHeight;
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h);
};

let isVisible = true;
const onVisibility = () => { isVisible = !document.hidden; };

onMounted(() => {
  init();
  window.addEventListener('resize', onResize);
  document.addEventListener('visibilitychange', onVisibility);
  document.addEventListener('mousemove', onMouseMove);
  document.addEventListener('mouseleave', onMouseLeave);
  document.addEventListener('click', onClick);
});

onUnmounted(() => {
  if (animId) cancelAnimationFrame(animId);
  window.removeEventListener('resize', onResize);
  document.removeEventListener('visibilitychange', onVisibility);
  document.removeEventListener('mousemove', onMouseMove);
  document.removeEventListener('mouseleave', onMouseLeave);
  document.removeEventListener('click', onClick);
  if (renderer) {
    renderer.dispose();
    containerRef.value?.removeChild(renderer.domElement);
  }
});
</script>

<style scoped>
.dynamic-bg {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  z-index: -1;
  pointer-events: none;
  background: linear-gradient(135deg, rgba(0,212,255,0.03), rgba(0,102,255,0.03));
}

.dynamic-bg canvas {
  display: block;
  width: 100% !important;
  height: 100% !important;
}
</style>
