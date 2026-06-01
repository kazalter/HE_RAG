<script setup>
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  ArrowDown,
  ArrowUp,
  ChatDotRound,
  ChatLineRound,
  Delete,
  Document,
  EditPen,
  Files,
  Key,
  Plus,
  Refresh,
  Search,
  Setting,
  UploadFilled,
} from "@element-plus/icons-vue";

const STORAGE_KEY = "rag_thesis_conversations";
const MODEL_STORAGE_KEY = "rag_thesis_model";

const apiKey = ref(sessionStorage.getItem("deepseek_api_key") || "");
const apiKeySaved = ref(false);
const question = ref("");
const topK = ref(3);
const status = ref("正在连接服务...");
const model = ref(localStorage.getItem(MODEL_STORAGE_KEY) || "deepseek-v4-flash");
const modelOptions = ref([
  { value: "deepseek-v4-flash", label: "DeepSeek V4 Flash" },
  { value: "deepseek-v4-pro", label: "DeepSeek V4 Pro" },
]);
const loading = ref(false);
const documentLoading = ref(false);
const settingsOpen = ref(false);
const activeSettingsTab = ref("chat");
const conversations = ref([]);
const activeConversationId = ref("");
const expandedSourceMessages = ref(new Set());
const chatAreaRef = ref(null);
const documents = ref([]);
const uploadFile = ref(null);
const replaceFileInput = ref(null);
const replaceTarget = ref(null);

const hasApiKey = computed(() => apiKeySaved.value || Boolean(apiKey.value.trim()));
const documentCount = computed(() => documents.value.length);

const activeConversation = computed(() => {
  return conversations.value.find((item) => item.id === activeConversationId.value) || null;
});

const messages = computed(() => activeConversation.value?.messages || []);
const isBlankActiveConversation = computed(() => {
  const conversation = activeConversation.value;
  return Boolean(conversation && conversation.messages.length === 0);
});

const canAsk = computed(() => {
  return hasApiKey.value && question.value.trim() && !loading.value;
});

const askButtonText = computed(() => {
  if (loading.value) return "生成中";
  if (!hasApiKey.value) return "先填 Key";
  if (!question.value.trim()) return "输入问题";
  return "提问";
});

onMounted(async () => {
  loadConversations();
  await checkHealth();
  await loadDocuments();
  scrollChatToBottom();
});

watch(model, (value) => {
  localStorage.setItem(MODEL_STORAGE_KEY, value);
});

watch(
  [activeConversationId, () => messages.value.length],
  () => {
    scrollChatToBottom();
  },
  { flush: "post" }
);

function makeConversation(title = "新对话") {
  const now = new Date().toISOString();
  return {
    id: `chat_${Date.now()}_${Math.random().toString(16).slice(2)}`,
    title,
    createdAt: now,
    updatedAt: now,
    messages: [],
  };
}

function loadConversations() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    conversations.value = Array.isArray(saved) ? saved : [];
  } catch {
    conversations.value = [];
  }

  if (!conversations.value.length) {
    conversations.value = [makeConversation()];
  }
  activeConversationId.value = conversations.value[0].id;
}

function saveConversations() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations.value));
}

function newConversation() {
  if (isBlankActiveConversation.value) {
    question.value = "";
    scrollChatToTop();
    return;
  }

  const conversation = makeConversation();
  conversations.value.unshift(conversation);
  activeConversationId.value = conversation.id;
  question.value = "";
  saveConversations();
  scrollChatToTop();
}

function selectConversation(id) {
  activeConversationId.value = id;
  question.value = "";
  scrollChatToBottom();
}

async function deleteConversation(id) {
  if (conversations.value.length <= 1) {
    conversations.value[0].messages = [];
    conversations.value[0].title = "新对话";
    conversations.value[0].updatedAt = new Date().toISOString();
    saveConversations();
    return;
  }

  conversations.value = conversations.value.filter((item) => item.id !== id);
  if (activeConversationId.value === id) {
    activeConversationId.value = conversations.value[0].id;
  }
  saveConversations();
  scrollChatToBottom();
}

