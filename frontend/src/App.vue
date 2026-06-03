<script setup>
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { toast } from "./lib/toast.js";
import Toast from "./components/Toast.vue";
import ConfirmDialog from "./components/ConfirmDialog.vue";
import Sidebar from "./components/Sidebar.vue";
import TopBar from "./components/TopBar.vue";
import ChatMessage from "./components/ChatMessage.vue";
import EmptyState from "./components/EmptyState.vue";
import Composer from "./components/Composer.vue";
import ModelPicker from "./components/ModelPicker.vue";
import SettingsModal from "./components/SettingsModal.vue";
import KBManager from "./components/KBManager.vue";

const STORAGE_KEY = "rag_thesis_conversations";
const MODEL_STORAGE_KEY = "rag_thesis_model";

const MODEL_META = {
  "deepseek-v4-flash": { name: "DeepSeek V4 Flash", desc: "快速响应 · 通用问答", badge: "推荐" },
  "deepseek-v4-pro": { name: "DeepSeek V4 Pro", desc: "更强推理 · 复杂问题" },
};
const SUGGESTION_CHIPS = ["这份资料的核心内容是什么？", "总结主要章节", "有哪些关键概念？"];

// ── UI 状态 ──
const collapsed = ref(false);
const mobileOpen = ref(false);
const kbOpen = ref(false);
const modelOpen = ref(false);
const settingsOpen = ref(false);

// ── 自定义确认框（替代 Element Plus 的 ElMessageBox）──
const confirmState = ref({ open: false, title: "", message: "", confirmText: "确定", cancelText: "取消", danger: false });
let confirmResolve = null;

function askConfirm(opts) {
  confirmState.value = { open: true, title: "确认操作", message: "", confirmText: "确定", cancelText: "取消", danger: false, ...opts };
  return new Promise((resolve) => {
    confirmResolve = resolve;
  });
}

function resolveConfirm(ok) {
  confirmState.value.open = false;
  if (confirmResolve) {
    confirmResolve(ok);
    confirmResolve = null;
  }
}

// ── 数据状态 ──
const model = ref(localStorage.getItem(MODEL_STORAGE_KEY) || "deepseek-v4-flash");
const modelOptions = ref([
  { value: "deepseek-v4-flash", label: "DeepSeek V4 Flash" },
  { value: "deepseek-v4-pro", label: "DeepSeek V4 Pro" },
]);
const ready = ref(false);
const apiKeySaved = ref(false);
const topK = ref(3);
const busy = ref(false);
const documents = ref([]);
const conversations = ref([]);
const activeConversationId = ref("");
const threadRef = ref(null);

let MSG_SEQ = 1;
const nextId = () => `${Date.now()}_${MSG_SEQ++}`;

// ── 计算属性 ──
const models = computed(() =>
  modelOptions.value.map((o) => {
    const meta = MODEL_META[o.value] || { name: o.label || o.value, desc: "" };
    return { id: o.value, name: meta.name, desc: meta.desc, badge: meta.badge };
  })
);
const currentModel = computed(
  () => models.value.find((m) => m.id === model.value) || { id: model.value, name: model.value, desc: "" }
);

const activeConversation = computed(
  () => conversations.value.find((c) => c.id === activeConversationId.value) || null
);
const messages = computed(() => activeConversation.value?.messages || []);

const kb = computed(() => {
  const docCount = documents.value.length;
  const chunkCount = documents.value.reduce((sum, d) => sum + (d.chunk_count || 0), 0);
  const indexed = documents.value.filter((d) => (d.chunk_count || 0) > 0).length;
  const health = docCount ? Math.round((indexed / docCount) * 100) : ready.value ? 100 : 0;
  const healthLabel = health >= 90 ? "良好" : health >= 60 ? "一般" : "待完善";
  return { name: "本地知识库", docCount, chunkCount, health, healthLabel };
});

// ── 生命周期 ──
onMounted(async () => {
  loadConversations();
  await checkHealth();
  await loadDocuments();
});

watch(model, (v) => localStorage.setItem(MODEL_STORAGE_KEY, v));
watch(
  [activeConversationId, () => messages.value.length],
  () => scrollBottom(),
  { flush: "post" }
);

