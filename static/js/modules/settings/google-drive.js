/**
 * google-drive.js - Google Drive 集成
 * 
 * 处理 Google Drive 授权、上传、文件夹管理等。
 * 依赖: state.js, api.js
 */

// ============================================================================
// Google Drive 状态管理
// ============================================================================

/**
 * 检查 Google Drive 连接状态并更新 UI
 */
window.checkGoogleDriveStatus = async () => {
    try {
        const res = await fetch(`${API_BASE}/google_drive/status`);
        const data = await res.json();

        const indicator = document.getElementById('gdrive-status-indicator');
        const statusText = document.getElementById('gdrive-status-text');
        const authBtn = document.getElementById('gdrive-auth-btn');
        const disconnectBtn = document.getElementById('gdrive-disconnect-btn');
        const folderSection = document.getElementById('gdrive-folder-section');
        const autoSection = document.getElementById('gdrive-auto-section');
        const autoUploadIcon = document.getElementById('auto-upload-icon');

        if (data.authenticated) {
            // 已连接
            isGoogleDriveConnected = true;
            indicator.className = 'status-dot connected';
            statusText.textContent = data.user_email || '已连接';
            authBtn.classList.add('hidden');
            disconnectBtn.classList.remove('hidden');
            folderSection.classList.remove('hidden');
            autoSection.classList.remove('hidden');

            // 显示工具栏自动上传按钮
            if (autoUploadIcon) {
                autoUploadIcon.classList.remove('hidden');
            }

            // 加载文件夹列表
            refreshGDriveFolders();

            // 同步自动上传状态
            syncAutoUploadState();
        } else if (data.configured) {
            // 已配置但未授权
            isGoogleDriveConnected = false;
            indicator.className = 'status-dot pending';
            statusText.textContent = '请点击授权';
            authBtn.classList.remove('hidden');
            disconnectBtn.classList.add('hidden');
            folderSection.classList.add('hidden');
            autoSection.classList.add('hidden');

            // 隐藏工具栏自动上传按钮
            if (autoUploadIcon) {
                autoUploadIcon.classList.add('hidden');
            }
        } else {
            // 未配置
            isGoogleDriveConnected = false;
            indicator.className = 'status-dot disconnected';
            statusText.textContent = '未配置凭据';
            authBtn.classList.remove('hidden'); // Allow user to click to see error message
            disconnectBtn.classList.add('hidden');
            folderSection.classList.add('hidden');
            autoSection.classList.add('hidden');

            // 隐藏工具栏自动上传按钮
            if (autoUploadIcon) {
                autoUploadIcon.classList.add('hidden');
            }
        }

        // 更新配置区域显示状态 (未连接时均显示，以便覆盖凭据)
        const setupSection = document.getElementById('gdrive-setup-section');
        if (setupSection) {
            if (!data.authenticated) {
                setupSection.classList.remove('hidden');

                // 如果已配置，修改按钮文字为 "更换凭据"
                const uploadBtn = setupSection.querySelector('button i.fa-upload').parentElement;
                if (data.configured) {
                    if (uploadBtn.childNodes[1]) {
                        uploadBtn.childNodes[1].textContent = " 更换凭据 (覆盖)";
                    }
                } else {
                    if (uploadBtn.childNodes[1]) {
                        uploadBtn.childNodes[1].textContent = " 上传凭据 (client_secrets.json)";
                    }
                }
            } else {
                setupSection.classList.add('hidden');
            }
        }

    } catch (e) {
        console.error('[GDrive] Status check failed:', e);
    }
};

/**
 * 上传 Google Drive 凭据
 */
