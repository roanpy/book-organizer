/**
 * app.js - 应用入口
 * 
 * 初始化和事件监听器设置。
 * 
 * 依赖模块（按加载顺序）：
 * 1. state.js   - 全局状态和 DOM 引用
 * 2. ui.js      - UI 渲染函数
 * 3. api.js     - API 调用
 * 4. batch.js   - 批量处理
 * 5. zoom.js    - 封面缩放
 * 6. settings.js - 设置和配置
 * 7. ai_config.js - AI 配置（独立模块）
 */

// ============================================================================
// 工具函数
// ============================================================================

/**
 * 获取当前选中的文件名/路径
 * 统一使用 state.js 中的 getCurrentBookPath()
 */
function getCurrentFilename() {
    // 使用统一的路径获取方法（定义在 state.js）
    if (typeof getCurrentBookPath === 'function') {
        return getCurrentBookPath();
    }
    // 回退逻辑
    if (window.currentBookPath) {
        return window.currentBookPath;
    }
    if (window.currentBook) {
        return window.currentBook;
    }
    const el = document.getElementById('current-filename');
    return el ? el.textContent : null;
}
window.getCurrentFilename = getCurrentFilename;

// ============================================================================
// 初始化
// ============================================================================

async function init() {
    initEngineSelection();
    await fetchConfig();
    await fetchBooks();
    await loadAIConfig();
    if (!window.aiConfig && typeof aiConfig !== 'undefined') window.aiConfig = aiConfig;
    setupEventListeners();
    setupZoomInteractions();
    if (typeof initBookPreview === 'function') initBookPreview();
    initGlobalTooltip();
    initToggles();
    if (typeof initSyncFeature === 'function') initSyncFeature();
    // Initialize Lifecycle Sync Check (Startup/Shutdown)
    if (typeof initSyncLifecycle === 'function') initSyncLifecycle();

    // 初始化批量下拉菜单状态（默认为入库模式）
    if (typeof updateBatchDropdownForMode === 'function') {
        updateBatchDropdownForMode('inbound');
    }
}

// ============================================================================
// 引擎和搜索初始化
// ============================================================================

let statusCheckInterval = null;

async function initEngineSelection() {
    // Dropdown elements
    const container = document.getElementById('engine-dropdown-container');
    const btn = document.getElementById('engine-dropdown-btn');
    const menu = document.getElementById('engine-dropdown-menu');
    const hiddenInput = document.getElementById('engine-select');
    const label = document.getElementById('current-engine-label');
    const statusDot = document.getElementById('current-engine-status');

    if (!container || !btn || !menu || !hiddenInput) return;

    // Toggle dropdown
    btn.onclick = (e) => {
        e.stopPropagation();
        const isOpening = !container.classList.contains('open');
        container.classList.toggle('open');

        // When opening, refresh all provider statuses
        if (isOpening && window.checkAllProviderStatus) {
            window.checkAllProviderStatus();
        }
    };

    // Close on click outside
    document.addEventListener('click', (e) => {
        if (!container.contains(e.target)) {
            container.classList.remove('open');
        }
    });

    try {
        // Load config to get all available providers
        const configRes = await fetch(`${API_BASE}/config`);
        const cfg = await configRes.json();

        // Clear existing options
        menu.innerHTML = '';

        // Provider display labels
        const providerLabels = {
            'gemini': 'Gemini',
            'deepseek': 'DeepSeek',
            'ollama': 'Ollama',
            'offline': '离线模式'
        };

        // ==== Add "Offline Mode" (停用 AI) option first ====
        const offlineItem = document.createElement('div');
        offlineItem.className = 'dropdown-item model-option';
        offlineItem.innerHTML = `
            <span><i class="fa-solid fa-power-off"></i> 离线模式</span>
            <span id="status-dot-offline" class="status-dot status-offline" title="本地功能可用"></span>
        `;
        offlineItem.onclick = () => selectOption('offline', '离线模式');
        menu.appendChild(offlineItem);

        // Add separator
        const divider = document.createElement('div');
        divider.className = 'dropdown-divider';
        menu.appendChild(divider);

        // Collect all configured providers (offline is already added manually above)
        const allProviders = [];

        // Check built-in style providers
        ['gemini', 'deepseek', 'ollama'].forEach(p => {
            if (cfg[p] && (cfg[p].configured || cfg[p].api_key || cfg[p].url) && cfg[p].model_name) {
                allProviders.push({ name: p, label: providerLabels[p] || p });
            }
        });

        // Add custom providers
        if (cfg.custom_providers) {
            Object.keys(cfg.custom_providers).forEach(name => {
                allProviders.push({ name: name, label: name });
            });
        }

        // Helper to select an option
        const selectOption = async (value, text) => {
            hiddenInput.value = value;
            label.textContent = text;

            // Sync visible status dot with the selected item's status
            const selectedItemDot = document.getElementById(`status-dot-${value}`);
            if (selectedItemDot) {
                statusDot.className = selectedItemDot.className; // Copy classes
            } else {
                statusDot.className = 'status-dot'; // Reset
            }

            container.classList.remove('open');

            // Save preference
            try {
                await fetch(`${API_BASE}/user_preferences`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ selectedEngine: value })
                });
            } catch (e) {
                console.error('Failed to save engine preference:', e);
            }
        };

        // Populate dropdown
        allProviders.forEach(p => {
            const item = document.createElement('div');
            item.className = 'dropdown-item model-option';
            item.innerHTML = `
                <span>${p.label}</span>
                <span id="status-dot-${p.name}" class="status-dot" title="检查中..."></span>
            `;
            item.onclick = () => selectOption(p.name, p.label);
            menu.appendChild(item);
        });

        // If no providers
        if (allProviders.length === 0) {
            menu.innerHTML = '<div class="dropdown-item">请先配置 AI 模型</div>';
            label.textContent = '未配置';
        }

        // Load user preference
        const prefsRes = await fetch(`${API_BASE}/user_preferences`);
        const prefs = await prefsRes.json();
        let selected = prefs.selectedEngine;

        // Verify selected engine exists
        const exists = allProviders.find(p => p.name === selected);
        // Special case: 'offline' is valid but not in allProviders
        if (selected !== 'offline' && !exists && allProviders.length > 0) {
            selected = allProviders[0].name;
        }

        if (selected) {
            if (selected === 'offline') {
                hiddenInput.value = 'offline';
                label.textContent = '离线模式';
                const offlineDot = document.getElementById('status-dot-offline');
                if (offlineDot && statusDot) {
                    statusDot.className = offlineDot.className;
                }
            } else {
                const p = allProviders.find(p => p.name === selected);
                if (p) {
                    hiddenInput.value = p.name;
                    label.textContent = p.label;
                }
            }
        }

        // Start polling status
        startStatusPolling(allProviders);

    } catch (e) {
        console.error('Failed to init engine selection:', e);
    }
}

