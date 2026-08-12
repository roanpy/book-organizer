
/**
 * Database Synchronization & Deduplication Module
 */

let currentAnalysisResults = null;
let currentDedupResults = null; // { active_groups: [], ignored_groups: [] }
let currentDedupTab = 'active'; // 'active' | 'ignored'

async function fetchJsonWithTimeout(url, options = {}, timeoutMs = 20000) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
    try {
        const res = await fetch(url, { ...options, signal: controller.signal });
        const text = await res.text();
        let data = {};
        if (text) {
            try {
                data = JSON.parse(text);
            } catch (e) {
                data = { message: text };
            }
        }
        if (!res.ok) {
            throw new Error(data.detail || data.error || data.message || `HTTP ${res.status}`);
        }
        return data;
    } finally {
        clearTimeout(timeoutId);
    }
}

function formatRequestError(error, actionText) {
    if (error && error.name === 'AbortError') {
        return `${actionText}超时，可能是数据库较大或后台正忙，请稍后重试。`;
    }
    return `${actionText}: ${error?.message || '未知错误'}`;
}

function initSyncFeature() {
    injectSyncDropdown();
    if (!document.getElementById('sync-modal')) injectSyncModal();
    if (!document.getElementById('dedup-modal')) injectDedupModal();

    // 全局点击监听器：用于关闭下拉菜单
    document.addEventListener('click', (e) => {
        const dropdown = document.getElementById('sync-dropdown');
        if (dropdown && !dropdown.contains(e.target)) {
            dropdown.classList.remove('open');
        }
    });
}
window.initSyncFeature = initSyncFeature;

function injectSyncConflictModal() {
    if (document.getElementById('sync-conflict-modal')) return;

    const modalHtml = `
    <div id="sync-conflict-modal" class="modal hidden">
        <div class="modal-content glass-panel" style="max-width: 550px;">
            <div class="modal-header">
                <div class="conflict-icon-circle">
                    <i class="fa-solid fa-cloud-arrow-up"></i>
                </div>
            </div>
            <h3 class="conflict-title">云端数据冲突</h3>
            <p class="conflict-description">检测到云端和本地都存在数据库文件，请选择同步方向。</p>
            
            <div class="sync-conflict-comparison">
                <div class="conflict-row">
                    <div style="text-align: left;">
                        <div class="conflict-data-label"><i class="fa-solid fa-cloud"></i> 云端数据</div>
                        <div class="conflict-data-value" id="conflict-cloud-size">-- MB</div>
                        <div class="conflict-data-time" id="conflict-cloud-time">--</div>
                    </div>
                    <div class="conflict-separator">
                        <i class="fa-solid fa-arrow-right-arrow-left"></i>
                    </div>
                    <div style="text-align: right;">
                        <div class="conflict-data-label"><i class="fa-solid fa-laptop"></i> 本地数据</div>
                        <div class="conflict-data-value" id="conflict-local-size">-- MB</div>
                        <div class="conflict-data-time" id="conflict-local-time">--</div>
                    </div>
                </div>
                <div class="conflict-last-sync">
                    <i class="fa-solid fa-circle-info"></i> 上次同步: <span id="conflict-last-sync">--</span>
                </div>
            </div>

            <div class="modal-footer">
                <button class="btn-primary" id="btn-conflict-download">
                    <i class="fa-solid fa-cloud-arrow-down"></i> 云端 → 本地 下载
                </button>
                <button class="btn-secondary" id="btn-conflict-upload">
                    <i class="fa-solid fa-cloud-arrow-up"></i> 本地 → 云端 上传
                </button>
                <button class="btn-text" id="btn-conflict-cancel">
                    取消操作
                </button>
            </div>
        </div>
    </div>`;
    document.body.insertAdjacentHTML('beforeend', modalHtml);
}

function showSyncConflictModal(cloudData, localData, lastSync) {
    injectSyncConflictModal();
    const modal = document.getElementById('sync-conflict-modal');

    // 填充数据
    document.getElementById('conflict-cloud-size').innerText = cloudData.size_mb + ' MB';
    document.getElementById('conflict-cloud-time').innerText = new Date(cloudData.mtime * 1000).toLocaleString();

    document.getElementById('conflict-local-size').innerText = localData.size_mb + ' MB';
    document.getElementById('conflict-local-time').innerText = new Date(localData.mtime * 1000).toLocaleString();

    let lastSyncText = '未知';
    if (lastSync && lastSync.device) {
        const ts = lastSync.time || lastSync.timestamp;
        let dateStr = '未知时间';
        if (ts) {
            try {
                const date = new Date(ts);
                if (!isNaN(date.getTime())) {
                    dateStr = date.toLocaleString();
                } else {
                    dateStr = String(ts);
                }
            } catch (e) {
                dateStr = String(ts);
            }
        }
        lastSyncText = `${lastSync.device} (${dateStr})`;
    }
    document.getElementById('conflict-last-sync').innerText = lastSyncText;

    // 显示弹窗
    modal.classList.remove('hidden');

    return new Promise((resolve) => {
        const cleanUp = () => {
            modal.classList.add('hidden');
            // Remove listeners to prevent leak if called multiple times (though simple onclick replacement is fine)
        };

        document.getElementById('btn-conflict-download').onclick = () => {
            cleanUp();
            resolve(true); // true = use cloud (download)
        };

        document.getElementById('btn-conflict-upload').onclick = () => {
            cleanUp();
            resolve(false); // false = use local (upload)
        };

        document.getElementById('btn-conflict-cancel').onclick = () => {
            cleanUp();
            resolve(null); // null = cancel
        };
    });
}


