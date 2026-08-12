/**
 * settings.js - 设置主模块
 * 
 * 元数据识别、文件名模板、目录选择器、快捷开关等。
 * 依赖: state.js, api.js
 * 子模块: settings/model-config.js, settings/google-drive.js, settings/cloud-sync.js
 */

// ============================================================================
// 元数据识别和文件名
// ============================================================================

window.identifyMetadata = async (silent = false) => {
    if (!currentBookFilename) return;

    const btn = document.getElementById('btn-identify');

    // 如果正在分析中且用户点击，则取消操作
    if (btn.classList.contains('analyzing')) {
        if (currentIdentifyController || window.currentIdentifyController) {
            (currentIdentifyController || window.currentIdentifyController).abort();
            currentIdentifyController = null;
            window.currentIdentifyController = null;
        }
        btn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> 识别信息';
        btn.classList.remove('analyzing');
        showNotification('已取消识别', 2000);
        return;
    }

    // 互斥：检查是否有其他操作正在进行，需要用户确认
    const activeOp = getActiveOperation();
    if (activeOp && !silent) {
        const confirmed = await confirmCancelOperation('元数据识别');
        if (!confirmed) return;
    }

    // 取消其他正在进行的操作
    cancelAllOperations();

    // 记录请求时的书籍路径/文件名，用于后续验证
    const requestedPath = window.currentBookPath || window.currentBookFilename || currentBookFilename;
    // Keep reference to basename for UI if needed, but validation should rely on path equality

    currentIdentifyController = new AbortController();
    window.currentIdentifyController = currentIdentifyController;  // 同步到 window

    const engine = document.getElementById('engine-select').value;
    const enableSearch = isWebSearchEnabled;

    const originalText = btn.innerHTML;
    if (!silent) {
        btn.innerHTML = '<div class="spinner-small"></div> 识别中... <i class="fa-solid fa-stop" style="margin-left:4px"></i>';
        btn.classList.add('analyzing');
        // Don't disable - let user click to cancel
    }

    const uiMetadata = {
        title: document.getElementById('meta-title').value.trim(),
        author: document.getElementById('meta-author').value.trim(),
        publisher: document.getElementById('meta-publisher').value.trim(),
        series: document.getElementById('meta-series').value.trim(),
        tags: document.getElementById('meta-tags').value.trim()
    };

    try {
        const data = await fetchJson(`${API_BASE}/identify_metadata`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                filename: requestedPath,  // Send full path if avail
                engine: engine,
                enable_search: enableSearch,
                user_metadata: uiMetadata
            }),
            signal: currentIdentifyController.signal
        }, '识别失败');

        // 验证：只有当前书籍仍然是请求时的书籍才更新 UI
        const currentPath = window.currentBookPath || window.currentBookFilename || currentBookFilename;
        if (currentPath === requestedPath) {
            if (data.title) document.getElementById('meta-title').value = data.title;
            if (data.author) document.getElementById('meta-author').value = data.author;
            if (data.publisher) document.getElementById('meta-publisher').value = data.publisher;
            if (data.series) document.getElementById('meta-series').value = data.series;
            if (data.tags) document.getElementById('meta-tags').value = data.tags;

            applyFilenameTemplate();
            bookOperationStatus.metadataIdentified = true;
            // 点亮保存按钮
            enableSaveButton();
        } else {
            console.log('识别结果已过期，用户已切换到其他书籍');
        }

    } catch (e) {
        if (e.name === 'AbortError') {
            console.log('元数据识别已取消');
            return;
        }
        if (!silent) showNotification(`识别失败: ${e.message}`, 5000, 'error');
    } finally {
        currentIdentifyController = null;
        window.currentIdentifyController = null;
        if (!silent) {
            btn.innerHTML = originalText;
            btn.classList.remove('analyzing');
            btn.disabled = false;
        }
    }
};

