<script setup>
import { ref, watch } from "vue";
import Icon from "./Icon.vue";
import FileTypeBadge from "./FileTypeBadge.vue";

const props = defineProps({
  open: { type: Boolean, default: false },
  kb: { type: Object, required: true },
  documents: { type: Array, default: () => [] },
  busy: { type: Boolean, default: false },
});
const emit = defineEmits(["close", "upload", "replace", "delete", "refresh"]);

const dragOver = ref(false);
const uploadInput = ref(null);
const replaceInput = ref(null);
const replaceTarget = ref(null);

// 文档详情（版本历史 / 索引状态 / chunk 预览）
const detail = ref(null);
const detailLoading = ref(false);
const detailError = ref("");

async function openDetail(doc) {
  detail.value = null;
  detailError.value = "";
  detailLoading.value = true;
  try {
    const res = await fetch(`/api/documents/${doc.id}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    detail.value = await res.json();
  } catch (err) {
    detailError.value = "加载详情失败，请稍后重试。";
  } finally {
    detailLoading.value = false;
  }
}

function closeDetail() {
  detail.value = null;
  detailError.value = "";
}

// 抽屉关闭后重置详情，下次打开回到资料清单
watch(
  () => props.open,
  (open) => {
    if (!open) closeDetail();
  },
);

// 版本状态 → 展示样式（已索引 / 处理中 / 失败 / 历史版本）
function versionStatus(v) {
  const map = {
    indexed: { label: "已索引", cls: "text-emerald-600 bg-emerald-50" },
    pending: { label: "处理中", cls: "text-amber-600 bg-amber-50" },
    failed: { label: "失败", cls: "text-rose-600 bg-rose-50" },
    archived: { label: "历史版本", cls: "text-stone-500 bg-stone-100" },
  };
  return map[v.status] || { label: v.status || "未知", cls: "text-stone-500 bg-stone-100" };
}

function extOf(doc) {
  const ext = (doc.file_ext || "").replace(/^\./, "").toLowerCase();
  if (ext) return ext;
  const name = doc.original_filename || "";
  const m = name.match(/\.([^.]+)$/);
  return m ? m[1].toLowerCase() : "";
}

function formatSize(size) {
  const v = Number(size);
  if (!Number.isFinite(v)) return "-";
  if (v < 1024) return `${v} B`;
  if (v < 1024 * 1024) return `${(v / 1024).toFixed(1)} KB`;
  return `${(v / 1024 / 1024).toFixed(1)} MB`;
}

function formatDate(value) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(d);
}

function onDrop(e) {
  dragOver.value = false;
  const file = e.dataTransfer?.files?.[0];
  if (file) emit("upload", file);
}

function onUploadPick(e) {
  const file = e.target.files?.[0];
  e.target.value = "";
  if (file) emit("upload", file);
}

function openReplace(doc) {
  replaceTarget.value = doc;
  replaceInput.value?.click();
}

function onReplacePick(e) {
  const file = e.target.files?.[0];
  e.target.value = "";
  const target = replaceTarget.value;
  replaceTarget.value = null;
  if (file && target) emit("replace", { id: target.id, file });
}
</script>

<template>
  <div v-if="open" class="fixed inset-0 z-50 flex justify-end">
    <div class="absolute inset-0 bg-stone-900/25 backdrop-blur-[2px] animate-fade-in" @click="emit('close')"></div>
    <div
      class="relative w-full max-w-[440px] h-full bg-paper-50 shadow-2xl shadow-stone-900/20 flex flex-col animate-slide-in"
    >
      <!-- 头 -->
      <div class="h-[60px] shrink-0 flex items-center gap-3 px-5 border-b border-stone-200/60">
        <span class="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-coral-50 text-coral-500">
          <Icon name="layers" :size="17" />
        </span>
        <div class="flex-1 min-w-0">
          <div class="text-[15px] font-semibold text-stone-800 truncate">{{ kb.name }}</div>
          <div class="text-[11.5px] text-stone-400">知识库管理</div>
        </div>
        <button
          class="w-9 h-9 grid place-items-center rounded-lg text-stone-400 hover:bg-stone-200/50 hover:text-stone-700 transition-colors"
          @click="emit('refresh')"
          title="刷新"
        >
          <Icon name="refresh" :size="17" />
        </button>
        <button
          class="w-9 h-9 grid place-items-center rounded-lg text-stone-400 hover:bg-stone-200/50 hover:text-stone-700 transition-colors"
          @click="emit('close')"
        >
          <Icon name="x" :size="18" />
        </button>
      </div>

      <div class="flex-1 overflow-y-auto sidebar-scroll p-5">
        <!-- 资料清单视图 -->
        <template v-if="!detail && !detailLoading && !detailError">
        <!-- 概览 -->
        <div class="grid grid-cols-3 gap-2.5 mb-5">
          <div class="rounded-xl bg-white ring-1 ring-stone-200/70 px-3 py-3 text-center">
            <div class="text-[18px] font-semibold text-stone-800 tabular-nums leading-none">{{ kb.docCount }}</div>
            <div class="text-[11px] text-stone-400 mt-1.5">份资料</div>
          </div>
          <div class="rounded-xl bg-white ring-1 ring-stone-200/70 px-3 py-3 text-center">
            <div class="text-[18px] font-semibold text-stone-800 tabular-nums leading-none">{{ kb.chunkCount }}</div>
            <div class="text-[11px] text-stone-400 mt-1.5">向量片段</div>
          </div>
          <div class="rounded-xl bg-white ring-1 ring-stone-200/70 px-3 py-3 text-center">
            <div class="text-[18px] font-semibold text-stone-800 tabular-nums leading-none">{{ kb.health }}%</div>
            <div class="text-[11px] text-stone-400 mt-1.5">健康度</div>
          </div>
        </div>

        <!-- 上传区 -->
        <button
          class="w-full rounded-2xl border-2 border-dashed py-6 flex flex-col items-center gap-2 transition-all mb-5 group"
          :class="
            dragOver
              ? 'border-coral-300 bg-coral-50/40 text-coral-500'
              : 'border-stone-300/70 bg-white/50 text-stone-400 hover:border-coral-300 hover:text-coral-500 hover:bg-coral-50/30'
          "
          :disabled="busy"
          @click="uploadInput?.click()"
          @dragover.prevent="dragOver = true"
          @dragleave.prevent="dragOver = false"
          @drop.prevent="onDrop"
        >
          <span
            class="w-11 h-11 rounded-xl grid place-items-center transition-colors"
            :class="dragOver ? 'bg-coral-100' : 'bg-stone-100 group-hover:bg-coral-100'"
          >
            <Icon name="upload" :size="20" class="group-hover:text-coral-500 transition-colors" />
          </span>
          <span class="text-[13px] font-medium text-stone-600 group-hover:text-coral-600">
            {{ busy ? "正在处理…" : "拖拽文件到此 或 点击上传" }}
          </span>
          <span class="text-[11.5px] text-stone-400">支持 PDF · Word · Markdown · TXT</span>
        </button>
        <input
          ref="uploadInput"
          type="file"
          accept=".docx,.pdf,.txt,.md"
          class="hidden"
          @change="onUploadPick"
        >
        <input
          ref="replaceInput"
          type="file"
          accept=".docx,.pdf,.txt,.md"
          class="hidden"
          @change="onReplacePick"
        >

        <!-- 资料清单 -->
        <div class="flex items-center justify-between mb-2.5">
          <span class="text-[12.5px] font-medium text-stone-500">资料清单</span>
          <span class="text-[11.5px] text-stone-400">{{ documents.length }} 项</span>
        </div>

        <div v-if="documents.length" class="space-y-2">
          <div
            v-for="doc in documents"
            :key="doc.id"
            class="group flex items-center gap-3 rounded-xl bg-white ring-1 ring-stone-200/70 px-3 py-2.5 hover:ring-stone-300/90 transition-all"
          >
            <button
              class="flex items-center gap-3 flex-1 min-w-0 text-left"
              title="查看详情"
              @click="openDetail(doc)"
            >
              <FileTypeBadge :type="extOf(doc)" />
              <div class="flex-1 min-w-0">
                <div class="text-[13px] font-medium text-stone-800 truncate group-hover:text-coral-600 transition-colors">
                  {{ doc.title || doc.original_filename || "未命名资料" }}
                </div>
                <div class="flex items-center gap-2 mt-0.5 text-[11px] text-stone-400">
                  <span>{{ formatSize(doc.file_size) }}</span><span>·</span>
                  <span>{{ doc.chunk_count || 0 }} 片段</span><span>·</span>
                  <span>{{ formatDate(doc.indexed_at) }}</span>
                </div>
              </div>
            </button>

            <span
              v-if="(doc.chunk_count || 0) > 0"
              class="flex items-center gap-1 text-[11px] text-emerald-600 shrink-0 group-hover:hidden"
            >
              <Icon name="check" :size="13" />就绪
            </span>
            <span v-else class="flex items-center gap-1 text-[11px] text-amber-600 shrink-0 group-hover:hidden">
              <span class="w-3 h-3 border-2 border-amber-300 border-t-amber-500 rounded-full animate-spin"></span>处理中
            </span>

            <div class="hidden group-hover:flex items-center gap-1 shrink-0">
              <button
                title="替换"
                class="w-7 h-7 grid place-items-center rounded-lg text-stone-400 hover:bg-coral-50 hover:text-coral-500 transition-colors"
                :disabled="busy"
                @click="openReplace(doc)"
              >
                <Icon name="edit" :size="15" />
              </button>
              <button
                title="删除"
                class="w-7 h-7 grid place-items-center rounded-lg text-stone-400 hover:bg-rose-50 hover:text-rose-500 transition-colors"
                :disabled="busy"
                @click="emit('delete', doc)"
              >
                <Icon name="trash" :size="15" />
              </button>
            </div>
          </div>
        </div>

        <div v-else class="text-center text-[12.5px] text-stone-400 py-10">还没有登记资料</div>
        </template>

        <!-- 详情视图：版本历史 / 索引状态 / chunk 预览 -->
        <template v-else>
          <button
            class="flex items-center gap-1.5 text-[12.5px] text-stone-500 hover:text-coral-600 transition-colors mb-4"
            @click="closeDetail"
          >
            <Icon name="x" :size="14" /> 返回清单
          </button>

          <div v-if="detailLoading" class="text-center text-[12.5px] text-stone-400 py-10">
            正在加载详情…
          </div>
          <div v-else-if="detailError" class="text-center text-[12.5px] text-rose-500 py-10">
            {{ detailError }}
          </div>

          <template v-else-if="detail">
            <!-- 元数据 -->
            <div class="rounded-xl bg-white ring-1 ring-stone-200/70 px-4 py-3.5 mb-5">
              <div class="text-[14px] font-semibold text-stone-800 break-all">
                {{ detail.document.title || (detail.versions[0] && detail.versions[0].original_filename) || "未命名资料" }}
              </div>
              <div class="grid grid-cols-2 gap-y-1.5 gap-x-3 mt-3 text-[11.5px]">
                <div class="text-stone-400">片段数<span class="text-stone-700 ml-1.5 tabular-nums">{{ (detail.chunks || []).length }}</span></div>
                <div class="text-stone-400">版本数<span class="text-stone-700 ml-1.5 tabular-nums">{{ (detail.versions || []).length }}</span></div>
                <div class="text-stone-400">向量模型<span class="text-stone-700 ml-1.5">{{ (detail.versions[0] && detail.versions[0].embedding_model) || "—" }}</span></div>
                <div class="text-stone-400">索引时间<span class="text-stone-700 ml-1.5">{{ formatDate(detail.versions[0] && detail.versions[0].indexed_at) }}</span></div>
              </div>
            </div>

            <!-- 版本历史 -->
            <div class="text-[12.5px] font-medium text-stone-500 mb-2.5">版本历史</div>
            <div class="space-y-2 mb-5">
              <div
                v-for="v in detail.versions"
                :key="v.id"
                class="rounded-xl bg-white ring-1 ring-stone-200/70 px-3 py-2.5"
              >
                <div class="flex items-center gap-2">
                  <span class="text-[12.5px] font-medium text-stone-800 truncate flex-1 min-w-0">{{ v.original_filename }}</span>
                  <span class="shrink-0 px-1.5 py-0.5 rounded text-[10.5px] font-medium" :class="versionStatus(v).cls">
                    {{ versionStatus(v).label }}
                  </span>
                </div>
                <div class="flex items-center gap-2 mt-1 text-[11px] text-stone-400">
                  <span>{{ formatSize(v.file_size) }}</span><span>·</span>
                  <span>{{ v.chunk_count || 0 }} 片段</span><span>·</span>
                  <span>{{ formatDate(v.created_at) }}</span>
                </div>
                <div v-if="v.parse_error" class="mt-1.5 text-[11px] text-rose-500 break-all">
                  失败原因：{{ v.parse_error }}
                </div>
              </div>
            </div>

            <!-- 切块预览 -->
            <div class="text-[12.5px] font-medium text-stone-500 mb-2.5">
              切块预览<span class="text-stone-400 font-normal ml-1">（当前版本 {{ (detail.chunks || []).length }} 段）</span>
            </div>
            <div v-if="(detail.chunks || []).length" class="space-y-2">
              <div
                v-for="c in detail.chunks"
                :key="c.chunk_index"
                class="rounded-xl bg-white ring-1 ring-stone-200/70 px-3 py-2.5"
              >
                <div class="flex items-center gap-2 mb-1">
                  <span class="shrink-0 w-5 h-5 grid place-items-center rounded bg-stone-100 text-[10.5px] text-stone-500 tabular-nums">{{ c.chunk_index }}</span>
                  <span class="text-[12px] font-medium text-stone-700 truncate flex-1 min-w-0">{{ c.section_title || "（无章节标题）" }}</span>
                  <span class="shrink-0 text-[10.5px] text-stone-400 tabular-nums">{{ c.char_count || 0 }} 字</span>
                </div>
                <div class="text-[11.5px] text-stone-500 leading-relaxed line-clamp-3">{{ c.text_preview }}</div>
              </div>
            </div>
            <div v-else class="text-center text-[12.5px] text-stone-400 py-8">该版本暂无切块记录</div>
          </template>
        </template>
      </div>
    </div>
  </div>
</template>