window.uploadGDriveCredentials = async (input) => {
    if (!input.files || !input.files[0]) return;

    const file = input.files[0];
    const formData = new FormData();
    formData.append('file', file);

    try {
        showNotification('正在上传凭据...', 0, 'info'); // 0 = no timeout

        const res = await fetch(`${API_BASE}/google_drive/upload_credentials`, {
            method: 'POST',
            body: formData
        });

        const data = await res.json();

        if (res.ok) {
            showNotification('凭据上传成功，请点击授权连接', 3000, 'success');
            // 清空 input
            input.value = '';
            // 刷新状态
            checkGoogleDriveStatus();
        } else {
            showNotification(`上传失败: ${data.detail || '未知错误'}`, 5000, 'error');
        }
    } catch (e) {
        console.error('Upload failed:', e);
        showNotification('上传发生网络错误', 3000, 'error');
    }
};

/**
 * 切换 Google Drive 帮助显示
 */
window.toggleGDriveHelp = () => {
    const helpText = document.getElementById('gdrive-help-text');
    if (helpText) {
        if (helpText.classList.contains('hidden')) {
            helpText.classList.remove('hidden');
        } else {
            helpText.classList.add('hidden');
        }
    }
};

// ============================================================================
// 自动上传管理
// ============================================================================

/**
 * 同步自动上传状态（从配置或复选框）
 */
function syncAutoUploadState() {
    const settingsCheckbox = document.getElementById('gdrive-auto-upload');
    const toolbarIcon = document.getElementById('auto-upload-icon');

    // 从配置读取状态
    const autoUpload = config?.beta_features?.google_drive?.auto_upload || false;
    isAutoUploadEnabled = autoUpload;

    // 同步设置页面复选框
    if (settingsCheckbox) {
        settingsCheckbox.checked = autoUpload;
    }

    // 同步工具栏按钮状态
    updateAutoUploadIconState();
}
window.syncAutoUploadState = syncAutoUploadState;

/**
 * 更新工具栏自动上传按钮的视觉状态
 */
function updateAutoUploadIconState() {
    const icon = document.getElementById('auto-upload-icon');
    if (!icon) return;

    if (isAutoUploadEnabled) {
        icon.classList.add('active');
        icon.setAttribute('data-tooltip', '自动上传: 已开启');
    } else {
        icon.classList.remove('active');
        icon.setAttribute('data-tooltip', '自动上传: 已关闭');
    }
}

/**
 * 切换自动上传状态（工具栏按钮点击）
 */
window.toggleAutoUpload = async () => {
    if (!isGoogleDriveConnected) {
        showNotification('请先连接 Google Drive', 3000, 'warning');
        return;
    }

    isAutoUploadEnabled = !isAutoUploadEnabled;

    // 同步到设置页面
    const settingsCheckbox = document.getElementById('gdrive-auto-upload');
    if (settingsCheckbox) {
        settingsCheckbox.checked = isAutoUploadEnabled;
    }

    // 更新工具栏按钮状态
    updateAutoUploadIconState();

    // 保存到配置
    try {
        const resLoad = await fetch(`${API_BASE}/config`);
        const currentConfig = await resLoad.json();

        if (!currentConfig.beta_features) currentConfig.beta_features = {};
        if (!currentConfig.beta_features.google_drive) currentConfig.beta_features.google_drive = {};
        currentConfig.beta_features.google_drive.auto_upload = isAutoUploadEnabled;

        await fetch(`${API_BASE}/config`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(currentConfig)
        });

        config = currentConfig;
        showNotification(`自动上传: ${isAutoUploadEnabled ? '已开启' : '已关闭'}`, 2000, 'success');
    } catch (e) {
        console.error('[GDrive] Failed to save auto-upload setting:', e);
    }
};

// ============================================================================
// 授权与连接管理
// ============================================================================

/**
 * 启动 Google Drive OAuth 授权
 */
