<script setup>
import { computed } from "vue";

const props = defineProps({
  type: { type: String, default: "" },
});

const MAP = {
  pdf: "bg-rose-50 text-rose-500 ring-rose-100",
  docx: "bg-sky-50 text-sky-500 ring-sky-100",
  doc: "bg-sky-50 text-sky-500 ring-sky-100",
  md: "bg-violet-50 text-violet-500 ring-violet-100",
  txt: "bg-stone-100 text-stone-500 ring-stone-200",
};

const cls = computed(() => MAP[props.type?.toLowerCase()] || "bg-stone-100 text-stone-500 ring-stone-200");
</script>

<template>
  <span
    class="inline-flex items-center justify-center w-8 h-8 rounded-lg ring-1 text-[10px] font-bold uppercase tracking-wide shrink-0"
    :class="cls"
  >
    {{ type }}
  </span>
</template>
