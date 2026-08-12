/**
 * cloud-sync.js - 云同步管理 (iCloud)
 * 
 * 处理数据库和配置的云端同步。
 * 依赖: state.js, api.js
 */

// ============================================================================
// 同步设置管理
// ============================================================================

window.toggleSyncSettings = () => {
    const enabled = document.getElementById('sync-enabled').checked;
    const panel = document.getElementById('sync-settings-panel');
    if (enabled) {
        panel.classList.remove('hidden');
    } else {
        panel.classList.add('hidden');
    }
};

async function cloudSyncFetchJsonWithTimeout(url, options = {}, timeoutMs = 20000) {
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

function cloudSyncErrorMessage(error, actionText) {
    if (error && error.name === 'AbortError') {
        return `${actionText}超时，可能是数据库较大或后台正忙，请稍后重试。`;
    }
    return `${actionText}: ${error?.message || '未知错误'}`;
}

window.loadSyncSettings = async () => {
    try {
        const cfg = await cloudSyncFetchJsonWithTimeout(`${API_BASE}/config`, {}, 8000);
        const sync = cfg.sync || { enabled: false, path: '' };

        const enabledCheckbox = document.getElementById('sync-enabled');
        const pathInput = document.getElementById('cfg-sync-path');
        const autoCheckCheckbox = document.getElementById('sync-auto-check');
        const sensitiveCredentialsCheckbox = document.getElementById('sync-sensitive-credentials');

        if (enabledCheckbox) enabledCheckbox.checked = sync.enabled;
        if (pathInput) pathInput.value = sync.path || '';
        if (sensitiveCredentialsCheckbox) {
            sensitiveCredentialsCheckbox.checked = sync.sync_sensitive_credentials === true;
        }
        if (autoCheckCheckbox) {
            autoCheckCheckbox.checked = (sync.auto_check !== false); // default true
            // 添加事件监听器，使复选框点击后立刻保存设置
            autoCheckCheckbox.onchange = async () => {
                try {
                    const currentPath = document.getElementById('cfg-sync-path').value.trim();
                    const currentEnabled = document.getElementById('sync-enabled').checked;
                    if (!currentEnabled || !currentPath) return; // 如果同步未启用，不发送请求

                    await cloudSyncFetchJsonWithTimeout(`${API_BASE}/config/sync`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            enabled: currentEnabled,
                            path: currentPath,
                            auto_check: autoCheckCheckbox.checked,
                            sync_sensitive_credentials: document.getElementById('sync-sensitive-credentials')?.checked === true,
                            sync_database: 'skip',
                            sync_config: 'skip'
                        })
                    }, 30000);
                    showNotification(
                        autoCheckCheckbox.checked ? '已开启自动检测差异' : '已关闭自动检测差异',
                        2000, 'success'
                    );
                } catch (e) {
                    console.error('保存自动检测设置失败:', e);
                }
            };
        }

        window.toggleSyncSettings();

        // 自动刷新同步状态
        if (sync.enabled && sync.path) {
            setTimeout(() => refreshSyncStatus(), 500);
        }
    } catch (e) {
        console.error("Failed to load sync settings:", e);
    }
};

