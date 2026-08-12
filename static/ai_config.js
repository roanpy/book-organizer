// ===== AI 配置管理模块 =====

let aiConfig = null;

// 加载 AI 配置
async function loadAIConfig() {
    try {
        const res = await fetch(`${window.API_BASE || '/api'}/ai_config`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        aiConfig = await res.json();
        window.aiConfig = aiConfig; // 暴露到全局供 app.js 使用
        updateAIStatusIndicators();
        return aiConfig;
    } catch (e) {
        console.error('Failed to load AI config', e);
        // showNotification('加载配置失败: ' + e.message); // Optional: notify user
        return null;
    }
}

// 实时更新增强规则指示器 (从 app.js 的开关调用)
function updateEnhancedRulesIndicator() {
    const tabEnhanced = document.getElementById('tab-status-enhanced');
    const headerEnhanced = document.getElementById('ai-status-enhanced');
    const isEnhanced = window.isEnhancedModeEnabled;

    if (tabEnhanced) {
        tabEnhanced.classList.toggle('active', isEnhanced);
    }
    if (headerEnhanced) {
        headerEnhanced.classList.toggle('active', isEnhanced);
    }
}

// 暴露到全局供 app.js 同步调用
window.updateEnhancedRulesIndicator = updateEnhancedRulesIndicator;

// 更新状态指示器
async function updateAIStatusIndicators() {
    if (!aiConfig) return;

    // 顶部按钮指示器
    const coreStatus = document.getElementById('ai-status-core');
    const additionalStatus = document.getElementById('ai-status-additional');
    const historicalStatus = document.getElementById('ai-status-historical');

    // 核心规则始终激活
    coreStatus.classList.add('active');

    // 更新附加规则状态
    if (aiConfig.additional_rules.enabled) {
        additionalStatus.classList.add('active');
    } else {
        additionalStatus.classList.remove('active');
    }

    // 更新历史参考状态
    if (aiConfig.historical_reference.enabled) {
        historicalStatus.classList.add('active');
    } else {
        historicalStatus.classList.remove('active');
    }

    // 标签页指示器
    const tabEnhanced = document.getElementById('tab-status-enhanced');
    const headerEnhanced = document.getElementById('ai-status-enhanced');

    // 从后端 API 检查增强模式是否启用
    let isEnhanced = false;
    try {
        const res = await fetch(`${window.API_BASE || '/api'}/user_preferences`);
        const prefs = await res.json();
        isEnhanced = prefs.enhancedModeEnabled;
    } catch (e) {
        console.error('Failed to load enhanced mode status:', e);
    }

    if (isEnhanced) {
        tabEnhanced.classList.add('active');
        if (headerEnhanced) headerEnhanced.classList.add('active');
    } else {
        tabEnhanced.classList.remove('active');
        if (headerEnhanced) headerEnhanced.classList.remove('active');
    }

    const tabAdditional = document.getElementById('tab-status-additional');
    const tabHistorical = document.getElementById('tab-status-historical');

    if (aiConfig.additional_rules.enabled) {
        tabAdditional.classList.add('active');
    } else {
        tabAdditional.classList.remove('active');
    }

    if (aiConfig.historical_reference.enabled) {
        tabHistorical.classList.add('active');
    } else {
        tabHistorical.classList.remove('active');
    }

    // 字段提取标签页指示器（配置存在时始终激活）
    const tabExtraction = document.getElementById('tab-status-extraction');
    const headerExtraction = document.getElementById('ai-status-extraction');
    if (aiConfig.field_extraction_rules) {
        tabExtraction.classList.add('active');
        headerExtraction.classList.add('active');
    } else {
        tabExtraction.classList.remove('active');
        headerExtraction.classList.remove('active');
    }

    // 内容与搜索控制标签页指示器（基于启用标志）
    const tabContentSearch = document.getElementById('tab-status-content-search');
    const headerContentSearch = document.getElementById('ai-status-content-search');
    if (aiConfig.content_and_search_control?.enabled) {
        tabContentSearch.classList.add('active');
        headerContentSearch.classList.add('active');
    } else {
        tabContentSearch.classList.remove('active');
        headerContentSearch.classList.remove('active');
    }

    // 目录规则标签页指示器（任一模式启用时激活）
    const tabTocRules = document.getElementById('tab-status-toc-rules');
    const headerTocRules = document.getElementById('ai-status-toc-rules');
    const tocRules = aiConfig.toc_rules || {};
    const organizeEnabled = tocRules.organize_existing?.enabled;
    const extractEnabled = tocRules.extract_from_content?.enabled;

    if (organizeEnabled || extractEnabled) {
        if (tabTocRules) tabTocRules.classList.add('active');
        if (headerTocRules) headerTocRules.classList.add('active');
    } else {
        if (tabTocRules) tabTocRules.classList.remove('active');
        if (headerTocRules) headerTocRules.classList.remove('active');
    }

    // 更新 AI 配置按钮的悬浮提示（显示已启用功能列表）
    updateAIConfigTooltip(isEnhanced, aiConfig);
}

/**
 * 更新 AI 配置按钮的悬浮提示，显示已开启的功能列表
 */
function updateAIConfigTooltip(isEnhanced, config) {
    const aiConfigBtn = document.getElementById('ai-config-btn');
    if (!aiConfigBtn) return;

    // 添加 has-tooltip class
    aiConfigBtn.classList.add('has-tooltip');

    // 收集所有功能状态
    const features = [
        { name: '核心规则', enabled: true },
        { name: '增强模式', enabled: isEnhanced },
        { name: '附加规则', enabled: config?.additional_rules?.enabled },
        { name: '历史参考', enabled: config?.historical_reference?.enabled },
        { name: '字段提取', enabled: !!config?.field_extraction_rules },
        { name: '内容与搜索', enabled: config?.content_and_search_control?.enabled },
    ];

    // 目录规则
    const tocRules = config?.toc_rules || {};
    const tocEnabled = tocRules.organize_existing?.enabled || tocRules.extract_from_content?.enabled;
    features.push({ name: '目录规则', enabled: tocEnabled });

    // 生成 tooltip 内容 - 蓝色高亮已开启，灰色显示尚未开启
    const enabledList = features
        .map(f => {
            if (f.enabled) {
                return `<span style="color: #3b82f6;">✓ ${f.name}: 已开启</span>`;
            } else {
                return `<span style="color: #6b7280;">${f.name}: 尚未开启</span>`;
            }
        })
        .join('<br>');

    const tooltipContent = `<strong style="color: #e5e7eb;">AI 配置状态</strong><br>${enabledList}`;
    aiConfigBtn.setAttribute('data-tooltip', tooltipContent);
}
window.updateAIStatusIndicators = updateAIStatusIndicators;

// 切换 AI 配置标签页
window.switchAITab = (tabName) => {
    // 更新标签页按钮
    const modal = document.getElementById('ai-config-modal');
    // 使用稳定的 data-tab 选择器
    const tabs = modal.querySelectorAll('.tab-btn');
    const contents = modal.querySelectorAll('.tab-content');

    tabs.forEach(tab => {
        tab.classList.remove('active');
        if (tab.dataset.tab === tabName) {
            tab.classList.add('active');
        }
    });

    contents.forEach(content => {
        content.classList.remove('active');
    });

    const selectedContent = document.getElementById(`ai-tab-${tabName}`);
    if (selectedContent) {
        selectedContent.classList.add('active');
    }
};

// 打开 AI 配置弹窗
window.openAIConfig = async () => {
    const modal = document.getElementById('ai-config-modal');
    modal.classList.remove('hidden');

    await loadAIConfig();
    populateAIConfigUI();

    // 默认选中核心规则标签页
    switchAITab('core');
};

// 填充 AI 配置 UI
function populateAIConfigUI() {
    if (!aiConfig) return;

    // 核心规则
    document.getElementById('core-rules-content').value = aiConfig.core_rules.content;

    // 增强规则
    const enhanced = aiConfig.enhanced_rules || {};
    document.getElementById('enhanced-summary-prompt').value = enhanced.summary_prompt || "图书简介: 对书籍核心内容和主题的概述（200字左右）。";
    document.getElementById('enhanced-details-prompt').value = enhanced.details_prompt || "详细要点: 列出书中的关键论点、概念或章节精华。请务必使用数字列表格式，并对每个要点的核心词进行加粗。格式示例：1. **核心观点**: 详细解释...";
    document.getElementById('enhanced-applications-prompt').value = enhanced.applications_prompt || "具体应用: 说明书中的知识或方法如何在实际工作或生活中应用。请务必使用数字列表格式，并对每个场景进行加粗。格式示例：1. **工作应用**: 详细说明...";

    // 附加规则
    document.getElementById('additional-rules-enabled').checked = aiConfig.additional_rules.enabled;
    // 从配置读取 AI 规则数量（默认 7）
    document.getElementById('ai-rules-count').value = aiConfig.additional_rules.ai_rules_count || 7;
    renderAdditionalRules();
    updateSourceToggleLabels();

    // 历史数据参考
    document.getElementById('historical-enabled').checked = aiConfig.historical_reference.enabled;
    document.getElementById('days-range').value = aiConfig.historical_reference.days_range;
    updateDaysDisplay();

    // 字段提取规则
    const rules = aiConfig.field_extraction_rules || {};
    document.getElementById('prompt-title').value = rules.title_prompt || "请提取完整书名，包含副标题（如有）。";
    document.getElementById('prompt-author').value = rules.author_prompt || "请提取作者名，如果有多个作者请用逗号分隔。";
    document.getElementById('prompt-publisher').value = rules.publisher_prompt || "请提取出版社名称。";
    document.getElementById('prompt-tags').value = rules.tags_prompt || "请提取3-5个最相关的标签，用逗号分隔。";
    document.getElementById('prompt-series').value = rules.series_prompt || "如果这本书属于某个系列，请提取系列名称，否则留空。";
    document.getElementById('prompt-filename').value = rules.filename_prompt || "{title} - [{country}] {author}";

    // 内容与搜索控制
    const ctrl = aiConfig.content_and_search_control || {};
    document.getElementById('ctrl-enabled').checked = ctrl.enabled !== false;
    document.getElementById('ctrl-summary-max-chars').value = ctrl.summary_max_chars || 100;
    document.getElementById('ctrl-pdf-max-pages').value = ctrl.pdf_max_pages || 10;
    document.getElementById('ctrl-epub-max-chapters').value = ctrl.epub_max_chapters || 10;
    document.getElementById('ctrl-raw-scan-limit').value = ctrl.raw_scan_char_limit || 3000;
    document.getElementById('ctrl-standard-chars').value = ctrl.standard_mode_chars || 1500;
    document.getElementById('ctrl-search-chars').value = ctrl.search_mode_chars || 800;
    document.getElementById('ctrl-adaptive-extraction').checked = ctrl.adaptive_extraction !== false;
    document.getElementById('ctrl-head-chars').value = ctrl.head_chars || 500;
    document.getElementById('ctrl-search-count').value = ctrl.search_result_count || 3;

    updateSearchCountDisplay();
    updateTailCharsDisplay();

    // 目录规则
    const tocRules = aiConfig.toc_rules || {};
    const organizeExisting = tocRules.organize_existing || {};
    const extractFromContent = tocRules.extract_from_content || {};

    document.getElementById('toc-organize-enabled').checked = organizeExisting.enabled !== false;
    document.getElementById('toc-organize-prompt').value = organizeExisting.prompt || '';
    document.getElementById('toc-extract-enabled').checked = extractFromContent.enabled === true;
    document.getElementById('toc-extract-pages').value = extractFromContent.pages || 10;
    document.getElementById('toc-extract-prompt').value = extractFromContent.prompt || '';
}

// 渲染附加规则列表（按来源筛选）
function renderAdditionalRules() {
    const listEl = document.getElementById('additional-rules-list');
    const allRules = aiConfig.additional_rules.rules || [];

    // 按当前来源选择筛选规则
    const rules = allRules.filter(r => {
        const source = r.source || 'manual';
        return source === currentRuleSource;
    });

    // 获取原始索引以确保开关/删除操作正确
    const ruleIndices = allRules.map((r, i) => ({ rule: r, originalIndex: i }))
        .filter(item => (item.rule.source || 'manual') === currentRuleSource);

    if (rules.length === 0) {
        const sourceLabel = currentRuleSource === 'ai' ? 'AI生成' : '手工生成';
        listEl.innerHTML = `
            <div class="rules-list-empty">
                <i class="fa-solid fa-inbox"></i>
                <p>暂无${sourceLabel}规则</p>
            </div>
        `;
        return;
    }

    listEl.innerHTML = '';
    ruleIndices.forEach(({ rule, originalIndex }, displayIndex) => {
        const source = rule.source || 'manual';
        const sourceLabel = source === 'ai' ? 'AI生成' : '手工生成';
        const sourceBadgeClass = source === 'ai' ? 'ai' : 'manual';
        const titleColorClass = source === 'ai' ? 'source-ai' : 'source-manual';

        const ruleDiv = document.createElement('div');
        ruleDiv.className = `rule-item ${!rule.enabled ? 'disabled' : ''}`;
        ruleDiv.innerHTML = `
            <div class="rule-item-header">
                <span class="rule-item-title ${titleColorClass}">
                    规则 ${displayIndex + 1}
                    <span class="rule-source-badge ${sourceBadgeClass}">${sourceLabel}</span>
                </span>
                <div class="rule-item-controls">
                    <label class="toggle-switch">
                        <input type="checkbox" ${rule.enabled ? 'checked' : ''} 
                               onchange="toggleRule(${originalIndex})">
                        <span class="slider"></span>
                    </label>
                    <button class="btn-danger btn-sm" onclick="deleteRule(${originalIndex})">
                        <i class="fa-solid fa-trash"></i>
                    </button>
                </div>
            </div>
            <div class="rule-item-content">
                <textarea onchange="updateRuleContent(${originalIndex}, this.value)">${rule.content}</textarea>
            </div>
            <div class="rule-item-meta">
                创建于: ${new Date(rule.created_at).toLocaleString('zh-CN')}
            </div>
        `;
        listEl.appendChild(ruleDiv);
    });
}

// 当前规则来源（手工或 AI）
let currentRuleSource = 'manual';

// 按来源获取规则数量
function getRuleCounts() {
    const rules = aiConfig?.additional_rules?.rules || [];
    const aiCount = rules.filter(r => r.source === 'ai').length;
    const manualCount = rules.filter(r => r.source !== 'ai').length;
    return { ai: aiCount, manual: manualCount };
}

// 更新来源切换按钮标签（显示数量）
function updateSourceToggleLabels() {
    const counts = getRuleCounts();
    const manualBtn = document.getElementById('source-manual');
    const aiBtn = document.getElementById('source-ai');
    if (manualBtn) manualBtn.innerHTML = `<i class="fa-solid fa-hand"></i> 手工 (${counts.manual})`;
    if (aiBtn) aiBtn.innerHTML = `<i class="fa-solid fa-robot"></i> AI (${counts.ai})`;
}

// 设置规则来源
window.setRuleSource = (source) => {
    currentRuleSource = source;
    const manualBtn = document.getElementById('source-manual');
    const aiBtn = document.getElementById('source-ai');
    if (manualBtn) manualBtn.classList.toggle('active', source === 'manual');
    if (aiBtn) aiBtn.classList.toggle('active', source === 'ai');
    // 更新标签显示数量
    updateSourceToggleLabels();
    // 重新渲染筛选后的规则列表
    renderAdditionalRules();
};

// 添加附加规则
window.addAdditionalRule = () => {
    if (!aiConfig.additional_rules.rules) {
        aiConfig.additional_rules.rules = [];
    }

    // 规则数量不再限制 - AI 和手工独立管理

    const newRule = {
        id: `rule_${Date.now()}`,
        content: '在此输入新的规则内容...',
        enabled: true,
        source: currentRuleSource,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
    };

    aiConfig.additional_rules.rules.push(newRule);
    renderAdditionalRules();
    updateSourceToggleLabels();
};

// 切换规则状态
window.toggleRule = (index) => {
    aiConfig.additional_rules.rules[index].enabled = !aiConfig.additional_rules.rules[index].enabled;
    aiConfig.additional_rules.rules[index].updated_at = new Date().toISOString();
    renderAdditionalRules();
};

// 更新规则内容
window.updateRuleContent = (index, content) => {
    aiConfig.additional_rules.rules[index].content = content;
    aiConfig.additional_rules.rules[index].updated_at = new Date().toISOString();
};

// 删除规则
window.deleteRule = (index) => {
    if (confirm('确定要删除这条规则吗？')) {
        aiConfig.additional_rules.rules.splice(index, 1);
        renderAdditionalRules();
        updateSourceToggleLabels();
    }
};

// 保存核心规则
window.saveCoreRules = async () => {
    aiConfig.core_rules.content = document.getElementById('core-rules-content').value;
    await saveAIConfig();
};

// 重置核心规则
window.resetCoreRules = async () => {
    // Removed confirmation - proceed directly
    try {
        // Fetch default config from server
        const res = await fetch(`${API_BASE}/ai_config/default`);
        if (!res.ok) throw new Error('获取默认配置失败');

        const defaultConfig = await res.json();
        aiConfig.core_rules.content = defaultConfig.core_rules.content;
        document.getElementById('core-rules-content').value = aiConfig.core_rules.content;
        await saveAIConfig();
        showNotification('核心规则已恢复为默认值');
    } catch (e) {
        showNotification('恢复默认规则失败: ' + e.message);
    }
};

// 保存增强规则
window.saveEnhancedRules = async () => {
    if (!aiConfig.enhanced_rules) aiConfig.enhanced_rules = {};

    aiConfig.enhanced_rules.summary_prompt = document.getElementById('enhanced-summary-prompt').value;
    aiConfig.enhanced_rules.details_prompt = document.getElementById('enhanced-details-prompt').value;
    aiConfig.enhanced_rules.applications_prompt = document.getElementById('enhanced-applications-prompt').value;

    await saveAIConfig();
};

// 重置增强规则
window.resetEnhancedRules = async () => {
    try {
        const res = await fetch(`${API_BASE}/ai_config/default`);
        if (!res.ok) throw new Error('获取默认配置失败');

        const defaultConfig = await res.json();
        const defaultRules = defaultConfig.enhanced_rules || {};

        document.getElementById('enhanced-summary-prompt').value = defaultRules.summary_prompt || '';
        document.getElementById('enhanced-details-prompt').value = defaultRules.details_prompt || '';
        document.getElementById('enhanced-applications-prompt').value = defaultRules.applications_prompt || '';

        aiConfig.enhanced_rules = { ...defaultRules };

        await saveAIConfig();
        showNotification('增强规则已恢复为默认值');
    } catch (e) {
        showNotification('恢复默认规则失败: ' + e.message);
    }
};

// 保存附加规则
window.saveAdditionalRules = async () => {
    aiConfig.additional_rules.enabled = document.getElementById('additional-rules-enabled').checked;
    aiConfig.additional_rules.ai_rules_count = parseInt(document.getElementById('ai-rules-count').value) || 7;
    await saveAIConfig();
};

// 保存历史数据设置
window.saveHistoricalSettings = async () => {
    aiConfig.historical_reference.enabled = document.getElementById('historical-enabled').checked;
    aiConfig.historical_reference.days_range = parseInt(document.getElementById('days-range').value);
    aiConfig.historical_reference.days_range = parseInt(document.getElementById('days-range').value);
    await saveAIConfig();
};

// 保存字段提取规则
window.saveExtractionRules = async () => {
    if (!aiConfig.field_extraction_rules) aiConfig.field_extraction_rules = {};

    aiConfig.field_extraction_rules.title_prompt = document.getElementById('prompt-title').value;
    aiConfig.field_extraction_rules.author_prompt = document.getElementById('prompt-author').value;
    aiConfig.field_extraction_rules.publisher_prompt = document.getElementById('prompt-publisher').value;
    aiConfig.field_extraction_rules.tags_prompt = document.getElementById('prompt-tags').value;
    aiConfig.field_extraction_rules.series_prompt = document.getElementById('prompt-series').value;
    aiConfig.field_extraction_rules.filename_prompt = document.getElementById('prompt-filename').value;

    await saveAIConfig();
};

// 重置字段提取规则
window.resetExtractionRules = async () => {
    try {
        // Fetch default config from server
        const res = await fetch(`${API_BASE}/ai_config/default`);
        if (!res.ok) throw new Error('获取默认配置失败');

        const defaultConfig = await res.json();
        const defaultRules = defaultConfig.field_extraction_rules || {};

        // 用默认值更新字段
        document.getElementById('prompt-title').value = defaultRules.title_prompt || '';
        document.getElementById('prompt-author').value = defaultRules.author_prompt || '';
        document.getElementById('prompt-publisher').value = defaultRules.publisher_prompt || '';
        document.getElementById('prompt-tags').value = defaultRules.tags_prompt || '';
        document.getElementById('prompt-series').value = defaultRules.series_prompt || '';
        document.getElementById('prompt-filename').value = defaultRules.filename_prompt || '';

        // 更新本地配置
        aiConfig.field_extraction_rules = { ...defaultRules };

        await saveAIConfig();
        showNotification('字段提取规则已恢复为默认值');
    } catch (e) {
        showNotification('恢复默认规则失败: ' + e.message);
    }
};

// 保存 AI 配置
async function saveAIConfig() {
    try {
        const apiBase = window.API_BASE || '/api';
        const res = await fetch(`${apiBase}/ai_config`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(aiConfig)
        });

        if (!res.ok) throw new Error('保存失败');

        await loadAIConfig();
        showNotification('AI配置已保存');
    } catch (e) {
        showNotification(`保存失败: ${e.message}`);
    }
}