// ── 对话管理（localStorage） ──
function makeConversation() {
  const now = new Date().toISOString();
  return { id: `chat_${Date.now()}_${Math.random().toString(16).slice(2)}`, title: "新对话", createdAt: now, updatedAt: now, messages: [] };
}
function loadConversations() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    conversations.value = Array.isArray(saved) ? saved : [];
  } catch {
    conversations.value = [];
  }
  // 归一化：历史消息一律视为 done
  for (const c of conversations.value) {
    for (const m of c.messages || []) {
      if (m.role === "assistant") m.phase = "done";
    }
  }
  if (!conversations.value.length) conversations.value = [makeConversation()];
  activeConversationId.value = conversations.value[0].id;
}
function saveConversations() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations.value));
}
function newChat() {
  if (busy.value) return;
  const blank = activeConversation.value && activeConversation.value.messages.length === 0;
  if (!blank) {
    const c = makeConversation();
    conversations.value.unshift(c);
    activeConversationId.value = c.id;
    saveConversations();
  }
  mobileOpen.value = false;
}
function selectConversation(id) {
  activeConversationId.value = id;
  mobileOpen.value = false;
}
function deleteConversation(id) {
  if (conversations.value.length <= 1) {
    const c = conversations.value[0];
    c.messages = [];
    c.title = "新对话";
    c.updatedAt = new Date().toISOString();
  } else {
    conversations.value = conversations.value.filter((c) => c.id !== id);
    if (activeConversationId.value === id) activeConversationId.value = conversations.value[0].id;
  }
  saveConversations();
}
function pushMessage(message) {
  const c = activeConversation.value;
  if (!c) return null;
  c.messages.push(message);
  c.updatedAt = new Date().toISOString();
  if (message.role === "user" && c.title === "新对话") {
    c.title = (message.text || "").slice(0, 22) || "新对话";
  }
  return c.messages[c.messages.length - 1];
}

// ── 后端交互 ──
async function checkHealth() {
  try {
    const data = await (await fetch("/api/health")).json();
    if (Array.isArray(data.models) && data.models.length) {
      modelOptions.value = data.models;
      const valid = new Set(data.models.map((o) => o.value));
      if (!valid.has(model.value)) model.value = data.model && valid.has(data.model) ? data.model : data.models[0].value;
    }
    if (typeof data.top_k === "number") topK.value = data.top_k;
    apiKeySaved.value = Boolean(data.api_key_saved);
    ready.value = Boolean(data.ready);
  } catch {
    ready.value = false;
  }
}
async function loadDocuments() {
  try {
    const data = await (await fetch("/api/documents")).json();
    documents.value = data.documents || [];
  } catch {
    documents.value = [];
  }
}
async function saveKey(key) {
  if (!key) {
    toast.warning("请先输入 DeepSeek API Key");
    return;
  }
  try {
    const res = await fetch("/api/settings/api-key", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key: key }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "保存失败");
    apiKeySaved.value = true;
    settingsOpen.value = false;
    toast.success("Key 已保存");
  } catch (error) {
    toast.error(error.message);
  }
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const v = String(reader.result || "");
      resolve(v.includes(",") ? v.split(",", 2)[1] : v);
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

async function uploadDocument(file) {
  if (busy.value) return;
  busy.value = true;
  try {
    const content_base64 = await fileToBase64(file);
    const res = await fetch("/api/documents", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename: file.name, title: file.name.replace(/\.[^.]+$/, ""), content_base64 }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "上传失败");
    toast.success(`已上传并索引，生成 ${data.chunk_count || 0} 个片段`);
    await loadDocuments();
  } catch (error) {
    toast.error(error.message);
  } finally {
    busy.value = false;
  }
}

async function replaceDocument({ id, file }) {
  if (busy.value) return;
  busy.value = true;
  try {
    const content_base64 = await fileToBase64(file);
    const res = await fetch(`/api/documents/${id}/replace`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename: file.name, content_base64 }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "替换失败");
    toast.success("替换完成，旧向量已删除");
    await loadDocuments();
  } catch (error) {
    toast.error(error.message);
  } finally {
    busy.value = false;
  }
}

async function deleteDocument(doc) {
  const ok = await askConfirm({
    title: "删除资料",
    message: `确定删除「${doc.title || doc.original_filename}」吗？对应向量会一起删除。`,
    confirmText: "删除",
    danger: true,
  });
  if (!ok) return;
  busy.value = true;
  try {
    const res = await fetch(`/api/documents/${doc.id}`, { method: "DELETE" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "删除失败");
    toast.success("资料已删除");
    await loadDocuments();
  } catch (error) {
    toast.error(error.message);
  } finally {
    busy.value = false;
  }
}

// ── 提问 + 流式渐显 ──
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function cleanAnswer(text = "") {
  return String(text)
    .split(/\r?\n/)
    .filter((line) => !/chunk\s*[_-]?\s*id/i.test(line))
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function chunkToSource(chunk, index) {
  let score = Number(chunk.relevance);
  if (!Number.isFinite(score)) {
    const d = Number(chunk.distance);
    score = Number.isFinite(d) ? 1 - d / 2 : 0;
  }
  return {
    id: chunk.chunk_id || `s${index}`,
    file: chunk.source || "资料",
    loc: chunk.section_title || "",
    score: Math.min(Math.max(score, 0), 1),
    quote: chunk.text || "",
  };
}

async function send(text) {
  if (busy.value) return;
  if (!apiKeySaved.value) {
    toast.warning("请先在设置中保存 DeepSeek API Key");
    settingsOpen.value = true;
    return;
  }
  busy.value = true;
  pushMessage({ id: nextId(), role: "user", text, time: new Date().toISOString() });
  const ai = pushMessage({
    id: nextId(),
    role: "assistant",
    phase: "retrieving",
    retrieveLabel: "正在检索知识库…",
    displayText: "",
    sources: [],
    status: "grounded",
    time: new Date().toISOString(),
  });
  await nextTick();
  scrollBottom();

  try {
    const res = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key: "", question: text, top_k: Number(topK.value) || 3, model: model.value }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "请求失败");

    const fullText = cleanAnswer(data.answer);
    const sources = (data.chunks || []).map(chunkToSource);
    const status = data.refused ? "insufficient" : "grounded";

    // 渐显（对真实答案做打字机效果）
    ai.phase = "streaming";
    ai.displayText = "";
    const step = Math.max(2, Math.round(fullText.length / 120));
    for (let i = 0; i <= fullText.length; i += step) {
      ai.displayText = fullText.slice(0, i);
      scrollBottom();
      await sleep(14);
    }
    ai.phase = "done";
    ai.displayText = fullText;
    ai.sources = sources;
    ai.status = status;
  } catch (error) {
    ai.phase = "done";
    ai.status = "error";
    ai.displayText = error.message || "请求失败";
    ai.sources = [];
  } finally {
    busy.value = false;
    saveConversations();
    scrollBottom();
  }
}