function startStatusPolling(providers) {
    if (statusCheckInterval) clearInterval(statusCheckInterval);

    // Store providers globally for dropdown open check
    window._allProviders = providers;

    // Check only the selected model (optimized)
    const checkSelectedStatus = async () => {
        // Pause polling if settings modal is open
        const settingsModal = document.getElementById('settings-modal');
        if (settingsModal && !settingsModal.classList.contains('hidden')) return;

        const currentEngine = document.getElementById('engine-select').value;
        const mainStatusDot = document.getElementById('current-engine-status');
        if (!currentEngine || !mainStatusDot) return;

        // Special handling for Offline Mode
        if (currentEngine === 'offline') {
            mainStatusDot.className = 'status-dot status-offline';
            mainStatusDot.title = '本地功能可用';
            return;
        }

        try {
            const res = await fetch(`${API_BASE}/models/${currentEngine}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({})
            });
            const data = await res.json();

            mainStatusDot.classList.remove('status-checking', 'status-green', 'status-red', 'status-offline');
            if (data.models && data.models.length > 0) {
                mainStatusDot.classList.add('status-green');
                mainStatusDot.title = '状态正常';
            } else {
                mainStatusDot.classList.add('status-red');
                mainStatusDot.title = data.error || '连接失败';
            }

            // Also update the dropdown item if it exists
            const dropdownDot = document.getElementById(`status-dot-${currentEngine}`);
            if (dropdownDot) {
                dropdownDot.className = mainStatusDot.className;
                dropdownDot.title = mainStatusDot.title;
            }
        } catch (e) {
            mainStatusDot.classList.remove('status-checking', 'status-green', 'status-offline');
            mainStatusDot.classList.add('status-red');
            mainStatusDot.title = '请求失败';
        }
    };

    // Run immediately for selected model
    checkSelectedStatus();

    // Poll every 60 seconds for selected model only
    statusCheckInterval = setInterval(checkSelectedStatus, 60000);
}

// Check all providers (called when dropdown opens)
async function checkAllProviderStatus() {
    const providers = window._allProviders || [];
    const currentEngine = document.getElementById('engine-select').value;
    const mainStatusDot = document.getElementById('current-engine-status');

    for (const p of providers) {
        const dot = document.getElementById(`status-dot-${p.name}`);
        if (!dot) continue;

        try {
            const res = await fetch(`${API_BASE}/models/${p.name}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({})
            });
            const data = await res.json();

            dot.classList.remove('status-checking', 'status-green', 'status-red', 'status-offline');
            if (data.models && data.models.length > 0) {
                dot.classList.add('status-green');
                dot.title = '状态正常';
            } else {
                dot.classList.add('status-red');
                dot.title = data.error || '连接失败';
            }
        } catch (e) {
            dot.classList.remove('status-checking', 'status-green', 'status-offline');
            dot.classList.add('status-red');
            dot.title = '请求失败';
        }

        // Sync main button if this is the selected engine
        if (p.name === currentEngine && mainStatusDot) {
            mainStatusDot.className = dot.className;
            mainStatusDot.title = dot.title;
        }
    }
}
window.checkAllProviderStatus = checkAllProviderStatus;

// Expose globally
window.initEngineSelection = initEngineSelection;