// 更新天数显示
window.updateDaysDisplay = () => {
    const value = document.getElementById('days-range').value;
    document.getElementById('days-display').textContent = `${value} 天`;
    document.getElementById('days-text').textContent = value;
};

// 打开核心规则参考
window.openCoreRulesRef = () => {
    const content = aiConfig.core_rules.content;
    const modal = `
        <div style="position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.8);z-index:2000;display:flex;align-items:center;justify-content:center;" onclick="this.remove()">
            <div style="background:#1e293b;padding:20px;border-radius:12px;max-width:600px;max-height:80vh;overflow:auto;" onclick="event.stopPropagation()">
                <h3 style="margin-bottom:16px;">核心规则参考</h3>
                <pre style="white-space:pre-wrap;color:#e2e8f0;font-size:0.9rem;line-height:1.6;">${content}</pre>
                <button onclick="this.closest('div[style*=fixed]').remove()" style="margin-top:16px;padding:8px 16px;background:#3b82f6;color:white;border:none;border-radius:8px;cursor:pointer;">关闭</button>
            </div>
        </div>
    `;
    document.body.insertAdjacentHTML('beforeend', modal);
};

// AI 优化规则（带防抖保护）
let _isOptimizing = false;
window.optimizeRulesWithAI = async () => {
    // 防抖：避免短时间内多次触发
    if (_isOptimizing) {
        console.log('AI优化正在进行中，跳过重复调用');
        return;
    }

    const engineSelect = document.getElementById('engine-select');
    const engine = engineSelect.value;

    if (!engine) {
        showNotification('请先在分析页面选择一个AI引擎');
        return;
    }

    if (!aiConfig) {
        // 尝试重新加载
        await loadAIConfig();
        if (!aiConfig) {
            showNotification('配置加载失败，无法进行优化');
            return;
        }
    }

    // 延迟一帧再显示确认框，避免点击事件干扰
    await new Promise(resolve => setTimeout(resolve, 50));

    if (!confirm('将使用AI分析历史转移记录来优化附加规则。是否继续？')) {
        return;
    }

    _isOptimizing = true;

    // 显示加载通知
    showNotification('正在AI优化规则，请稍候...', 0); // duration 0 = persistent

    try {
        const existingRules = aiConfig.additional_rules.rules || [];
        // Get AI rules count from input field
        const ruleCount = parseInt(document.getElementById('ai-rules-count').value) || 7;

        const res = await fetch(`${API_BASE}/ai_config/optimize_rules`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                engine: engine,
                existing_rules: existingRules,
                rule_count: ruleCount
            })
        });

        if (!res.ok) throw new Error('优化失败');

        const data = await res.json();

        if (data.success && data.optimized_rules && data.optimized_rules.length > 0) {
            // 从输入框直接获取 AI 规则数量（而非从已保存的配置）
            const aiRulesCount = parseInt(document.getElementById('ai-rules-count').value) || 7;
            // 添加新 AI 生成的规则（保留现有手工规则）
            const existingManualRules = (aiConfig.additional_rules.rules || []).filter(r => r.source !== 'ai');
            const newAIRules = data.optimized_rules.slice(0, aiRulesCount).map((content, i) => ({
                id: `rule_${Date.now()}_${i}`,
                content: content,
                enabled: true,
                source: 'ai',
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString()
            }));
            aiConfig.additional_rules.rules = [...existingManualRules, ...newAIRules];

            renderAdditionalRules();
            updateSourceToggleLabels();
            showNotification(`成功生成 ${newAIRules.length} 条AI规则`);
        } else {
            showNotification('未能生成优化规则');
        }
    } catch (e) {
        showNotification(`AI 优化失败: ${e.message}`);
    } finally {
        _isOptimizing = false;
    }
};