window.authorizeGoogleDrive = async () => {
    const btn = document.getElementById('gdrive-auth-btn');
    const originalText = btn.innerHTML;

    try {
        btn.disabled = true;
        btn.innerHTML = '<div class="spinner-small"></div> 授权中...';

        showNotification('正在打开浏览器进行授权...', 3000, 'info');

        const res = await fetch(`${API_BASE}/google_drive/auth`, { method: 'POST' });
        const data = await res.json();

        if (res.ok && data.success) {
            showNotification(`授权成功: ${data.user_email}`, 3000, 'success');
            checkGoogleDriveStatus();
        } else {
            throw new Error(data.detail || data.message || '授权失败');
        }
    } catch (e) {
        showNotification(`授权失败: ${e.message}`, 5000, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
};

/**
 * 断开 Google Drive 连接
 */
window.disconnectGoogleDrive = async () => {
    try {
        const res = await fetch(`${API_BASE}/google_drive/disconnect`, { method: 'POST' });
        if (res.ok) {
            showNotification('已断开 Google Drive', 2000, 'success');
            checkGoogleDriveStatus();
        }
    } catch (e) {
        showNotification(`断开失败: ${e.message}`, 3000, 'error');
    }
};

// ============================================================================
// 文件夹与上传管理
// ============================================================================

/**
 * 刷新 Google Drive 文件夹列表
 */
window.refreshGDriveFolders = async () => {
    const select = document.getElementById('gdrive-folder-select');
    if (!select) return;

    try {
        const res = await fetch(`${API_BASE}/google_drive/folders`);
        const data = await res.json();

        select.innerHTML = '';

        // 1. NotebookLLM (默认选项，对应后端空值逻辑)
        const optDefault = document.createElement('option');
        optDefault.value = "";
        optDefault.textContent = "NotebookLLM";
        select.appendChild(optDefault);

        // 2. 根目录 (显式指定 root)
        const optRoot = document.createElement('option');
        optRoot.value = "root";
        optRoot.textContent = "根目录 (我的云端硬盘)";
        select.appendChild(optRoot);

        if (data.success && data.folders) {
            data.folders.forEach(folder => {
                // 过滤掉名字叫 NotebookLLM 的文件夹，避免重复（因为默认选项已经涵盖了它）
                if (folder.name === 'NotebookLLM') return;

                const option = document.createElement('option');
                option.value = folder.id;
                option.textContent = folder.name;
                select.appendChild(option);
            });
        }

        // 恢复已保存的选择
        const savedFolderId = config?.beta_features?.google_drive?.target_folder_id;
        if (savedFolderId) {
            select.value = savedFolderId;
        } else {
            // 如果没有保存过（或者保存为空），默认就是 NotebookLLM
            select.value = "";
        }
    } catch (e) {
        console.error('[GDrive] Folder list failed:', e);
    }
};

/**
 * 上传文件到 Google Drive
 */
window.uploadToGoogleDrive = async (filePath) => {
    try {
        const folderId = document.getElementById('gdrive-folder-select')?.value || '';

        const res = await fetch(`${API_BASE}/google_drive/upload`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ file_path: filePath, folder_id: folderId })
        });

        const data = await res.json();

        if (res.ok && data.success) {
            showNotification(`已上传到 Google Drive`, 3000, 'success');
            return data;
        } else {
            throw new Error(data.detail || data.message || '上传失败');
        }
    } catch (e) {
        showNotification(`上传失败: ${e.message}`, 5000, 'error');
        return { success: false };
    }
};

// ============================================================================
// 初始化
// ============================================================================

// 页面加载时检查 Google Drive 状态并设置监听器
document.addEventListener('DOMContentLoaded', () => {
    // 延迟检查，等待其他初始化完成
    setTimeout(checkGoogleDriveStatus, 1000);

    // 设置页面复选框变化时同步到工具栏按钮
    const autoUploadCheckbox = document.getElementById('gdrive-auto-upload');
    if (autoUploadCheckbox) {
        autoUploadCheckbox.addEventListener('change', () => {
            isAutoUploadEnabled = autoUploadCheckbox.checked;
            // 更新工具栏按钮状态
            const icon = document.getElementById('auto-upload-icon');
            if (icon) {
                if (isAutoUploadEnabled) {
                    icon.classList.add('active');
                    icon.setAttribute('data-tooltip', '自动上传: 已开启');
                } else {
                    icon.classList.remove('active');
                    icon.setAttribute('data-tooltip', '自动上传: 已关闭');
                }
            }
        });
    }
});