async function initToggles() {
    // Get icon buttons
    const webSearchIcon = document.getElementById('web-search-icon');
    const enhancedModeIcon = document.getElementById('enhanced-mode-icon');
    const tocModeIcon = document.getElementById('toc-mode-icon');

    // New Master Toggle in AI Config Modal
    const enhancedModeCheckbox = document.getElementById('enhanced-mode-enabled');

    // Load preferences from backend
    try {
        const res = await fetch(`${API_BASE}/user_preferences`);
        const prefs = await res.json();
        isWebSearchEnabled = prefs.webSearchEnabled ?? false;
        window.isWebSearchEnabled = isWebSearchEnabled; // 同步全局状态
        window.isEnhancedModeEnabled = prefs.enhancedModeEnabled ?? false;
        window.isTocEnabled = prefs.tocEnabled ?? false;
    } catch (e) {
        console.error('Failed to load toggle preferences:', e);
        isWebSearchEnabled = false;
        window.isEnhancedModeEnabled = false;
        window.isTocEnabled = false;
    }

    // Save preferences to backend
    async function saveTogglePrefs() {
        try {
            await fetch(`${API_BASE}/user_preferences`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    webSearchEnabled: isWebSearchEnabled,
                    enhancedModeEnabled: window.isEnhancedModeEnabled,
                    tocEnabled: window.isTocEnabled
                })
            });
        } catch (e) {
            console.error('Failed to save toggle preferences:', e);
        }
    }

    // Update UI state
    function updateToggleUI() {
        // Icon buttons - active class controls color
        if (webSearchIcon) {
            webSearchIcon.classList.toggle('active', isWebSearchEnabled);
            webSearchIcon.setAttribute('data-tooltip', isWebSearchEnabled ? '联网搜索: 已开启' : '联网搜索: 已关闭');
        }
        if (enhancedModeIcon) {
            enhancedModeIcon.classList.toggle('active', window.isEnhancedModeEnabled);
            enhancedModeIcon.setAttribute('data-tooltip', window.isEnhancedModeEnabled ? '增强模式: 已开启' : '增强模式: 已关闭');
        }
        if (tocModeIcon) {
            tocModeIcon.classList.toggle('active', window.isTocEnabled);
            tocModeIcon.setAttribute('data-tooltip', window.isTocEnabled ? '识别目录: 已开启' : '识别目录: 已关闭');
        }

        // Update Enhanced Mode Checkbox (if exists)
        const currentCheckbox = document.getElementById('enhanced-mode-enabled');
        if (currentCheckbox) {
            currentCheckbox.checked = window.isEnhancedModeEnabled;
        }

        // Update enhanced summary button state
        const enhancedSummaryBtn = document.getElementById('btn-gen-summary');
        if (enhancedSummaryBtn) {
            if (window.isEnhancedModeEnabled) {
                enhancedSummaryBtn.disabled = false;
                enhancedSummaryBtn.classList.remove('btn-disabled');
            } else {
                enhancedSummaryBtn.disabled = true;
                enhancedSummaryBtn.classList.add('btn-disabled');
            }
        }

        // Update TOC button state
        const tocBtn = document.getElementById('btn-extract-toc');
        if (tocBtn) {
            if (window.isTocEnabled) {
                tocBtn.disabled = false;
                tocBtn.classList.remove('btn-disabled');
            } else {
                tocBtn.disabled = true;
                tocBtn.classList.add('btn-disabled');
            }
        }

        // Sync with AI config enhanced rules indicator if function exists
        if (typeof window.updateEnhancedRulesIndicator === 'function') {
            window.updateEnhancedRulesIndicator();
        }

        if (typeof window.updateAnalyzeButtonLabel === 'function') {
            window.updateAnalyzeButtonLabel();
        }
    }

    window.updateAnalyzeButtonLabel = function () {
        const analyzeButton = document.getElementById('analyze-btn');
        if (!analyzeButton || analyzeButton.classList.contains('analyzing')) return;

        const parts = ['信息'];
        if (window.isEnhancedModeEnabled) parts.push('简介');
        if (window.isTocEnabled) parts.push('目录');

        const actionLabel = parts.length > 2
            ? `${parts.slice(0, -1).join('、')}及${parts[parts.length - 1]}`
            : parts.join('及');
        analyzeButton.innerHTML = `<i class="fa-solid fa-play"></i> 开始${actionLabel}分析`;
        analyzeButton.title = `将联动分析：${parts.join('、')}`;
    };

    updateToggleUI();
    // Expose for external sync
    window.updateToggleUI = updateToggleUI;

    // --- Global Setters for Toggles ---

    /**
     * Set Enhanced Mode State
     * @param {boolean} enabled 
     */
    window.setEnhancedMode = async function (enabled) {
        window.isEnhancedModeEnabled = enabled;
        updateToggleUI();
        await saveTogglePrefs();
    };

    // --- Event Listeners ---

    // Icon button click handlers (direct toggle)
    if (webSearchIcon) {
        webSearchIcon.onclick = async () => {
            isWebSearchEnabled = !isWebSearchEnabled;
            window.isWebSearchEnabled = isWebSearchEnabled; // 同步全局状态
            updateToggleUI();
            await saveTogglePrefs();
            showNotification(isWebSearchEnabled ? '联网搜索已开启' : '联网搜索已关闭', 2000);
        };
    }

    if (enhancedModeIcon) {
        enhancedModeIcon.onclick = async () => {
            await window.setEnhancedMode(!window.isEnhancedModeEnabled);
            showNotification(window.isEnhancedModeEnabled ? '增强模式已开启' : '增强模式已关闭', 2000);
        };
    }

    if (tocModeIcon) {
        tocModeIcon.onclick = async () => {
            window.isTocEnabled = !window.isTocEnabled;
            updateToggleUI();
            await saveTogglePrefs();
            showNotification(window.isTocEnabled ? '目录识别已开启' : '目录识别已关闭', 2000);
        };
    }

    // Checkbox listener - We need to delegate or attach if element exists.
    // Since modal might be created/destroyed or hidden, we can attach to document body or just check when init.
    // However, the checkbox is in static HTML, so we can attach directly if it exists, 
    // BUT initToggles runs once. If we add the checkbox later to DOM (dynamic), we need delegation.
    // IN THIS CASE: The modal is invalidating/recreating? No, it's static in index.html.
    // So we can attach listener here.

    // We'll use a delegation or dynamic check just to be safe if `initToggles` runs early.
    document.addEventListener('change', async (e) => {
        if (e.target && e.target.id === 'enhanced-mode-enabled') {
            await window.setEnhancedMode(e.target.checked);
        }
    });

}