// 保存内容与搜索控制设置
window.saveContentSearchControl = async () => {
    if (!aiConfig.content_and_search_control) aiConfig.content_and_search_control = {};

    aiConfig.content_and_search_control.enabled = document.getElementById('ctrl-enabled').checked;
    aiConfig.content_and_search_control.summary_max_chars = parseInt(document.getElementById('ctrl-summary-max-chars').value) || 100;
    aiConfig.content_and_search_control.pdf_max_pages = parseInt(document.getElementById('ctrl-pdf-max-pages').value) || 10;
    aiConfig.content_and_search_control.epub_max_chapters = parseInt(document.getElementById('ctrl-epub-max-chapters').value) || 10;
    aiConfig.content_and_search_control.raw_scan_char_limit = parseInt(document.getElementById('ctrl-raw-scan-limit').value) || 3000;
    aiConfig.content_and_search_control.standard_mode_chars = parseInt(document.getElementById('ctrl-standard-chars').value) || 1500;
    aiConfig.content_and_search_control.search_mode_chars = parseInt(document.getElementById('ctrl-search-chars').value) || 800;
    aiConfig.content_and_search_control.adaptive_extraction = document.getElementById('ctrl-adaptive-extraction').checked;
    aiConfig.content_and_search_control.head_chars = parseInt(document.getElementById('ctrl-head-chars').value) || 500;

    // 自动计算并保存 tail_chars (基于标准模式，仅作参考)
    const standardChars = aiConfig.content_and_search_control.standard_mode_chars;
    const headChars = aiConfig.content_and_search_control.head_chars;
    aiConfig.content_and_search_control.tail_chars = Math.max(0, standardChars - headChars);

    aiConfig.content_and_search_control.search_result_count = parseInt(document.getElementById('ctrl-search-count').value) || 3;

    await saveAIConfig();
};