function onSelectModel(id) {
  model.value = id;
  modelOpen.value = false;
}

async function scrollBottom() {
  await nextTick();
  const el = threadRef.value;
  if (!el) return;
  requestAnimationFrame(() => {
    el.scrollTop = el.scrollHeight;
  });
}
</script>

<template>
  <div class="h-screen w-screen flex bg-paper-50 overflow-hidden text-stone-800">
    <!-- 桌面侧栏 -->
    <div class="hidden md:flex h-full">
      <Sidebar
        :collapsed="collapsed"
        :kb="kb"
        :conversations="conversations"
        :active-id="activeConversationId"
        :model="currentModel"
        @toggle="collapsed = !collapsed"
        @new-chat="newChat"
        @open-kb="kbOpen = true"
        @open-model="modelOpen = true"
        @select="selectConversation"
        @delete="deleteConversation"
      />
    </div>

    <!-- 移动侧栏 -->
    <div v-if="mobileOpen" class="md:hidden fixed inset-0 z-50 flex">
      <div class="absolute inset-0 bg-stone-900/30 backdrop-blur-[2px] animate-fade-in" @click="mobileOpen = false"></div>
      <div class="relative animate-slide-left">
        <Sidebar
          :collapsed="false"
          :kb="kb"
          :conversations="conversations"
          :active-id="activeConversationId"
          :model="currentModel"
          @toggle="mobileOpen = false"
          @new-chat="newChat"
          @open-kb="kbOpen = true"
          @open-model="modelOpen = true"
          @select="selectConversation"
          @delete="deleteConversation"
        />
      </div>
    </div>

    <!-- 主区 -->
    <main class="flex-1 min-w-0 flex flex-col h-full">
      <TopBar
        :kb-name="kb.name"
        :model="currentModel"
        :ready="ready"
        @open-mobile="mobileOpen = true"
        @open-model="modelOpen = true"
        @open-kb="kbOpen = true"
        @open-settings="settingsOpen = true"
      />

      <div ref="threadRef" class="flex-1 overflow-y-auto thread-scroll">
        <EmptyState
          v-if="!messages.length"
          :kb-name="kb.name"
          :doc-count="kb.docCount"
          :chips="SUGGESTION_CHIPS"
          @suggest="send"
        />
        <div v-else class="max-w-3xl mx-auto px-5 py-8 space-y-7">
          <ChatMessage
            v-for="m in messages"
            :key="m.id"
            :msg="m"
            @suggest-upload="kbOpen = true"
            @suggest-rephrase="toast.info('试着用资料里的关键词重新提问')"
          />
          <div class="h-2"></div>
        </div>
      </div>

      <Composer :busy="busy" :model="currentModel" @send="send" @open-model="modelOpen = true" />
    </main>

    <ModelPicker
      :open="modelOpen"
      :models="models"
      :current="model"
      @close="modelOpen = false"
      @select="onSelectModel"
    />
    <SettingsModal
      :open="settingsOpen"
      :api-key-saved="apiKeySaved"
      :top-k="topK"
      @close="settingsOpen = false"
      @save-key="saveKey"
      @update-top-k="(v) => (topK = v)"
    />
    <KBManager
      :open="kbOpen"
      :kb="kb"
      :documents="documents"
      :busy="busy"
      @close="kbOpen = false"
      @upload="uploadDocument"
      @replace="replaceDocument"
      @delete="deleteDocument"
      @refresh="loadDocuments"
    />

    <ConfirmDialog
      :open="confirmState.open"
      :title="confirmState.title"
      :message="confirmState.message"
      :confirm-text="confirmState.confirmText"
      :cancel-text="confirmState.cancelText"
      :danger="confirmState.danger"
      @confirm="resolveConfirm(true)"
      @cancel="resolveConfirm(false)"
    />
    <Toast />
  </div>
</template>
