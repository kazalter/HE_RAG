<script setup>
import Icon from "./Icon.vue";

defineProps({
  open: { type: Boolean, default: false },
  models: { type: Array, default: () => [] },
  current: { type: String, default: "" },
});
const emit = defineEmits(["close", "select"]);
</script>

<template>
  <div
    v-if="open"
    class="fixed inset-0 z-50 flex items-start justify-center pt-[15vh] px-4"
    @click="emit('close')"
  >
    <div class="absolute inset-0 bg-stone-900/20 backdrop-blur-[2px] animate-fade-in"></div>
    <div
      class="relative w-full max-w-md rounded-2xl bg-white ring-1 ring-stone-200/80 shadow-2xl shadow-stone-900/10 p-2 animate-pop"
      @click.stop
    >
      <div class="px-3 pt-2.5 pb-1.5 text-[12px] font-medium text-stone-400">选择模型</div>
      <button
        v-for="m in models"
        :key="m.id"
        class="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left transition-colors"
        :class="m.id === current ? 'bg-coral-50' : 'hover:bg-stone-100'"
        @click="emit('select', m.id)"
      >
        <div
          class="w-9 h-9 rounded-lg grid place-items-center shrink-0 text-white"
          :class="m.id === current ? 'bg-coral-500' : 'bg-stone-800'"
        >
          <Icon name="cpu" :size="17" />
        </div>
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2">
            <span class="text-[14px] font-semibold text-stone-800">{{ m.name }}</span>
            <span
              v-if="m.badge"
              class="px-1.5 h-4 inline-flex items-center rounded text-[10px] font-medium"
              :class="m.badge === '推荐' ? 'bg-coral-100 text-coral-600' : 'bg-stone-100 text-stone-500'"
            >{{ m.badge }}</span>
          </div>
          <div class="text-[12px] text-stone-400 mt-0.5">{{ m.desc }}</div>
        </div>
        <Icon v-if="m.id === current" name="check" :size="17" class="text-coral-500" />
      </button>
    </div>
  </div>
</template>