// 重置内容与搜索控制为默认值
window.resetContentSearchControl = async () => {
    // Removed confirmation - proceed directly
    try {
        const res = await fetch(`${API_BASE}/ai_config/default`);
        if (!res.ok) throw new Error('获取默认配置失败');

        const defaultConfig = await res.json();
        aiConfig.content_and_search_control = defaultConfig.content_and_search_control;

        // 更新界面
        const ctrl = aiConfig.content_and_search_control || {};
        document.getElementById('ctrl-enabled').checked = ctrl.enabled !== false;
        document.getElementById('ctrl-summary-max-chars').value = ctrl.summary_max_chars || 100;
        document.getElementById('ctrl-pdf-max-pages').value = ctrl.pdf_max_pages || 10;
        document.getElementById('ctrl-epub-max-chapters').value = ctrl.epub_max_chapters || 10;
        document.getElementById('ctrl-raw-scan-limit').value = ctrl.raw_scan_char_limit || 3000;
        document.getElementById('ctrl-standard-chars').value = ctrl.standard_mode_chars || 1500;
        document.getElementById('ctrl-search-chars').value = ctrl.search_mode_chars || 800;
        document.getElementById('ctrl-adaptive-extraction').checked = ctrl.adaptive_extraction !== false;
        document.getElementById('ctrl-head-chars').value = ctrl.head_chars || 500;
        document.getElementById('ctrl-search-count').value = ctrl.search_result_count || 3;

        updateSearchCountDisplay();
        updateTailCharsDisplay();

        await saveAIConfig();
        showNotification('内容与搜索控制设置已恢复为默认值');
    } catch (e) {
        showNotification('恢复默认设置失败: ' + e.message);
    }
};