// ============================================================================
// 事件监听器
// ============================================================================

function setupEventListeners() {
    refreshBtn.onclick = fetchBooks;
    analyzeBtn.onclick = () => analyzeBook();
    skipBtn.onclick = () => skipBook();
    deleteBtn.onclick = () => deleteBook();

    settingsBtn.onclick = async () => {
        await fetchConfig();
        settingsModal.classList.remove('hidden');
        updateConfigUI();
        // 加载自定义 Providers
        if (window.loadCustomProviders) {
            window.loadCustomProviders();
        }
    };
    closeSettingsBtn.onclick = () => settingsModal.classList.add('hidden');

    // Cloud Sync Button
    const cloudSyncBtn = document.getElementById('cloud-sync-btn');
    if (cloudSyncBtn) {
        cloudSyncBtn.onclick = () => {
            if (window.triggerCloudSync) {
                window.triggerCloudSync();
            } else {
                console.error('triggerCloudSync not found, make sure sync.js is loaded');
            }
        };
    }

    // Help Modal
    const helpBtn = document.getElementById('help-btn');
    const helpModal = document.getElementById('help-modal');
    const closeHelpBtn = document.getElementById('close-help');

    helpBtn.onclick = () => helpModal.classList.remove('hidden');
    closeHelpBtn.onclick = () => helpModal.classList.add('hidden');

    // AI Config Modal
    aiConfigBtn.onclick = () => openAIConfig();
    closeAIConfigBtn.onclick = () => aiConfigModal.classList.add('hidden');

    closeDirPickerBtn.onclick = () => dirPickerModal.classList.add('hidden');

    pickerSelectBtn.onclick = () => {
        if (currentPickerTarget) {
            document.getElementById(`cfg-${currentPickerTarget}`).value = currentBrowsePath;
        }
        dirPickerModal.classList.add('hidden');
    };

    // Process Dropdown
    const processDropdown = document.getElementById('process-dropdown');
    const processDropdownBtn = document.getElementById('process-dropdown-btn');

    processDropdownBtn.onclick = (e) => {
        e.stopPropagation();
        if (isSequentialMode) {
            stopSequential();
        } else {
            processDropdown.classList.toggle('open');
        }
    };

    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
        if (!processDropdown.contains(e.target)) {
            processDropdown.classList.remove('open');
        }
    });

    // Batch & Sequential (now dropdown items)
    seqBtn.onclick = () => {
        processDropdown.classList.remove('open');
        startSequential();
    };
    batchBtn.onclick = () => {
        processDropdown.classList.remove('open');
        batchModal.classList.remove('hidden');
    };
    closeBatchBtn.onclick = () => batchModal.classList.add('hidden');

    // Cancel button handler
    const cancelBatchBtn = document.getElementById('cancel-batch-btn');
    if (cancelBatchBtn) {
        cancelBatchBtn.onclick = () => {
            batchModal.classList.add('hidden');
            batchReviewArea.classList.add('hidden');
            batchLogEl.classList.remove('hidden');
            startBatchBtn.classList.remove('hidden');
            executeBatchBtn.classList.add('hidden');
            cancelBatchBtn.classList.add('hidden');
            stopBatchBtn.classList.add('hidden');
            batchPlan = [];
        };
    }

    startBatchBtn.onclick = startBatchAnalysis;
    executeBatchBtn.onclick = executeBatch;
    stopBatchBtn.onclick = () => shouldStopBatch = true;
}

// ============================================================================
// TOC (目录) Functions
// ============================================================================

// Current book's TOC data
let currentTocData = null;
let tocLoadSequence = 0;
let summaryLoadSequence = 0;

/**
 * Switch between summary and TOC tabs
 */
function switchContentTab(tabName) {
    const tabSummary = document.getElementById('tab-summary');
    const tabToc = document.getElementById('tab-toc');
    const contentSummary = document.getElementById('content-summary');
    const contentToc = document.getElementById('content-toc');
    const summarySourceControls = document.getElementById('summary-source-controls');
    const tocSourceControls = document.getElementById('toc-source-controls');

    if (tabName === 'summary') {
        tabSummary.classList.add('active');
        tabToc.classList.remove('active');
        contentSummary.classList.add('active');
        contentToc.classList.remove('active');
        summarySourceControls?.classList.add('active');
        tocSourceControls?.classList.remove('active');
    } else {
        tabSummary.classList.remove('active');
        tabToc.classList.add('active');
        contentSummary.classList.remove('active');
        contentToc.classList.add('active');
        summarySourceControls?.classList.remove('active');
        tocSourceControls?.classList.add('active');
    }
}
window.switchContentTab = switchContentTab;

