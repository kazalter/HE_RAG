// 轻量全局消息提示，替代 Element Plus 的 ElMessage。
// 模块级 reactive 数组由 Toast.vue 渲染，任意处 import { toast } 即可推送。
import { reactive } from "vue";

export const toasts = reactive([]);
let seq = 0;

function push(type, message, duration) {
  const id = ++seq;
  toasts.push({ id, type, message });
  if (duration > 0) setTimeout(() => dismiss(id), duration);
}

export function dismiss(id) {
  const index = toasts.findIndex((t) => t.id === id);
  if (index !== -1) toasts.splice(index, 1);
}

export const toast = {
  success: (message) => push("success", message, 2600),
  error: (message) => push("error", message, 3800),
  warning: (message) => push("warning", message, 3000),
  info: (message) => push("info", message, 2600),
};
