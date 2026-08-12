/**
 * state.js - 全局状态和 DOM 元素引用
 * 
 * 所有模块共享的状态变量和 DOM 引用。
 * 必须在其他模块之前加载。
 */

// ============================================================================
// API 基础路径
// ============================================================================
const API_BASE = '/api';
window.API_BASE = API_BASE;

// ============================================================================
// API 错误归一化
// ============================================================================

function extractApiErrorMessage(payload, fallback = '请求失败') {
    if (!payload) return fallback;

    if (typeof payload === 'string') {
        const trimmed = payload.trim();
        if (!trimmed) return fallback;
        try {
            return extractApiErrorMessage(JSON.parse(trimmed), fallback);
        } catch (_) {
            return trimmed;
        }
    }

    if (Array.isArray(payload)) {
        return payload.map(item => extractApiErrorMessage(item, '')).filter(Boolean).join('；') || fallback;
    }

    if (typeof payload === 'object') {
        return extractApiErrorMessage(
            payload.detail || payload.message || payload.error || payload.reason,
            fallback
        );
    }

    return String(payload);
}

function formatApiErrorMessage(error, fallback = '请求失败') {
    const rawMessage = error instanceof Error
        ? error.message
        : extractApiErrorMessage(error, fallback);
    const message = extractApiErrorMessage(rawMessage, fallback);

    if (/ServiceUnavailable|UNAVAILABLE|high demand|503/i.test(message)) {
        return 'AI 服务暂时繁忙（503），请稍后重试，或临时切换其他模型。';
    }
    if (/API key|api_key|Unauthorized|401|403|permission|quota/i.test(message)) {
        return 'AI 配置、额度或 API Key 可能不可用，请检查模型配置。';
    }
    if (/Failed to fetch|NetworkError|Load failed/i.test(message)) {
        return '本地服务连接失败，请确认 BookOrganizer 正在运行。';
    }

    return message.length > 300 ? `${message.slice(0, 300)}...` : message;
}

async function readApiError(response, fallback = '请求失败') {
    try {
        const contentType = response.headers.get('content-type') || '';
        if (contentType.includes('application/json')) {
            return formatApiErrorMessage(await response.json(), fallback);
        }
        return formatApiErrorMessage(await response.text(), fallback);
    } catch (_) {
        return fallback;
    }
}

async function fetchJson(url, options = {}, fallback = '请求失败') {
    const response = await fetch(url, options);
    if (!response.ok) {
        throw new Error(await readApiError(response, fallback));
    }
    if (response.status === 204) return null;
    return response.json();
}

window.extractApiErrorMessage = extractApiErrorMessage;
window.formatApiErrorMessage = formatApiErrorMessage;
window.readApiError = readApiError;
window.fetchJson = fetchJson;

// ============================================================================
// HTML 转义工具（防 XSS）
// ============================================================================

function escapeHtml(str) {
    if (str == null) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}
window.escapeHtml = escapeHtml;

// ============================================================================
// 状态订阅机制（发布-订阅，可选使用）
// ============================================================================

const _stateListeners = {};

/**
 * 订阅状态变化。
 * @param {string} key - 状态键名（如 'books', 'currentBook'）
 * @param {function} callback - 回调函数 (newValue, key) => void
 * @returns {function} 取消订阅函数
 */
function subscribeState(key, callback) {
    if (!_stateListeners[key]) _stateListeners[key] = [];
    _stateListeners[key].push(callback);
    return () => {
        _stateListeners[key] = _stateListeners[key].filter(cb => cb !== callback);
    };
}
window.subscribeState = subscribeState;

/**
 * 通知状态变化（供 setState 等调用）。
 * @param {string} key
 * @param {*} value
 */
function _notifyState(key, value) {
    if (_stateListeners[key]) {
        for (const cb of _stateListeners[key]) cb(value, key);
    }
}
window._notifyState = _notifyState;

// ============================================================================
// 全局状态变量
// ============================================================================