function setContentSourceButtons(type, source) {
    const group = document.getElementById(type === 'toc' ? 'toc-source-controls' : 'summary-source-controls');
    if (!group) return;
    const normalizedSource = source === 'metadata' ? 'metadata' : 'database';
    group.querySelectorAll('.content-source-btn').forEach((btn) => {
        btn.classList.toggle('active', btn.dataset.source === normalizedSource);
    });
}
window.setContentSourceButtons = setContentSourceButtons;

window.switchContentSource = function (type, source) {
    const filename = window.currentBookPath || window.currentBookFilename || getCurrentFilename();
    if (!filename) {
        showNotification('未选择图书', 2000, 'warning');
        return;
    }
    setContentSourceButtons(type, source);
    if (type === 'toc') {
        if (typeof window.loadTocForBook === 'function') {
            window.loadTocForBook(filename, { source });
        }
        return;
    }
    if (typeof window.loadSummaryForBook === 'function') {
        window.loadSummaryForBook(filename, { source });
        return;
    }
    if (typeof window.switchEnhancedSummarySource === 'function') {
        window.switchEnhancedSummarySource(source);
    }
};

function escapeHtmlText(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

/**
 * Render TOC tree
 */
function renderTocSourceSwitcher(selectedSource = 'database') {
    setContentSourceButtons('toc', selectedSource);
    return '';
}

window.switchTocSource = function (source) {
    const filename = window.currentBookPath || window.currentBookFilename || getCurrentFilename();
    if (!filename || typeof window.loadTocForBook !== 'function') {
        showNotification('未选择图书', 2000, 'warning');
        return;
    }
    window.loadTocForBook(filename, { source });
};

function renderToc(tocData, options = {}) {
    const tocResult = document.getElementById('toc-result');
    const emptyState = document.querySelector('.empty-toc-state');

    if (!tocData || !tocData.toc || tocData.toc.length === 0) {
        if (tocResult) tocResult.classList.add('hidden');
        if (emptyState) {
            emptyState.innerHTML = `
                <i class="fa-solid fa-list-ol"></i>
                <p>该图书未检测到目录</p>
            `;
        }
        return;
    }

    currentTocData = tocData;
    const selectedSource = options.source || tocData.source || 'database';

    // Build TOC tree HTML
    let html = '<ul class="toc-tree">';
    for (const item of tocData.toc) {
        const level = item.level || 1;
        const levelClass = `level-${Math.min(level, 4)}`;
        const pageInfo = item.page ? `<span class="toc-page">p.${escapeHtmlText(item.page)}</span>` : '';
        html += `<li class="toc-item ${levelClass}">${escapeHtmlText(item.title)}${pageInfo}</li>`;
    }
    html += '</ul>';
    html += `<p class="text-muted text-sm" style="margin-top: 12px;">共 ${tocData.entry_count || tocData.toc.length} 条目录</p>`;
    html += renderTocSourceSwitcher(selectedSource);

    if (tocResult) {
        tocResult.innerHTML = html;
        tocResult.classList.remove('hidden');
    }
    if (emptyState) {
        emptyState.style.display = 'none';
    }
}
window.renderToc = renderToc;

/**
 * Render AI-formatted TOC text
 */
function renderTocText(tocText, options = {}) {
    const tocResult = document.getElementById('toc-result');
    const emptyState = document.querySelector('.empty-toc-state');

    if (!tocText || tocText.trim().length === 0) {
        if (tocResult) tocResult.classList.add('hidden');
        if (emptyState) {
            emptyState.innerHTML = `
                <i class="fa-solid fa-list-ol"></i>
                <p>AI 未能识别目录</p>
            `;
            emptyState.style.display = 'flex';
        }
        return;
    }

    // 将文本转换为HTML（保留换行和缩进）
    const escapedText = escapeHtmlText(tocText)
        .replace(/\n/g, '<br>');

    const html = `
        <div class="toc-ai-result">
            <div class="toc-text-content">${escapedText}</div>
        </div>
        <p class="text-muted text-sm" style="margin-top: 12px;">AI 整理结果</p>
        ${renderTocSourceSwitcher(options.source || 'database')}
    `;

    if (tocResult) {
        tocResult.innerHTML = html;
        tocResult.classList.remove('hidden');
    }
    if (emptyState) {
        emptyState.style.display = 'none';
    }
}
window.renderTocText = renderTocText;

/**
 * Extract TOC from current book
 * @param {boolean} autoSwitch - 是否自动切换到 TOC 标签
 * @param {boolean} skipMutexCheck - 是否跳过互斥检查（从 analyzeBook 内部调用时为 true）
 * @param {boolean} silent - 是否静默运行（不改变按钮 UI，用于联动模式）
 * @param {string|null} targetFilename - 显式指定图书路径，避免联动时读错当前选中项
 */
async function extractToc(autoSwitch = true, skipMutexCheck = false, silent = false, targetFilename = null) {
    const filename = targetFilename || getCurrentFilename();
    if (!filename) {
        showNotification('请先选择一本书', 3000);
        return;
    }
    const requestedBook = filename;

    const btn = document.getElementById('btn-extract-toc');
    const tocContent = document.querySelector('.toc-content');
    const tocResult = document.getElementById('toc-result');
    const emptyState = document.querySelector('.empty-toc-state');

    // 如果正在提取中且用户点击，则取消操作
    if (btn && btn.classList.contains('analyzing') && !silent) {
        if (currentTocController || window.currentTocController) {
            (currentTocController || window.currentTocController).abort();
            currentTocController = null;
            window.currentTocController = null;
        }
        if (window.cancelBookScopedTask) {
            window.cancelBookScopedTask('toc-extract');
        }
        btn.innerHTML = '<i class="fa-solid fa-list-ol"></i> 识别目录';
        btn.classList.remove('analyzing');
        showNotification('已取消识别', 2000);
        if (emptyState) {
            emptyState.innerHTML = `
                <i class="fa-solid fa-list-ol"></i>
                <p>点击上方按钮识别图书目录</p>
            `;
            emptyState.style.display = 'flex';
        }
        return;
    }

    // 互斥：检查是否有其他操作正在进行，需要用户确认（除非跳过）
    if (!skipMutexCheck) {
        const activeOp = getActiveOperation();
        if (activeOp) {
            const confirmed = await confirmCancelOperation('目录识别');
            if (!confirmed) return;
        }
        // 取消其他正在进行的操作
        cancelAllOperations();
    }

    const tocTask = window.beginBookScopedTask
        ? window.beginBookScopedTask('toc-extract', requestedBook)
        : null;
    const tocController = tocTask ? tocTask.controller : new AbortController();
    currentTocController = tocController;
    window.currentTocController = tocController;  // 同步到 window

    // 设置按钮为分析中状态
    const originalText = btn ? btn.innerHTML : '';
    if (btn && !silent) {
        btn.innerHTML = '<div class="spinner-small"></div> 识别中... <i class="fa-solid fa-stop" style="margin-left:4px"></i>';
        btn.classList.add('analyzing');
    }

    // Show loading state
    if (emptyState) {
        emptyState.innerHTML = `
            <div class="spinner"></div>
            <p>正在识别图书目录...</p>
        `;
        emptyState.style.display = 'flex';
    }
    if (tocResult) tocResult.classList.add('hidden');

    // Auto-switch to TOC tab if triggered by button click
    if (autoSwitch) {
        switchContentTab('toc');
    }

    try {
        // 检查是否启用了 AI 目录规则
        const aiConfig = window.aiConfig || {};
        const tocRules = aiConfig.toc_rules || {};
        const organizeEnabled = tocRules.organize_existing?.enabled;
        const extractEnabled = tocRules.extract_from_content?.enabled;

        const engine = document.getElementById('engine-select')?.value || 'gemini';
        // 离线模式强制禁用 AI，即使规则开启
        const useAI = (organizeEnabled || extractEnabled) && engine !== 'offline';

        let data;

        if (useAI) {
            // 使用 AI 处理目录
            data = await fetchJson(`${API_BASE}/toc/ai_extract`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filename, engine }),
                signal: tocTask ? tocTask.signal : tocController.signal
            }, '目录识别失败');

            if (tocTask ? !tocTask.isCurrent() : (window.isCurrentBookTarget && !window.isCurrentBookTarget(requestedBook))) {
                return;
            }
            if (data.success && data.toc_text) {
                // AI 返回的是格式化文本
                renderTocText(data.toc_text);
                showNotification(`AI 目录识别成功`, 3000);
                bookOperationStatus.tocExtracted = true;
                // 点亮保存按钮
                enableSaveButton();
            } else if (!data.success) {
                throw new Error(data.detail || '目录识别失败');
            }
        } else {
            // 使用原始目录提取
            data = await fetchJson(`${API_BASE}/toc/extract`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filename }),
                signal: tocTask ? tocTask.signal : tocController.signal
            }, '目录识别失败');

            if (tocTask ? !tocTask.isCurrent() : (window.isCurrentBookTarget && !window.isCurrentBookTarget(requestedBook))) {
                return;
            }
            if (data.success) {
                renderToc(data);
                showNotification(`目录识别成功，共 ${data.entry_count} 条`, 3000);
                bookOperationStatus.tocExtracted = true;
            } else {
                if (emptyState) {
                    emptyState.innerHTML = `
                        <i class="fa-solid fa-list-ol"></i>
                        <p>${escapeHtmlText(data.error || '该图书未检测到目录')}</p>
                    `;
                    emptyState.style.display = 'flex';
                }
            }
        }
    } catch (e) {
        if (e.name === 'AbortError') {
            console.log('目录识别已取消');
            return;
        }
        console.error('Failed to extract TOC:', e);
        const message = formatApiErrorMessage(e, '目录识别失败');
        if (emptyState) {
            emptyState.innerHTML = `
                <i class="fa-solid fa-exclamation-triangle"></i>
                <p>${escapeHtmlText(message)}</p>
            `;
            emptyState.style.display = 'flex';
        }
        showNotification(message, 5000, 'error');
    } finally {
        const isCurrentToc = currentTocController === tocController
            || window.currentTocController === tocController;
        if (tocTask) {
            tocTask.finish();
        }
        if (isCurrentToc) {
            currentTocController = null;
            window.currentTocController = null;
        }
        if (btn && !silent && isCurrentToc) {
            btn.innerHTML = originalText;
            btn.classList.remove('analyzing');
        }
    }
}
window.extractToc = extractToc;

