/**
 * model-config.js - AI 模型配置管理
 * 
 * 包含标签切换、内置模型连接测试、配置保存、状态检查等。
 * 依赖: state.js, api.js, custom-provider.js
 */

// ============================================================================
// 标签页切换
// ============================================================================

window.switchTab = (tabName) => {
    document.querySelectorAll('.tab-btn').forEach(b => {
        b.classList.remove('active');
        if (b.getAttribute('onclick').includes(`'${tabName}'`)) {
            b.classList.add('active');
        }
    });
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.getElementById(`tab-${tabName}`).classList.add('active');

    if (tabName === 'models' && window.checkSettingsModelStatus) {
        window.checkSettingsModelStatus();
    }

    if (tabName === 'sync' && window.loadSyncSettings) {
        window.loadSyncSettings();
    }

    // Control footer button visibility
    const saveGeneralBtn = document.getElementById('save-general-btn');
    const saveBetaBtn = document.getElementById('save-beta-btn');
    const saveFormatsBtn = document.getElementById('save-formats-btn');
    const saveGeneralContainer = document.querySelector('.modal-footer');

    if (saveGeneralBtn && saveBetaBtn && saveFormatsBtn) {
        if (tabName === 'general') {
            saveGeneralBtn.classList.remove('hidden');
            saveBetaBtn.classList.add('hidden');
            saveFormatsBtn.classList.add('hidden');
            if (saveGeneralContainer) saveGeneralContainer.style.display = 'flex';
        } else if (tabName === 'beta') {
            saveGeneralBtn.classList.add('hidden');
            saveBetaBtn.classList.remove('hidden');
            saveFormatsBtn.classList.add('hidden');
            if (saveGeneralContainer) saveGeneralContainer.style.display = 'flex';
        } else if (tabName === 'formats') {
            saveGeneralBtn.classList.add('hidden');
            saveBetaBtn.classList.add('hidden');
            saveFormatsBtn.classList.remove('hidden');
            if (saveGeneralContainer) saveGeneralContainer.style.display = 'flex';
            if (window.refreshBookExtensionCounts) window.refreshBookExtensionCounts();
        } else {
            saveGeneralBtn.classList.add('hidden');
            saveBetaBtn.classList.add('hidden');
            saveFormatsBtn.classList.add('hidden');
            if (saveGeneralContainer) saveGeneralContainer.style.display = 'none';
        }
    }
};

window.toggleEdit = (provider) => {
    const body = document.getElementById(`edit-${provider}`);
    body.classList.toggle('hidden');
};

// ============================================================================
// 内置模型管理
// ============================================================================