let books = [];
let currentBook = null;
let currentBookFilename = null;
let currentBookSummary = '';
// 同步到 window 以确保跨模块访问一致
window.currentBookSummary = currentBookSummary;
let isSequentialMode = false;
let currentBrowsePath = '';
let currentPickerType = '';
let batchPlan = [];
let shouldStopBatch = false;
let isBatchRunning = false;
let isWebSearchEnabled = true;
window.isWebSearchEnabled = isWebSearchEnabled; // 同步到 window
let currentMode = 'organize'; // 'organize' | 'manage'
window.currentMode = currentMode;
let libraryBooks = [];
let libraryStats = { total: 0, enhanced: 0, not_enhanced: 0 };
let currentStatsFilter = null; // null | 'skipped' | 'enhanced' | 'not_enhanced'
let sidebarSearchQuery = '';   // 搜索关键词
let searchDebounceTimer = null; // 搜索防抖定时器
// 暴露到 window
window.sidebarSearchQuery = sidebarSearchQuery;
window.searchDebounceTimer = searchDebounceTimer;
let config = {};

/**
 * 响应式状态更新辅助函数。
 * 更新变量值并通知订阅者（如果有）。
 * 也可通过 window.setState 访问。
 *
 * @param {string} key - 状态键名
 * @param {*} value - 新值
 */
function setState(key, value) {
    switch (key) {
        case 'books': books = value; break;
        case 'currentBook': currentBook = value; break;
        case 'currentBookFilename': currentBookFilename = value; break;
        case 'currentBookSummary':
            currentBookSummary = value;
            window.currentBookSummary = value;
            break;
        case 'isSequentialMode': isSequentialMode = value; break;
        case 'currentBrowsePath': currentBrowsePath = value; break;
        case 'currentPickerType': currentPickerType = value; break;
        case 'shouldStopBatch': shouldStopBatch = value; break;
        case 'isBatchRunning': isBatchRunning = value; break;
        case 'isWebSearchEnabled':
            isWebSearchEnabled = value;
            window.isWebSearchEnabled = value;
            break;
        case 'currentMode':
            currentMode = value;
            window.currentMode = value;
            break;
        case 'config': config = value; break;
        default: break;
    }
    _notifyState(key, value);
}
window.setState = setState;

// 分析中止控制器
let currentAnalysisController = null;
// 元数据识别中止控制器
let currentIdentifyController = null;
// 增强简介中止控制器
let currentEnhancedSummaryController = null;
// 目录提取中止控制器
let currentTocController = null;

// 将 controller 暴露到 window 以确保跨模块访问
window.currentAnalysisController = currentAnalysisController;
window.currentIdentifyController = currentIdentifyController;
window.currentEnhancedSummaryController = currentEnhancedSummaryController;
window.currentTocController = currentTocController;

// 当前图书的操作完成状态（用于智能联动）
let bookOperationStatus = {
    metadataIdentified: false,  // 识别信息已完成
    summaryGenerated: false,    // 增强简介已完成
    tocExtracted: false,        // 识别目录已完成
    metadataManuallyEdited: false  // 用户手动编辑过元数据
};
window.bookOperationStatus = bookOperationStatus;

/**
 * 重置图书操作状态（切换图书时调用）
 */
function resetBookOperationStatus() {
    bookOperationStatus.metadataIdentified = false;
    bookOperationStatus.summaryGenerated = false;
    bookOperationStatus.tocExtracted = false;
    bookOperationStatus.metadataManuallyEdited = false;
}
window.resetBookOperationStatus = resetBookOperationStatus;

/**
 * 获取当前图书的路径（统一方法，自动适配两种模式）
 * 
 * - 在库管理模式：返回 currentBookPath（包含子目录的完整相对路径）
 * - 在入库整理模式：返回 currentBook（文件名）
 * 
 * @returns {string|null} 当前图书路径
 */
function getCurrentBookPath() {
    const mode = window.currentMode || currentMode || 'organize';

    // 在库管理模式优先使用完整相对路径。
    if (mode === 'manage' && window.currentBookPath) {
        return window.currentBookPath;
    }
    // 入库整理模式优先使用当前待入库文件名，避免沿用库管理遗留路径。
    if (window.currentBook) {
        return window.currentBook;
    }
    if (currentBook) {
        return currentBook;
    }
    if (window.currentBookPath) {
        return window.currentBookPath;
    }
    // 最后尝试从 DOM 获取
    const currentFilename = document.getElementById('current-filename')?.textContent;
    if (currentFilename && currentFilename !== 'Filename.pdf') {
        return currentFilename;
    }
    return null;
}
window.getCurrentBookPath = getCurrentBookPath;

function normalizeBookTarget(target) {
    return target ? String(target).replace(/\\/g, '/').replace(/^\.\/+/, '') : '';
}
window.normalizeBookTarget = normalizeBookTarget;