/**
 * Load TOC for current book.
 * Auto mode prefers the application database cache; if missing, the backend
 * extracts a valid file TOC and writes it into the database. The source switch
 * below the content is view-only and does not change global preferences.
 */
async function loadTocForBook(filename, options = {}) {
    const requestedBook = filename;
    const task = window.beginBookScopedTask
        ? window.beginBookScopedTask('toc-load', requestedBook)
        : null;
    const tocResult = document.getElementById('toc-result');
    const emptyState = document.querySelector('.empty-toc-state');
    const isCurrentLoad = () => task
        ? task.isCurrent()
        : (!window.isCurrentBookTarget || window.isCurrentBookTarget(requestedBook));

    // Reset state
    currentTocData = null;
    if (tocResult) tocResult.classList.add('hidden');
    if (emptyState) {
        emptyState.innerHTML = `
            <i class="fa-solid fa-list-ol"></i>
            <p>点击上方按钮识别图书目录</p>
        `;
        emptyState.style.display = 'flex';
    }

    const forcedSource = options.source || 'auto';
    const useMetadata = forcedSource === 'metadata';

    try {
        if (useMetadata) {
            // 从文件内置目录加载
            const data = await fetchJson(`${API_BASE}/toc/extract`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filename }),
                signal: task ? task.signal : undefined
            }, '读取内置目录失败');

            if (!isCurrentLoad()) {
                return;
            }
            if (data.success && data.toc && data.toc.length > 0) {
                renderToc(data, { source: 'metadata' });
            } else if (emptyState) {
                emptyState.innerHTML = `
                    <i class="fa-solid fa-list-ol"></i>
                    <p>文件内置未检测到目录</p>
                `;
                emptyState.style.display = 'flex';
            }
        } else {
            // 从数据库加载；数据库没有缓存时，后端会尝试提取并写入数据库。
            const data = await fetchJson(
                `${API_BASE}/toc_query?filename=${encodeURIComponent(filename)}`,
                { signal: task ? task.signal : undefined },
                '读取数据库目录失败'
            );

            if (!isCurrentLoad()) {
                return;
            }
            if (data.success) {
                const renderedSource = forcedSource === 'database' ? 'database' : data.source || 'database';
                // 检查是 AI 处理的文本格式还是原始目录数组
                if (data.toc_text) {
                    // AI 处理后的文本格式
                    renderTocText(data.toc_text, { source: renderedSource });
                } else if (data.toc && data.toc.length > 0) {
                    // 原始目录数组格式
                    renderToc(data, { source: renderedSource });
                }
            } else if (emptyState) {
                emptyState.innerHTML = `
                    <i class="fa-solid fa-list-ol"></i>
                    <p>该图书未检测到目录</p>
                `;
                emptyState.style.display = 'flex';
            }
        }
    } catch (e) {
        if (e.name === 'AbortError') {
            return;
        }
        if (isCurrentLoad()) {
            console.error('Failed to load TOC:', e);
        }
    } finally {
        if (task) task.finish();
    }
}
window.loadTocForBook = loadTocForBook;