function injectSyncDropdown() {
    const recordsBtn = document.getElementById('records-btn');
    if (!recordsBtn || document.getElementById('sync-dropdown')) return;

    // 创建下拉菜单容器
    const container = document.createElement('div');
    container.className = 'dropdown';
    container.id = 'sync-dropdown';

    // 注入 HTML
    container.innerHTML = `
        <button class="btn-icon btn-labeled dropdown-toggle" id="sync-dropdown-btn" title="同步与维护">
            <i class="fa-solid fa-rotate"></i>
            <i class="fa-solid fa-caret-down dropdown-caret"></i>
        </button>
        <div class="dropdown-menu dropdown-menu-right">
            <div class="dropdown-item" id="menu-db-sync">
                <i class="fa-solid fa-database"></i> 数据库同步
            </div>
            <div class="dropdown-item" id="menu-lib-dedup">
                <i class="fa-solid fa-clone"></i> 图书馆查重
            </div>
        </div>
    `;

    // Insert after records button
    recordsBtn.parentNode.insertBefore(container, recordsBtn.nextSibling);

    // 绑定事件
    document.getElementById('sync-dropdown-btn').onclick = (e) => {
        e.stopPropagation();
        container.classList.toggle('open');
    };

    document.getElementById('menu-db-sync').onclick = () => {
        container.classList.remove('open');
        openSyncModal();
    };

    document.getElementById('menu-lib-dedup').onclick = () => {
        container.classList.remove('open');
        openDedupModal();
    };
}

/**
 * 手动触发云同步
 */
async function triggerCloudSync() {
    const btn = document.getElementById('cloud-sync-btn');
    if (!btn) return;

    // 防止重复点击
    if (btn.classList.contains('syncing')) return;
    const icon = btn.querySelector('i');
    const originalClass = icon ? icon.className : 'fa-solid fa-cloud-arrow-up';

    try {
        // 1. 获取当前同步配置
        const config = await fetchJsonWithTimeout('/api/config', {}, 8000);
        const sync = config.sync || {};

        if (!sync.enabled || !sync.path) {
            showNotification('请先在"设置 > 数据同步"中配置并开启同步', 3000, 'warning');
            return;
        }

        // 2. 验证并询问用户选择同步方向
        let useCloud = null;  // null = 自动判断（使用后端安全检查）

        try {
            const validateData = await fetchJsonWithTimeout('/api/config/sync/validate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: sync.path })
            }, 15000);

            if (validateData.success && validateData.needs_confirmation) {
                const cloud = validateData.cloud;
                const local = validateData.local;

                // 延迟一帧，避免点击事件干扰确认弹窗
                await new Promise(resolve => setTimeout(resolve, 50));

                // 使用自定义冲突弹窗
                const selection = await showSyncConflictModal(cloud, local, validateData.last_sync);

                if (selection === null) {
                    showNotification('已取消同步', 2000, 'info');
                    return; // 用户取消
                }

                useCloud = selection;
            }
        } catch (e) {
            console.error('Sync validation failed:', e);
            showNotification(formatRequestError(e, '同步状态检查失败'), 5000, 'error');
            return;
        }

        // 3. 设置加载状态
        if (icon) icon.className = 'fa-solid fa-cloud fa-spin'; // 旋转云图标
        btn.classList.add('syncing');

        showNotification('正在与云端同步数据...', 0, 'info');

        // 4. 触发同步
        const data = await fetchJsonWithTimeout('/api/config/sync', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                enabled: sync.enabled,
                path: sync.path,
                auto_check: sync.auto_check !== false,
                sync_sensitive_credentials: sync.sync_sensitive_credentials === true,
                sync_database: 'auto',
                sync_config: 'auto',
                use_cloud: useCloud  // 用户明确选择的方向，null 时后端自动判断
            })
        }, 90000);

        if (data.success) {
            showNotification(`✅ ${data.message || '同步完成'}`, 4000, 'success');
            window.hasUnsyncedChanges = false;
            // 不再自动刷新，让用户看到消息
            // 如果同步了数据库，提示用户手动刷新
            if (data.message && data.message.includes('数据库')) {
                setTimeout(() => {
                    if (confirm('数据库已同步更新。是否刷新页面以加载最新数据？')) {
                        window.location.reload();
                    }
                }, 1500);
            }
        } else {
            showNotification(`同步失败: ${data.message}`, 5000, 'error');
        }

    } catch (e) {
        console.error(e);
        showNotification(formatRequestError(e, '同步出错'), 5000, 'error');
    } finally {
        setTimeout(() => {
            if (icon) icon.className = originalClass;
            btn.classList.remove('syncing');
        }, 600);
    }
}
window.triggerCloudSync = triggerCloudSync;

