<script setup>
import { toasts, dismiss } from "../lib/toast.js";
import Icon from "./Icon.vue";

// type → 图标 + 配色（沿用全局 stone/coral 调性的语义色）
const STYLES = {
  success: { icon: "check", cls: "text-emerald-500" },
  error: { icon: "alert", cls: "text-rose-500" },
  warning: { icon: "alert", cls: "text-amber-500" },
  info: { icon: "message", cls: "text-stone-500" },
};
const styleOf = (type) => STYLES[type] || STYLES.info;
</script>

<template>
  <div class="fixed top-4 left-1/2 -translate-x-1/2 z-[60] flex flex-col items-center gap-2 pointer-events-none">
    <transition-group name="toast">
      <div
        v-for="t in toasts"
        :key="t.id"
        class="pointer-events-auto flex items-center gap-2.5 pl-3.5 pr-4 py-2.5 rounded-xl bg-white shadow-lg shadow-stone-900/10 ring-1 ring-stone-200/70 text-[13px] text-stone-700 max-w-[440px] cursor-pointer"
        @click="dismiss(t.id)"
      >
        <Icon :name="styleOf(t.type).icon" :size="16" :class="styleOf(t.type).cls" />
        <span class="leading-snug">{{ t.message }}</span>
      </div>
    </transition-group>
  </div>
</template>

<style scoped>
.toast-enter-active,
.toast-leave-active {
  transition: all 0.22s cubic-bezier(0.16, 1, 0.3, 1);
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