window.applyFilenameTemplate = () => {
    if (!currentBookFilename) return;

    const title = document.getElementById('meta-title').value.trim();
    const author = document.getElementById('meta-author').value.trim();
    const publisher = document.getElementById('meta-publisher').value.trim();
    const series = document.getElementById('meta-series').value.trim();
    const tags = document.getElementById('meta-tags').value.trim();

    if (title || author || publisher || series || tags) {
        bookOperationStatus.metadataIdentified = true;
    }

    let template = "{title} - {author}";
    if (window.aiConfig && window.aiConfig.field_extraction_rules && window.aiConfig.field_extraction_rules.filename_prompt) {
        const promptText = window.aiConfig.field_extraction_rules.filename_prompt;
        const templateMatch = promptText.match(/格式为[：:](.*?)['\"\。]/);
        if (templateMatch && templateMatch[1].includes('{')) {
            template = templateMatch[1].trim();
        }
    }

    const ext = currentBookFilename.substring(currentBookFilename.lastIndexOf('.'));

    let newName = template;
    newName = newName.replace(/{title}/g, title || '未命名');
    newName = newName.replace(/{author}/g, author || '佚名');
    newName = newName.replace(/{publisher}/g, publisher || '');
    newName = newName.replace(/{series}/g, series || '');
    newName = newName.replace(/{tags}/g, tags || '');

    newName = newName.replace(/\[\]/g, '');
    newName = newName.replace(/\(\)/g, '');
    newName = newName.replace(/\s+/g, ' ').trim();
    newName = newName.replace(/^\s*-\s*/, '');
    newName = newName.replace(/\s*-\s*$/, '');

    document.getElementById('meta-filename').value = newName + ext;
};

/**
 * transferBook - 保存元数据修改（重命名图书）
 * 
 * 注意: 此函数已与 api.js 中的 saveMetadata 合并统一
 * 保留此入口点是为了向后兼容 HTML 中的 onclick 调用
 */
window.transferBook = async () => {
    // 直接委托给统一的 saveMetadata 函数
    if (window.saveMetadata) {
        await window.saveMetadata();
    }
};

window.updateFilenamePreview = async () => {
    applyFilenameTemplate();
};

// ============================================================================
// 目录选择器
// ============================================================================

let currentPickerTarget = '';

window.openDirPicker = (target) => {
    currentPickerTarget = target;
    dirPickerModal.classList.remove('hidden');
    const currentVal = document.getElementById(`cfg-${target}`).value;
    browseDirectory(currentVal || '/');
};

// ============================================================================
// 需转换格式管理
// ============================================================================

let convertFormats = [];

/**
 * 加载需转换格式列表
 */
window.loadConvertFormats = async () => {
    try {
        const cfg = await fetchJson(`${API_BASE}/config`, {}, '获取配置失败');
        const beta = cfg.beta_features || {};
        convertFormats = beta.convert_formats || ["epub", "mobi", "azw", "azw3", "fb2", "lit", "lrf", "pdb"];
        renderConvertFormats();
    } catch (e) {
        console.error('Failed to load convert formats:', e);
    }
};

/**
 * 渲染格式标签列表
 */
function renderConvertFormats() {
    const container = document.getElementById('convert-formats-list');
    if (!container) return;

    container.innerHTML = convertFormats.map(fmt => `
        <span class="format-tag">
            ${fmt}
            <button type="button" onclick="removeConvertFormat('${fmt}')" title="移除">
                <i class="fa-solid fa-times"></i>
            </button>
        </span>
    `).join('');
}

/**
 * 添加新格式
 */
window.addConvertFormat = async () => {
    const input = document.getElementById('convert-format-input');
    if (!input) return;

    let fmt = input.value.trim().toLowerCase();
    // 移除可能的点号前缀
    if (fmt.startsWith('.')) fmt = fmt.substring(1);

    if (!fmt) {
        showNotification('请输入格式名称', 2000, 'warning');
        return;
    }

    if (convertFormats.includes(fmt)) {
        showNotification(`"${fmt}" 已存在`, 2000, 'warning');
        input.value = '';
        return;
    }

    convertFormats.push(fmt);
    input.value = '';
    renderConvertFormats();
    await saveConvertFormats();
    showNotification(`已添加格式: ${fmt}`, 2000, 'success');
};

/**
 * 移除格式
 */
window.removeConvertFormat = async (fmt) => {
    convertFormats = convertFormats.filter(f => f !== fmt);
    renderConvertFormats();
    await saveConvertFormats();
    showNotification(`已移除格式: ${fmt}`, 2000, 'success');
};

/**
 * 保存格式列表到配置
 */
async function saveConvertFormats() {
    try {
        const cfg = await fetchJson(`${API_BASE}/config`, {}, '获取配置失败');
        if (!cfg.beta_features) cfg.beta_features = {};
        cfg.beta_features.convert_formats = convertFormats;
        await saveConfigPayload(cfg);
    } catch (e) {
        console.error('Failed to save convert formats:', e);
    }
}

/**
 * 检查格式是否需要转换为 PDF
 */
window.isFormatNeedsConversion = (ext) => {
    if (!ext) return false;
    ext = ext.toLowerCase();
    if (ext.startsWith('.')) ext = ext.substring(1);
    return convertFormats.includes(ext);
};

// 初始化时加载格式列表
document.addEventListener('DOMContentLoaded', () => {
    loadConvertFormats();
});

// ============================================================================
// 图书识别格式管理
// ============================================================================

const DEFAULT_BOOK_EXTENSIONS = [
    '.epub', '.pdf', '.mobi', '.azw3', '.azw', '.txt', '.md', '.markdown'
];

const BOOK_EXTENSION_PRESETS = [
    { group: '核心', formats: ['.epub', '.pdf'] },
    { group: 'Kindle', formats: ['.mobi', '.azw', '.azw3'] },
    { group: '文本', formats: ['.txt', '.md', '.markdown'] },
    { group: '电子书', formats: ['.djvu', '.fb2', '.lit', '.chm'] },
    { group: '漫画', formats: ['.cbr', '.cbz', '.cb7', '.cbt'] },
    { group: '文档', formats: ['.rtf', '.doc', '.docx'] }
];

let bookExtensions = [];
let bookExtensionCounts = {};
let bookExtensionCountController = null;

function normalizeBookExtension(value) {
    let fmt = String(value || '').trim().toLowerCase();
    if (!fmt) return '';
    if (!fmt.startsWith('.')) fmt = `.${fmt}`;
    if (!/^\.[a-z0-9][a-z0-9_-]{0,15}$/.test(fmt)) return '';
    return fmt;
}

function uniqueBookExtensions(values, fallbackToDefault = true) {
    const seen = new Set();
    const result = [];
    (values || []).forEach(value => {
        const fmt = normalizeBookExtension(value);
        if (!fmt || seen.has(fmt)) return;
        seen.add(fmt);
        result.push(fmt);
    });
    return result.length ? result : (fallbackToDefault ? [...DEFAULT_BOOK_EXTENSIONS] : []);
}

window.loadBookExtensions = async () => {
    try {
        const cfg = await fetchJson(`${API_BASE}/config`, {}, '获取配置失败');
        bookExtensions = uniqueBookExtensions(cfg.book_extensions || DEFAULT_BOOK_EXTENSIONS);
        renderBookExtensionPresets();
        renderBookExtensions();
        await refreshBookExtensionCounts();
    } catch (e) {
        console.error('Failed to load book extensions:', e);
    }
};

function renderBookExtensionPresets() {
    const container = document.getElementById('book-extension-presets');
    if (!container) return;
    container.innerHTML = BOOK_EXTENSION_PRESETS.map(group => `
        <div class="format-preset-group">
            <div class="format-preset-title">${group.group}</div>
            <div class="format-preset-items">
                ${group.formats.map(fmt => `
                    <label class="format-option">
                        <input type="checkbox" value="${fmt}" ${bookExtensions.includes(fmt) ? 'checked' : ''}
                            onchange="toggleBookExtension('${fmt}', this.checked)">
                        <span>${fmt.replace('.', '')}</span>
                    </label>
                `).join('')}
            </div>
        </div>
    `).join('');
}

function renderBookExtensions() {
    const container = document.getElementById('book-extensions-list');
    if (!container) return;
    container.innerHTML = bookExtensions.map(fmt => `
        <span class="format-tag">
            ${fmt.replace('.', '')}
            <button type="button" onclick="removeBookExtension('${fmt}')" title="移除">
                <i class="fa-solid fa-times"></i>
            </button>
        </span>
    `).join('');
}

function renderBookExtensionCounts() {
    const summary = document.getElementById('book-extension-count-summary');
    const list = document.getElementById('book-extension-counts');
    if (!summary || !list) return;

    const totalFiles = bookExtensions.reduce((sum, fmt) => {
        return sum + (bookExtensionCounts[fmt]?.total || 0);
    }, 0);
    summary.innerHTML = `
        <div class="format-summary-item">
            <span>纳入格式</span>
            <strong>${bookExtensions.length}</strong>
        </div>
        <div class="format-summary-item">
            <span>涉及文件</span>
            <strong>${totalFiles}</strong>
        </div>
    `;

    list.innerHTML = bookExtensions.map(fmt => {
        const item = bookExtensionCounts[fmt] || { total: 0, source: 0, target: 0, library: 0 };
        return `
            <div class="format-count-row">
                <strong>${fmt}</strong>
                <span>总计 ${item.total || 0}</span>
                <small>源目录 ${item.source || 0} · 目标目录 ${item.target || 0} · 其他库 ${item.library || 0}</small>
            </div>
        `;
    }).join('');
}

window.refreshBookExtensionCounts = async () => {
    if (!document.getElementById('book-extension-counts')) return;
    if (bookExtensionCountController) bookExtensionCountController.abort();
    bookExtensionCountController = new AbortController();

    try {
        const data = await fetchJson(`${API_BASE}/book_extensions/counts`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(bookExtensions),
            signal: bookExtensionCountController.signal
        }, '统计失败');
        bookExtensionCounts = data.counts || {};
        renderBookExtensionCounts();
    } catch (e) {
        if (e.name !== 'AbortError') {
            console.error('Failed to refresh book extension counts:', e);
        }
    } finally {
        bookExtensionCountController = null;
    }
};

window.toggleBookExtension = async (fmt, enabled) => {
    fmt = normalizeBookExtension(fmt);
    if (!fmt) return;
    if (enabled && !bookExtensions.includes(fmt)) {
        bookExtensions.push(fmt);
    } else if (!enabled) {
        bookExtensions = bookExtensions.filter(item => item !== fmt);
    }
    bookExtensions = uniqueBookExtensions(bookExtensions, false);
    if (!bookExtensions.length) {
        bookExtensions = [fmt];
        showNotification('至少保留一种识别格式', 2500, 'warning');
    }
    renderBookExtensionPresets();
    renderBookExtensions();
    await refreshBookExtensionCounts();
};

window.addBookExtension = async () => {
    const input = document.getElementById('book-extension-input');
    if (!input) return;
    const fmt = normalizeBookExtension(input.value);
    if (!fmt) {
        showNotification('请输入有效格式，例如 epub 或 .pdf', 2500, 'warning');
        return;
    }
    if (bookExtensions.includes(fmt)) {
        showNotification(`${fmt} 已在识别列表中`, 2000, 'warning');
        input.value = '';
        return;
    }
    bookExtensions.push(fmt);
    input.value = '';
    renderBookExtensionPresets();
    renderBookExtensions();
    await refreshBookExtensionCounts();
};

window.removeBookExtension = async (fmt) => {
    fmt = normalizeBookExtension(fmt);
    bookExtensions = bookExtensions.filter(item => item !== fmt);
    if (!bookExtensions.length) {
        showNotification('至少保留一种识别格式', 2500, 'warning');
        bookExtensions = [fmt || '.pdf'];
        return;
    }
    renderBookExtensionPresets();
    renderBookExtensions();
    await refreshBookExtensionCounts();
};

window.saveBookExtensions = async () => {
    try {
        const res = await fetch(`${API_BASE}/config`);
        const cfg = await res.json();
        cfg.book_extensions = uniqueBookExtensions(bookExtensions);
        await saveConfigPayload(cfg);
        config = cfg;
        showNotification('识别格式已保存，并会随配置同步', 2500, 'success');
    } catch (e) {
        showNotification(`保存失败: ${e.message}`, 4000, 'error');
    }
};

document.addEventListener('DOMContentLoaded', () => {
    loadBookExtensions();
});

// ============================================================================
// 顶部快捷开关联动
// ============================================================================

/**
 * 切换内容与搜索控制开关
 * 与 AI 配置中的 ctrl-enabled 复选框联动
 */
window.toggleContentSearch = async () => {
    const icon = document.getElementById('content-search-icon');
    if (!icon) return;

    try {
        // 加载当前 AI 配置
        const res = await fetch(`${API_BASE}/ai_config`);
        const aiConfig = await res.json();

        // 切换状态
        if (!aiConfig.content_and_search_control) {
            aiConfig.content_and_search_control = {};
        }
        const newEnabled = !aiConfig.content_and_search_control.enabled;
        aiConfig.content_and_search_control.enabled = newEnabled;

        // 保存配置
        await fetch(`${API_BASE}/ai_config`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(aiConfig)
        });

        // 更新按钮状态
        icon.classList.toggle('active', newEnabled);
        icon.setAttribute('data-tooltip', `内容与搜索: ${newEnabled ? '已开启' : '已关闭'}`);

        // 更新状态灯
        const headerStatus = document.getElementById('ai-status-content-search');
        if (headerStatus) {
            headerStatus.classList.toggle('active', newEnabled);
        }

        showNotification(`内容与搜索控制: ${newEnabled ? '已开启' : '已关闭'}`, 2000, 'success');
    } catch (e) {
        showNotification(`切换失败: ${e.message}`, 3000, 'error');
    }
};