// ============================================================================
// Database Sync Logic (Existing)
// ============================================================================
// ... (Keeping exact same logic for Sync, omitted for brevity but I must include it)
// Checking previous file content to ensure I don't break sync modal ...
// Actually, I can just copy-paste the whole file content to be safe.

function injectSyncModal() {
    const modalHtml = `
    <div id="sync-modal" class="modal hidden">
        <div class="modal-content glass-panel larger-modal fixed-footer-modal sync-modal-wide">
            <div class="modal-header">
                <h3><i class="fa-solid fa-database"></i> 数据库同步与清理</h3>
                <button id="close-sync-modal" class="btn-close"><i class="fa-solid fa-xmark"></i></button>
            </div>
            <div class="modal-body modal-body-fixed">
                <div id="sync-state-loading" class="sync-state-view hidden">
                    <div class="sync-spinner-container">
                        <div class="spinner"></div>
                        <p class="sync-spinner-text">正在分析数据库与文件系统差异...</p>
                    </div>
                </div>
                <div id="sync-state-error" class="sync-state-view hidden">
                    <div class="sync-success-message">
                        <i class="fa-solid fa-triangle-exclamation sync-error-icon"></i>
                        <h4 class="sync-success-title">分析未完成</h4>
                        <p id="sync-error-msg">请稍后重试。</p>
                        <button class="btn-secondary" id="sync-retry-btn" type="button">
                            <i class="fa-solid fa-rotate-right"></i> 重试
                        </button>
                    </div>
                </div>
                <div id="sync-state-results" class="sync-state-view hidden">
                    <div class="sync-results-summary">
                        <p id="sync-health-summary" class="text-xs text-muted">正在检查数据库健康状态...</p>
                        <p>发现 <strong id="sync-op-count" class="highlight">0</strong> 个待处理项。</p>
                        <p class="text-xs text-muted">这些操作将修正数据库记录以匹配当前文件系统状态。</p>
                    </div>
                    <div class="sync-list-header">
                        <div class="sync-list-col-check"><input type="checkbox" id="sync-check-all" checked></div>
                        <div class="sync-list-col-type">类型</div>
                        <div class="sync-list-col-detail">详情</div>
                        <div class="sync-list-col-reason">原因</div>
                    </div>
                    <div id="sync-items-list" class="scrollable-list sync-items-list"></div>
                </div>
                <div id="sync-state-success" class="sync-state-view hidden">
                    <div class="sync-success-message">
                        <i class="fa-solid fa-circle-check sync-success-icon"></i>
                        <h4 class="sync-success-title">同步完成</h4>
                        <p id="sync-result-msg">数据库已更新。</p>
                        <p id="sync-backup-path" class="text-xs text-muted sync-backup-path"></p>
                    </div>
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn-secondary" id="sync-cancel-btn">取消</button>
                <button class="btn-primary" id="sync-execute-btn" disabled>
                    <i class="fa-solid fa-bolt"></i> 执行处理
                </button>
            </div>
        </div>
    </div>`;
    document.body.insertAdjacentHTML('beforeend', modalHtml);

    document.getElementById('close-sync-modal').onclick = () => document.getElementById('sync-modal').classList.add('hidden');
    document.getElementById('sync-cancel-btn').onclick = () => document.getElementById('sync-modal').classList.add('hidden');
    document.getElementById('sync-execute-btn').onclick = executeSync;
    document.getElementById('sync-retry-btn').onclick = fetchAnalysis;
    document.getElementById('sync-check-all').onchange = (e) => {
        document.querySelectorAll('.sync-item-check').forEach(cb => cb.checked = e.target.checked);
        updateExecuteButtonState();
    };
}

function openSyncModal() {
    const modal = document.getElementById('sync-modal');
    modal.classList.remove('hidden');
    showState('sync', 'loading');
    currentAnalysisResults = null;
    document.getElementById('sync-execute-btn').disabled = true;
    document.getElementById('sync-execute-btn').style.display = 'none';
    document.getElementById('sync-cancel-btn').innerText = '取消';
    fetchAnalysis();
}

function showState(prefix, state) {
    ['loading', 'results', 'success', 'empty', 'error'].forEach(s => {
        const el = document.getElementById(`${prefix}-state-${s}`);
        if (el) el.classList.toggle('hidden', s !== state);
    });

    if (prefix === 'sync') {
        if (state === 'results') {
            document.getElementById('sync-execute-btn').style.display = 'block';
            document.getElementById('sync-cancel-btn').innerText = '取消';
        } else if (state === 'success') {
            document.getElementById('sync-execute-btn').style.display = 'none';
            document.getElementById('sync-cancel-btn').innerText = '关闭';
        } else if (state === 'loading' || state === 'error') {
            document.getElementById('sync-execute-btn').style.display = 'none';
            document.getElementById('sync-cancel-btn').innerText = state === 'error' ? '关闭' : '取消';
        }
    }
}