function pushMessage(message) {
  const conversation = activeConversation.value;
  if (!conversation) return;

  conversation.messages.push(message);
  conversation.updatedAt = new Date().toISOString();
  if (message.type === "user" && conversation.title === "新对话") {
    conversation.title = message.text.slice(0, 22) || "新对话";
  }
  saveConversations();
}

async function checkHealth() {
  try {
    const response = await fetch("/api/health");
    const data = await response.json();
    const savedModel = localStorage.getItem(MODEL_STORAGE_KEY);
    if (Array.isArray(data.models) && data.models.length) {
      modelOptions.value = data.models;
      const availableModels = new Set(data.models.map((option) => option.value));
      if (savedModel && availableModels.has(savedModel)) {
        model.value = savedModel;
      } else if (data.model && availableModels.has(data.model)) {
        model.value = data.model;
      } else if (!availableModels.has(model.value)) {
        model.value = data.models[0].value;
      }
    } else if (!savedModel && data.model) {
      model.value = data.model;
    }
    apiKeySaved.value = Boolean(data.api_key_saved);
    status.value = data.ready ? "向量库已加载" : "服务加载中";
  } catch {
    status.value = "后端服务未连接";
  }
}

async function loadDocuments() {
  try {
    const response = await fetch("/api/documents");
    const data = await response.json();
    documents.value = data.documents || [];
  } catch {
    documents.value = [];
  }
}

async function saveKey() {
  const trimmedKey = apiKey.value.trim();
  if (!trimmedKey) {
    ElMessage.warning("请先输入 DeepSeek API Key");
    return;
  }

  try {
    const response = await fetch("/api/settings/api-key", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key: trimmedKey }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "保存失败");
    }
    sessionStorage.removeItem("deepseek_api_key");
    apiKey.value = "";
    apiKeySaved.value = true;
    status.value = "DeepSeek API Key 已永久保存";
    ElMessage.success("Key 已永久保存");
  } catch (error) {
    ElMessage.error(error.message);
  }
}

function clearChat() {
  const conversation = activeConversation.value;
  if (!conversation) return;
  conversation.messages = [];
  conversation.title = "新对话";
  conversation.updatedAt = new Date().toISOString();
  question.value = "";
  saveConversations();
}

function onUploadFileChange(uploadFileItem) {
  uploadFile.value = uploadFileItem.raw || null;
}

function onUploadRemove() {
  uploadFile.value = null;
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const value = String(reader.result || "");
      resolve(value.includes(",") ? value.split(",", 2)[1] : value);
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

async function uploadDocument() {
  if (!uploadFile.value || documentLoading.value) return;

  documentLoading.value = true;
  status.value = "正在上传并写入向量...";
  try {
    const file = uploadFile.value;
    const contentBase64 = await fileToBase64(file);
    const response = await fetch("/api/documents", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        filename: file.name,
        title: file.name.replace(/\.[^.]+$/, ""),
        content_base64: contentBase64,
      }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "上传失败");
    }
    status.value = `已上传，生成 ${data.chunk_count || 0} 个 chunk`;
    uploadFile.value = null;
    ElMessage.success("资料已上传并索引");
    await loadDocuments();
  } catch (error) {
    status.value = error.message;
    ElMessage.error(error.message);
  } finally {
    documentLoading.value = false;
  }
}

function openReplacePicker(document) {
  if (documentLoading.value) return;
  replaceTarget.value = document;
  replaceFileInput.value?.click();
}

async function onReplaceFileChange(event) {
  const file = event.target.files?.[0];
  event.target.value = "";
  const document = replaceTarget.value;
  replaceTarget.value = null;
  if (!file || !document || documentLoading.value) return;

  documentLoading.value = true;
  status.value = `正在替换 ${document.title}...`;
  try {
    const contentBase64 = await fileToBase64(file);
    const response = await fetch(`/api/documents/${document.id}/replace`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        filename: file.name,
        content_base64: contentBase64,
      }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "替换失败");
    }
    status.value = `替换完成，旧向量已删除，新生成 ${data.chunk_count || 0} 个 chunk`;
    ElMessage.success("替换完成，旧向量已删除");
    await loadDocuments();
  } catch (error) {
    status.value = error.message;
    ElMessage.error(error.message);
  } finally {
    documentLoading.value = false;
  }
}