/**
 * 切换数据库增强开关（数据源优先级）
 * 与设置中的 beta-data-priority-group 按钮组联动
 */
window.toggleDbEnhance = async () => {
    const icon = document.getElementById('db-enhance-icon');
    if (!icon) return;

    try {
        // 加载当前配置
        const res = await fetch(`${API_BASE}/config`);
        const cfg = await res.json();

        if (!cfg.beta_features) cfg.beta_features = {};

        // 切换状态：database <-> metadata
        const currentPriority = cfg.beta_features.data_priority || 'database';
        const newPriority = currentPriority === 'database' ? 'metadata' : 'database';
        cfg.beta_features.data_priority = newPriority;

        // 保存配置
        await saveConfigPayload(cfg);
        config = cfg;

        // 更新按钮状态
        const isDatabase = newPriority === 'database';
        icon.classList.toggle('active', isDatabase);
        icon.setAttribute('data-tooltip', `兜底来源: ${isDatabase ? '数据库优先' : '元数据优先'}`);

        // 同步设置页面中的按钮组
        const priorityGroup = document.getElementById('beta-data-priority-group');
        if (priorityGroup) {
            priorityGroup.querySelectorAll('.btn-toggle').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.value === newPriority);
            });
        }

        // 更新标签文本
        updateContentTabLabels();

        // 顶部开关只影响增强简介自动选择的兜底偏好；目录始终以数据库缓存为主。
        if (window.currentMode === 'manage' && window.currentBookPath) {
            if (typeof window.loadSummaryForBook === 'function') {
                window.loadSummaryForBook(window.currentBookPath);
            }
        }

        showNotification(`兜底来源: ${isDatabase ? '数据库优先' : '元数据优先'}`, 2000, 'success');
    } catch (e) {
        showNotification(`切换失败: ${e.message}`, 3000, 'error');
    }
};

