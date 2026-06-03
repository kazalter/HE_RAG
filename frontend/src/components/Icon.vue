<script setup>
import { computed } from "vue";
import { ICONS } from "../lib/icons.js";

const props = defineProps({
  name: { type: String, required: true },
  size: { type: [Number, String], default: 18 },
  strokeWidth: { type: [Number, String], default: 1.7 },
});

// 把单条 path 串按 " M" 拆成多段子路径，与设计稿 Icon 行为一致
const segments = computed(() => {
  const d = ICONS[props.name];
  if (!d) return [];
  return d.split(" M").map((seg, idx) => (idx ? "M" + seg : seg));
});
</script>

<template>
  <svg
    v-if="segments.length"
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    :stroke-width="strokeWidth"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path v-for="(d, idx) in segments" :key="idx" :d="d" />
  </svg>
</template>
