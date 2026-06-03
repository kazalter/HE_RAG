// 轻量 Markdown → HTML 渲染器（移植自设计稿 src/markdown.js）。
// 仅支持子集：段落 / 标题 / 有序·无序列表 / 引用 / 代码块 / 行内代码 / 表格 / 粗斜体 / 链接。
// 输出带 Tailwind 类名的 HTML 字符串，配合 .md-body 样式使用。
export function renderMarkdown(src) {
  const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  // 仅允许安全协议的链接，避免 javascript: 等注入
  const safeHref = (href) => {
    const value = href.trim();
    if (/^(https?:|mailto:|\/|#)/i.test(value)) return value;
    return "#";
  };

  const inline = (t) => {
    let s = esc(t);
    s = s.replace(
      /`([^`]+)`/g,
      '<code class="px-1.5 py-0.5 rounded-md bg-stone-100 text-stone-700 text-[0.88em] font-mono ring-1 ring-stone-200/70">$1</code>'
    );
    s = s.replace(/\*\*([^*]+)\*\*/g, '<strong class="font-semibold text-stone-900">$1</strong>');
    s = s.replace(/(^|[^*])\*([^*]+)\*/g, '$1<em class="italic">$2</em>');
    s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_m, text, href) =>
      `<a href="${safeHref(href)}" class="text-coral-600 underline decoration-coral-300 underline-offset-2 hover:decoration-coral-500">${text}</a>`
    );
    return s;
  };

  const lines = String(src || "").replace(/\r\n/g, "\n").split("\n");
  let html = "";
  let i = 0;
  let listType = null;

  const closeList = () => {
    if (listType) {
      html += `</${listType}>`;
      listType = null;
    }
  };

  while (i < lines.length) {
    const line = lines[i];

    // 代码块
    if (/^```/.test(line)) {
      closeList();
      const lang = line.replace(/^```/, "").trim();
      i++;
      let code = "";
      while (i < lines.length && !/^```/.test(lines[i])) {
        code += lines[i] + "\n";
        i++;
      }
      i++;
      html += `<div class="my-3 rounded-xl overflow-hidden ring-1 ring-stone-200/80 bg-stone-50">
        <div class="flex items-center justify-between px-3.5 py-2 border-b border-stone-200/70 bg-stone-100/60">
          <span class="text-[11px] font-mono tracking-wide text-stone-400 uppercase">${esc(lang || "code")}</span>
        </div>
        <pre class="px-4 py-3 overflow-x-auto text-[13px] leading-relaxed font-mono text-stone-700"><code>${esc(code.replace(/\n$/, ""))}</code></pre>
      </div>`;
      continue;
    }

    // 表格
    if (
      line.includes("|") &&
      i + 1 < lines.length &&
      /^\s*\|?[\s:|-]+\|?\s*$/.test(lines[i + 1]) &&
      lines[i + 1].includes("-")
    ) {
      closeList();
      const parseRow = (r) =>
        r.replace(/^\s*\|/, "").replace(/\|\s*$/, "").split("|").map((c) => c.trim());
      const head = parseRow(line);
      i += 2;
      const rows = [];
      while (i < lines.length && lines[i].includes("|") && lines[i].trim() !== "") {
        rows.push(parseRow(lines[i]));
        i++;
      }
      html += `<div class="my-4 overflow-x-auto rounded-xl ring-1 ring-stone-200/80">
        <table class="w-full text-sm border-collapse">
          <thead><tr class="bg-stone-50">${head
            .map(
              (h) =>
                `<th class="text-left font-semibold text-stone-600 px-4 py-2.5 border-b border-stone-200/80">${inline(h)}</th>`
            )
            .join("")}</tr></thead>
          <tbody>${rows
            .map(
              (r, ri) =>
                `<tr class="${ri % 2 ? "bg-stone-50/40" : "bg-white"}">${r
                  .map(
                    (c) =>
                      `<td class="px-4 py-2.5 text-stone-600 border-b border-stone-100 align-top">${inline(c)}</td>`
                  )
                  .join("")}</tr>`
            )
            .join("")}</tbody>
        </table></div>`;
      continue;
    }

    // 引用
    if (/^>\s?/.test(line)) {
      closeList();
      let quote = "";
      while (i < lines.length && /^>\s?/.test(lines[i])) {
        quote += lines[i].replace(/^>\s?/, "") + " ";
        i++;
      }
      html += `<blockquote class="my-3.5 pl-4 border-l-[3px] border-coral-300/80 text-stone-500 text-[0.95em] leading-relaxed">${inline(quote.trim())}</blockquote>`;
      continue;
    }

    // 标题
    let m = line.match(/^(#{1,4})\s+(.*)$/);
    if (m) {
      closeList();
      const lvl = m[1].length;
      const sizes = { 1: "text-2xl", 2: "text-xl", 3: "text-lg", 4: "text-base" };
      html += `<h${lvl} class="${sizes[lvl]} font-semibold text-stone-900 mt-5 mb-2.5 first:mt-0">${inline(m[2])}</h${lvl}>`;
      i++;
      continue;
    }

    // 有序列表
    m = line.match(/^\s*\d+\.\s+(.*)$/);
    if (m) {
      if (listType !== "ol") {
        closeList();
        html += '<ol class="my-3 space-y-2 list-none">';
        listType = "ol";
      }
      html += `<li class="md-oli pl-9 relative text-stone-600 leading-relaxed">${inline(m[1])}</li>`;
      i++;
      continue;
    }

    // 无序列表
    m = line.match(/^\s*[-*•]\s+(.*)$/);
    if (m) {
      if (listType !== "ul") {
        closeList();
        html += '<ul class="my-3 space-y-2">';
        listType = "ul";
      }
      html += `<li class="pl-6 relative text-stone-600 leading-relaxed before:content-[''] before:absolute before:left-1 before:top-[0.62em] before:w-1.5 before:h-1.5 before:rounded-full before:bg-coral-400">${inline(m[1])}</li>`;
      i++;
      continue;
    }

    // 空行
    if (line.trim() === "") {
      closeList();
      i++;
      continue;
    }

    // 普通段落
    closeList();
    let para = line;
    i++;
    while (
      i < lines.length &&
      lines[i].trim() !== "" &&
      !/^(#{1,4}\s|>|```|\s*[-*•]\s|\s*\d+\.\s)/.test(lines[i]) &&
      !lines[i].includes("|")
    ) {
      para += " " + lines[i];
      i++;
    }
    html += `<p class="my-3 text-stone-600 leading-[1.75] first:mt-0">${inline(para)}</p>`;
  }
  closeList();
  return html;
}