// 更新搜索数量显示
window.updateSearchCountDisplay = () => {
    const value = document.getElementById('ctrl-search-count').value;
    document.getElementById('search-count-display').textContent = `${value} 条`;
};

// 更新尾部字数显示
window.updateTailCharsDisplay = () => {
    const headChars = parseInt(document.getElementById('ctrl-head-chars').value) || 0;
    const standardChars = parseInt(document.getElementById('ctrl-standard-chars').value) || 0;
    const searchChars = parseInt(document.getElementById('ctrl-search-chars').value) || 0;

    // 计算尾部字数
    const standardTail = Math.max(0, standardChars - headChars);
    const searchTail = Math.max(0, searchChars - headChars);

    // 更新显示
    document.getElementById('tail-standard-display').textContent = `${standardTail} 字符`;
    document.getElementById('tail-search-display').textContent = `${searchTail} 字符`;
};

// ===== 目录规则函数 =====

// 保存目录规则
window.saveTocRules = async () => {
    if (!aiConfig) aiConfig = {};
    if (!aiConfig.toc_rules) aiConfig.toc_rules = {};

    aiConfig.toc_rules.organize_existing = {
        enabled: document.getElementById('toc-organize-enabled').checked,
        prompt: document.getElementById('toc-organize-prompt').value
    };

    aiConfig.toc_rules.extract_from_content = {
        enabled: document.getElementById('toc-extract-enabled').checked,
        pages: parseInt(document.getElementById('toc-extract-pages').value) || 10,
        prompt: document.getElementById('toc-extract-prompt').value
    };

    await saveAIConfig();
    showNotification('目录规则已保存');
};

// 重置目录规则
window.resetTocRules = async () => {
    try {
        const res = await fetch(`${window.API_BASE || '/api'}/ai_config/default`);
        const defaultConfig = await res.json();
        const defaultRules = defaultConfig.toc_rules || {};
        const organizeExisting = defaultRules.organize_existing || {};
        const extractFromContent = defaultRules.extract_from_content || {};

        document.getElementById('toc-organize-enabled').checked = organizeExisting.enabled !== false;
        document.getElementById('toc-organize-prompt').value = organizeExisting.prompt || '';
        document.getElementById('toc-extract-enabled').checked = extractFromContent.enabled === true;
        document.getElementById('toc-extract-pages').value = extractFromContent.pages || 10;
        document.getElementById('toc-extract-prompt').value = extractFromContent.prompt || '';

        aiConfig.toc_rules = { ...defaultRules };
        await saveAIConfig();
        showNotification('目录规则已恢复为默认值');
    } catch (e) {
        showNotification('恢复默认设置失败: ' + e.message);
    }
};

