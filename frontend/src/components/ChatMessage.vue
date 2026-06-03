<script setup>
import { computed, ref } from "vue";
import Icon from "./Icon.vue";
import { renderMarkdown } from "../lib/markdown.js";

const props = defineProps({
  msg: { type: Object, required: true },
});
const emit = defineEmits(["suggest-upload", "suggest-rephrase"]);

const sourcesOpen = ref(false);
const copied = ref(false);

const html = computed(() => renderMarkdown(props.msg.displayText || ""));
const pct = (score) => `${Math.round(Math.min(Math.max(Number(score) || 0, 0), 1) * 100)}%`;

function copy() {
  const text = props.msg.displayText || "";
  if (navigator.clipboard?.writeText) {
    navigator.clipboard.writeText(text).catch(() => {});
  }
  copied.value = true;
  setTimeout(() => (copied.value = false), 1400);
}
</script>

<template>
  <!-- 用户消息 -->
  <div v-if="msg.role === 'user'" class="flex justify-end animate-msg-in">
    <div
      class="max-w-[78%] rounded-2xl rounded-tr-md bg-coral-500 text-white px-4 py-2.5 text-[14.5px] leading-relaxed shadow-sm shadow-coral-500/20 whitespace-pre-wrap"
    >
      {{ msg.text }}
    </div>
  </div>

  <!-- AI 消息 -->
  <div v-else class="flex gap-3.5 animate-msg-in group/msg">
    <div
      class="w-8 h-8 rounded-[10px] bg-gradient-to-br from-coral-400 to-coral-600 grid place-items-center shadow-sm shadow-coral-500/25 shrink-0"
    >
      <Icon name="layers" :size="16" class="text-white" />
    </div>

    <div class="flex-1 min-w-0 pt-0.5">
      <!-- 检索中 -->
      <div v-if="msg.phase === 'retrieving'" class="flex items-center gap-2.5 text-[13px] text-stone-500">
        <span class="flex gap-1">
          <span class="w-1.5 h-1.5 rounded-full bg-coral-400 animate-bounce" style="animation-delay: 0ms"></span>
          <span class="w-1.5 h-1.5 rounded-full bg-coral-400 animate-bounce" style="animation-delay: 150ms"></span>
          <span class="w-1.5 h-1.5 rounded-full bg-coral-400 animate-bounce" style="animation-delay: 300ms"></span>
        </span>
        <span class="scan-text">{{ msg.retrieveLabel || "正在检索知识库…" }}</span>
      </div>

      <!-- 错误 -->
      <div
        v-else-if="msg.status === 'error'"
        class="rounded-2xl bg-gradient-to-br from-rose-50/70 to-paper-50 ring-1 ring-rose-200/60 p-4"
      >
        <div class="flex items-center gap-2 text-[13px] font-medium text-rose-600">
          <span class="inline-flex items-center justify-center w-5 h-5 rounded-full bg-rose-100 text-rose-500">
            <Icon name="alert" :size="12" />
          </span>
          请求未成功
        </div>
        <p class="mt-2 text-[12.5px] leading-relaxed text-stone-500">{{ msg.displayText }}</p>
      </div>

      <!-- 答案正文 -->
      <template v-else>
        <div class="md-body text-[14.5px]">
          <div v-html="html"></div>
          <span v-if="msg.phase === 'streaming'" class="stream-caret"></span>
        </div>

        <!-- 资料不足引导卡 -->
        <div
          v-if="msg.phase === 'done' && msg.status === 'insufficient'"
          class="mt-3.5 rounded-2xl bg-gradient-to-br from-amber-50/70 to-paper-50 ring-1 ring-amber-200/50 p-4"
        >
          <div class="flex items-center gap-2 text-[13px] font-medium text-amber-700">
            <span class="inline-flex items-center justify-center w-5 h-5 rounded-full bg-amber-100 text-amber-600">
              <Icon name="search" :size="12" />
            </span>
            知识库中相关内容有限
          </div>
          <p class="mt-2 text-[12.5px] leading-relaxed text-stone-500">
            为避免给出不准确的信息，系统没有进行推测。你可以试试下面的方式：
          </p>
          <div class="mt-3 flex flex-col gap-2">
            <button
              class="flex items-center gap-2.5 text-left px-3 py-2.5 rounded-xl bg-white/80 ring-1 ring-stone-200/70 text-[12.5px] text-stone-600 hover:ring-amber-300 hover:bg-white transition-all group"
              @click="emit('suggest-upload')"
            >
              <Icon name="upload" :size="14" class="text-amber-500 shrink-0" />
              <span class="flex-1">上传相关资料到知识库</span>
              <Icon name="chevronRight" :size="13" class="text-stone-300 group-hover:text-amber-400 group-hover:translate-x-0.5 transition-all" />
            </button>
            <button
              class="flex items-center gap-2.5 text-left px-3 py-2.5 rounded-xl bg-white/80 ring-1 ring-stone-200/70 text-[12.5px] text-stone-600 hover:ring-amber-300 hover:bg-white transition-all group"
              @click="emit('suggest-rephrase')"
            >
              <Icon name="edit" :size="14" class="text-amber-500 shrink-0" />
              <span class="flex-1">换个问法，使用资料里的关键词</span>
              <Icon name="chevronRight" :size="13" class="text-stone-300 group-hover:text-amber-400 group-hover:translate-x-0.5 transition-all" />
            </button>
          </div>
        </div>

        <!-- 来源展开 -->
        <div v-if="msg.phase === 'done' && msg.sources && msg.sources.length" class="mt-3.5">
          <button
            class="inline-flex items-center gap-2 pl-2 pr-3 h-8 rounded-full bg-white ring-1 ring-stone-200/80 text-[12.5px] text-stone-600 hover:ring-coral-300 hover:text-coral-600 shadow-[0_1px_2px_rgba(0,0,0,0.03)] transition-all group"
            @click="sourcesOpen = !sourcesOpen"
          >
            <span class="inline-flex items-center justify-center w-5 h-5 rounded-full bg-coral-50 text-coral-500">
              <Icon name="book" :size="12" />
            </span>
            参考了 <span class="font-semibold tabular-nums">{{ msg.sources.length }}</span> 处资料
            <span class="flex -space-x-1 ml-0.5">
              <span
                v-for="(s, i) in msg.sources.slice(0, 3)"
                :key="i"
                class="w-1.5 h-1.5 rounded-full bg-coral-300 ring-2 ring-white"
              ></span>
            </span>
            <Icon
              name="chevronDown"
              :size="13"
              class="text-stone-300 group-hover:text-coral-400 transition-transform"
              :class="sourcesOpen ? 'rotate-180' : ''"
            />
          </button>

          <div class="collapse-anim" :style="{ gridTemplateRows: sourcesOpen ? '1fr' : '0fr' }">
            <div class="overflow-hidden">
              <div class="mt-3 space-y-2 pt-0.5">
                <div
                  v-for="(s, i) in msg.sources"
                  :key="s.id || i"
                  class="source-card rounded-xl bg-white ring-1 ring-stone-200/70 p-3.5 hover:ring-stone-300/90 hover:shadow-[0_4px_16px_-8px_rgba(0,0,0,0.12)] transition-all"
                  :style="{ animationDelay: `${i * 70}ms` }"
                >
                  <div class="flex items-start gap-3">
                    <span
                      class="mt-0.5 inline-flex items-center justify-center w-6 h-6 rounded-md bg-coral-50 text-coral-600 text-[11px] font-semibold shrink-0"
                    >{{ i + 1 }}</span>
                    <div class="flex-1 min-w-0">
                      <div class="flex items-center gap-2 flex-wrap">
                        <span class="text-[13px] font-medium text-stone-800">{{ s.file }}</span>
                        <span v-if="s.loc" class="text-[11px] text-stone-400">· {{ s.loc }}</span>
                      </div>
                      <p class="mt-1.5 text-[12.5px] leading-relaxed text-stone-500 line-clamp-4">{{ s.quote }}</p>
                      <div class="mt-2.5 flex items-center gap-2">
                        <div class="flex-1 h-1 rounded-full bg-stone-100 overflow-hidden max-w-[120px]">
                          <div
                            class="h-full rounded-full bg-gradient-to-r from-coral-300 to-coral-500"
                            :style="{ width: pct(s.score) }"
                          ></div>
                        </div>
                        <span class="text-[11px] font-medium text-stone-400 tabular-nums">相关度 {{ pct(s.score) }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 操作条 -->
        <div
          v-if="msg.phase === 'done'"
          class="flex items-center gap-1 mt-3 -ml-1.5 opacity-0 group-hover/msg:opacity-100 transition-opacity"
        >
          <button
            title="复制"
            class="w-7 h-7 grid place-items-center rounded-lg text-stone-400 hover:bg-stone-200/50 hover:text-stone-600 transition-colors"
            @click="copy"
          >
            <Icon :name="copied ? 'check' : 'copy'" :size="15" :class="copied ? 'text-emerald-500' : ''" />
          </button>
        </div>
      </template>
    </div>
  </div>
</template>