function isCurrentBookTarget(target) {
    if (!target) return true;
    const current = getCurrentBookPath();
    return normalizeBookTarget(current) === normalizeBookTarget(target);
}
window.isCurrentBookTarget = isCurrentBookTarget;

const bookScopedAsyncTasks = {};

function beginBookScopedTask(name, target, options = {}) {
    const previous = bookScopedAsyncTasks[name];
    if (previous && previous.controller && options.abortPrevious !== false) {
        previous.controller.abort();
    }

    const controller = options.controller || new AbortController();
    const task = {
        name,
        target,
        normalizedTarget: normalizeBookTarget(target),
        controller,
        sequence: (previous?.sequence || 0) + 1
    };
    bookScopedAsyncTasks[name] = task;

    const isCurrent = () => {
        if (bookScopedAsyncTasks[name] !== task) return false;
        if (!task.normalizedTarget) return true;
        return isCurrentBookTarget(task.normalizedTarget);
    };

    const finish = () => {
        if (bookScopedAsyncTasks[name] === task) {
            delete bookScopedAsyncTasks[name];
        }
    };

    return {
        controller,
        signal: controller.signal,
        target,
        sequence: task.sequence,
        isCurrent,
        finish
    };
}

function cancelBookScopedTask(name) {
    const task = bookScopedAsyncTasks[name];
    if (task && task.controller) {
        task.controller.abort();
    }
    delete bookScopedAsyncTasks[name];
}

window.beginBookScopedTask = beginBookScopedTask;
window.cancelBookScopedTask = cancelBookScopedTask;
window.bookScopedAsyncTasks = bookScopedAsyncTasks;

/**
 * 取消所有正在进行的操作（互斥逻辑）
 */
function cancelAllOperations() {
    cancelBookScopedTask('toc-load');
    cancelBookScopedTask('summary-load');
    cancelBookScopedTask('toc-extract');
    cancelBookScopedTask('enhanced-summary');

    // 取消分析
    if (currentAnalysisController || window.currentAnalysisController) {
        (currentAnalysisController || window.currentAnalysisController).abort();
        currentAnalysisController = null;
        window.currentAnalysisController = null;
        window.currentAnalysisTaskId = null;
    }
    // 取消识别
    if (currentIdentifyController || window.currentIdentifyController) {
        (currentIdentifyController || window.currentIdentifyController).abort();
        currentIdentifyController = null;
        window.currentIdentifyController = null;
    }
    // 取消增强简介
    if (currentEnhancedSummaryController || window.currentEnhancedSummaryController) {
        (currentEnhancedSummaryController || window.currentEnhancedSummaryController).abort();
        currentEnhancedSummaryController = null;
        window.currentEnhancedSummaryController = null;
    }
    // 取消目录提取
    if (currentTocController || window.currentTocController) {
        (currentTocController || window.currentTocController).abort();
        currentTocController = null;
        window.currentTocController = null;
    }

    // 重置按钮UI状态（包括恢复原始文本）
    const btnIdentify = document.getElementById('btn-identify');
    const btnSummary = document.getElementById('btn-gen-summary');
    const btnToc = document.getElementById('btn-extract-toc');
    const analyzeBtn = document.getElementById('analyze-btn');

    if (btnIdentify && btnIdentify.classList.contains('analyzing')) {
        btnIdentify.classList.remove('analyzing');
        btnIdentify.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> 识别信息';
    }
    if (btnSummary && btnSummary.classList.contains('analyzing')) {
        btnSummary.classList.remove('analyzing');
        btnSummary.innerHTML = '<i class="fa-solid fa-file-lines"></i> 增强简介';
        delete btnSummary.dataset.originalContent;
    }
    if (btnToc && btnToc.classList.contains('analyzing')) {
        btnToc.classList.remove('analyzing');
        btnToc.innerHTML = '<i class="fa-solid fa-list-ol"></i> 识别目录';
    }
    if (analyzeBtn && analyzeBtn.classList.contains('analyzing')) {
        analyzeBtn.classList.remove('analyzing');
        // analyzeBtn 的文本由 showAnalysisLoading(false) 处理
    }

    // 隐藏分析加载状态
    if (typeof showAnalysisLoading === 'function') {
        showAnalysisLoading(false);
    }
}
window.cancelAllOperations = cancelAllOperations;

/**
 * 检查是否有正在进行的操作
 * @returns {string|null} 正在进行的操作名称，或 null
 */
