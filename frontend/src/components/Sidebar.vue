<script setup>
import { computed, ref } from "vue";
import Icon from "./Icon.vue";
import HealthRing from "./HealthRing.vue";

const props = defineProps({
  collapsed: { type: Boolean, default: false },
  kb: { type: Object, required: true },
  conversations: { type: Array, default: () => [] },
  activeId: { type: String, default: "" },
  model: { type: Object, required: true },
});

const emit = defineEmits(["toggle", "new-chat", "open-kb", "open-model", "select", "delete"]);

const query = ref("");

const GROUP_ORDER = ["今天", "昨天", "本周", "更早"];

function groupOf(updatedAt) {
  const now = new Date();
  const d = new Date(updatedAt);
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const t = d.getTime();
  if (t >= startOfToday) return "今天";
  if (t >= startOfToday - 86400000) return "昨天";
  if (t >= startOfToday - 6 * 86400000) return "本周";
  return "更早";
}

const filtered = computed(() =>
  props.conversations.filter((c) => (c.title || "").includes(query.value.trim()))
);

const grouped = computed(() => {
  const buckets = {};
  for (const c of filtered.value) {
    const g = groupOf(c.updatedAt);
    (buckets[g] ||= []).push(c);
  }
  return GROUP_ORDER.filter((g) => buckets[g]?.length).map((g) => ({ group: g, items: buckets[g] }));
});
</script>