window.applySyncSettings = async () => {
    const enabled = document.getElementById('sync-enabled').checked;
    const path = document.getElementById('cfg-sync-path').value.trim();
    const autoCheck = document.getElementById('sync-auto-check').checked;
    const syncSensitiveCredentials = document.getElementById('sync-sensitive-credentials')?.checked === true;

    if (enabled && !path) {
        showNotification('请选择同步目录', 3000, 'warning');
        return;
    }

    // 如果启用同步，先验证并询问用户选择
    let useCloud = null;  // null = 自动判断

    if (enabled) {
        try {
            // 调用验证 API 获取对比信息
            const validateData = await cloudSyncFetchJsonWithTimeout(`${API_BASE}/config/sync/validate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: path })
            }, 20000);

            if (!validateData.success) {
                showNotification(`路径验证失败: ${validateData.message}`, 5000, 'error');
                return;
            }

            // 如果双方都有数据，让用户选择
            if (validateData.needs_confirmation) {
                const cloud = validateData.cloud;
                const local = validateData.local;

                const cloudInfo = `云端: ${cloud.size_mb} MB`;
                const localInfo = `本地: ${local.size_mb} MB`;

                const choice = confirm(
                    `检测到云端和本地都有数据库：\n\n` +
                    `📁 ${cloudInfo}\n` +
                    `💻 ${localInfo}\n\n` +
                    `点击"确定"：云端 → 本地（下载，适合新设备）\n` +
                    `点击"取消"：本地 → 云端（上传，覆盖云端）`
                );

                useCloud = choice;  // true = 下载云端, false = 上传本地
            }
        } catch (e) {
            console.error('Sync validation failed:', e);
            showNotification(cloudSyncErrorMessage(e, '同步状态检查失败'), 5000, 'error');
            return;
        }
    }

    showNotification('正在应用同步设置 (可能需要几秒钟)...', 0, 'info');

    try {
        const data = await cloudSyncFetchJsonWithTimeout(`${API_BASE}/config/sync`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                enabled: enabled,
                path: path,
                auto_check: autoCheck,
                sync_sensitive_credentials: syncSensitiveCredentials,
                sync_database: 'auto',
                sync_config: 'auto',
                use_cloud: useCloud  // 用户明确选择的方向
            })
        }, 90000);

        if (data.success) {
            showNotification('设置保存成功！', 3000, 'success');
            setTimeout(() => {
                alert(`同步设置已应用: ${data.message}\n\n重要：请务必重启应用程序以使数据库连接切换生效！`);
            }, 500);
            // 刷新状态显示
            refreshSyncStatus();
        } else {
            showNotification(`设置失败: ${data.message}`, 5000, 'error');
        }
    } catch (e) {
        showNotification(cloudSyncErrorMessage(e, '保存同步设置失败'), 5000, 'error');
    }
};

// ============================================================================
// 同步状态管理
// ============================================================================

/**
 * 刷新同步状态对比信息
 */
window.refreshSyncStatus = async () => {
    const path = document.getElementById('cfg-sync-path')?.value?.trim();
    if (!path) {
        updateSyncStatusUI(null);
        return;
    }

    try {
        const data = await cloudSyncFetchJsonWithTimeout(`${API_BASE}/config/sync/validate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: path })
        }, 20000);

        if (data.success) {
            updateSyncStatusUI(data);
        } else {
            updateSyncStatusUI(null);
        }
    } catch (e) {
        console.error('Failed to refresh sync status:', e);
        updateSyncStatusUI(null);
        showNotification(cloudSyncErrorMessage(e, '刷新同步状态失败'), 4000, 'error');
    }
};

/**
 * 更新同步状态 UI
 */
function updateSyncStatusUI(data) {
    const dbLocalEl = document.getElementById('sync-db-local');
    const dbCloudEl = document.getElementById('sync-db-cloud');
    const cfgLocalEl = document.getElementById('sync-config-local');
    const cfgCloudEl = document.getElementById('sync-config-cloud');
    const lastTextEl = document.getElementById('sync-last-text');

    if (!data) {
        if (dbLocalEl) dbLocalEl.innerHTML = renderSyncSide('local', '本地', '--');
        if (dbCloudEl) dbCloudEl.innerHTML = renderSyncSide('cloud', '云端', '--');
        if (cfgLocalEl) cfgLocalEl.innerHTML = renderSyncSide('local', '本地', '--');
        if (cfgCloudEl) cfgCloudEl.innerHTML = renderSyncSide('cloud', '云端', '--');
        if (lastTextEl) lastTextEl.textContent = '暂无同步记录';
        return;
    }

    // 数据库信息
    if (data.database) {
        const dbLocal = data.database.local;
        const dbCloud = data.database.cloud;
        const dbCompare = data.database.compare || {};
        const dbStatus = renderSyncStatusBadge(dbCompare);
        if (dbCloudEl) {
            dbCloudEl.innerHTML = dbCloud.exists
                ? renderSyncSide('cloud', '云端', `${dbCloud.size_mb}MB · ${dbCloud.mtime || '未知'}`, dbStatus)
                : renderSyncSide('cloud', '云端', '无数据');
        }
        if (dbLocalEl) {
            dbLocalEl.innerHTML = dbLocal.exists
                ? renderSyncSide('local', '本地', `${dbLocal.size_mb}MB · ${dbLocal.mtime || '未知'}`, dbStatus)
                : renderSyncSide('local', '本地', '无数据');
        }
    }

    // 配置信息
    if (data.config) {
        const cfgLocal = data.config.local;
        const cfgCloud = data.config.cloud;
        if (cfgCloudEl) {
            cfgCloudEl.innerHTML = cfgCloud.exists
                ? renderSyncSide('cloud', '云端', cfgCloud.mtime || '有数据')
                : renderSyncSide('cloud', '云端', '无数据');
        }
        if (cfgLocalEl) {
            cfgLocalEl.innerHTML = cfgLocal.exists
                ? renderSyncSide('local', '本地', cfgLocal.mtime || '有数据')
                : renderSyncSide('local', '本地', '无数据');
        }
    }

    // 最后同步信息
    if (data.last_sync && lastTextEl) {
        const syncTime = data.last_sync.time
            ? new Date(data.last_sync.time).toLocaleString('zh-CN')
            : '未知';
        lastTextEl.textContent = `${data.last_sync.device || '未知设备'} · ${syncTime}`;
    }
}