/**
 * Load summary for current book.
 * Auto mode delegates source choice to the backend. The backend prefers valid,
 * newer structured enhanced summaries and syncs stale database values.
 */
async function loadSummaryForBook(filename, options = {}) {
    const requestedBook = filename;
    const task = window.beginBookScopedTask
        ? window.beginBookScopedTask('summary-load', requestedBook)
        : null;
    const summaryResultEl = document.getElementById('ai-summary-result');
    const emptyState = document.querySelector('.empty-ai-state');
    const isCurrentLoad = () => task
        ? task.isCurrent()
        : (!window.isCurrentBookTarget || window.isCurrentBookTarget(requestedBook));

    const forcedSource = options.source || 'auto';

    try {
        const data = await fetchJson(
            `${API_BASE}/enhanced_summary?filename=${encodeURIComponent(filename)}`,
            { signal: task ? task.signal : undefined },
            '读取增强简介失败'
        );

        if (!isCurrentLoad()) {
            return;
        }

        let selectedSource = forcedSource === 'metadata'
            ? 'metadata'
            : forcedSource === 'database'
                ? 'database'
                : data.source || 'database';
        let forcedSummary = forcedSource === 'metadata'
            ? data.embedded_summary
            : forcedSource === 'database'
                ? data.database_summary
                : data.summary;

        if (forcedSource === 'auto' && !String(forcedSummary || '').trim()) {
            if (String(data.database_summary || '').trim()) {
                selectedSource = 'database';
                forcedSummary = data.database_summary;
            } else if (String(data.embedded_summary || '').trim()) {
                selectedSource = 'metadata';
                forcedSummary = data.embedded_summary;
            }
        }

        if (data.success && forcedSummary) {
            if (typeof renderEnhancedSummary === 'function') {
                renderEnhancedSummary(forcedSummary, false, {
                    selectedSource,
                    databaseSummary: data.database_summary || '',
                    embeddedSummary: data.embedded_summary || ''
                });
            } else if (summaryResultEl && emptyState) {
                summaryResultEl.innerHTML = `<div class="enhanced-summary-text"><p>${escapeHtmlText(forcedSummary)}</p></div>`;
                summaryResultEl.classList.remove('hidden');
                emptyState.classList.add('hidden');
            }
        } else {
            if (emptyState) emptyState.classList.remove('hidden');
            if (summaryResultEl) summaryResultEl.classList.add('hidden');
        }
    } catch (e) {
        if (e.name === 'AbortError') {
            return;
        }
        if (isCurrentLoad()) {
            console.error('Failed to load summary:', e);
            if (emptyState) emptyState.classList.remove('hidden');
            if (summaryResultEl) summaryResultEl.classList.add('hidden');
        }
    } finally {
        if (task) task.finish();
    }
}
window.loadSummaryForBook = loadSummaryForBook;

