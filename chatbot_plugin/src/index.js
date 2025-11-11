// index.js
import { ChatbotUI } from "./ui.js";
import { ChatService } from "./chat.js";
import { AuthService } from "./auth.js";
import { CONFIG, initConfig } from "./config.js";
import "./styles.css";

(async function initChatbot() {
  await initConfig();
  const authBootstrap = await bootstrapAuth();
  if (!authBootstrap) {
    return;
  }

  const { token, context: tokenContext } = authBootstrap || {};

  const ui = new ChatbotUI();
  ui.init();

  const chatService = new ChatService();
  if (tokenContext) {
    chatService.setTokenContext(tokenContext);
  }
  if (token) {
    chatService.token = token;
  }

  const messages = [];
  let typingInterval = null;

  // Wait for DOM to be ready before accessing elements
  let chatBox, chatEmpty, input, sendBtn, stopBtn;
  let inFlight = false;
  let abortController = null;
  let currentTypingFinish = null;

  await new Promise(resolve => setTimeout(resolve, 100));

  chatBox = document.getElementById("chat-box");
  chatEmpty = document.getElementById("chat-empty");
  input = document.getElementById("chat-message");
  sendBtn = document.getElementById("chat-send");
  stopBtn = document.getElementById("chat-stop");

  initializeMessages();

  if (CONFIG?.ui) {
    const root = document.documentElement;
    const {
      primaryColor,
      secondaryColor,
      primaryGradientDegree,
      gradientDegree,
      headerTextColor,
      placeholderHighlightColor
    } = CONFIG.ui;

    const gradientRegex = /linear-gradient\(([^,]+),\s*([^,]+),\s*([^)]+)\)/i;

    let startColor = primaryColor || "";
    let endColor = secondaryColor || "";
    let angle = primaryGradientDegree || gradientDegree || "";

    const normalize = (value) => (typeof value === "string" ? value.trim() : value);
    startColor = normalize(startColor);
    endColor = normalize(endColor);
    angle = normalize(angle);

    const extractGradient = (value) => {
      if (typeof value !== "string") return null;
      const match = value.match(gradientRegex);
      if (!match) return null;
      return match.slice(1).map((part) => part.trim());
    };

    const parsedGradient = extractGradient(primaryColor) || extractGradient(secondaryColor);
    if (parsedGradient) {
      const [matchedAngle, matchedStart, matchedEnd] = parsedGradient;
      angle = angle || matchedAngle;
      startColor = startColor && !startColor.startsWith("linear-gradient")
        ? startColor
        : matchedStart;
      endColor = endColor && !endColor.startsWith("linear-gradient")
        ? endColor
        : matchedEnd;
    }

    if (!startColor && endColor) {
      startColor = endColor;
    }

    if (startColor && !endColor) {
      endColor = startColor;
    }

    if (!angle && startColor !== endColor) {
      angle = "135deg";
    }

    const gradientValue = startColor && endColor
      ? angle
        ? `linear-gradient(${angle}, ${startColor}, ${endColor})`
        : `linear-gradient(135deg, ${startColor}, ${endColor})`
      : startColor || endColor || "";

    if (angle) root.style.setProperty("--chat-primary-angle", angle);
    if (startColor) root.style.setProperty("--chat-primary-start", startColor);
    if (endColor) root.style.setProperty("--chat-primary-end", endColor);
    if (startColor) root.style.setProperty("--chat-primary-solid", startColor);
    if (gradientValue) root.style.setProperty("--chat-primary", gradientValue);

    const highlightGradient = placeholderHighlightColor || gradientValue;
    if (highlightGradient) {
      root.style.setProperty("--chat-placeholder-highlight", highlightGradient);
    }
    if (startColor) {
      root.style.setProperty("--chat-placeholder-highlight-solid", startColor);
    }

    if (headerTextColor) {
      root.style.setProperty("--chat-header-text", headerTextColor);
    }
  }

  async function bootstrapAuth() {
    try {
      const storedToken = AuthService.getStoredToken();
      if (storedToken) {
        AuthService.clearToken();
      }

      const storedContext = AuthService.getTokenContext?.();
      if (storedContext?.valid) {
        AuthService.clearTokenContext();
      }

      let pluginLookup = await AuthService.lookupPluginCredentials().catch(() => null);

      if (pluginLookup?.plugin_token) {
        AuthService.storeToken(pluginLookup.plugin_token);
      }

      if (pluginLookup?.plugin_token || pluginLookup?.is_active === true) {
        const context = {
          valid: true,
          collection_id: pluginLookup?.collection_id || null,
          user_id: pluginLookup?.user_id || null,
          username: pluginLookup?.username || null,
          website_id: pluginLookup?.website_id || null
        };
        AuthService.storeTokenContext?.(context);
        return { token: pluginLookup?.plugin_token || null, context };
      }

      const pluginToken = AuthService.getConfiguredPluginToken?.();
      if (pluginToken) {
        const pluginVerification = await AuthService.verifyToken(pluginToken);
        if (pluginVerification?.valid) {
          AuthService.storeToken(pluginToken);
          return { token: pluginToken, context: pluginVerification };
        }

        return null;
      }

      const creds = AuthService.getTestCredentials();
      if (!creds) {
        return null;
      }

      const auth = await AuthService.login(creds);
      const accessToken = auth?.access_token;
      if (!accessToken) {
        return null;
      }

      const verification = await AuthService.verifyToken(accessToken);
      if (!verification?.valid) {
        AuthService.clearToken();
        return null;
      }

      return { token: accessToken, context: verification };
    } catch (error) {
      return null;
    }
  }

  if (CONFIG.ui.logoUrl) {
    const headerLogo = document.querySelector('.header .logo');
    if (headerLogo && !headerLogo.querySelector('img.chat-global-logo')) {
      const img = document.createElement('img');
      img.src = CONFIG.ui.logoUrl;
      img.alt = CONFIG.ui.logoAlt || 'Logo';
      img.className = 'chat-global-logo';
      headerLogo.prepend(img);
    }
  }

  document.addEventListener("click", async (e) => {
    const downloadBtn = e.target.closest(".source-download");
    if (downloadBtn) {
      e.preventDefault();
      await handleDownloadSource(
        downloadBtn.dataset.sourceRef,
        downloadBtn.dataset.sourceName,
        downloadBtn
      );
      return;
    }

    if (e.target.id === "chat-send") {
      await handleSendMessage();
    } else if (e.target.id === "chat-stop") {
      handleStop();
    } else if (e.target.id === "new-chat-btn" || e.target.closest("#new-chat-btn")) {
      handleNewChat();
    }
  });

  document.addEventListener("keypress", async (e) => {
    if (e.target.id === "chat-message" && e.key === "Enter") {
      e.preventDefault();
      if (token) {
        await handleSendMessage();
      }
    }
  });

  async function handleSendMessage() {
    // Double-check that we're not already processing a message
    if (inFlight) {
      return;
    }
    
    const userMsg = input.value.trim();
    if (!userMsg) {
      return;
    }

    // Set inFlight flag and disable UI elements
    inFlight = true;
    abortController = new AbortController();
    
    try {
      input.disabled = true;
      if (sendBtn) {
        sendBtn.disabled = true;
        sendBtn.innerHTML = "⏳";
      }
      if (stopBtn) stopBtn.style.display = "none";

      addMessage({ user: true, text: userMsg, formatted: false });
      input.value = "";
      input.dispatchEvent(new Event("input", { bubbles: true }));

      const typingIndicator = showTypingIndicator();

      const reply = await chatService.sendMessage(userMsg, { signal: abortController.signal });
      removeTypingIndicator(typingIndicator);
      input.disabled = false;
      if (stopBtn) stopBtn.style.display = "inline-flex";
      await typeAssistantMessage(reply.text, reply.sources).then(() => {
        ui.updateContextIndicator(chatService.getContextInfo());
      });
    } catch (error) {
      // Re-enable input and send button on error
      input.disabled = false;
      if (sendBtn) {
        sendBtn.disabled = false;
        sendBtn.innerHTML = "➤";
      }
      
      if (error?.name !== 'AbortError') {
        addMessage({
          user: false,
          text: "Sorry, I encountered an error. Please try again.",
          formatted: false,
          isError: true
        });
      }
    } finally {
      // Ensure send button is re-enabled even if there was an error
      if (sendBtn) {
        sendBtn.disabled = false;
        sendBtn.innerHTML = "➤";
      }
      inFlight = false;
      abortController = null;
    }
  }

  function handleStop() {
    if (typeof currentTypingFinish === 'function') {
      clearInterval(typingInterval);
      typingInterval = null;
      currentTypingFinish();
      if (chatBox) chatBox.scrollTop = chatBox.scrollHeight;
    }
  }

  function handleNewChat() {
    if (!ui.canTriggerNewChat()) return;
    ui.startNewChatCooldown();

    clearInterval(typingInterval);
    typingInterval = null;
    inFlight = false;
    if (stopBtn) stopBtn.style.display = "none";
    abortController = null;

    chatService.clearContext();
    initializeMessages();
    ui.updateContextIndicator(chatService.getContextInfo());
    input.value = "";
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.focus();
  }

  function addMessage(message) {
    const storedMessage = {
      user: Boolean(message.user),
      text: message.text || "",
      formatted: Boolean(message.formatted),
      timestamp: message.timestamp || new Date().toISOString(),
      isError: Boolean(message.isError),
      isTyping: Boolean(message.isTyping),
      isTypingIndicator: Boolean(message.isTypingIndicator),
      sources: message.sources || []
    };
    messages.push(storedMessage);
    renderMessages();
    return storedMessage;
  }

  function showTypingIndicator() {
    return addMessage({ user: false, text: "", formatted: false, isTypingIndicator: true });
  }

  function removeTypingIndicator(messageRef) {
    const index = messages.indexOf(messageRef);
    if (index !== -1) {
      messages.splice(index, 1);
      renderMessages();
    }
  }

  function typeAssistantMessage(fullText, sources = []) {
    return new Promise((resolve) => {
      clearInterval(typingInterval);

      const typingMessage = addMessage({ user: false, text: "", formatted: true, isTyping: true, sources });
      let completed = false;

      const finishTyping = () => {
        if (completed) return;
        completed = true;
        typingMessage.text = fullText || "";
        typingMessage.isTyping = false;
        renderMessages();
        resolve();
        if (stopBtn) stopBtn.style.display = "none";
        sendBtn.disabled = false;
        sendBtn.innerHTML = "➤";
        inFlight = false;
        abortController = null;
        currentTypingFinish = null;
        input.focus();
        if (chatBox) chatBox.scrollTop = chatBox.scrollHeight;
      };

      if (!fullText || document.hidden) {
        finishTyping();
        return;
      }

      let index = 0;
      typingInterval = setInterval(() => {
        if (document.hidden) {
          clearInterval(typingInterval);
          typingInterval = null;
          finishTyping();
          return;
        }

        index += 1;
        typingMessage.text = fullText.slice(0, index);
        renderMessages();

        if (index >= fullText.length) {
          clearInterval(typingInterval);
          typingInterval = null;
          finishTyping();
        }
      }, 15);
      currentTypingFinish = finishTyping;
    });
  }

  function initializeMessages() {
    messages.length = 0;
    renderMessages();
  }

  function renderMessages() {
    if (!chatBox) return;
    const wasNearBottom = chatBox.scrollHeight - chatBox.clientHeight - chatBox.scrollTop <= 32;
    const previousScrollTop = chatBox.scrollTop;

    const html = messages.map(renderMessageHtml).join("");
    chatBox.innerHTML = html;

    if (wasNearBottom) chatBox.scrollTop = chatBox.scrollHeight;
    else chatBox.scrollTop = previousScrollTop;

    if (chatEmpty) chatEmpty.style.display = messages.length ? "none" : "flex";
  }

  function renderMessageHtml(message) {
    if (message.user) {
      return `<div class="plugin-msg msg user">
        <div class="plugin-msg-content msg-content">${escapeHtml(message.text)}</div>
      </div>`;
    }
    if (message.isTypingIndicator) {
      return `<div class="plugin-msg msg bot typing">
        <div class="plugin-typing-dots typing-dots"><span></span><span></span><span></span></div>
      </div>`;
    }
    const classes = ["msg", "bot"];
    if (message.isError) classes.push("error");
    if (message.isTyping) classes.push("typing-text");
    const content = renderAssistantContent(message);
    return `<div class="plugin-msg ${classes.join(" ")}">${content}</div>`;
  }

  function renderAssistantContent(message) {
    if (message.formatted) {
      const html = renderAssistantText(message.text, message.sources || []);
      return `<div class="plugin-msg-content msg-content text-sm"><div class="plugin-prose prose prose-sm max-w-none">${html}</div></div>`;
    }
    return `<div class="plugin-msg-content msg-content">${escapeHtml(message.text)}</div>`;
  }

  // --- DOWNLOAD HANDLER ---
  async function handleDownloadSource(sourceRef, downloadName, triggerEl) {
    if (!sourceRef && !downloadName) return;

    const button = triggerEl;
    const initialLabel = button?.textContent;

    try {
      if (button) {
        button.disabled = true;
        button.classList.add("is-loading");
        button.textContent = "Downloading…";
      }

      await chatService.ensureToken();
      const token = chatService.token;
      if (!token) throw new Error("Missing authentication token");

      const headers = { Authorization: `Bearer ${token}` };
      const normalizedName = (downloadName || "").trim();
      const ref = (sourceRef || "").trim();
      const base = (CONFIG.apiBase || "").replace(/\/+$/, "");

      if (!ref && !normalizedName) {
        throw new Error("Missing file reference");
      }

      const encodedRef = encodeURIComponent(ref || normalizedName);
      const downloadUrl = `${base}/files/download/${encodedRef}`;

      const response = await fetch(downloadUrl, { headers });
      if (!response.ok) {
        throw new Error(`Download failed (${response.status})`);
      }

      const blob = await response.blob();
      const filename = normalizedName || ref || "source";
      triggerBrowserDownload(blob, filename);
      return;
    } catch (err) {
      if (button) {
        button.classList.add("download-error");
        button.textContent = initialLabel || "Download failed";
      }
      alert("Unable to download this source. Please try again later.");
    } finally {
      if (button) {
        button.disabled = false;
        button.classList.remove("is-loading");
        if (initialLabel) button.textContent = initialLabel;
      }
    }
  }

  function triggerBrowserDownload(blob, filename) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename || "download";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  function extractDownloadName(label) {
    const trimmed = (label || "").trim();
    const match = trimmed.match(/\(([^)]+)\)\s*$/);
    if (match) {
      const base = trimmed.replace(match[0], "").trim();
      return { displayLabel: base || match[1], downloadName: match[1] };
    }
    return { displayLabel: trimmed, downloadName: trimmed };
  }

  function escapeAttribute(value) {
    return `${value ?? ""}`.replace(/[&"'<>]/g, (char) => {
      switch (char) {
        case "&": return "&amp;";
        case '"': return "&quot;";
        case "'": return "&#39;";
        case "<": return "&lt;";
        case ">": return "&gt;";
        default: return "";
      }
    });
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text ?? "";
    return div.innerHTML;
  }

  // --- MAIN TEXT RENDERER ---