function renderSyncSide(kind, label, value, badge = '') {
    const icon = kind === 'cloud' ? 'fa-cloud' : 'fa-laptop';
    return `
        <span class="sync-side-line sync-side-${kind}">
            <i class="fa-solid ${icon}"></i>
            <span class="sync-side-label">${label}</span>
            <span class="sync-side-value">${value}</span>
            ${badge}
        </span>
    `;
}

function renderSyncStatusBadge(compare = {}) {
    if (compare.same_content) {
        const text = compare.cache_different ? '核心一致' : '内容一致';
        return `<span class="sync-state-badge sync-state-ok">${text}</span>`;
    }
    if (compare.different) {
        return '<span class="sync-state-badge sync-state-diff">内容不同</span>';
    }
    return '';
}

/**
 * 单独同步某个组件
 * @param {string} component - 'database' 或 'config'
 * @param {string} direction - 'upload' 或 'download'
 */
window.syncComponent = async (component, direction) => {
    const path = document.getElementById('cfg-sync-path')?.value?.trim();
    if (!path) {
        showNotification('请先配置同步目录', 3000, 'warning');
        return;
    }

    const actionText = direction === 'upload' ? '上传' : '下载';
    const componentText = component === 'database' ? '数据库' : '配置';

    // 延迟一帧，避免点击事件干扰确认弹窗
    await new Promise(resolve => setTimeout(resolve, 50));

    const directionText = direction === 'upload' ? '本地 → 云端' : '云端 → 本地';
    const impactText = direction === 'upload' ? '云端数据将被本地覆盖' : '本地数据将被云端覆盖';

    if (!confirm(`确定要${actionText}${componentText}吗？\n\n方向：${directionText}\n结果：${impactText}`)) {
        return;
    }

    showNotification(`正在${actionText}${componentText}...`, 0, 'info');

    try {
        const data = await cloudSyncFetchJsonWithTimeout(`${API_BASE}/config/sync`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                enabled: true,
                path: path,
                auto_check: document.getElementById('sync-auto-check')?.checked !== false,
                sync_sensitive_credentials: document.getElementById('sync-sensitive-credentials')?.checked === true,
                sync_database: component === 'database' ? direction : 'skip',
                sync_config: component === 'config' ? direction : 'skip'
            })
        }, 90000);

        if (data.success) {
            showNotification(`${componentText}${actionText}成功！`, 3000, 'success');
            window.hasUnsyncedChanges = false;
            refreshSyncStatus();

            if (component === 'database') {
                alert('数据库已更新。建议重启应用以加载最新数据。');
            }
        } else {
            showNotification(`${actionText}失败: ${data.message}`, 5000, 'error');
        }
    } catch (e) {
        showNotification(cloudSyncErrorMessage(e, `${actionText}${componentText}失败`), 5000, 'error');
    }
};