async function fetchAnalysis() {
    showState('sync', 'loading');
    try {
        const data = await fetchJsonWithTimeout('/api/db/sync/analyze', { method: 'POST' }, 30000);
        if (data.success) {
            currentAnalysisResults = data.operations;
            renderSyncResults(data.operations);
            renderDatabaseHealth(data.health);
            showState('sync', 'results');
        } else {
            showSyncError('分析失败: ' + (data.error || data.detail || '未知错误'));
        }
    } catch (e) {
        console.error(e);
        showSyncError(formatRequestError(e, '数据库同步分析失败'));
    }
}

function renderDatabaseHealth(health) {
    const element = document.getElementById('sync-health-summary');
    if (!element) return;
    if (!health) {
        element.textContent = '数据库健康检查暂不可用。';
        return;
    }
    const issues = health.issues || {};
    const issueCount = Object.values(issues).reduce((sum, value) => sum + Number(value || 0), 0);
    element.textContent = health.status === 'healthy'
        ? `数据库完整，已扫描 ${health.scanned_files || 0} 个文件。`
        : `数据库需关注：${issueCount} 项（只读检查，不会自动修改）。`;
}

function showSyncError(message) {
    const msg = document.getElementById('sync-error-msg');
    if (msg) msg.innerText = message;
    showState('sync', 'error');
}

function renderSyncResults(ops) {
    const list = document.getElementById('sync-items-list');
    list.innerHTML = '';
    document.getElementById('sync-op-count').innerText = ops.length;

    if (ops.length === 0) {
        list.innerHTML = '<div class="sync-empty-state">未发现不一致项。</div>';
        return;
    }

    ops.forEach((op, index) => {
        const row = document.createElement('div');
        row.className = 'sync-item-row';

        let badge = op.type === 'UPDATE' ?
            `<span class="sync-badge-update">更新</span>` :
            `<span class="sync-badge-delete">删除</span>`;

        let details = op.type === 'UPDATE' ?
            `<div class="sync-filename">${op.filename}</div><div class="sync-new-filename"><i class="fa-solid fa-arrow-right"></i> ${op.data.new_filename}</div>` :
            `<div class="sync-filename">${op.filename}</div>`;

        row.innerHTML = `
            <div class="sync-list-col-check"><input type="checkbox" class="sync-item-check" data-index="${index}" checked></div>
            <div class="sync-list-col-type">${badge}</div>
            <div class="sync-list-col-detail">${details}</div>
            <div class="sync-list-col-reason">${op.description}</div>
        `;
        list.appendChild(row);
    });

    list.querySelectorAll('.sync-item-check').forEach(cb => cb.onchange = updateExecuteButtonState);
    updateExecuteButtonState();
}

function updateExecuteButtonState() {
    const checkedCount = document.querySelectorAll('.sync-item-check:checked').length;
    const btn = document.getElementById('sync-execute-btn');
    btn.disabled = checkedCount === 0;
    btn.innerHTML = `<i class="fa-solid fa-bolt"></i> 执行处理 (${checkedCount})`;
}

async function executeSync() {
    const checkboxes = document.querySelectorAll('.sync-item-check:checked');
    const selectedOps = Array.from(checkboxes).map(cb => currentAnalysisResults[parseInt(cb.dataset.index)]);
    const btn = document.getElementById('sync-execute-btn');
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 执行中...';
    btn.disabled = true;
    try {
        const data = await fetchJsonWithTimeout('/api/db/sync/execute', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ operations: selectedOps })
        }, 60000);
        if (data.success) {
            showState('sync', 'success');
            document.getElementById('sync-result-msg').innerText = data.message;
            if (data.backup_created) document.getElementById('sync-backup-path').innerText = "已创建本地滚动备份";
        } else {
            showSyncError('执行失败: ' + (data.detail || data.error || '未知错误'));
            btn.disabled = false;
        }
    } catch (e) {
        console.error(e);
        showSyncError(formatRequestError(e, '数据库同步执行失败'));
        btn.disabled = false;
    }
}


// ============================================================================
// 图书馆查重逻辑 (包含忽略列表和标签切换)
// ============================================================================

