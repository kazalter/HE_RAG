<script setup>
import Icon from "./Icon.vue";

defineProps({
  kbName: { type: String, default: "本地知识库" },
  docCount: { type: Number, default: 0 },
  chips: { type: Array, default: () => [] },
});
const emit = defineEmits(["suggest"]);
</script>

<template>
  <div class="h-full flex flex-col items-center justify-center px-6 -mt-8">
    <div
      class="w-14 h-14 rounded-2xl bg-gradient-to-br from-coral-400 to-coral-600 grid place-items-center shadow-lg shadow-coral-500/25 mb-5 animate-msg-in"
    >
      <Icon name="layers" :size="26" class="text-white" />
    </div>
    <h1 class="text-[22px] font-semibold text-stone-800 animate-msg-in" style="animation-delay: 60ms">
      向「{{ kbName }}」提问
    </h1>
    <p
      class="mt-2 text-[14px] text-stone-400 text-center max-w-md animate-msg-in"
      style="animation-delay: 120ms"
    >
      系统会基于库中的 {{ docCount }} 份资料检索并作答，并标注引用来源。
    </p>
    <div
      v-if="chips.length"
      class="mt-7 flex flex-wrap items-center justify-center gap-2 max-w-lg animate-msg-in"
      style="animation-delay: 180ms"
    >
      <button
        v-for="(c, i) in chips"
        :key="i"
        class="px-3.5 h-9 rounded-full bg-white ring-1 ring-stone-200/80 text-[13px] text-stone-600 shadow-[0_1px_2px_rgba(0,0,0,0.03)] hover:ring-coral-300 hover:text-coral-600 transition-all"
        @click="emit('suggest', c)"
      >
        {{ c }}
      </button>
    </div>
  </div>
</template>