/**
 * 初始化快捷开关状态
 */
window.initQuickToggleStates = async () => {
    // 内容与搜索开关
    const contentSearchIcon = document.getElementById('content-search-icon');
    if (contentSearchIcon) {
        try {
            const res = await fetch(`${API_BASE}/ai_config`);
            const aiConfig = await res.json();
            const enabled = aiConfig.content_and_search_control?.enabled || false;
            contentSearchIcon.classList.toggle('active', enabled);
            contentSearchIcon.setAttribute('data-tooltip', `内容与搜索: ${enabled ? '已开启' : '已关闭'}`);
        } catch (e) {
            console.error('Failed to init content-search toggle:', e);
        }
    }

    // 数据库增强开关
    const dbEnhanceIcon = document.getElementById('db-enhance-icon');
    if (dbEnhanceIcon) {
        const priority = config?.beta_features?.data_priority || 'database';
        const isDatabase = priority === 'database';
        dbEnhanceIcon.classList.toggle('active', isDatabase);
        dbEnhanceIcon.setAttribute('data-tooltip', `兜底来源: ${isDatabase ? '数据库优先' : '元数据优先'}`);
    }
};

// ============================================================================
// 标签文本动态更新
// ============================================================================

/**
 * 更新增强简介/目录标签文本
 * 展示层自动选择有效内容，来源优先级仅作为兜底策略。
 */
window.updateContentTabLabels = () => {
    const summaryText = document.getElementById('tab-summary-text');
    const tocText = document.getElementById('tab-toc-text');
    if (!summaryText || !tocText) return;

    summaryText.textContent = '增强简介';
    tocText.textContent = '图书目录';
};

// 绑定快捷开关点击事件
document.addEventListener('DOMContentLoaded', () => {
    const contentSearchIcon = document.getElementById('content-search-icon');
    if (contentSearchIcon) {
        contentSearchIcon.addEventListener('click', window.toggleContentSearch);
    }

    const dbEnhanceIcon = document.getElementById('db-enhance-icon');
    if (dbEnhanceIcon) {
        dbEnhanceIcon.addEventListener('click', window.toggleDbEnhance);
    }

    // 延迟初始化快捷开关状态（等待配置加载完成）
    setTimeout(() => {
        window.initQuickToggleStates();
        window.updateContentTabLabels();
    }, 500);
});