function injectDedupModal() {
    const modalHtml = `
    <div id="dedup-modal" class="modal hidden">
        <div class="modal-content glass-panel larger-modal fixed-footer-modal sync-modal-wider">
            <div class="modal-header">
                <h3 class="dedup-header-title">
                    <i class="fa-solid fa-clone" style="font-size: 1.1em;"></i>
                    <span>图书馆查重</span>
                    <span id="dedup-badge" class="dedup-badge">共<span id="dedup-header-count">0</span>组重复</span>
                </h3>
                
                <div class="dedup-tabs-container">
                     <div class="dedup-tab active" id="tab-dedup-active">
                        <i class="fa-solid fa-list-ul"></i> 查重记录 (<span id="count-active">0</span>)
                     </div>
                     <div class="dedup-tab" id="tab-dedup-ignored">
                        <i class="fa-solid fa-eye-slash"></i> 忽略记录 (<span id="count-ignored">0</span>)
                     </div>
                </div>
                
                <button id="close-dedup-modal" class="btn-close"><i class="fa-solid fa-xmark"></i></button>
            </div>
            
            <div class="modal-body modal-body-fixed" style="padding: 0; display: flex; flex-direction: column; overflow: hidden;">
                <div id="dedup-state-loading" class="dedup-state-view hidden dedup-loading-container">
                    <div class="spinner-container">
                        <div class="spinner"></div>
                        <p class="sync-spinner-text">正在深度扫描相似图书...</p>
                    </div>
                </div>
                <div id="dedup-state-error" class="dedup-state-view hidden dedup-empty-container">
                    <i class="fa-solid fa-triangle-exclamation dedup-empty-icon"></i>
                    <p id="dedup-error-msg" class="dedup-empty-text">查重分析未完成。</p>
                    <button class="btn-secondary" id="dedup-retry-btn" type="button">
                        <i class="fa-solid fa-rotate-right"></i> 重试
                    </button>
                </div>
                <div id="dedup-state-results" class="dedup-state-view hidden dedup-results-container">
                    <!-- Scrollable list takes full remaining height with padding inside -->
                    <div id="dedup-items-list" class="scrollable-list dedup-items-list"></div>
                </div>
                <div id="dedup-state-empty" class="dedup-state-view hidden dedup-empty-container">
                    <i class="fa-solid fa-check-double dedup-empty-icon"></i>
                    <p id="dedup-empty-msg" class="dedup-empty-text">未发现重复图书。</p>
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn-primary" onclick="document.getElementById('dedup-modal').classList.add('hidden')">关闭</button>
            </div>
        </div>
    </div>`;
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    document.getElementById('close-dedup-modal').onclick = () => document.getElementById('dedup-modal').classList.add('hidden');

    // 绑定标签页事件
    document.getElementById('tab-dedup-active').onclick = () => switchDedupTab('active');
    document.getElementById('tab-dedup-ignored').onclick = () => switchDedupTab('ignored');
    document.getElementById('dedup-retry-btn').onclick = fetchDedupAnalysis;
}

function openDedupModal() {
    const modal = document.getElementById('dedup-modal');
    modal.classList.remove('hidden');
    showState('dedup', 'loading');

    // 默认显示"查重记录"标签
    switchDedupTab('active', false);

    fetchDedupAnalysis();
}

function switchDedupTab(tab, render = true) {
    currentDedupTab = tab;

    // 更新 UI
    const tActive = document.getElementById('tab-dedup-active');
    const tIgnored = document.getElementById('tab-dedup-ignored');

    if (tab === 'active') {
        tActive.classList.add('active');
        tIgnored.classList.remove('active');
    } else {
        tActive.classList.remove('active');
        tIgnored.classList.add('active');
    }

    if (render && currentDedupResults) {
        renderDedupView();
    }
}

async function fetchDedupAnalysis() {
    showState('dedup', 'loading');
    try {
        const data = await fetchJsonWithTimeout('/api/db/deduplicate/analyze', { method: 'POST' }, 45000);
        if (data.success) {
            // data.groups 主要用于向后兼容，这里我们需要详细列表
            currentDedupResults = {
                active: data.active_groups || data.groups || [],
                ignored: data.ignored_groups || []
            };

            // 更新计数
            document.getElementById('count-active').innerText = currentDedupResults.active.length;
            document.getElementById('count-ignored').innerText = currentDedupResults.ignored.length;

            renderDedupView();
        } else {
            showDedupError('分析失败: ' + (data.detail || data.error || '未知错误'));
        }
    } catch (e) {
        console.error(e);
        showDedupError(formatRequestError(e, '图书馆查重失败'));
    }
}

function showDedupError(message) {
    const msg = document.getElementById('dedup-error-msg');
    if (msg) msg.innerText = message;
    document.getElementById('dedup-header-count').innerText = '0';
    showState('dedup', 'error');
}

