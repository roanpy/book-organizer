/**
 * batch.js - 批量处理功能
 * 
 * 批量分析和执行。
 * 依赖: state.js, api.js
 */

// ============================================================================
// 批量分析
// ============================================================================

/**
 * 入库批量分析 - 使用优化后的合并API
 * 根据开关状态决定是否生成增强简介，目录识别单独处理
 */
async function startBatchAnalysis() {
    isBatchRunning = true;
    shouldStopBatch = false;
    batchPlan = [];

    // UI Reset
    startBatchBtn.classList.add('hidden');
    executeBatchBtn.classList.add('hidden');
    stopBatchBtn.classList.remove('hidden');
    batchReviewArea.classList.add('hidden');
    batchLogEl.classList.remove('hidden');
    batchLogEl.innerHTML = '';

    const pendingBooks = books.filter(b => b.status === 'pending');
    const total = pendingBooks.length;

    if (total === 0) {
        logBatch('没有待处理的图书。');
        stopBatch();
        return;
    }

    // 获取开关状态
    let isEnhancedEnabled = false;
    let isWebSearchEnabled = false;
    try {
        const prefs = await fetchJson(`${API_BASE}/user_preferences`, {}, '获取用户偏好失败');
        isEnhancedEnabled = prefs.enhancedModeEnabled === true;
        // 联网搜索状态从全局变量获取（由 UI 开关控制）
        isWebSearchEnabled = window.isWebSearchEnabled === true;
    } catch (e) {
        console.warn('获取用户偏好失败，使用默认设置:', e);
    }

    const engine = engineSelect?.value || 'deepseek';
    logBatch(`开始分析 ${total} 本图书... (联网: ${isWebSearchEnabled ? '开' : '关'}, 增强: ${isEnhancedEnabled ? '开' : '关'})`);


    for (let i = 0; i < total; i++) {
        if (shouldStopBatch) {
            logBatch('用户停止分析。');
            break;
        }

        const book = pendingBooks[i];
        const progress = Math.round(((i) / total) * 100);
        updateBatchProgress(progress, `正在分析: ${book.name}`);

        try {
            logBatch(`[${i + 1}/${total}] 分析: ${book.name}`);

            // 使用合并API - 一次调用获取元数据+目录建议+增强简介(可选)
            const result = await fetchJson(`${API_BASE}/batch_organize_single`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    filename: book.name,
                    engine: engine,
                    enable_enhanced_summary: isEnhancedEnabled,
                    enable_online_search: isWebSearchEnabled
                })
            }, '分析失败');

            let item = {
                filename: book.name,
                suggestions: [],
                suggestion: '',
                status: 'skip',
                reason: '无推荐',
                metadata: null,
                summary: '',
                duplicates: []
            };

            if (result.suggestions && result.suggestions.length > 0) {
                item.suggestions = result.suggestions;
                item.suggestion = result.suggestions[0];
                item.status = 'move';
                item.reason = 'AI推荐';

                if (result.metadata) {
                    item.metadata = result.metadata;
                }
                // 优先使用增强简介，否则使用短简介
                if (result.enhancedSummary) {
                    item.summary = result.enhancedSummary;
                } else if (result.summary) {
                    item.summary = result.summary;
                }

                logBatch(`  -> 推荐: ${item.suggestions.length} 个路径`);

                // 重复检测
                if (result.metadata && result.metadata.title) {
                    try {
                        const query = getSearchQueryFromTitle(result.metadata.title);
                        const similarData = await fetchJson(`${API_BASE}/find_similar`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ query: query })
                        }, '重复检测失败');
                        if (similarData.matches && similarData.matches.length > 0) {
                            item.duplicates = similarData.matches;
                            logBatch(`  -> 发现 ${similarData.matches.length} 个潜在重复`);
                        }
                    } catch (e) {
                        console.error('Failed to check duplicates:', e);
                    }
                }
            } else {
                logBatch(`  -> 无推荐`);
            }

            batchPlan.push(item);
        } catch (e) {
            logBatch(`  -> 错误: ${e.message}`);
            batchPlan.push({
                filename: book.name,
                suggestions: [],
                suggestion: '',
                status: 'skip',
                reason: `错误: ${e.message}`,
                metadata: null,
                summary: '',
                duplicates: []
            });
        }
    }

    updateBatchProgress(100, '分析完成，请审核');
    stopBatch();

    if (batchPlan.length > 0) {
        renderBatchReview();
    }
}


// ============================================================================
// 批量审核
// ============================================================================

