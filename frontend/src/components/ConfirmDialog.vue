<script setup>
import Icon from "./Icon.vue";

defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, default: "确认操作" },
  message: { type: String, default: "" },
  confirmText: { type: String, default: "确定" },
  cancelText: { type: String, default: "取消" },
  danger: { type: Boolean, default: false },
  showCheckbox: { type: Boolean, default: false },
  checkboxLabel: { type: String, default: "" },
  checked: { type: Boolean, default: false },
});
const emit = defineEmits(["confirm", "cancel", "update:checked"]);
</script>

<template>
  <div v-if="open" class="fixed inset-0 z-[70] flex items-center justify-center p-4">
    <div class="absolute inset-0 bg-stone-900/30 backdrop-blur-[2px] animate-fade-in" @click="emit('cancel')"></div>
    <div class="relative w-full max-w-[380px] rounded-2xl bg-white shadow-2xl shadow-stone-900/20 p-5 animate-pop">
      <div class="flex items-start gap-3">
        <span
          class="shrink-0 inline-flex items-center justify-center w-9 h-9 rounded-xl"
          :class="danger ? 'bg-rose-50 text-rose-500' : 'bg-coral-50 text-coral-500'"
        >
          <Icon name="alert" :size="18" />
        </span>
        <div class="flex-1 min-w-0 pt-0.5">
          <div class="text-[14.5px] font-semibold text-stone-800">{{ title }}</div>
          <p class="text-[12.5px] text-stone-500 leading-relaxed mt-1.5 break-words">{{ message }}</p>
          
          <!-- 可选的复选框 -->
          <div v-if="showCheckbox" class="mt-3 flex items-center gap-2">
            <input
              id="confirm-dialog-checkbox"
              type="checkbox"
              :checked="checked"
              @change="emit('update:checked', $event.target.checked)"
              class="w-4 h-4 rounded text-coral-500 border-stone-300 focus:ring-coral-400 cursor-pointer"
            />
            <label for="confirm-dialog-checkbox" class="text-[12px] text-stone-600 select-none cursor-pointer">
              {{ checkboxLabel }}
            </label>
          </div>
        </div>
      </div>

      <div class="flex justify-end gap-2 mt-5">
        <button
          class="px-3.5 py-1.5 rounded-lg text-[13px] font-medium text-stone-600 hover:bg-stone-100 transition-colors"
          @click="emit('cancel')"
        >
          {{ cancelText }}
        </button>
        <button
          class="px-3.5 py-1.5 rounded-lg text-[13px] font-medium text-white transition-colors"
          :class="danger ? 'bg-rose-500 hover:bg-rose-600' : 'bg-coral-500 hover:bg-coral-600'"
          @click="emit('confirm')"
        >
          {{ confirmText }}
        </button>
      </div>
    </div>
  </div>
</template>