function renderDedupView() {
    const list = document.getElementById('dedup-items-list');
    list.innerHTML = '';

    const groups = currentDedupTab === 'active' ? currentDedupResults.active : currentDedupResults.ignored;
    document.getElementById('dedup-header-count').innerText = groups.length;

    if (groups.length === 0) {
        showState('dedup', 'empty');
        document.getElementById('dedup-empty-msg').innerText = currentDedupTab === 'active' ? '未发现重复图书。' : '没有已忽略的记录。';
        return;
    }

    showState('dedup', 'results');

    groups.forEach((group, gIdx) => {
        const groupEl = document.createElement('div');
        groupEl.className = 'dedup-group';

        // 头部区域
        const header = document.createElement('div');
        header.className = 'dedup-group-header';

        const title = document.createElement('div');
        title.innerHTML = `<i class="fa-solid fa-layer-group"></i> 疑似分组: "${group.key}"`;

        const actionBtn = document.createElement('button');
        actionBtn.className = 'btn-sm btn-secondary';

        if (currentDedupTab === 'active') {
            actionBtn.innerHTML = '<i class="fa-solid fa-eye-slash"></i> 忽略';
            actionBtn.onclick = () => ignoreGroup(group, gIdx);
        } else {
            actionBtn.innerHTML = '<i class="fa-solid fa-eye"></i> 取消忽略';
            actionBtn.onclick = () => unignoreGroup(group, gIdx);
        }

        header.appendChild(title);
        header.appendChild(actionBtn);
        groupEl.appendChild(header);

        // 图书列表区域
        const itemsContainer = document.createElement('div');
        itemsContainer.className = 'dedup-items-container';
        itemsContainer.id = `dedup-group-c-${gIdx}`;

        group.items.forEach(item => {
            const itemEl = document.createElement('div');
            itemEl.className = 'dedup-item';

            // 格式化徽章
            const extBadge = `<span class="dedup-extension-badge">${item.ext.toUpperCase().replace('.', '')}</span>`;
            const summaryBadge = item.has_summary ? `<span class="dedup-feature-badge success" title="有增强简介"><i class="fa-solid fa-file-lines"></i></span>` : '';
            const tocBadge = item.toc_count > 0 ? `<span class="dedup-feature-badge warning" title="有目录 (${item.toc_count})"><i class="fa-solid fa-list-ol"></i> ${item.toc_count}</span>` : '';

            const sizeMB = (item.size / 1024 / 1024).toFixed(2) + ' MB';

            itemEl.innerHTML = `
                <div class="dedup-item-content">
                    <div class="dedup-item-top-row">
                        ${extBadge}
                        <span class="dedup-filename" title="${item.filename}">${item.filename}</span>
                        ${summaryBadge} ${tocBadge}
                    </div>
                    <div class="dedup-item-bottom-row">
                        <span title="${item.path}">${item.rel_path}</span>
                        <span>${sizeMB}</span>
                    </div>
                </div>
                <button class="btn-danger btn-sm dedup-delete-btn" title="删除此文件">
                    <i class="fa-solid fa-trash"></i>
                </button>
            `;

            // 绑定删除事件
            itemEl.querySelector('.dedup-delete-btn').onclick = () => deleteDuplicateBook(item.path, itemEl, gIdx);

            itemsContainer.appendChild(itemEl);
        });

        groupEl.appendChild(itemsContainer);
        list.appendChild(groupEl);
    });
}

async function ignoreGroup(group, idx) {
    if (!confirm('确定忽略此分组吗？\n如果该组合再次出现（文件完全一致）将自动隐藏。\n一旦有文件增删，它将重新出现在列表。')) return;

    // 立即更新 UI (乐观更新)
    // 1. 从活动列表中移除
    currentDedupResults.active.splice(idx, 1);

    // 2. 添加到忽略列表 (构建预测对象)
    // 注意：严格来说我们需要后端确认规则 ID 才能进行反操作，
    // 但我们可以稍后追加 ID，或者等用户切换标签时刷新。
    // 当前策略：等待后端返回 ID，然后更新本地数组。
    // 关键点在于不要调用 fetchDedupAnalysis() 触发磁盘重扫。

    try {
        const data = await fetchJsonWithTimeout('/api/db/deduplicate/ignore', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ paths: group.items.map(i => i.path) })
        }, 20000);

        if (data.success) {
            // 成功：完全更新本地状态
            group.ignore_rule_id = data.rule_id; // 赋值后端返回的 ID
            currentDedupResults.ignored.push(group); // 移入忽略列表

            // 重新渲染当前视图 (活动列表)
            // 因为我们已经从 currentDedupResults.active 中移除了元素，直接重新渲染即可。
            document.getElementById('count-active').innerText = currentDedupResults.active.length;
            document.getElementById('count-ignored').innerText = currentDedupResults.ignored.length;
            renderDedupView();

        } else {
            // 失败时回滚
            alert('操作失败: ' + data.message);
            // 如果操作失败，安全起见触发全量刷新
            fetchDedupAnalysis(); // Fallback to full reload on error
        }
    } catch (e) {
        console.error(e);
        alert('请求出错');
        fetchDedupAnalysis();
    }
}

