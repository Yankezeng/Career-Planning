<template>
  <div class="assistant-message-renderer" @click="handleRendererClick">
    <div v-if="hasContent && !preferPlainText" class="bubble-markdown" v-html="markdownPayload.html"></div>

    <div v-else-if="preferPlainText" class="bubble-text" :class="{ 'bubble-text-typewriter': typewriter }">
      <template v-if="typewriter">
        <span v-for="(char, index) in plainChars" :key="`typing-char-${index}`" class="typing-char">{{ char }}</span>
      </template>
      <template v-else>{{ displayContent || "" }}</template>
    </div>

    <template v-else-if="normalizedBlocks.length">
      <section v-for="(block, index) in normalizedBlocks" :key="`${block.type}-${index}`" class="msg-block" :class="`block-${block.type}`">
        <div v-if="block.type === 'summary'" class="block-summary">{{ block.text }}</div>

        <div v-else-if="block.type === 'bullets'" class="block-bullets">
          <div v-if="block.title" class="block-title">{{ block.title }}</div>
          <ul>
            <li v-for="(item, i) in block.items || []" :key="`${index}-item-${i}`">{{ item }}</li>
          </ul>
        </div>

        <div v-else-if="block.type === 'actions'" class="block-actions">
          <span v-for="(item, i) in block.items || []" :key="`${index}-action-${i}`" class="action-chip">{{ item }}</span>
        </div>

        <div v-else-if="block.type === 'note'" class="block-note">{{ block.text }}</div>

        <div v-else-if="block.type === 'code'" class="block-code" v-html="block.codeHtml"></div>

        <div v-else class="block-summary">{{ block.text || "" }}</div>
      </section>
    </template>

    <div v-else class="bubble-text">{{ displayContent || "" }}</div>

    <section v-if="normalizedArtifacts.length" class="artifact-list">
      <article v-for="(item, index) in normalizedArtifacts" :key="`${item.id || item.name || 'artifact'}-${index}`" class="artifact-item" :class="`artifact-${item.kind}`">
        <template v-if="item.kind === 'image' && item.url">
          <img :src="item.url" :alt="item.name || 'image'" class="artifact-image" />
        </template>

        <template v-else-if="item.kind === 'audio' && item.url">
          <audio class="artifact-audio" controls :src="item.url"></audio>
        </template>

        <template v-else-if="item.kind === 'video' && item.url">
          <video class="artifact-video" controls :src="item.url"></video>
        </template>

        <template v-else>
          <div class="artifact-file-card pinned">
            <div class="pin-icon">
              <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M16 12V4H17V2H7V4H8V12L6 14V16H11.2V22H12.8V16H18V14L16 12Z" fill="#dc2626"/>
              </svg>
            </div>
            <div class="file-info">
              <span class="file-label">FILE</span>
              <span class="file-name">{{ item.name || "文件" }}</span>
            </div>
            <div class="artifact-actions-inline">
              <button
                v-if="canDownloadArtifact(item)"
                type="button"
                class="artifact-btn artifact-icon-btn"
                :disabled="isDownloading(item)"
                :title="isDownloading(item) ? '下载中...' : '下载'"
                @click="downloadArtifact(item)"
              >
                <svg v-if="!isDownloading(item)" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                <svg v-else viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" class="downloading-icon">
                  <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2" fill="none" opacity="0.3"/>
                  <path d="M12 2a10 10 0 0110 10" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                    <animateTransform attributeName="transform" type="rotate" from="0 12 12" to="360 12 12" dur="1s" repeatCount="indefinite"/>
                  </path>
                </svg>
              </button>
            </div>
          </div>
        </template>

        <div v-if="(item.kind !== 'file') && (item.kind !== 'image' && item.url)" class="artifact-actions">
          <button
            v-if="item.kind !== 'file' && item.url"
            type="button"
            class="artifact-btn artifact-icon-btn"
            :title="'打开'"
            @click="openArtifact(item.url)"
          >
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6M15 3h6v6M10 14L21 3" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
          <button
            v-if="canDownloadArtifact(item)"
            type="button"
            class="artifact-btn artifact-icon-btn"
            :disabled="isDownloading(item)"
            :title="isDownloading(item) ? '下载中...' : '下载'"
            @click="downloadArtifact(item)"
          >
            <svg v-if="!isDownloading(item)" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            <svg v-else viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" class="downloading-icon">
              <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2" fill="none" opacity="0.3"/>
              <path d="M12 2a10 10 0 0110 10" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                <animateTransform attributeName="transform" type="rotate" from="0 12 12" to="360 12 12" dur="1s" repeatCount="indefinite"/>
              </path>
            </svg>
          </button>
        </div>
      </article>
    </section>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";