function renderBatchReview() {
    batchLogEl.classList.add('hidden');
    batchReviewArea.classList.remove('hidden');
    startBatchBtn.classList.add('hidden');
    document.getElementById('cancel-batch-btn').classList.remove('hidden');
    executeBatchBtn.classList.remove('hidden');

    reviewListEl.innerHTML = '';
    batchPlan.forEach((item, index) => {
        const tr = document.createElement('tr');
        tr.dataset.index = index;

        const tdName = document.createElement('td');
        const filenameCell = document.createElement('div');
        filenameCell.className = 'filename-cell';

        const nameSpan = document.createElement('span');
        nameSpan.textContent = item.filename;
        filenameCell.appendChild(nameSpan);

        if (item.summary) {
            const summaryIcon = document.createElement('span');
            summaryIcon.className = 'summary-icon has-tooltip';
            summaryIcon.innerHTML = '<i class="fa-solid fa-file-lines"></i>';
            summaryIcon.dataset.tooltip = `<strong>AI 简介：</strong><br>${item.summary}`;
            filenameCell.appendChild(summaryIcon);
        }

        if (item.duplicates && item.duplicates.length > 0) {
            const warningIcon = document.createElement('span');
            warningIcon.className = 'duplicate-warning has-tooltip';
            warningIcon.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i>';

            const duplicateList = item.duplicates.map(d =>
                `${d.filename} (${d.path})`
            ).join('<br>');
            warningIcon.dataset.tooltip = `<strong>检测到潜在重复：</strong><br>${duplicateList}`;

            filenameCell.appendChild(warningIcon);
        }

        tdName.appendChild(filenameCell);

        const tdDest = document.createElement('td');
        const select = document.createElement('select');
        select.className = 'target-select';

        if (item.suggestions && item.suggestions.length > 0) {
            item.suggestions.forEach((path, idx) => {
                const option = document.createElement('option');
                option.value = path;
                option.textContent = path;
                if (idx === 0) option.selected = true;
                select.appendChild(option);
            });
            item.suggestion = item.suggestions[0];
        } else {
            const option = document.createElement('option');
            option.value = '';
            option.textContent = '无推荐路径';
            option.disabled = true;
            option.selected = true;
            select.appendChild(option);
            select.disabled = true;
        }

        select.onchange = (e) => {
            item.suggestion = e.target.value;
            if (item.suggestion && item.status === 'skip') {
                item.status = 'move';
                updateRowStatus(tr, 'move');
            }
        };

        tdDest.appendChild(select);

        const tdAction = document.createElement('td');
        const actionGroup = document.createElement('div');
        actionGroup.className = 'action-buttons-group';

        const btnSkip = document.createElement('button');
        btnSkip.className = 'btn-skip btn-sm';
        btnSkip.innerHTML = '<i class="fa-solid fa-forward"></i> 跳过';
        btnSkip.title = '跳过此图书';
        btnSkip.onclick = () => {
            if (item.status === 'skip') {
                item.status = 'move';
                updateRowStatus(tr, 'move');
            } else {
                item.status = 'skip';
                updateRowStatus(tr, 'skip');
            }
        };

        const btnDelete = document.createElement('button');
        btnDelete.className = 'btn-danger btn-sm';
        btnDelete.innerHTML = '<i class="fa-solid fa-trash"></i> 删除';
        btnDelete.title = '从列表中移除';
        btnDelete.onclick = () => {
            if (confirm(`确定从批量处理列表中移除 "${item.filename}" 吗？`)) {
                batchPlan.splice(index, 1);
                tr.remove();
                renderBatchReview();
            }
        };

        actionGroup.appendChild(btnSkip);
        actionGroup.appendChild(btnDelete);
        tdAction.appendChild(actionGroup);

        tr.appendChild(tdName);
        tr.appendChild(tdDest);
        tr.appendChild(tdAction);

        updateRowStatus(tr, item.status);

        reviewListEl.appendChild(tr);
    });
}

function updateRowStatus(tr, status) {
    const select = tr.querySelector('select.target-select');
    const btnSkip = tr.querySelector('.btn-skip');

    if (status === 'move') {
        tr.classList.remove('skipped');
        if (select) select.disabled = false;
        if (btnSkip) {
            btnSkip.classList.remove('active');
            btnSkip.innerHTML = '<i class="fa-solid fa-forward"></i> 跳过';
        }
    } else if (status === 'skip') {
        tr.classList.add('skipped');
        if (select) select.disabled = true;
        if (btnSkip) {
            btnSkip.classList.add('active');
            btnSkip.innerHTML = '<i class="fa-solid fa-rotate-left"></i> 取消跳过';
        }
    }
}

// ============================================================================
// 批量执行
// ============================================================================