async function deleteDocument(document) {
  if (documentLoading.value) return;

  try {
    await ElMessageBox.confirm(
      `确定删除「${document.title}」吗？对应向量会一起删除。`,
      "删除资料",
      {
        confirmButtonText: "删除",
        cancelButtonText: "取消",
        type: "warning",
      },
    );
  } catch {
    return;
  }

  documentLoading.value = true;
  status.value = `正在删除 ${document.title}...`;
  try {
    const response = await fetch(`/api/documents/${document.id}`, {
      method: "DELETE",
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "删除失败");
    }
    status.value = "文档和当前向量已删除";
    ElMessage.success("资料已删除");
    await loadDocuments();
  } catch (error) {
    status.value = error.message;
    ElMessage.error(error.message);
  } finally {
    documentLoading.value = false;
  }
}

async function askQuestion() {
  if (!canAsk.value) return;

  const currentQuestion = question.value.trim();
  const currentApiKey = apiKey.value.trim();
  if (currentApiKey) {
    sessionStorage.setItem("deepseek_api_key", currentApiKey);
  }

  pushMessage({
    role: "你",
    type: "user",
    text: currentQuestion,
    time: new Date().toISOString(),
  });

  question.value = "";
  loading.value = true;
  status.value = "正在检索并生成回答...";
  await nextTick();

  try {
    const response = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        api_key: currentApiKey,
        question: currentQuestion,
        top_k: Number(topK.value) || 3,
        model: model.value,
      }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || data.error || "请求失败");
    }

    pushMessage({
      role: data.refused ? "系统" : "DeepSeek",
      type: "assistant",
      refused: Boolean(data.refused),
      text: cleanAnswerText(data.answer),
      chunks: data.chunks || [],
      time: new Date().toISOString(),
    });
    status.value = data.refused ? "依据不足，已拒答" : "就绪";
  } catch (error) {
    pushMessage({
      role: "系统",
      type: "error",
      text: error.message,
      time: new Date().toISOString(),
    });
    status.value = "请求失败";
  } finally {
    loading.value = false;
  }
}

function handleQuestionKeydown(event) {
  if (event.key !== "Enter" || event.shiftKey || event.isComposing) {
    return;
  }

  event.preventDefault();
  askQuestion();
}

function displayMessageText(message) {
  return message.type === "assistant" ? cleanAnswerText(message.text) : message.text;
}

function cleanAnswerText(text = "") {
  return String(text)
    .split(/\r?\n/)
    .filter((line) => !/chunk\s*[_-]?\s*id/i.test(line) && !/\bchunk[_-]\d+\b/i.test(line))
    .join("\n")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/^\s*[-*]\s+/gm, "• ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

async function scrollChatToBottom() {
  await nextTick();
  const chatArea = chatAreaRef.value?.$el || chatAreaRef.value;
  if (!chatArea) return;
  requestAnimationFrame(() => {
    chatArea.scrollTop = chatArea.scrollHeight;
  });
}

async function scrollChatToTop() {
  await nextTick();
  const chatArea = chatAreaRef.value?.$el || chatAreaRef.value;
  if (!chatArea) return;
  requestAnimationFrame(() => {
    chatArea.scrollTop = 0;
  });
}

function messageKey(message) {
  return `${message.time}-${message.role}`;
}

function isSourcesExpanded(message) {
  return expandedSourceMessages.value.has(messageKey(message));
}

function toggleSources(message) {
  const key = messageKey(message);
  const nextExpanded = new Set(expandedSourceMessages.value);
  if (nextExpanded.has(key)) {
    nextExpanded.delete(key);
  } else {
    nextExpanded.add(key);
  }
  expandedSourceMessages.value = nextExpanded;
}

function formatTime(date) {
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(date));
}

function formatDate(date) {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(date));
}

function formatDistance(distance) {
  const value = Number(distance);
  return Number.isFinite(value) ? value.toFixed(4) : "-";
}

function chunkRelevance(chunk) {
  // 后端已给出 relevance（[0,1]）；老数据没有时用距离兜底换算。
  let value = Number(chunk.relevance);
  if (!Number.isFinite(value)) {
    const distance = Number(chunk.distance);
    value = Number.isFinite(distance) ? 1 - distance / 2 : NaN;
  }
  if (!Number.isFinite(value)) return "-";
  return `${Math.round(Math.min(Math.max(value, 0), 1) * 100)}%`;
}