import MarkdownIt from "markdown-it";
import hljs from "highlight.js";
import "highlight.js/styles/github.css";
import { assistantApi } from "@/api";

const API_ORIGIN = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");

const props = defineProps({
  content: { type: String, default: "" },
  replyBlocks: { type: Array, default: () => [] },
  artifacts: { type: Array, default: () => [] },
  backendOrigin: { type: String, default: "" },
  preferPlainText: { type: Boolean, default: false },
  typewriter: { type: Boolean, default: false },
});

const MIME_BY_EXT = {
  png: "image/png",
  jpg: "image/jpeg",
  jpeg: "image/jpeg",
  webp: "image/webp",
  gif: "image/gif",
  svg: "image/svg+xml",
  mp3: "audio/mpeg",
  wav: "audio/wav",
  m4a: "audio/mp4",
  aac: "audio/aac",
  ogg: "audio/ogg",
  mp4: "video/mp4",
  webm: "video/webm",
  mov: "video/quicktime",
  avi: "video/x-msvideo",
  pdf: "application/pdf",
  doc: "application/msword",
  docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  txt: "text/plain",
};

const LANGUAGE_ALIAS = {
  js: "javascript",
  jsx: "javascript",
  ts: "typescript",
  tsx: "typescript",
  py: "python",
  c: "c",
  "c++": "cpp",
  cpp: "cpp",
  cc: "cpp",
  hpp: "cpp",
  h: "c",
  sh: "bash",
  shell: "bash",
  bash: "bash",
  zsh: "bash",
  html: "xml",
  vue: "xml",
  xml: "xml",
  css: "css",
  json: "json",
  yaml: "yaml",
  yml: "yaml",
  sql: "sql",
  md: "markdown",
  markdown: "markdown",
  vbs: "vbnet",
  vbscript: "vbnet",
};

const markdownIt = createMarkdownRenderer();

const rawContent = computed(() => String(props.content || ""));
const inferredDownloadArtifacts = computed(() => inferDownloadArtifactsFromContent(rawContent.value));
const displayContent = computed(() => stripDownloadSectionFromContent(rawContent.value, inferredDownloadArtifacts.value));
const hasContent = computed(() => String(displayContent.value || "").trim().length > 0);
const plainChars = computed(() => Array.from(String(displayContent.value || "")));
const downloadingIds = ref(new Set());

const markdownPayload = computed(() => {
  const text = String(displayContent.value || "");
  const env = { __codeMap: {}, __counter: 0 };
  const html = markdownIt.render(text, env);
  return {
    html,
    codeMap: env.__codeMap || {},
  };
});

const normalizedBlocksPayload = computed(() => {
  const codeMap = {};
  const blocks = (Array.isArray(props.replyBlocks) ? props.replyBlocks : [])
    .map((item, index) => {
      if (!item || typeof item !== "object") return null;
      const type = String(item.type || "").trim();
      if (!type) return null;
      const title = String(item.title || "").trim();
      const isCode = type === "code";
      const rawText = String(item.text ?? "");
      const code = String(item.code ?? "").trim() || rawText;
      const language = String(item.language || item.lang || "").trim();
      const text = isCode ? rawText : rawText.trim();
      const items = Array.isArray(item.items)
        ? item.items.map((entry) => String(entry || "").trim()).filter(Boolean)
        : [];

      if (!isCode) return { type, text, title, items, language: "", code: "", codeHtml: "" };

      const codeId = `block-code-${index}`;
      codeMap[codeId] = code;
      const codeHtml = renderCodeBlockHtml({
        code,
        language,
        codeId,
      });
      return { type, text, title, items, language, code, codeHtml };
    })
    .filter(Boolean);
  return { blocks, codeMap };
});