function renderAssistantText(text, sources = []) {
  if (!text) return "";

  // Normalize label like "Source 4: Leave_Policy.pdf" to match file_name
  function normalizeFileName(label) {
    return label.replace(/^Source\s*\d+:\s*/, "").trim();
  }

  // Build map of file_name => file_id from the API response
  // API returns: sources: [{ file_name: "...", file_id: "...", chunk_indices: [...] }]
  const fileNameToIdMap = {};
  const fileIdToNameMap = {};
  
  if (Array.isArray(sources)) {
    sources.forEach(source => {
      if (source.file_name && source.file_id) {
        const fileName = source.file_name.trim();
        const fileId = source.file_id.trim();
        fileNameToIdMap[fileName] = fileId;
        fileIdToNameMap[fileId] = fileName;
      }
    });
  }

  const linkTokens = [];
  const tableTokens = [];

  // Process markdown links [Label](ref)
  let processed = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, label, ref) => {
    const extraction = extractDownloadName(label);
    const normalized = normalizeFileName(extraction.downloadName);
    const fileRef = fileNameToIdMap[normalized] || ref.trim(); // Use file_id from API
    const dataRef = escapeAttribute(fileRef);
    const dataName = escapeAttribute(normalized);
    const buttonLabel = escapeHtml(extraction.displayLabel);
    const token = `__SOURCE_LINK_${linkTokens.length}__`;
    linkTokens.push(`<button type="button" class="source-download" data-source-ref="${dataRef}" data-source-name="${dataName}">${buttonLabel}</button>`);
    return token;
  });

  const plainSourceTokens = [];
  const lines = processed.split(/\n/);
  let inSourcesSection = false;

  for (let i = 0; i < lines.length; i += 1) {
    const trimmed = lines[i].trim();
    if (/^Sources?:/i.test(trimmed)) {
      inSourcesSection = true;
      continue;
    }
    if (!inSourcesSection) continue;
    if (!trimmed) continue;
    if (trimmed.includes("__SOURCE_LINK_")) continue;

    const match = lines[i].match(/^(\s*[-•]?\s*)(.+?\.[A-Za-z0-9]{2,12})(\s*)$/);
    if (match) {
      const rawName = match[2].trim();
      const normalized = normalizeFileName(rawName);
      const fileRef = fileNameToIdMap[normalized] || normalized; // Use file_id from API
      const displayName = normalized;
      const token = `__PLAIN_SOURCE_${plainSourceTokens.length}__`;
      plainSourceTokens.push({ token, fileId: fileRef, displayName });
      lines[i] = `${match[1]}${token}${match[3]}`;
      continue;
    }

    const fallback = lines[i].match(/^(\s*[-•]?\s*)(.+?)(\s*)$/);
    if (fallback) {
      const rawName = fallback[2].trim();
      const normalized = normalizeFileName(rawName);
      const fileRef = fileNameToIdMap[normalized] || normalized; // Use file_id from API
      const displayName = normalized;
      const token = `__PLAIN_SOURCE_${plainSourceTokens.length}__`;
      plainSourceTokens.push({ token, fileId: fileRef, displayName });
      lines[i] = `${fallback[1]}${token}${fallback[3]}`;
      continue;
    }

    if (!/^\s*[-•]/.test(lines[i])) inSourcesSection = false;
  }

  processed = lines.join("\n");

  // Tables
  processed = processed.replace(/(^|\n)((?:\s*\|[^\n]*\n){2,})/g, (m, lead, block) => {
    const rows = block.trim().split(/\n/).map(r => r.trim());
    if (rows.length < 2) return m;
    const header = rows[0];
    const divider = rows[1];
    if (!/^\|?\s*:?[-\s|:]+:?\s*\|?$/.test(divider)) return m;
    const bodyRows = rows.slice(2);
    const parseRow = (row) => row.replace(/^\|/, '').replace(/\|$/, '').split('|').map(c => c.trim());
    const ths = parseRow(header).map(h => `<th>${escapeHtml(h)}</th>`).join('');
    const trs = bodyRows.map(r => `<tr>${parseRow(r).map(c => `<td>${escapeHtml(c)}</td>`).join('')}</tr>`).join('');
    const html = `<table class="plugin-table chat-table"><thead><tr>${ths}</tr></thead><tbody>${trs}</tbody></table>`;
    const token = `__TABLE_BLOCK_${tableTokens.length}__`;
    tableTokens.push(html);
    return `${lead}${token}\n`;
  });

  processed = processed.replace(/<table[\s\S]*?<\/table>/gi, (tbl) => {
    const unsafeTag = /<(?!\/?(?:table|thead|tbody|tr|th|td)(\b|>))/i.test(tbl);
    if (unsafeTag) return escapeHtml(tbl);
    const token = `__TABLE_BLOCK_${tableTokens.length}__`;
    tableTokens.push(tbl);
    return token;
  });

  let safe = escapeHtml(processed);
  safe = safe.replace(/\r\n/g, "\n");
  linkTokens.forEach((html, index) => { safe = safe.replace(`__SOURCE_LINK_${index}__`, html); });
  plainSourceTokens.forEach(({ token, fileId, displayName }) => {
    const dataRef = escapeAttribute(fileId);
    const dataName = escapeAttribute(displayName);
    const buttonHtml = `<button type="button" class="source-download" data-source-ref="${dataRef}" data-source-name="${dataName}">${escapeHtml(displayName)}</button>`;
    safe = safe.replace(token, buttonHtml);
  });

  safe = safe.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  safe = safe.replace(/(^|\n)Sources?:/g, (match) => `<div class="source-section-title">${match.trim()}</div>`);
  safe = safe.replace(/^\s*-\s+/gm, "• ");
  safe = safe.replace(/\n\d+\./g, "<br/>$&");
  safe = safe.replace(/\n-\s*/g, "<br/>• ");
  safe = safe.replace(/\n/g, "<br/>");

  tableTokens.forEach((html, index) => {
    const token = `__TABLE_BLOCK_${index}__`;
    safe = safe.replace(token, html);
  });

  return safe;
}


})();
