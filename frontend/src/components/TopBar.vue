<script setup>
import Icon from "./Icon.vue";

defineProps({
  kbName: { type: String, default: "本地知识库" },
  model: { type: Object, required: true },
  ready: { type: Boolean, default: false },
});

const emit = defineEmits(["open-mobile", "open-model", "open-kb", "open-settings"]);
</script>

<template>
  <header
    class="h-[60px] shrink-0 flex items-center gap-3 px-4 border-b border-stone-200/60 bg-paper-50/80 backdrop-blur-md"
  >
    <button
      class="md:hidden w-9 h-9 grid place-items-center rounded-lg text-stone-500 hover:bg-stone-200/50"
      @click="emit('open-mobile')"
    >
      <Icon name="panelLeft" :size="19" />
    </button>

    <button class="flex items-center gap-2 min-w-0 group" @click="emit('open-kb')">
      <span class="inline-flex items-center justify-center w-7 h-7 rounded-lg bg-coral-50 text-coral-500 shrink-0">
        <Icon name="layers" :size="15" />
      </span>
      <span class="text-[14.5px] font-semibold text-stone-800 truncate">{{ kbName }}</span>
      <span
        v-if="ready"
        class="hidden sm:inline-flex items-center gap-1 px-2 h-5 rounded-full bg-emerald-50 text-emerald-600 text-[10.5px] font-medium ring-1 ring-emerald-100"
      >
        <span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>已连接
      </span>
      <span
        v-else
        class="hidden sm:inline-flex items-center gap-1 px-2 h-5 rounded-full bg-amber-50 text-amber-600 text-[10.5px] font-medium ring-1 ring-amber-100"
      >
        <span class="w-1.5 h-1.5 rounded-full bg-amber-500"></span>加载中
      </span>
    </button>

    <div class="flex-1"></div>

    <button
      class="flex items-center gap-2 h-9 pl-2.5 pr-3 rounded-xl ring-1 ring-stone-200/80 bg-white text-[13px] text-stone-600 hover:ring-stone-300 transition-all"
      @click="emit('open-model')"
    >
      <span class="w-5 h-5 rounded-md bg-stone-800 grid place-items-center text-white shrink-0">
        <Icon name="cpu" :size="12" />
      </span>
      <span class="font-medium hidden sm:inline">{{ model.name }}</span>
      <Icon name="chevronDown" :size="14" class="text-stone-400" />
    </button>

    <button
      title="设置"
      class="w-9 h-9 grid place-items-center rounded-xl text-stone-500 hover:bg-stone-200/50 transition-colors"
      @click="emit('open-settings')"
    >
      <Icon name="settings" :size="18" />
    </button>

    <div class="w-9 h-9 rounded-full bg-stone-800 grid place-items-center text-white text-[12px] font-semibold shrink-0">
      教
    </div>
  </header>
</template>