const normalizedBlocks = computed(() => normalizedBlocksPayload.value.blocks || []);

const codeSnippetMap = computed(() => ({
  ...(markdownPayload.value.codeMap || {}),
  ...(normalizedBlocksPayload.value.codeMap || {}),
}));

const normalizedArtifacts = computed(() =>
  dedupeNormalizedArtifacts(
    [...(Array.isArray(props.artifacts) ? props.artifacts : []), ...inferredDownloadArtifacts.value]
    .map((item) => normalizeArtifact(item))
    .filter((item) => item && (item.name || item.url)),
  ),
);

function inferDownloadArtifactsFromContent(content = "") {
  const text = String(content || "");
  const pattern = /\/uploads\/resume_exports\/[^\s`"'<>)]*\.(?:docx|doc|pdf)/gi;
  const seen = new Set();
  const artifacts = [];
  for (const match of text.matchAll(pattern)) {
    const url = String(match[0] || "").trim();
    if (!url || seen.has(url)) continue;
    seen.add(url);
    const extMatch = url.match(/\.([a-z0-9]+)$/i);
    const ext = extMatch ? extMatch[1].toLowerCase() : "";
    const isPdf = ext === "pdf";
    artifacts.push({
      name: isPdf ? "优化简历 PDF 版.pdf" : "优化简历 Word 版.docx",
      type: "document",
      download_url: url,
      mime_type: isPdf ? "application/pdf" : MIME_BY_EXT[ext] || "application/octet-stream",
    });
  }
  return artifacts;
}

function stripDownloadSectionFromContent(content = "", artifacts = []) {
  const text = String(content || "");
  if (!text || !Array.isArray(artifacts) || artifacts.length === 0) return text;

  const lines = text.split(/\r?\n/);
  const cleaned = [];
  let skipping = false;
  for (const line of lines) {
    const stripped = line.trim();
    const isDownloadHeading = /(文件获取方式|下载链接|导出文件)/.test(stripped);
    const hasDownloadReference = /\/uploads\/resume_exports\/[^\s`"'<>)]*\.(?:docx|doc|pdf)/i.test(stripped);

    if (isDownloadHeading) {
      skipping = true;
      continue;
    }
    if (hasDownloadReference) {
      continue;
    }
    if (skipping) {
      if (!stripped) continue;
      if (stripped.startsWith("#")) {
        skipping = false;
        cleaned.push(line);
      } else if (stripped.startsWith("---")) {
        skipping = false;
      } else if (/^[-*]\s*(Word|PDF|DOCX|DOC|文件|下载)/i.test(stripped)) {
        continue;
      } else {
        skipping = false;
        cleaned.push(line);
      }
      continue;
    }
    cleaned.push(line);
  }
  return cleaned.join("\n").replace(/\n{3,}/g, "\n\n").trim() || "文件已生成，可在下方下载卡片中获取。";
}

function dedupeNormalizedArtifacts(items = []) {
  const seen = new Set();
  const output = [];
  for (const item of items) {
    if (!item || typeof item !== "object") continue;
    const key = String(item.id || item.url || item.name || "").trim();
    if (!key || seen.has(key)) continue;
    seen.add(key);
    output.push(item);
  }
  return output;
}