// ============================================================================
// ISBN 查询（本地功能，无需 AI）
// ============================================================================

/**
 * 通过 ISBN 查询图书元数据
 * 尝试从当前图书提取 ISBN，然后调用外部 API 获取信息
 */
async function lookupISBN() {
    const filename = getCurrentFilename();
    if (!filename) {
        showNotification('请先选择一本书', 3000);
        return;
    }

    const btn = document.getElementById('btn-isbn-lookup');
    const originalText = btn ? btn.innerHTML : '';

    try {
        // 显示加载状态
        if (btn) {
            btn.innerHTML = '<div class="spinner-small"></div> 查询中...';
            btn.disabled = true;
        }

        // 调用 API
        const res = await fetch(`${API_BASE}/local/isbn-lookup`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ file_path: filename })
        });
        const data = await res.json();

        if (data.success && data.metadata) {
            const meta = data.metadata;

            // 填充元数据字段
            if (meta.title) {
                const titleEl = document.getElementById('meta-title');
                if (titleEl && !titleEl.value) titleEl.value = meta.title;
            }
            if (meta.author) {
                const authorEl = document.getElementById('meta-author');
                if (authorEl && !authorEl.value) authorEl.value = meta.author;
            }
            if (meta.publisher) {
                const publisherEl = document.getElementById('meta-publisher');
                if (publisherEl && !publisherEl.value) publisherEl.value = meta.publisher;
            }

            // 触发元数据输入事件以更新预览
            if (typeof handleMetadataInput === 'function') {
                handleMetadataInput();
            }

            showNotification(`ISBN 查询成功：${meta.title}`, 4000, 'success');

            // 点亮保存按钮
            if (typeof enableSaveButton === 'function') {
                enableSaveButton();
            }
        } else {
            showNotification(data.message || '未找到 ISBN 或查询失败', 3000, 'warning');
        }
    } catch (e) {
        console.error('ISBN lookup failed:', e);
        showNotification('ISBN 查询失败: ' + e.message, 3000, 'error');
    } finally {
        // 恢复按钮状态
        if (btn) {
            btn.innerHTML = originalText || '<i class="fa-solid fa-barcode"></i> ISBN';
            btn.disabled = false;
        }
    }
}
window.lookupISBN = lookupISBN;

// ============================================================================
// 本地自动分类（无需 AI）
// ============================================================================

/**
 * 根据书名自动推荐分类 (标签)
 */
async function autoCategorize() {
    const titleEl = document.getElementById('meta-title');
    const tagsEl = document.getElementById('meta-tags');

    const title = titleEl?.value?.trim();
    if (!title) {
        showNotification('请先输入书名', 3000);
        return;
    }

    const btn = document.getElementById('btn-auto-category');

    try {
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<div class="spinner-small"></div>';
        }

        // 获取当前已有的标签
        const existingTags = tagsEl?.value?.split(',').map(t => t.trim()).filter(Boolean) || [];

        const res = await fetch(`${API_BASE}/local/categorize`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title, tags: existingTags })
        });
        const data = await res.json();

        if (data.success && data.category) {
            // 将推荐的分类添加到标签（避免重复）
            if (tagsEl) {
                const currentTags = tagsEl.value.split(',').map(t => t.trim()).filter(Boolean);
                if (!currentTags.includes(data.category)) {
                    currentTags.push(data.category);
                    tagsEl.value = currentTags.join(', ');

                    // 触发元数据输入事件
                    if (typeof handleMetadataInput === 'function') {
                        handleMetadataInput();
                    }
                    // 点亮保存按钮
                    if (typeof enableSaveButton === 'function') {
                        enableSaveButton();
                    }
                }
            }
            showNotification(`推荐分类: ${data.category}`, 3000, 'success');
        } else {
            showNotification('未能匹配分类规则', 3000, 'info');
        }
    } catch (e) {
        console.error('Auto categorize failed:', e);
        showNotification('分类推荐失败: ' + e.message, 3000, 'error');
    } finally {
        if (btn) {
            btn.innerHTML = '<i class="fa-solid fa-tag"></i>';
            btn.disabled = false;
        }
    }
}
window.autoCategorize = autoCategorize;

// ============================================================================
// 启动
// ============================================================================

init();