function getActiveOperation() {
    // 检查模块局部变量和 window 上的变量（确保跨模块兼容）
    if (currentAnalysisController || window.currentAnalysisController) return '信息及目录分析';
    if (currentIdentifyController || window.currentIdentifyController) return '元数据识别';
    if (currentEnhancedSummaryController || window.currentEnhancedSummaryController) return '增强简介生成';
    if (currentTocController || window.currentTocController) return '目录识别';
    return null;
}
window.getActiveOperation = getActiveOperation;

/**
 * 确认取消正在进行的操作
 * @param {string} newOperationName 新操作的名称
 * @returns {Promise<boolean>} 用户是否确认
 */
async function confirmCancelOperation(newOperationName) {
    const activeOp = getActiveOperation();
    if (!activeOp) return true; // 没有正在进行的操作

    return confirm(`当前正在进行"${activeOp}"操作。\n\n是否停止当前操作并开始"${newOperationName}"？`);
}
window.confirmCancelOperation = confirmCancelOperation;

// 通知超时定时器
let notificationTimeout = null;

// 封面缩放状态
let currentZoom = 1;
let isDragging = false;
let startX = 0, startY = 0;
let currentTranslateX = 0, currentTranslateY = 0;

// ============================================================================
// DOM 元素引用
// ============================================================================

const bookListEl = document.getElementById('book-list');
const bookDetailEl = document.getElementById('book-detail');
const emptyStateEl = document.getElementById('empty-state');
const transferStatusEl = document.getElementById('transfer-status');
const transferStatusTextEl = document.getElementById('transfer-status-text');
const currentFilenameEl = document.getElementById('current-filename');
const currentParsedInfoEl = document.getElementById('current-parsed-info');
const analyzeBtn = document.getElementById('analyze-btn');
const skipBtn = document.getElementById('skip-btn');
const deleteBtn = document.getElementById('delete-btn');
const analysisResultEl = document.getElementById('analysis-result');
const analysisLoadingEl = document.getElementById('analysis-loading');
const aiSummaryEl = document.getElementById('ai-summary');
const suggestionListEl = document.getElementById('suggestion-list');
const engineSelect = document.getElementById('engine-select');
const webSearchBtn = document.getElementById('web-search-btn');
const webSearchText = document.getElementById('web-search-text');
const refreshBtn = document.getElementById('refresh-btn');
const settingsBtn = document.getElementById('settings-btn');
const settingsModal = document.getElementById('settings-modal');
const closeSettingsBtn = document.getElementById('close-settings');

// 批量处理元素
const batchBtn = document.getElementById('batch-btn');
const seqBtn = document.getElementById('seq-btn');
const processDropdown = document.getElementById('process-dropdown');
const processDropdownBtn = document.getElementById('process-dropdown-btn');
const batchModal = document.getElementById('batch-modal');
const closeBatchBtn = document.getElementById('close-batch');
const startBatchBtn = document.getElementById('start-batch-btn');
const executeBatchBtn = document.getElementById('execute-batch-btn');
const stopBatchBtn = document.getElementById('stop-batch-btn');
const batchLogEl = document.getElementById('batch-log');
const batchReviewArea = document.getElementById('batch-review-area');
const reviewListEl = document.getElementById('review-list');
const batchProgressEl = document.getElementById('batch-progress');
const batchStatusText = document.getElementById('batch-status-text');

// 目录选择器元素
const dirPickerModal = document.getElementById('dir-picker-modal');
const closeDirPickerBtn = document.getElementById('close-dir-picker');
const pickerCurrentPathEl = document.getElementById('picker-current-path');
const pickerListEl = document.getElementById('picker-list');
const pickerSelectBtn = document.getElementById('picker-select-btn');

// 统计元素
const statTotalEl = document.getElementById('stat-total');
const statSkippedEl = document.getElementById('stat-skipped');
const libNotEnhancedEl = document.getElementById('lib-not-enhanced');

// 封面元素
const bookCoverEl = document.getElementById('book-cover');
const bookIconPlaceholderEl = document.getElementById('book-icon-placeholder');

// AI 配置元素
const aiConfigBtn = document.getElementById('ai-config-btn');
const aiConfigModal = document.getElementById('ai-config-modal');
const closeAIConfigBtn = document.getElementById('close-ai-config');

// 帮助弹窗
const helpBtn = document.getElementById('help-btn');
const helpModal = document.getElementById('help-modal');
const closeHelpBtn = document.getElementById('close-help');