function createMarkdownRenderer() {
  const md = new MarkdownIt({
    html: false,
    breaks: true,
    linkify: true,
  });

  const defaultFence =
    md.renderer.rules.fence ||
    ((tokens, idx, options, env, self) => self.renderToken(tokens, idx, options));

  md.renderer.rules.fence = (tokens, idx, options, env, self) => {
    const token = tokens[idx];
    const code = String(token.content || "");
    const info = String(token.info || "").trim();
    const language = info.split(/\s+/)[0] || "";
    const context = env && typeof env === "object" ? env : {};
    if (!context.__codeMap) context.__codeMap = {};
    if (!Number.isFinite(context.__counter)) context.__counter = 0;
    const codeId = `md-code-${context.__counter}`;
    context.__counter += 1;
    context.__codeMap[codeId] = code;
    try {
      return renderCodeBlockHtml({ code, language, codeId });
    } catch (_) {
      return defaultFence(tokens, idx, options, env, self);
    }
  };

  const defaultLinkOpen =
    md.renderer.rules.link_open ||
    ((tokens, idx, options, env, self) => self.renderToken(tokens, idx, options));

  md.renderer.rules.link_open = (tokens, idx, options, env, self) => {
    const token = tokens[idx];
    const href = token.attrGet("href") || "";
    const isDownloadLink = checkIsDownloadLink(href);
    if (isDownloadLink) {
      token.attrSet("data-download-link", "true");
      token.attrSet("download", "");
    } else {
      token.attrSet("target", "_blank");
      token.attrSet("rel", "noopener noreferrer");
    }
    return defaultLinkOpen(tokens, idx, options, env, self);
  };

  const defaultImage =
    md.renderer.rules.image ||
    ((tokens, idx, options, env, self) => self.renderToken(tokens, idx, options));

  md.renderer.rules.image = (tokens, idx, options, env, self) => {
    const token = tokens[idx];
    const src = token.attrGet("src") || "";
    token.attrSet("src", resolveMarkdownAssetUrl(src));
    token.attrSet("loading", "lazy");
    return defaultImage(tokens, idx, options, env, self);
  };

  return md;
}

const resolveMarkdownAssetUrl = (url = "") => {
  const value = String(url || "").trim();
  if (!value) return "";
  if (/^(https?:|data:|blob:)/i.test(value)) return value;
  if (value.startsWith("/api/") || value.startsWith("/uploads/")) return `${API_ORIGIN}${value}`;
  return value;
};

const normalizeLanguageKey = (language = "") => {
  const key = String(language || "").trim().toLowerCase();
  if (!key) return "";
  return LANGUAGE_ALIAS[key] || key;
};

const languageLabel = (language = "") => {
  const label = String(language || "").trim();
  if (!label) return "TEXT";
  return label.toUpperCase();
};

const highlightCode = (code = "", language = "") => {
  const text = String(code || "");
  const normalizedLanguage = normalizeLanguageKey(language);
  if (normalizedLanguage && hljs.getLanguage(normalizedLanguage)) {
    return hljs.highlight(text, { language: normalizedLanguage, ignoreIllegals: true }).value;
  }
  return escapeHtml(text);
};

const renderCodeBlockHtml = ({ code = "", language = "", codeId = "" }) => {
  const label = languageLabel(language);
  const escapedId = escapeHtml(String(codeId || ""));
  const highlighted = highlightCode(code, language);
  const classLanguage = normalizeLanguageKey(language) || "plaintext";
  return `
    <div class="code-block" data-code-wrapper="${escapedId}">
      <div class="code-block-head">
        <span class="code-lang">${escapeHtml(label)}</span>
        <div class="code-copy-area">
          <span class="code-copy-tip" aria-hidden="true"></span>
          <button type="button" class="code-copy-btn" data-code-id="${escapedId}" data-default-label="复制">复制</button>
        </div>
      </div>
      <pre><code class="hljs language-${escapeHtml(classLanguage)}">${highlighted}</code></pre>
    </div>
  `.trim();
};

const escapeHtml = (value = "") =>
  String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");

const setCopyButtonText = (button, text) => {
  if (!(button instanceof HTMLElement)) return;
  const defaultLabel = String(button.dataset.defaultLabel || "复制");
  button.textContent = text;
  if (button.__restoreTimer) window.clearTimeout(button.__restoreTimer);
  button.__restoreTimer = window.setTimeout(() => {
    button.textContent = defaultLabel;
    button.__restoreTimer = null;
  }, 1400);
};