function formatSize(size) {
  const value = Number(size);
  if (!Number.isFinite(value)) return "-";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}
</script>

<template>
  <el-container class="app-shell">
    <el-aside class="chat-sidebar" width="300px">
      <div class="sidebar-brand">
        <div class="brand-icon">
          <el-icon><Files /></el-icon>
        </div>
        <div>
          <h1>论文 RAG</h1>
          <p>{{ documentCount }} 个资料 · {{ status }}</p>
        </div>
      </div>

      <el-button
        class="new-chat-button"
        :disabled="isBlankActiveConversation"
        :icon="Plus"
        type="primary"
        @click="newConversation"
      >
        新建对话
      </el-button>

      <div class="conversation-list">
        <button
          v-for="conversation in conversations"
          :key="conversation.id"
          class="conversation-item"
          :class="{ active: conversation.id === activeConversationId }"
          type="button"
          @click="selectConversation(conversation.id)"
        >
          <el-icon><ChatDotRound /></el-icon>
          <span>{{ conversation.title }}</span>
          <small>{{ formatDate(conversation.updatedAt) }}</small>
          <el-button
            :icon="Delete"
            circle
            link
            type="danger"
            @click.stop="deleteConversation(conversation.id)"
          />
        </button>
      </div>
    </el-aside>

    <el-container class="main-panel">
      <el-header class="topbar">
        <div>
          <h2>{{ activeConversation?.title || "新对话" }}</h2>
          <p>基于本地 Chroma 向量库与 SQLite 资料管理</p>
        </div>
        <div class="top-actions">
          <el-tag effect="light" type="success">{{ model }}</el-tag>
          <el-button :icon="Setting" @click="settingsOpen = true">设置与资料</el-button>
        </div>
      </el-header>

      <el-main ref="chatAreaRef" class="chat-area">
        <el-alert
          v-if="!hasApiKey"
          class="setup-alert"
          :closable="false"
          show-icon
          title="请先填写 DeepSeek API Key，或永久保存后直接提问"
          type="info"
        />

        <div v-if="!messages.length" class="empty-chat">
          <el-icon><ChatLineRound /></el-icon>
          <h3>开始提问</h3>
          <p>输入论文相关问题后，系统会检索资料 chunk 并生成回答。</p>
        </div>

        <article
          v-for="message in messages"
          :key="`${message.time}-${message.role}`"
          class="message"
          :class="message.type"
        >
          <div class="message-head">
            <el-tag
              :type="message.type === 'error' ? 'danger' : message.type === 'user' ? 'primary' : 'success'"
              effect="light"
            >
              {{ message.role }}
            </el-tag>
            <span>{{ formatTime(message.time) }}</span>
          </div>
          <el-alert
            v-if="message.refused"
            class="refusal-alert"
            :closable="false"
            show-icon
            title="资料中依据不足，已拒答"
            type="warning"
          >
            系统判定检索到的片段相关度不够，未调用大模型生成，避免编造。下方是最接近的片段，供你参考。
          </el-alert>
          <div class="message-body">{{ displayMessageText(message) }}</div>

          <div v-if="message.chunks?.length" class="source-toggle-row">
            <el-button
              class="source-toggle"
              :icon="isSourcesExpanded(message) ? ArrowUp : ArrowDown"
              link
              type="primary"
              @click="toggleSources(message)"
            >
              {{ isSourcesExpanded(message) ? "收起引用来源" : `展开引用来源（${message.chunks.length}）` }}
            </el-button>
          </div>

          <el-collapse v-if="message.chunks?.length && isSourcesExpanded(message)" class="sources">
            <el-collapse-item
              v-for="chunk in message.chunks"
              :key="chunk.chunk_id"
              :title="`${chunk.source || '资料'} · ${chunk.chunk_id} · 相关度 ${chunkRelevance(chunk)} · 距离 ${formatDistance(chunk.distance)}`"
            >
              <div class="source-title">{{ chunk.section_title }}</div>
              <div class="source-text">{{ chunk.text }}</div>
            </el-collapse-item>
          </el-collapse>
        </article>
      </el-main>

      <el-footer class="composer">
        <el-input
          v-model="question"
          :autosize="{ minRows: 3, maxRows: 7 }"
          placeholder="请输入问题，例如：Django 在系统中起到什么作用？"
          resize="none"
          type="textarea"
          @keydown="handleQuestionKeydown"
        />
        <el-button
          :disabled="!canAsk"
          :icon="Search"
          :loading="loading"
          type="primary"
          @click="askQuestion"
        >
          {{ askButtonText }}
        </el-button>
      </el-footer>
    </el-container>

    <el-drawer
      v-model="settingsOpen"
      direction="rtl"
      size="460px"
      title="设置与资料"
    >
      <el-tabs v-model="activeSettingsTab">
        <el-tab-pane label="问答设置" name="chat">
          <el-form label-position="top">
            <el-form-item label="DeepSeek API Key">
              <el-input
                v-model="apiKey"
                autocomplete="off"
                :placeholder="apiKeySaved ? 'API Key 已保存；输入新 Key 可覆盖' : '粘贴 DeepSeek API Key'"
                show-password
                type="password"
              >
                <template #prefix>
                  <el-icon><Key /></el-icon>
                </template>
              </el-input>
              <div v-if="apiKeySaved" class="saved-key-note">
                已保存到本地配置文件，之后打开会自动使用。
              </div>
            </el-form-item>

            <el-form-item label="检索数量">
              <el-input-number
                v-model="topK"
                :max="6"
                :min="1"
                controls-position="right"
              />
            </el-form-item>

            <el-form-item label="模型">
              <el-select v-model="model" class="model-select">
                <el-option
                  v-for="option in modelOptions"
                  :key="option.value"
                  :label="option.label"
                  :value="option.value"
                />
              </el-select>
            </el-form-item>

            <div class="drawer-actions">
              <el-button :icon="Key" type="primary" @click="saveKey">保存 Key</el-button>
              <el-button :icon="Delete" @click="clearChat">清空当前对话</el-button>
            </div>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="资料管理" name="documents">
          <div class="drawer-section-head">
            <span>{{ documentCount }} 个资料</span>
            <el-button :icon="Refresh" link type="primary" @click="loadDocuments">
              刷新
            </el-button>
          </div>

          <el-upload
            accept=".docx,.pdf,.txt,.md"
            :auto-upload="false"
            drag
            :limit="1"
            :on-change="onUploadFileChange"
            :on-remove="onUploadRemove"
          >
            <el-icon class="upload-icon"><UploadFilled /></el-icon>
            <div class="upload-text">拖入文件或点击选择</div>
          </el-upload>

          <el-button
            class="upload-button"
            :disabled="!uploadFile || documentLoading"
            :icon="Plus"
            :loading="documentLoading"
            type="primary"
            @click="uploadDocument"
          >
            上传并索引
          </el-button>

          <div v-if="documents.length" class="document-list">
            <article
              v-for="document in documents"
              :key="document.id"
              class="document-item"
            >
              <div class="document-main">
                <el-icon><Document /></el-icon>
                <div>
                  <strong>{{ document.title }}</strong>
                  <span>{{ document.original_filename || "未命名文件" }}</span>
                </div>
              </div>

              <div class="document-meta">
                <el-tag size="small">{{ document.chunk_count || 0 }} chunks</el-tag>
                <span>{{ formatSize(document.file_size) }}</span>
              </div>

              <div class="document-actions">
                <el-button
                  :icon="EditPen"
                  link
                  type="primary"
                  @click="openReplacePicker(document)"
                >
                  替换
                </el-button>
                <el-button
                  :icon="Delete"
                  link
                  type="danger"
                  @click="deleteDocument(document)"
                >
                  删除
                </el-button>
              </div>
            </article>
          </div>

          <el-empty
            v-if="!documents.length"
            :image-size="78"
            description="还没有登记资料"
          />

          <input
            ref="replaceFileInput"
            accept=".docx,.pdf,.txt,.md"
            class="hidden-file-input"
            type="file"
            @change="onReplaceFileChange"
          >
        </el-tab-pane>
      </el-tabs>
    </el-drawer>
  </el-container>
</template>