async function unignoreGroup(group, idx) {
    if (!group.ignore_rule_id) {
        alert('错误：无法找到规则 ID');
        return;
    }

    try {
        const data = await fetchJsonWithTimeout('/api/db/deduplicate/unignore', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: group.ignore_rule_id })
        }, 20000);
        if (data.success) {
            // 乐观更新
            currentDedupResults.ignored.splice(idx, 1);
            delete group.ignore_rule_id;
            currentDedupResults.active.push(group);

            // 更新计数与视图
            document.getElementById('count-active').innerText = currentDedupResults.active.length;
            document.getElementById('count-ignored').innerText = currentDedupResults.ignored.length;
            renderDedupView();

        } else {
            alert('操作失败: ' + data.message);
        }
    } catch (e) { console.error(e); alert('请求出错'); }
}

async function deleteDuplicateBook(path, element, groupIdx) {
    if (!confirm('确定要永久删除此文件吗？此操作无法撤销。')) return;

    const btn = element.querySelector('.dedup-delete-btn');
    const originalIcon = btn.innerHTML;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
    btn.disabled = true;

    try {
        const data = await fetchJsonWithTimeout('/api/db/deduplicate/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: path })
        }, 30000); // 之前已经确认后端 delete_file 会清理 DB including book_tocs mostly

        if (data.success) {
            // 删除元素前捕获容器 ID
            const cId = element.parentElement.id; // dedup-group-c-{gIdx}

            element.style.opacity = '0';
            setTimeout(() => {
                element.remove();

                // 检查分组是否应该移除（剩余少于2项）
                const container = document.getElementById(cId);
                if (container && container.children.length < 2) {
                    // 平滑移除整个分组
                    const groupEl = container.parentElement;
                    groupEl.style.opacity = '0';
                    setTimeout(() => {
                        groupEl.remove();
                        // 刷新数据以确保一致性 (计数等)
                        fetchDedupAnalysis();
                    }, 300);
                } else {
                    // 如果分组仍然有效，仅刷新计数
                    fetchDedupAnalysis();
                }
            }, 300);
        } else {
            alert('删除失败: ' + data.message);
            btn.innerHTML = originalIcon;
            btn.disabled = false;
        }
    } catch (e) {
        console.error(e);
        alert('删除出错');
        btn.innerHTML = originalIcon;
        btn.disabled = false;
    }
}

// ============================================================================
// Lifecycle Sync Check (Startup & Shutdown)
// ============================================================================

let isSyncCheckPending = false;

function initSyncLifecycle() {
    // 1. Startup Check
    // 延迟检查同步状态，确保 UI 和图书列表已经加载完成
    // 将延迟从 1s 增加到 3s，避免阻塞主内容加载
    setTimeout(() => {
        // 额外检查：确保图书列表已加载（避免空列表时弹窗阻塞加载）
        const bookList = document.getElementById('book-list');
        const hasBooks = bookList && bookList.children.length > 0;
        const loadingDone = !bookList || !bookList.querySelector('.loading-indicator');

        // 只有在页面内容基本加载完成后才检查同步
        if (loadingDone) {
            checkSyncStatus({ isShutdown: false });
        } else {
            // 如果还在加载，再延迟 2 秒
            setTimeout(() => {
                checkSyncStatus({ isShutdown: false });
            }, 2000);
        }
    }, 3000);

    // 2. Shutdown handling
    window.addEventListener('beforeunload', () => {
        // Desktop WebView shutdown must stay non-blocking. A returnValue prompt can
        // leave pywebview waiting during app quit, especially after sync or network I/O.
        window.hasUnsyncedChanges = false;
    });

    // Special: Intercept Electron window close if applicable (Hypothetical)
    // If this runs in a WebView/Electron, we would bind to window.onclose or similar custom API.
}
window.initSyncLifecycle = initSyncLifecycle;

/**
 * Perform sync status check
 * @param {Object} options - { isShutdown: boolean }
 */
async function checkSyncStatus({ isShutdown = false } = {}) {
    if (isSyncCheckPending) return;
    isSyncCheckPending = true;

    // 创建超时控制器，防止网络请求卡住阻塞应用加载
    const timeoutController = new AbortController();
    const timeoutId = setTimeout(() => {
        timeoutController.abort();
        console.warn('[Sync Check] Timeout after 5 seconds, skipping check.');
    }, 10000);

    try {
        // 1. Get Config
        const resConfig = await fetch('/api/config', {
            signal: timeoutController.signal
        });
        const config = await resConfig.json();
        const sync = config.sync || {};

        // Requirement: "If iCloud switch (enabled) is closed, do not detect"
        if (!sync.enabled) {
            isSyncCheckPending = false;
            clearTimeout(timeoutId);
            return;
        }

        // Requirement: Check "Database Sync Check Switch" (auto_check)
        // If undefined, default to true (backward compatibility)
        if (sync.auto_check === false) {
            isSyncCheckPending = false;
            clearTimeout(timeoutId);
            return;
        }

        // 2. Validate / Check Diff
        if (!sync.path) {
            isSyncCheckPending = false;
            clearTimeout(timeoutId);
            return;
        }

        const validateRes = await fetch('/api/config/sync/validate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: sync.path }),
            signal: timeoutController.signal
        });
        clearTimeout(timeoutId);
        const data = await validateRes.json();

        // Requirement: "If cloud has no data, do not prompt"
        if (!data.success || !data.cloud.exists || data.cloud.size < 1024) {
            isSyncCheckPending = false;
            return;
        }

        const local = data.local;
        const cloud = data.cloud;
        const isDifferent = Boolean(data.needs_confirmation || data.database?.compare?.different);

        if (isDifferent) {
            window.hasUnsyncedChanges = true; // Mark for beforeunload

            if (isShutdown) {
                // Handling shutdown check specifically if called manually
                // (e.g. if we had a custom close button)
                return showLifecycleSyncModal('shutdown', cloud, local, data.last_sync);
            } else {
                // Startup check
                return showLifecycleSyncModal('startup', cloud, local, data.last_sync);
            }
        } else {
            window.hasUnsyncedChanges = false;
        }

    } catch (e) {
        // 区分超时取消和实际错误
        if (e.name === 'AbortError') {
            // 超时取消是预期行为，静默处理
            console.warn('[Sync Check] Request aborted (likely timeout).');
        } else {
            console.error('Lifecycle sync check failed:', e);
        }
    } finally {
        isSyncCheckPending = false;
    }
}
window.checkSyncStatus = checkSyncStatus;