const showCopyTip = (button, text, isError = false) => {
  if (!(button instanceof HTMLElement)) return;
  const head = button.closest(".code-block-head");
  if (!(head instanceof HTMLElement)) return;
  const tip = head.querySelector(".code-copy-tip");
  if (!(tip instanceof HTMLElement)) return;

  tip.textContent = String(text || "").trim();
  tip.classList.remove("is-visible", "is-error");
  if (tip.__hideTimer) window.clearTimeout(tip.__hideTimer);

  if (isError) tip.classList.add("is-error");
  window.requestAnimationFrame(() => {
    tip.classList.add("is-visible");
  });

  tip.__hideTimer = window.setTimeout(() => {
    tip.classList.remove("is-visible", "is-error");
    tip.__hideTimer = null;
  }, 1300);
};

const copyWithFallback = async (text) => {
  const content = String(text || "");
  if (!content) return false;
  try {
    if (navigator?.clipboard?.writeText) {
      await navigator.clipboard.writeText(content);
      return true;
    }
  } catch (_) {
    // fallback to document.execCommand below
  }

  try {
    const textarea = document.createElement("textarea");
    textarea.value = content;
    textarea.setAttribute("readonly", "readonly");
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    textarea.style.left = "-9999px";
    document.body.appendChild(textarea);
    textarea.select();
    const copied = document.execCommand("copy");
    document.body.removeChild(textarea);
    return !!copied;
  } catch (_) {
    return false;
  }
};

const handleRendererClick = async (event) => {
  const target = event?.target;
  if (!(target instanceof Element)) return;

  const downloadLink = target.closest('a[data-download-link="true"]');
  if (downloadLink instanceof HTMLAnchorElement) {
    event.preventDefault();
    const href = downloadLink.getAttribute("href");
    if (href) {
      await handleDownloadLink(href, downloadLink.textContent || "download");
    }
    return;
  }

  const button = target.closest(".code-copy-btn");
  if (!(button instanceof HTMLElement)) return;

  const codeId = String(button.dataset.codeId || "");
  const code = String(codeSnippetMap.value?.[codeId] || "");
  if (!code) {
    setCopyButtonText(button, "失败");
    showCopyTip(button, "复制失败", true);
    return;
  }
  const copied = await copyWithFallback(code);
  setCopyButtonText(button, copied ? "已复制" : "失败");
  showCopyTip(button, copied ? "已复制" : "复制失败", !copied);
};

const normalizeArtifact = (raw) => {
  if (!raw || typeof raw !== "object") return null;
  const name = String(raw.name || raw.file_name || "").trim();
  const type = String(raw.type || "").trim().toLowerCase();
  const mimeRaw = String(raw.mime_type || raw.mime || "").trim().toLowerCase();
  const downloadUrl = String(raw.download_url || raw.url || "").trim();
  const artifactId = parseArtifactId(raw.id);
  const url = resolveArtifactUrl(downloadUrl);
  const ext = inferExtension(name, downloadUrl, type);
  const mime = resolveMime(mimeRaw, type, ext);
  const kind = resolveKind(mime, ext);

  return {
    id: artifactId,
    name,
    type,
    mime,
    ext,
    kind,
    url,
  };
};

const resolveArtifactUrl = (value) => {
  const text = String(value || "").trim();
  if (!text) return "";
  if (text.startsWith("http://") || text.startsWith("https://")) return text;
  const origin = String(props.backendOrigin || "").trim();
  if (!origin) return text;
  return `${origin}${text.startsWith("/") ? "" : "/"}${text}`;
};

const inferExtension = (name, downloadUrl, type) => {
  const fromName = extractExtension(name);
  if (fromName) return fromName;
  const fromUrl = extractExtension(downloadUrl);
  if (fromUrl) return fromUrl;
  if (type && !type.includes("/")) return type;
  return "";
};