async function executeBatch() {
    isBatchRunning = true;
    shouldStopBatch = false;

    batchReviewArea.classList.add('hidden');
    batchLogEl.classList.remove('hidden');
    executeBatchBtn.classList.add('hidden');
    stopBatchBtn.classList.remove('hidden');
    batchLogEl.innerHTML = '';

    const total = batchPlan.length;
    logBatch(`开始执行 ${total} 个任务...`);

    for (let i = 0; i < total; i++) {
        if (shouldStopBatch) {
            logBatch('用户停止执行。');
            break;
        }

        const item = batchPlan[i];
        const progress = Math.round(((i) / total) * 100);
        updateBatchProgress(progress, `正在执行: ${item.filename}`);

        try {
            if (item.status === 'move') {
                if (!item.suggestion) {
                    logBatch(`[跳过] ${item.filename}: 无目标路径`);
                    await skipBook(item.filename);
                    continue;
                }
                logBatch(`[移动] ${item.filename} -> ${item.suggestion}`);
                await moveBook(item.suggestion, item.filename, item.metadata, item.summary);
            } else {
                logBatch(`[跳过] ${item.filename}`);
                await skipBook(item.filename);
            }
        } catch (e) {
            logBatch(`  -> 错误: ${e.message}`);
        }
    }

    updateBatchProgress(100, '执行完成');
    stopBatch();
    // 重置所有按钮状态
    startBatchBtn.classList.remove('hidden');
    startBatchBtn.innerHTML = '<i class="fa-solid fa-play"></i> 开始分析';
    document.getElementById('cancel-batch-btn').classList.add('hidden');
    executeBatchBtn.classList.add('hidden');
    await fetchBooks();
}

function stopBatch() {
    isBatchRunning = false;
    shouldStopBatch = true;
    startBatchBtn.classList.remove('hidden');
    stopBatchBtn.classList.add('hidden');
}

function logBatch(msg) {
    const div = document.createElement('div');
    div.textContent = msg;
    batchLogEl.appendChild(div);
    batchLogEl.scrollTop = batchLogEl.scrollHeight;
}

function updateBatchProgress(percent, text) {
    batchProgressEl.style.width = `${percent}%`;
    batchStatusText.textContent = text;
}

// ============================================================================
// 顺序处理
// ============================================================================

function startSequential() {
    if (isSequentialMode) {
        stopSequential();
    } else {
        isSequentialMode = true;

        // Update main dropdown button
        if (processDropdownBtn) {
            processDropdownBtn.classList.add('btn-danger', 'pulsing');
            processDropdownBtn.innerHTML = '<i class="fa-solid fa-stop"></i> <span>停止处理</span>';
            processDropdownBtn.title = '点击停止顺序处理';
        }

        // Keep seqBtn updated too (inside dropdown)
        if (seqBtn) {
            seqBtn.classList.add('active-mode');
            seqBtn.innerHTML = '<i class="fa-solid fa-stop"></i> 停止顺序处理';
        }

        processNextSequential();
    }
}

function stopSequential() {
    isSequentialMode = false;

    // Reset main dropdown button
    if (processDropdownBtn) {
        processDropdownBtn.classList.remove('btn-danger', 'pulsing');
        processDropdownBtn.innerHTML = '<i class="fa-solid fa-layer-group"></i> <span>批量</span> <i class="fa-solid fa-caret-down dropdown-caret"></i>';
        processDropdownBtn.title = '处理模式';
    }

    // Reset seqBtn
    if (seqBtn) {
        seqBtn.classList.remove('active-mode');
        seqBtn.innerHTML = '<i class="fa-solid fa-play"></i> 顺序处理';
    }

    // Abort all in-progress requests
    if (currentAnalysisController || window.currentAnalysisController) {
        (currentAnalysisController || window.currentAnalysisController).abort();
        currentAnalysisController = null;
        window.currentAnalysisController = null;

        // 强制终止后端分析进程
        fetch(`${API_BASE}/analyze/cancel`, { method: 'POST' }).catch(() => { });
    }
    if (currentIdentifyController || window.currentIdentifyController) {
        (currentIdentifyController || window.currentIdentifyController).abort();
        currentIdentifyController = null;
        window.currentIdentifyController = null;
    }
    if (currentEnhancedSummaryController || window.currentEnhancedSummaryController) {
        (currentEnhancedSummaryController || window.currentEnhancedSummaryController).abort();
        currentEnhancedSummaryController = null;
        window.currentEnhancedSummaryController = null;
    }

    // Reset UI loading state
    showAnalysisLoading(false);
}

async function processNextSequential() {
    const nextBook = books.find(b => b.status === 'pending');
    if (nextBook) {
        // 选择书籍并清空旧数据（skipReset: false 确保清空上一本书的元数据）
        selectBook(nextBook.name, { skipReset: false });

        // 并行加载封面和内部元数据
        await Promise.all([
            // 等待封面加载（最多3秒）
            Promise.race([
                loadCover(nextBook.name),
                new Promise(resolve => setTimeout(resolve, 3000))
            ]),
            // 等待内部元数据加载（最多2秒）
            Promise.race([
                window.loadInternalMetadata ? window.loadInternalMetadata(nextBook.name) : Promise.resolve(),
                new Promise(resolve => setTimeout(resolve, 2000))
            ])
        ]);

        // 封面和元数据加载完成后再开始 AI 分析
        // 使用 await 确保分析完成后再处理下一本 (由 moveBook 触发)
        await analyzeBook();
    } else {
        showNotification('所有图书已处理完毕！');
        stopSequential();
        currentBook = null;
        bookDetailEl.classList.add('hidden');
        emptyStateEl.classList.remove('hidden');
    }
}
