<script setup>
import { nextTick, ref, watch } from "vue";
import Icon from "./Icon.vue";

const props = defineProps({
  busy: { type: Boolean, default: false },
  model: { type: Object, required: true },
});
const emit = defineEmits(["send", "open-model"]);

const text = ref("");
const area = ref(null);

function grow() {
  const el = area.value;
  if (!el) return;
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 200) + "px";
}
watch(text, () => nextTick(grow));

function submit() {
  const v = text.value.trim();
  if (!v || props.busy) return;
  emit("send", v);
  text.value = "";
  nextTick(() => {
    if (area.value) area.value.style.height = "auto";
  });
}

function onKey(e) {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    submit();
  }
}
</script>

<template>
  <div class="px-4 pb-4 pt-1">
    <div class="max-w-3xl mx-auto">
      <div
        class="rounded-[20px] bg-white ring-1 ring-stone-200/80 shadow-[0_2px_16px_-8px_rgba(0,0,0,0.12)] focus-within:ring-coral-300/80 focus-within:shadow-[0_4px_24px_-10px_rgba(217,119,87,0.25)] transition-all"
      >
        <textarea
          ref="area"
          v-model="text"
          rows="1"
          placeholder="向知识库提问，Enter 发送 · Shift+Enter 换行"
          class="w-full resize-none bg-transparent px-4 pt-3.5 pb-1 text-[14.5px] leading-relaxed text-stone-700 placeholder:text-stone-400 outline-none"
          @keydown="onKey"
        ></textarea>

        <div class="flex items-center gap-2 px-2.5 pb-2.5 pt-1">
          <button
            class="hidden md:flex items-center gap-1.5 h-8 px-2.5 rounded-lg text-[12.5px] text-stone-500 hover:bg-stone-100 transition-colors"
            @click="emit('open-model')"
          >
            <Icon name="cpu" :size="15" />
            <span class="font-medium text-stone-600">{{ model.name }}</span>
            <Icon name="chevronDown" :size="13" class="text-stone-400" />
          </button>

          <div class="flex-1"></div>

          <button
            :disabled="busy"
            class="w-9 h-9 grid place-items-center rounded-xl transition-all"
            :class="
              busy
                ? 'bg-stone-200 text-stone-400 cursor-not-allowed'
                : 'bg-coral-500 text-white shadow-sm shadow-coral-500/30 hover:bg-coral-600 active:scale-95'
            "
            @click="submit"
          >
            <span
              v-if="busy"
              class="w-3.5 h-3.5 border-2 border-stone-400/40 border-t-stone-500 rounded-full animate-spin"
            ></span>
            <Icon v-else name="send" :size="17" />
          </button>
        </div>
      </div>

      <div class="flex items-center justify-center gap-1.5 mt-2.5 text-[11px] text-stone-400">
        <Icon name="check" :size="12" class="text-emerald-500" />
        <span>回答将基于知识库内容并标注来源</span>
      </div>
    </div>
  </div>
</template>