const extractExtension = (value) => {
  const text = String(value || "").trim().toLowerCase();
  const match = text.match(/\.([a-z0-9]+)(?:\?|#|$)/);
  return match ? match[1] : "";
};

const resolveMime = (mimeRaw, type, ext) => {
  if (mimeRaw.includes("/")) return mimeRaw;
  if (type.includes("/")) return type;
  if (MIME_BY_EXT[ext]) return MIME_BY_EXT[ext];
  return "";
};

const resolveKind = (mime, ext) => {
  if (mime.startsWith("image/")) return "image";
  if (mime.startsWith("audio/")) return "audio";
  if (mime.startsWith("video/")) return "video";
  if (["png", "jpg", "jpeg", "webp", "gif", "svg"].includes(ext)) return "image";
  if (["mp3", "wav", "m4a", "aac", "ogg"].includes(ext)) return "audio";
  if (["mp4", "webm", "mov", "avi"].includes(ext)) return "video";
  return "file";
};

const parseArtifactId = (value) => {
  const parsed = Number.parseInt(String(value ?? "").trim(), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
};

const openArtifact = (url) => {
  const text = String(url || "").trim();
  if (!text) return;
  window.open(text, "_blank");
};

const saveBlobAsFile = (blob, fileName) => {
  const anchor = document.createElement("a");
  const objectUrl = URL.createObjectURL(blob);
  anchor.href = objectUrl;
  anchor.download = String(fileName || "artifact").trim() || "artifact";
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
};

const fallbackDownloadByUrl = (item) => {
  const url = String(item?.url || "").trim();
  if (!url) return;
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = String(item?.name || "artifact").trim() || "artifact";
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
};

const canDownloadArtifact = (item) => {
  if (!item || typeof item !== "object") return false;
  return Boolean(item.id || item.url);
};

const isDownloading = (item) => {
  const id = item?.id;
  if (!id) return false;
  return downloadingIds.value.has(id);
};

const downloadArtifact = async (item) => {
  if (!item || typeof item !== "object") return;
  const fileName = String(item.name || "artifact").trim() || "artifact";
  const artifactId = Number.isFinite(item.id) ? item.id : null;
  if (!artifactId) {
    fallbackDownloadByUrl(item);
    return;
  }
  if (downloadingIds.value.has(artifactId)) return;
  downloadingIds.value.add(artifactId);
  try {
    const blob = await assistantApi.downloadArtifact(artifactId);
    saveBlobAsFile(blob, fileName);
  } catch (_) {
    fallbackDownloadByUrl(item);
  } finally {
    downloadingIds.value.delete(artifactId);
  }
};

const checkIsDownloadLink = (href = "") => {
  const url = String(href || "").trim().toLowerCase();
  if (!url) return false;
  return url.includes("/export/") || url.includes("/download") || url.endsWith("/export") || url.includes("download=true") || url.includes("action=download");
};

const handleDownloadLink = async (href, fileName = "download") => {
  const url = String(href || "").trim();
  if (!url) return;
  try {
    const token = localStorage.getItem("career_agent_token");
    const headers = {};
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    const response = await fetch(url, { headers });
    if (!response.ok) {
      fallbackDownloadByUrl({ url, name: fileName });
      return;
    }
    const blob = await response.blob();
    const contentType = response.headers.get("content-type") || "";
    const contentDisposition = response.headers.get("content-disposition") || "";
    let extractedName = String(fileName || "").trim();
    const filenameMatch = contentDisposition.match(/filename\*?=(?:UTF-8''|"?)([^";\n]+)/i);
    if (filenameMatch && filenameMatch[1]) {
      extractedName = decodeURIComponent(filenameMatch[1].trim());
    }
    if (!extractedName) {
      const urlPath = new URL(url, window.location.origin).pathname;
      const pathParts = urlPath.split("/").filter(Boolean);
      if (pathParts.length > 0) {
        extractedName = pathParts[pathParts.length - 1] || "download";
      }
    }
    saveBlobAsFile(blob, extractedName || "download");
  } catch (_) {
    fallbackDownloadByUrl({ url, name: fileName });
  }
};
</script>

<style scoped>
.assistant-message-renderer {
  display: grid;
  gap: 8px;
  width: 100%;
  min-width: 0;
}

.msg-block {
  line-height: 1.75;
  color: #1f2937;
}

.block-title {
  margin-bottom: 6px;
  color: #334155;
  font-size: 13px;
  font-weight: 700;
}

.block-bullets ul {
  margin: 0;
  padding-left: 18px;
  display: grid;
  gap: 4px;
}

.block-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.action-chip {
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  border: 1px solid #dbe5f2;
  background: #f8fbff;
  color: #334155;
  display: inline-flex;
  align-items: center;
  font-size: 12px;
}

.block-note {
  border-left: 3px solid #cbd5e1;
  padding-left: 10px;
  color: #64748b;
  font-size: 13px;
}

.bubble-markdown {
  line-height: 1.8;
  color: #1f2937;
  white-space: normal;
  word-break: break-word;
  overflow-wrap: anywhere;
  width: 100%;
  min-width: 0;
}

.bubble-markdown :deep(p),
.bubble-markdown :deep(ul),
.bubble-markdown :deep(ol),
.bubble-markdown :deep(pre),
.bubble-markdown :deep(blockquote),
.bubble-markdown :deep(h1),
.bubble-markdown :deep(h2),
.bubble-markdown :deep(h3),
.bubble-markdown :deep(h4) {
  margin: 0;
}

.bubble-markdown :deep(p + p),
.bubble-markdown :deep(p + ul),
.bubble-markdown :deep(p + ol),
.bubble-markdown :deep(ul + p),
.bubble-markdown :deep(ol + p),
.bubble-markdown :deep(pre + p),
.bubble-markdown :deep(p + pre) {
  margin-top: 8px;
}

.bubble-markdown :deep(ul),
.bubble-markdown :deep(ol) {
  padding-left: 20px;
}

.bubble-markdown :deep(li + li) {
  margin-top: 4px;
}

.bubble-markdown :deep(a) {
  color: #1d4ed8;
  text-decoration: underline;
}

.bubble-markdown :deep(img) {
  display: block;
  width: auto;
  height: auto;
  max-width: min(100%, 680px);
  max-height: 760px;
  object-fit: contain;
  overflow: hidden;
  box-sizing: border-box;
  margin: 10px 0;
  border: 1px solid #dbe7ff;
  border-radius: 14px;
  box-shadow: 0 12px 36px rgba(37, 99, 235, 0.12);
  background: #ffffff;
}

.bubble-markdown :deep(code:not(.hljs)) {
  padding: 2px 6px;
  border-radius: 6px;
  border: 1px solid #dbe5f2;
  background: #f8fbff;
  color: #334155;
  font-size: 12px;
  font-family: "JetBrains Mono", "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
}

.assistant-message-renderer :deep(.code-block) {
  border: 1px solid #dbe5f2;
  border-radius: 12px;
  background: #f8fbff;
  overflow: hidden;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
}

.assistant-message-renderer :deep(.code-block-head) {
  min-height: 34px;
  padding: 0 10px;
  border-bottom: 1px solid #dbe5f2;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  background: #f1f6ff;
  min-width: 0;
  box-sizing: border-box;
}

.assistant-message-renderer :deep(.code-copy-area) {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.assistant-message-renderer :deep(.code-lang) {
  font-size: 11px;
  font-weight: 700;
  color: #475569;
  letter-spacing: 0.04em;
}

.assistant-message-renderer :deep(.code-copy-tip) {
  min-height: 20px;
  padding: 0 8px;
  border-radius: 999px;
  border: 1px solid #86efac;
  background: #ecfdf3;
  color: #15803d;
  font-size: 11px;
  display: inline-flex;
  align-items: center;
  opacity: 0;
  transform: translateY(-3px) scale(0.96);
  pointer-events: none;
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.assistant-message-renderer :deep(.code-copy-tip.is-visible) {
  opacity: 1;
  transform: translateY(0) scale(1);
}

.assistant-message-renderer :deep(.code-copy-tip.is-error) {
  border-color: #fecaca;
  background: #fef2f2;
  color: #b91c1c;
}

.assistant-message-renderer :deep(.code-copy-btn) {
  min-height: 24px;
  padding: 0 8px;
  border: 1px solid #d3def0;
  border-radius: 8px;
  background: #ffffff;
  color: #334155;
  font-size: 12px;
  cursor: pointer;
  transition: border-color 0.16s ease, color 0.16s ease, background-color 0.16s ease;
}

.assistant-message-renderer :deep(.code-copy-btn:hover) {
  border-color: #93c5fd;
  color: #1d4ed8;
  background: #eff6ff;
}

.assistant-message-renderer :deep(.code-block pre) {
  margin: 0;
  padding: 12px;
  overflow-x: auto;
  font-size: 12px;
  line-height: 1.6;
  background: transparent;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
}

.assistant-message-renderer :deep(.code-block code.hljs) {
  padding: 0;
  background: transparent;
  font-family: "JetBrains Mono", "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
}

.block-code {
  line-height: 1;
}

.bubble-text {
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: anywhere;
  line-height: 1.8;
}

.bubble-text-typewriter .typing-char {
  opacity: 0;
  animation: char-fade-in 0.2s ease forwards;
}

@keyframes char-fade-in {
  from {
    opacity: 0;
    filter: blur(1.8px);
  }
  to {
    opacity: 1;
    filter: blur(0);
  }
}

@media (prefers-reduced-motion: reduce) {
  .bubble-text-typewriter .typing-char {
    animation: none;
    opacity: 1;
    filter: none;
  }
}

.artifact-list {
  display: grid;
  gap: 10px;
  margin-top: 4px;
  min-width: 0;
}

.artifact-item {
  border: none;
  border-radius: 0;
  padding: 0;
  background: transparent;
  display: grid;
  gap: 8px;
  min-width: 0;
}

.artifact-head {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.artifact-kind {
  border: 1px solid #c7d7f4;
  border-radius: 999px;
  padding: 2px 8px;
  color: #1d4ed8;
  font-size: 11px;
  font-weight: 700;
}

.artifact-name {
  color: #0f172a;
  font-size: 13px;
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.artifact-image {
  width: 100%;
  height: auto;
  max-width: 100%;
  max-height: 320px;
  display: block;
  object-fit: contain;
  overflow: hidden;
  box-sizing: border-box;
  border-radius: 8px;
  border: 1px solid #dbe5f2;
  background: #ffffff;
}

.artifact-audio,
.artifact-video {
  width: 100%;
  border-radius: 8px;
}

.artifact-file-card {
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #ffffff;
  padding: 0;
  display: flex;
  align-items: center;
  gap: 0;
  min-width: 0;
  min-height: 48px;
  overflow: hidden;
  position: relative;
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.08);
}

.artifact-file-card.pinned {
  max-width: 400px;
  padding-left: 28px;
}

.pin-icon {
  position: absolute;
  left: -2px;
  top: -2px;
  width: 20px;
  height: 24px;
  z-index: 10;
  filter: drop-shadow(0 1px 2px rgba(220, 38, 38, 0.25));
}

.pin-icon svg {
  width: 100%;
  height: 100%;
  display: block;
}

.file-info {
  flex: 1;
  padding: 14px 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.file-label {
  font-size: 11px;
  font-weight: 800;
  color: #1d4ed8;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 4px;
  padding: 3px 8px;
  letter-spacing: 0.08em;
  white-space: nowrap;
  flex-shrink: 0;
}

.file-name {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.3;
}

.artifact-actions-inline {
  display: flex;
  align-items: center;
  padding-right: 10px;
  flex-shrink: 0;
}

.artifact-actions {
  display: flex;
  gap: 8px;
}

.artifact-btn {
  border: 1px solid #dbe5f2;
  border-radius: 8px;
  background: #ffffff;
  color: #334155;
  min-height: 28px;
  padding: 0 10px;
  cursor: pointer;
}

.artifact-btn:disabled {
  cursor: not-allowed;
  opacity: 0.65;
}

.artifact-btn:hover {
  border-color: #93c5fd;
  color: #1d4ed8;
}

.artifact-icon-btn {
  width: 32px;
  height: 32px;
  min-width: 32px;
  min-height: 32px;
  padding: 0;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #f8fbff;
  border-color: #d3def0;
}

.artifact-icon-btn svg {
  width: 16px;
  height: 16px;
  display: block;
}

.artifact-icon-btn:hover {
  background: #eff6ff;
  border-color: #93c5fd;
  box-shadow: 0 2px 8px rgba(29, 78, 216, 0.15);
}

.artifact-icon-btn:disabled {
  opacity: 0.6;
}

.downloading-icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@media (max-width: 900px) {
  .assistant-message-renderer :deep(.code-block pre) {
    font-size: 11px;
    padding: 10px;
  }
}
</style>
