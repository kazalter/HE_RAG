<script setup>
import { ref, watch } from "vue";
import Icon from "./Icon.vue";

const props = defineProps({
  open: { type: Boolean, default: false },
  apiKeySaved: { type: Boolean, default: false },
  topK: { type: Number, default: 3 },
});
const emit = defineEmits(["close", "save-key", "update-top-k"]);

const keyInput = ref("");
const localTopK = ref(props.topK);

watch(
  () => props.topK,
  (v) => (localTopK.value = v)
);
watch(
  () => props.open,
  (v) => {
    if (v) keyInput.value = "";
  }
);

function save() {
  emit("save-key", keyInput.value.trim());
  keyInput.value = "";
}

function setTopK(v) {
  const n = Math.min(6, Math.max(1, Number(v) || 3));
  localTopK.value = n;
  emit("update-top-k", n);
}
</script>

<template>
  <div
    v-if="open"
    class="fixed inset-0 z-50 flex items-start justify-center pt-[12vh] px-4"
    @click="emit('close')"
  >
    <div class="absolute inset-0 bg-stone-900/20 backdrop-blur-[2px] animate-fade-in"></div>
    <div
      class="relative w-full max-w-md rounded-2xl bg-white ring-1 ring-stone-200/80 shadow-2xl shadow-stone-900/10 p-5 animate-pop"
      @click.stop
    >
      <div class="flex items-center gap-2 mb-4">
        <span class="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-stone-100 text-stone-600">
          <Icon name="settings" :size="17" />
        </span>
        <div class="flex-1 text-[15px] font-semibold text-stone-800">设置</div>
        <button
          class="w-8 h-8 grid place-items-center rounded-lg text-stone-400 hover:bg-stone-200/50 hover:text-stone-700 transition-colors"
          @click="emit('close')"
        >
          <Icon name="x" :size="17" />
        </button>
      </div>

      <!-- API Key -->
      <label class="block text-[12.5px] font-medium text-stone-500 mb-1.5">DeepSeek API Key</label>
      <input
        v-model="keyInput"
        type="password"
        autocomplete="off"
        :placeholder="apiKeySaved ? 'API Key 已保存；输入新 Key 可覆盖' : '粘贴 DeepSeek API Key'"
        class="w-full h-10 px-3 rounded-xl bg-stone-50 ring-1 ring-stone-200/80 text-[13.5px] text-stone-700 placeholder:text-stone-400 outline-none focus:bg-white focus:ring-coral-300 transition-all"
      >
      <p v-if="apiKeySaved" class="mt-1.5 text-[11.5px] text-emerald-600">
        已保存到本地配置文件，之后打开会自动使用。
      </p>

      <!-- 检索数量 -->
      <label class="block text-[12.5px] font-medium text-stone-500 mt-4 mb-1.5">检索数量 (top_k)</label>
      <div class="flex items-center gap-2">
        <button
          class="w-9 h-9 grid place-items-center rounded-lg ring-1 ring-stone-200/80 text-stone-500 hover:bg-stone-100"
          @click="setTopK(localTopK - 1)"
        >−</button>
        <div class="w-14 h-9 grid place-items-center rounded-lg bg-stone-50 ring-1 ring-stone-200/80 text-[14px] font-semibold text-stone-700 tabular-nums">
          {{ localTopK }}
        </div>
        <button
          class="w-9 h-9 grid place-items-center rounded-lg ring-1 ring-stone-200/80 text-stone-500 hover:bg-stone-100"
          @click="setTopK(localTopK + 1)"
        >+</button>
        <span class="text-[11.5px] text-stone-400 ml-1">每次检索返回的片段数（1–6）</span>
      </div>

      <button
        class="mt-5 w-full h-10 rounded-xl bg-coral-500 text-white text-[13.5px] font-medium shadow-sm shadow-coral-500/30 hover:bg-coral-600 active:scale-[0.99] transition-all"
        @click="save"
      >
        保存 Key
      </button>
    </div>
  </div>
</template>
