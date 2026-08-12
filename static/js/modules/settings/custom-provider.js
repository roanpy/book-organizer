/**
 * custom-provider.js - 自定义 AI Provider 管理
 * 
 * 处理自定义 Provider 的添加、编辑、删除和测试。
 * 依赖: state.js, api.js
 */

// ============================================================================
// 自定义 Provider 弹窗控制
// ============================================================================

window.openAddProviderModal = () => {
    document.getElementById('add-provider-modal').classList.remove('hidden');
};

window.closeAddProviderModal = () => {
    document.getElementById('add-provider-modal').classList.add('hidden');
    // Clear form
    document.getElementById('new-provider-name').value = '';
    document.getElementById('new-provider-key').value = '';
    document.getElementById('new-provider-url').value = '';
    document.getElementById('new-provider-model').value = '';
};

// ============================================================================
// 自定义 Provider CRUD 操作
// ============================================================================

window.saveNewProvider = async () => {
    const name = document.getElementById('new-provider-name').value.trim();
    const type = document.getElementById('new-provider-type').value;
    const apiKey = document.getElementById('new-provider-key').value.trim();
    const baseUrl = document.getElementById('new-provider-url').value.trim();
    const modelName = document.getElementById('new-provider-model').value.trim();
    const supportsJsonMode = document.getElementById('new-provider-json-mode').checked;

    if (!name) {
        showNotification('请输入 Provider 名称', 3000, 'warning');
        return;
    }
    if (!modelName) {
        showNotification('请输入 Model 名称', 3000, 'warning');
        return;
    }

    try {
        const res = await fetch(`${API_BASE}/config`);
        const cfg = await res.json();

        if (!cfg.custom_providers) cfg.custom_providers = {};

        // 检查是否与内置 Provider 冲突
        const builtInProviders = ['gemini', 'deepseek', 'ollama'];
        if (builtInProviders.includes(name.toLowerCase())) {
            showNotification(`名称 "${name}" 与内置 Provider 冲突，请使用其他名称`, 4000, 'warning');
            return;
        }
        if (cfg.custom_providers[name]) {
            showNotification(`名称 "${name}" 已存在，请使用其他名称`, 4000, 'warning');
            return;
        }

        cfg.custom_providers[name] = {
            type: type,
            api_key: apiKey,
            base_url: baseUrl,
            model_name: modelName,
            supports_json_mode: supportsJsonMode
        };
        cfg[name] = cfg.custom_providers[name];

        await saveConfigPayload(cfg);
        showNotification(`${name} 已添加`, 2000, 'success');
        closeAddProviderModal();

        renderCustomProviders(cfg.custom_providers);
        if (window.initEngineSelection) await window.initEngineSelection();
    } catch (e) {
        showNotification(`添加失败: ${e.message}`, 4000, 'error');
    }
};

window.deleteCustomProvider = async (name) => {
    if (!confirm(`确定要删除 ${name} 吗？`)) return;

    try {
        const res = await fetch(`${API_BASE}/config`);
        const cfg = await res.json();

        if (cfg.custom_providers && cfg.custom_providers[name]) {
            delete cfg.custom_providers[name];
        }
        if (cfg[name]) {
            delete cfg[name];
        }

        await saveConfigPayload(cfg);
        showNotification(`${name} 已删除`, 2000, 'success');
        renderCustomProviders(cfg.custom_providers || {});

        if (window.initEngineSelection) await window.initEngineSelection();
    } catch (e) {
        showNotification(`删除失败: ${e.message}`, 4000, 'error');
    }
};

window.testCustomProvider = async (name) => {
    showNotification('正在验证连接...', 2000);
    try {
        const res = await fetch(`${API_BASE}/config`);
        const cfg = await res.json();
        const providerCfg = cfg.custom_providers?.[name] || cfg[name];

        if (!providerCfg) {
            showNotification('未找到 Provider 配置', 3000, 'error');
            return;
        }

        const testRes = await fetch(`${API_BASE}/test_custom_provider`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                provider: name,
                model_name: providerCfg.model_name,
                api_key: providerCfg.api_key || providerCfg.api_key_masked,
                base_url: providerCfg.base_url,
                supports_json_mode: providerCfg.supports_json_mode
            })
        });

        const result = await testRes.json();
        if (result.success) {
            showNotification('连接成功！', 3000, 'success');
        } else {
            showNotification(`连接失败: ${result.message}`, 5000, 'error');
        }
    } catch (e) {
        showNotification(`验证失败: ${e.message}`, 4000, 'error');
    }
};

