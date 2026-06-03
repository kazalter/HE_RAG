<script setup>
import { computed } from "vue";

const props = defineProps({
  value: { type: Number, default: 100 },
  size: { type: Number, default: 44 },
  stroke: { type: Number, default: 4 },
});

const radius = computed(() => (props.size - props.stroke) / 2);
const circumference = computed(() => 2 * Math.PI * radius.value);
const dashOffset = computed(() => circumference.value * (1 - props.value / 100));
</script>

<template>
  <div class="relative" :style="{ width: size + 'px', height: size + 'px' }">
    <svg :width="size" :height="size" class="-rotate-90">
      <circle
        :cx="size / 2"
        :cy="size / 2"
        :r="radius"
        fill="none"
        stroke="rgb(231 229 224)"
        :stroke-width="stroke"
      />
      <circle
        :cx="size / 2"
        :cy="size / 2"
        :r="radius"
        fill="none"
        stroke="url(#hg)"
        :stroke-width="stroke"
        :stroke-dasharray="circumference"
        :stroke-dashoffset="dashOffset"
        stroke-linecap="round"
        style="transition: stroke-dashoffset 1.1s cubic-bezier(0.4, 0, 0.2, 1)"
      />
      <defs>
        <linearGradient id="hg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="#e8895f" />
          <stop offset="100%" stop-color="#d97757" />
        </linearGradient>
      </defs>
    </svg>
    <div class="absolute inset-0 flex items-center justify-center">
      <span class="text-[12px] font-semibold text-stone-700 tabular-nums">{{ value }}</span>
    </div>
  </div>
</template>