/**
 * Show Lifecycle Sync Modal
 * @param {string} type - 'startup' | 'shutdown'
 */
function showLifecycleSyncModal(type, cloudData, localData, lastSync) {
    // Remove existing if any
    const existing = document.getElementById('sync-lifecycle-modal');
    if (existing) existing.remove();

    const title = type === 'startup' ? '启动同步检测' : '退出同步检测';
    const msg = type === 'startup'
        ? '检测到云端和本地数据库内容不同，请选择同步方向。'
        : '检测到本地数据库内容与云端版本不一致，建议同步后再退出。';

    const btnCancelText = type === 'startup' ? '忽略' : '取消退出';

    // 格式化时间
    const cloudTime = new Date(cloudData.mtime * 1000).toLocaleString('zh-CN');
    const localTime = new Date(localData.mtime * 1000).toLocaleString('zh-CN');
    const cloudSize = (cloudData.size / 1024 / 1024).toFixed(2);
    const localSize = (localData.size / 1024 / 1024).toFixed(2);

    // 上次同步信息
    let lastSyncText = '未知';
    if (lastSync && lastSync.time) {
        lastSyncText = `${lastSync.device || '未知设备'} (${new Date(lastSync.time).toLocaleString('zh-CN')})`;
    }

    const modalHtml = `
    <div id="sync-lifecycle-modal" class="modal">
        <div class="modal-content glass-panel">
            <div class="modal-header">
                <div class="conflict-icon-circle">
                    <i class="fa-solid fa-cloud-arrow-up"></i>
                </div>
            </div>
            <h3 class="conflict-title">${title}</h3>
            <p class="conflict-description">${msg}</p>
            
            <div class="sync-conflict-comparison">
                <div class="conflict-row">
                    <div style="text-align: left;">
                        <div class="conflict-data-label"><i class="fa-solid fa-cloud"></i> 云端数据</div>
                        <div class="conflict-data-value">${cloudSize} MB</div>
                        <div class="conflict-data-time">${cloudTime}</div>
                    </div>
                    <div class="conflict-separator">
                        <i class="fa-solid fa-arrow-right-arrow-left"></i>
                    </div>
                    <div style="text-align: right;">
                        <div class="conflict-data-label"><i class="fa-solid fa-laptop"></i> 本地数据</div>
                        <div class="conflict-data-value">${localSize} MB</div>
                        <div class="conflict-data-time">${localTime}</div>
                    </div>
                </div>
                <div class="conflict-last-sync">
                    <i class="fa-solid fa-circle-info"></i> 上次同步: <span>${lastSyncText}</span>
                </div>
            </div>

            <div class="modal-footer">
                <button class="btn-primary" id="btn-lifecycle-jump">
                    <i class="fa-solid fa-arrow-right"></i> 去同步
                </button>
                <button class="btn-text" id="btn-lifecycle-cancel">
                    ${btnCancelText}
                </button>
            </div>
        </div>
    </div>`;
    document.body.insertAdjacentHTML('beforeend', modalHtml);

    return new Promise((resolve) => {
        const modal = document.getElementById('sync-lifecycle-modal');

        document.getElementById('btn-lifecycle-cancel').onclick = () => {
            modal.remove();
            resolve('cancel');
        };

        document.getElementById('btn-lifecycle-jump').onclick = () => {
            modal.remove();
            // Open Sync Settings
            const settingsBtn = document.getElementById('settings-btn');
            if (settingsBtn) settingsBtn.click();

            // Switch to Sync Tab
            // We need to wait for modal to open
            setTimeout(() => {
                const syncTabBtn = document.querySelector('.settings-tabs button[onclick="switchTab(\'sync\')"]');
                if (syncTabBtn) syncTabBtn.click();
            }, 100);

            resolve('jump');
        };
    });
}