<template>
  <!-- 折叠态：图标轨道 -->
  <aside
    v-if="collapsed"
    class="h-full w-[64px] shrink-0 bg-paper-100 border-r border-stone-200/70 flex flex-col items-center py-4 gap-2"
  >
    <button
      title="展开侧栏"
      class="w-10 h-10 grid place-items-center rounded-xl text-stone-500 hover:bg-stone-200/60 hover:text-stone-800 transition-colors"
      @click="emit('toggle')"
    >
      <Icon name="panelLeft" :size="19" />
    </button>
    <button
      title="新建对话"
      class="w-10 h-10 grid place-items-center rounded-xl bg-coral-500 text-white shadow-sm shadow-coral-500/25 hover:bg-coral-600 transition-colors"
      @click="emit('new-chat')"
    >
      <Icon name="plus" :size="19" />
    </button>
    <button
      title="知识库"
      class="w-10 h-10 grid place-items-center rounded-xl text-stone-500 hover:bg-stone-200/60 hover:text-stone-800 transition-colors"
      @click="emit('open-kb')"
    >
      <Icon name="layers" :size="19" />
    </button>
    <div class="mt-auto">
      <div class="w-9 h-9 rounded-full bg-stone-800 grid place-items-center text-white text-xs font-semibold">
        教
      </div>
    </div>
  </aside>

  <!-- 展开态 -->
  <aside
    v-else
    class="h-full w-[286px] shrink-0 bg-paper-100 border-r border-stone-200/70 flex flex-col"
  >
    <!-- Logo -->
    <div class="flex items-center gap-2.5 px-4 h-[60px] shrink-0">
      <div
        class="w-8 h-8 rounded-[10px] bg-gradient-to-br from-coral-400 to-coral-600 grid place-items-center shadow-sm shadow-coral-500/30 shrink-0"
      >
        <Icon name="layers" :size="17" class="text-white" />
      </div>
      <div class="flex-1 min-w-0">
        <div class="text-[15px] font-semibold text-stone-800 leading-tight">RAG 知识库</div>
        <div class="text-[11px] text-stone-400 leading-tight">本地检索增强问答</div>
      </div>
      <button
        title="收起侧栏"
        class="w-8 h-8 grid place-items-center rounded-lg text-stone-400 hover:bg-stone-200/60 hover:text-stone-700 transition-colors"
        @click="emit('toggle')"
      >
        <Icon name="panelLeft" :size="18" />
      </button>
    </div>

    <!-- 新建对话 -->
    <div class="px-3 pb-2">
      <button
        class="w-full flex items-center gap-2.5 px-3.5 h-10 rounded-xl bg-white ring-1 ring-stone-200/80 text-stone-700 text-sm font-medium shadow-[0_1px_2px_rgba(0,0,0,0.03)] hover:ring-coral-300 hover:text-coral-600 transition-all group"
        @click="emit('new-chat')"
      >
        <Icon name="plus" :size="17" class="text-stone-400 group-hover:text-coral-500 transition-colors" />
        新建对话
      </button>
    </div>

    <!-- 知识库状态卡 -->
    <div class="px-3 pb-2">
      <button
        class="w-full text-left rounded-2xl bg-white ring-1 ring-stone-200/70 p-3.5 shadow-[0_1px_2px_rgba(0,0,0,0.03)] hover:ring-stone-300/90 hover:shadow-[0_4px_16px_-6px_rgba(0,0,0,0.1)] transition-all group"
        @click="emit('open-kb')"
      >
        <div class="flex items-center gap-3">
          <HealthRing :value="kb.health" />
          <div class="flex-1 min-w-0">
            <div class="text-[13px] font-semibold text-stone-800 truncate">{{ kb.name }}</div>
            <div class="text-[11.5px] text-stone-400 mt-0.5">向量库健康度 · {{ kb.healthLabel }}</div>
          </div>
          <Icon
            name="chevronRight"
            :size="15"
            class="text-stone-300 group-hover:text-stone-500 group-hover:translate-x-0.5 transition-all"
          />
        </div>
        <div class="grid grid-cols-2 gap-2 mt-3">
          <div class="rounded-lg bg-stone-50 px-2.5 py-2">
            <div class="text-[15px] font-semibold text-stone-700 tabular-nums leading-none">
              {{ kb.docCount }}
            </div>
            <div class="text-[10.5px] text-stone-400 mt-1">份资料</div>
          </div>
          <div class="rounded-lg bg-stone-50 px-2.5 py-2">
            <div class="text-[15px] font-semibold text-stone-700 tabular-nums leading-none">
              {{ kb.chunkCount }}
            </div>
            <div class="text-[10.5px] text-stone-400 mt-1">向量片段</div>
          </div>
        </div>
      </button>
    </div>

    <!-- 历史搜索 -->
    <div class="px-3 pt-2 pb-1.5">
      <div class="relative">
        <Icon name="search" :size="15" class="absolute left-3 top-1/2 -translate-y-1/2 text-stone-300" />
        <input
          v-model="query"
          placeholder="搜索对话"
          class="w-full h-9 pl-9 pr-3 rounded-lg bg-stone-100/70 text-[13px] text-stone-700 placeholder:text-stone-400 outline-none focus:bg-white focus:ring-1 focus:ring-stone-300 transition-all"
        >
      </div>
    </div>

    <!-- 历史列表 -->
    <nav class="flex-1 overflow-y-auto px-2 pb-2 sidebar-scroll">
      <div v-if="!grouped.length" class="text-center text-[12px] text-stone-400 py-8">
        没有匹配的对话
      </div>
      <div v-for="bucket in grouped" :key="bucket.group" class="mb-1">
        <div class="px-2.5 pt-3 pb-1.5 text-[11px] font-medium text-stone-400">{{ bucket.group }}</div>
        <a
          v-for="item in bucket.items"
          :key="item.id"
          href="#"
          class="group flex items-center gap-2 px-2.5 h-9 rounded-lg text-[13px] transition-colors"
          :class="
            item.id === activeId
              ? 'bg-coral-50 text-coral-700 font-medium'
              : 'text-stone-600 hover:bg-stone-200/50'
          "
          @click.prevent="emit('select', item.id)"
        >
          <Icon
            name="message"
            :size="14"
            :class="item.id === activeId ? 'text-coral-400' : 'text-stone-300 group-hover:text-stone-400'"
          />
          <span class="flex-1 min-w-0 truncate">{{ item.title || "新对话" }}</span>
          <button
            class="opacity-0 group-hover:opacity-100 w-6 h-6 -mr-1 grid place-items-center rounded-md hover:bg-white/70 hover:text-rose-500"
            :class="item.id === activeId ? 'text-coral-400' : 'text-stone-400'"
            title="删除对话"
            @click.prevent.stop="emit('delete', item.id)"
          >
            <Icon name="trash" :size="14" />
          </button>
        </a>
      </div>
    </nav>

    <!-- 底部模型条 -->
    <div class="px-3 py-3 border-t border-stone-200/70">
      <button
        class="w-full flex items-center gap-2.5 px-3 h-12 rounded-xl hover:bg-stone-200/40 transition-colors group"
        @click="emit('open-model')"
      >
        <div class="w-8 h-8 rounded-lg bg-stone-800 grid place-items-center text-white shrink-0">
          <Icon name="cpu" :size="16" />
        </div>
        <div class="flex-1 min-w-0 text-left">
          <div class="text-[12.5px] font-semibold text-stone-800 truncate">{{ model.name }}</div>
          <div class="text-[11px] text-stone-400 truncate">{{ model.desc }}</div>
        </div>
        <Icon name="chevronDown" :size="15" class="text-stone-300 group-hover:text-stone-500 transition-colors" />
      </button>
    </div>
  </aside>
</template>