window.testConnection = async (provider) => {
    let payload = { provider: provider };
    if (provider === 'gemini') {
        payload.api_key = document.getElementById('cfg-gemini-key').value;
    } else if (provider === 'deepseek') {
        payload.api_key = document.getElementById('cfg-deepseek-key').value;
    } else if (provider === 'ollama') {
        payload.url = document.getElementById('cfg-ollama-url').value;
    }

    const savedProviderConfig = window.config?.[provider] || {};
    const hasSavedCredential = Boolean(savedProviderConfig.configured || savedProviderConfig.api_key_masked);
    if (!payload.api_key && !payload.url && !hasSavedCredential) {
        showNotification('请输入 API Key 或 URL', 3000, 'warning');
        return;
    }

    try {
        const res = await fetch(`${API_BASE}/test_connection_v2`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();

        if (data.success) {
            const selectEl = document.getElementById(`cfg-${provider}-model`);
            selectEl.innerHTML = '';
            data.models.forEach(m => {
                const opt = document.createElement('option');
                opt.value = m;
                opt.textContent = m;
                selectEl.appendChild(opt);
            });
            if (data.models.length > 0) selectEl.value = data.models[0];
            showNotification(data.message, 3000, 'success');
        } else {
            showNotification(`连接失败: ${data.message}`, 4000, 'error');
        }
    } catch (e) {
        showNotification(`请求失败: ${e.message}`, 4000, 'error');
    }

    if (window.checkSettingsModelStatus) window.checkSettingsModelStatus();
};

window.saveGeneralConfig = async () => {
    try {
        const resLoad = await fetch(`${API_BASE}/config`);
        const currentConfig = await resLoad.json();

        currentConfig.source_dir = document.getElementById('cfg-source').value;
        currentConfig.target_dir = document.getElementById('cfg-target').value;
        currentConfig.data_dir = document.getElementById('cfg-data-dir').value;

        if (!currentConfig.beta_features) currentConfig.beta_features = {};
        const pdfExportDirEl = document.getElementById('cfg-pdf-export-dir');
        currentConfig.beta_features.pdf_export_dir = pdfExportDirEl ? pdfExportDirEl.value.trim() : '';

        await saveConfigPayload(currentConfig);
        showNotification('通用设置已保存', 2000, 'success');
    } catch (e) {
        showNotification(`保存失败: ${e.message}`, 4000, 'error');
    }
};

window.saveModelConfig = async (provider) => {
    let modelConfig = {};
    if (provider === 'gemini') {
        modelConfig = {
            api_key: document.getElementById('cfg-gemini-key').value,
            model_name: document.getElementById('cfg-gemini-model').value
        };
    } else if (provider === 'deepseek') {
        modelConfig = {
            api_key: document.getElementById('cfg-deepseek-key').value,
            model_name: document.getElementById('cfg-deepseek-model').value
        };
    } else if (provider === 'ollama') {
        modelConfig = {
            url: document.getElementById('cfg-ollama-url').value,
            model_name: document.getElementById('cfg-ollama-model').value
        };
    }

    let payload = {};
    payload[provider] = modelConfig;
    try {
        await saveConfigPayload(payload);
        showNotification(`${provider.toUpperCase()} 配置已保存`, 2000, 'success');
        if (window.initEngineSelection) await window.initEngineSelection();
    } catch (e) {
        showNotification(`保存失败: ${e.message}`, 4000, 'error');
    }

    if (window.checkSettingsModelStatus) window.checkSettingsModelStatus();
};

window.clearModelConfig = async (provider) => {
    let payload = {};
    if (provider === 'ollama') {
        payload[provider] = { url: '', model_name: '' };
    } else {
        payload[provider] = { api_key: '', model_name: '' };
    }

    try {
        await saveConfigPayload(payload);
        showNotification(`${provider.toUpperCase()} 配置已清除`, 2000, 'success');
        if (window.initEngineSelection) await window.initEngineSelection();
    } catch (e) {
        showNotification(`清除失败: ${e.message}`, 4000, 'error');
    }

    document.getElementById(`cfg-${provider}-key`) ? document.getElementById(`cfg-${provider}-key`).value = '' : null;
    document.getElementById(`cfg-${provider}-url`) ? document.getElementById(`cfg-${provider}-url`).value = '' : null;
    const modelSelect = document.getElementById(`cfg-${provider}-model`);
    if (modelSelect) modelSelect.innerHTML = '<option value="">请先验证</option>';
    const statusBadge = document.getElementById(`status-${provider}`);
    if (statusBadge) {
        statusBadge.textContent = '未配置';
        statusBadge.classList.remove('active');
    }

    if (window.checkSettingsModelStatus) window.checkSettingsModelStatus();
};

// ============================================================================
// 模型状态检查
// ============================================================================

window.checkSettingsModelStatus = async () => {
    const settingsModal = document.getElementById('settings-modal');
    const modelsTab = document.getElementById('tab-models');
    if (!settingsModal || settingsModal.classList.contains('hidden') ||
        !modelsTab || !modelsTab.classList.contains('active')) {
        return;
    }

    const builtin = ['gemini', 'deepseek', 'ollama'];

    let custom = [];
    if (window.config && window.config.custom_providers) {
        custom = Object.keys(window.config.custom_providers);
    } else {
        try {
            const res = await fetch(`${API_BASE}/config`);
            const cfg = await res.json();
            if (cfg.custom_providers) custom = Object.keys(cfg.custom_providers);
        } catch (e) { }
    }

    const allProviders = [...builtin, ...custom];

    for (const p of allProviders) {
        const dot = document.getElementById(`status-dot-settings-${p}`);
        if (!dot) continue;

        try {
            const res = await fetch(`${API_BASE}/models/${p}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({})
            });
            const data = await res.json();

            dot.className = 'status-dot';
            if (data.models && data.models.length > 0) {
                dot.classList.add('status-green');
                dot.title = '连接正常';
            } else {
                dot.classList.add('status-red');
                dot.title = data.error || '连接失败';
            }
        } catch (e) {
            dot.className = 'status-dot status-red';
            dot.title = '请求失败';
        }
    }
};

// ============================================================================
// 高级功能配置
// ============================================================================

window.saveBetaConfig = async () => {
    try {
        const resLoad = await fetch(`${API_BASE}/config`);
        const currentConfig = await resLoad.json();

        if (!currentConfig.beta_features) currentConfig.beta_features = {};

        currentConfig.beta_features.enable_similar_search = document.getElementById('beta-similar-search').checked;
        currentConfig.beta_features.enable_metadata_write_epub = document.getElementById('beta-metadata-write-epub').checked;
        currentConfig.beta_features.enable_summary_write_epub = document.getElementById('beta-summary-write-epub').checked;
        currentConfig.beta_features.enable_metadata_write_pdf = document.getElementById('beta-metadata-write-pdf').checked;
        currentConfig.beta_features.enable_summary_write_pdf = document.getElementById('beta-summary-write-pdf').checked;

        if (!currentConfig.beta_features.google_drive) currentConfig.beta_features.google_drive = {};
        const gdriveFolder = document.getElementById('gdrive-folder-select');
        const gdriveAuto = document.getElementById('gdrive-auto-upload');
        currentConfig.beta_features.google_drive.target_folder_id = gdriveFolder ? gdriveFolder.value : '';
        currentConfig.beta_features.google_drive.auto_upload = gdriveAuto ? gdriveAuto.checked : false;

        const activeBtn = document.querySelector('#beta-data-priority-group .btn-toggle.active');
        currentConfig.beta_features.data_priority = activeBtn ? activeBtn.dataset.value : 'database';

        const resSave = await fetch(`${API_BASE}/config`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(currentConfig)
        });

        if (!resSave.ok) throw new Error('保存失败');

        config = currentConfig;
        showNotification('高级设置已保存', 2000, 'success');
    } catch (e) {
        showNotification(`保存失败: ${e.message}`, 4000, 'error');
    }
};

window.setDataPriority = (value) => {
    const group = document.getElementById('beta-data-priority-group');
    if (group) {
        group.querySelectorAll('.btn-toggle').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.value === value);
        });
    }
};