window.saveCustomProvider = async (originalName) => {
    try {
        const res = await fetch(`${API_BASE}/config`);
        const cfg = await res.json();

        if (!cfg.custom_providers) cfg.custom_providers = {};

        const newName = document.getElementById(`cfg-custom-${originalName}-name`).value.trim();
        const type = document.getElementById(`cfg-custom-${originalName}-type`).value;
        const modelName = document.getElementById(`cfg-custom-${originalName}-model`).value.trim();
        const apiKey = document.getElementById(`cfg-custom-${originalName}-key`).value.trim();
        const baseUrl = document.getElementById(`cfg-custom-${originalName}-url`).value.trim();
        const supportsJson = document.getElementById(`cfg-custom-${originalName}-json`).checked;

        if (!newName) {
            showNotification('请输入 Provider 名称', 3000, 'warning');
            return;
        }
        if (!modelName) {
            showNotification('请输入 Model 名称', 3000, 'warning');
            return;
        }

        if (newName !== originalName) {
            const builtInProviders = ['gemini', 'deepseek', 'ollama'];
            if (builtInProviders.includes(newName.toLowerCase())) {
                showNotification(`名称 "${newName}" 与内置 Provider 冲突`, 4000, 'warning');
                return;
            }
            if (cfg.custom_providers[newName]) {
                showNotification(`名称 "${newName}" 已存在`, 4000, 'warning');
                return;
            }
            delete cfg.custom_providers[originalName];
            delete cfg[originalName];
        }

        cfg.custom_providers[newName] = {
            type: type,
            model_name: modelName,
            api_key: apiKey,
            base_url: baseUrl,
            supports_json_mode: supportsJson
        };
        cfg[newName] = cfg.custom_providers[newName];

        await saveConfigPayload(cfg);
        showNotification(`${newName} 配置已保存`, 2000, 'success');

        renderCustomProviders(cfg.custom_providers);
        if (document.getElementById('tab-models').classList.contains('active')) {
            window.checkSettingsModelStatus();
        }
        if (window.initEngineSelection) await window.initEngineSelection();
    } catch (e) {
        showNotification(`保存失败: ${e.message}`, 4000, 'error');
    }
};

window.loadCustomProviders = async () => {
    try {
        const res = await fetch(`${API_BASE}/config`);
        const cfg = await res.json();
        renderCustomProviders(cfg.custom_providers || {});
    } catch (e) {
        console.error('Failed to load custom providers:', e);
    }
};

// ============================================================================
// 自定义 Provider 列表渲染
// ============================================================================

function renderCustomProviders(providers) {
    const container = document.getElementById('custom-providers-container');
    if (!container) return;

    container.innerHTML = '';

    Object.entries(providers || {}).forEach(([name, cfg]) => {
        const jsonModeStatus = cfg.supports_json_mode !== false;
        const card = document.createElement('div');
        card.className = 'model-card';
        card.id = `card-custom-${escapeHtml(name)}`;
        card.innerHTML = `
            <div class="card-header">
                <h4><i class="fa-solid fa-plug"></i> ${escapeHtml(name)}
                    <span id="status-dot-settings-${escapeHtml(name)}" class="status-dot" title="未检查" style="width:8px;height:8px;margin-left:8px;display:inline-block;"></span>
                </h4>
                <span class="status-badge active">${escapeHtml(cfg.type)}</span>
            </div>
            <div class="card-body hidden" id="edit-custom-${escapeHtml(name)}">
                <div class="form-group">
                    <label>Provider 名称 <span class="text-muted">(唯一标识)</span></label>
                    <input type="text" id="cfg-custom-${escapeHtml(name)}-name" value="${escapeHtml(name)}">
                </div>
                <div class="form-group">
                    <label>Provider 类型</label>
                    <select id="cfg-custom-${escapeHtml(name)}-type">
                        <option value="openrouter" ${cfg.type === 'openrouter' ? 'selected' : ''}>OpenRouter</option>
                        <option value="azure" ${cfg.type === 'azure' ? 'selected' : ''}>Azure</option>
                        <option value="anthropic" ${cfg.type === 'anthropic' ? 'selected' : ''}>Anthropic</option>
                        <option value="volcengine" ${cfg.type === 'volcengine' ? 'selected' : ''}>火山引擎</option>
                        <option value="custom" ${cfg.type === 'custom' ? 'selected' : ''}>自定义</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Model 名称</label>
                    <input type="text" id="cfg-custom-${escapeHtml(name)}-model" value="${escapeHtml(cfg.model_name || '')}">
                </div>
                <div class="form-group">
                    <label>API Key</label>
                    <input type="password" id="cfg-custom-${escapeHtml(name)}-key" value="${escapeHtml(cfg.api_key || cfg.api_key_masked || '')}" placeholder="API Key">
                </div>
                <div class="form-group">
                    <label>Base URL <span class="text-muted">(可选)</span></label>
                    <input type="text" id="cfg-custom-${escapeHtml(name)}-url" value="${escapeHtml(cfg.base_url || '')}" placeholder="例如: https://api.openrouter.ai/v1">
                </div>
                <div class="form-group">
                    <label class="checkbox-label">
                        <input type="checkbox" id="cfg-custom-${escapeHtml(name)}-json" ${jsonModeStatus ? 'checked' : ''}>
                        <span>支持 JSON 模式</span>
                    </label>
                </div>
                <div class="card-actions">
                    <button class="btn-secondary btn-sm" onclick="testCustomProvider('${name.replace(/'/g, "\\'")}')">验证连接</button>
                    <button class="btn-primary btn-sm" onclick="saveCustomProvider('${name.replace(/'/g, "\\'")}')">保存</button>
                    <button class="btn-danger btn-sm" onclick="deleteCustomProvider('${name.replace(/'/g, "\\'")}')">删除</button>
                </div>
            </div>
            <div class="card-footer">
                <span class="text-muted text-sm">JSON模式: ${jsonModeStatus ? '✓' : '✗'}</span>
                <button class="btn-text" onclick="toggleEdit('custom-${escapeHtml(name)}')">配置 / 修改</button>
            </div>
        `;
        container.appendChild(card);
    });
}

// 暴露给全局
window.renderCustomProviders = renderCustomProviders;
