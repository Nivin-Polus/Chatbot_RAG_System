// config.js

async function getConfig() {
  let configUrl = "../dist/assets/config.json";

  if (typeof document !== "undefined") {
    let script =
      document.currentScript ||
      document.querySelector('script[src*="chatbot.min.js"]') ||
      document.querySelector('script[src*="chatbot.js"]');

    if (script?.src) {
      try {
        const scriptUrl = new URL(script.src, window.location.href);
        scriptUrl.search = "";
        scriptUrl.hash = "";
        configUrl = new URL("assets/config.json", scriptUrl).href;
      } catch (error) {
        // Unable to resolve config URL
      }
    }
  }

  const response = await fetch(configUrl);
  if (!response.ok) {
    throw new Error(`Failed to load config.json: ${response.status}`);
  }
  const data = await response.json();
  return data;
}

const DEFAULT_CONFIG = {
  apiBase: "",
  websiteUrl: typeof window !== "undefined" ? window.location.href : null,
  pluginToken: null,
  pluginUsername: null,
  pluginActive: true,
  auth: {
    username: "",
    password: ""
  },
  collectionId: "",
  collectionName: null,
  configUrl: "",
  ui: {
    apiBase: "",
    logoUrl: "",
    logoAlt: "",
    placeholderLogoUrl: "",
    iconsBaseUrl: "",
    primaryColor: "",
    secondaryColor: "",
    primaryGradientDegree: "",
    gradientDegree: "",
    headerTextColor: "",
    headerTitle: "Chat Assistant",
    welcomeMessage: "",
    inputPlaceholder: "",
    placeholderHighlightText: "",
    placeholderHighlightColor: ""
  }
};

const UI_KEYS = [
  "logoUrl",
  "logoAlt",
  "placeholderLogoUrl",
  "iconsBaseUrl",
  "primaryColor",
  "secondaryColor",
  "primaryGradientDegree",
  "gradientDegree",
  "headerTextColor",
  "headerTitle",
  "welcomeMessage",
  "inputPlaceholder",
  "placeholderHighlightText",
  "placeholderHighlightColor"
];

const CONFIG = {
  ...DEFAULT_CONFIG,
  auth: { ...DEFAULT_CONFIG.auth },
  ui: { ...DEFAULT_CONFIG.ui }
};

let configPromise = null;

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function merge(target, overrides) {
  if (!isObject(target) || !isObject(overrides)) {
    return target;
  }

  Object.entries(overrides).forEach(([key, value]) => {
    if (isObject(value)) {
      target[key] = merge(isObject(target[key]) ? { ...target[key] } : {}, value);
    } else if (value !== undefined) {
      target[key] = value;
    }
  });

  return target;
}

function normalizeConfig(raw = {}) {
  if (!isObject(raw)) {
    return {};
  }

  const overrides = {};
  const uiOverrides = {};

  Object.entries(raw).forEach(([key, value]) => {
    if (value === undefined) return;

    if (key === "apiBase1") {
      uiOverrides.apiBase = value;
      return;
    }

    if (UI_KEYS.includes(key)) {
      uiOverrides[key] = value;
      return;
    }

    overrides[key] = value;
  });

  if (Object.keys(uiOverrides).length) {
    overrides.ui = uiOverrides;
  }

  return overrides;
}

function applyRuntimeConfig(overrides = {}) {
  if (!isObject(overrides)) {
    return CONFIG;
  }

  merge(CONFIG, overrides);
  return CONFIG;
}

async function loadConfig() {
  try {
    const raw = await getConfig();
    const overrides = normalizeConfig(raw);
    applyRuntimeConfig(overrides);
  } catch (error) {
    // Failed to load config
  }

  if (!CONFIG.websiteUrl && typeof window !== "undefined") {
    CONFIG.websiteUrl = window.location.href;
  }

  return CONFIG;
}

function initConfig(options = {}) {
  if (options?.forceRefresh) {
    configPromise = null;
  }

  if (!configPromise) {
    configPromise = loadConfig();
  }

  return configPromise;
}

export { CONFIG, applyRuntimeConfig, getConfig, initConfig };
