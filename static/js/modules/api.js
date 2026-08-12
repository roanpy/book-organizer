/**
 * api.js - API 调用函数
 * 
 * 所有与后端的 HTTP 通信。
 * 依赖: state.js
 */

// ============================================================================
// 配置和图书列表
// ============================================================================

async function fetchConfig() {
    try {
        const res = await fetch(`${API_BASE}/config?t=${new Date().getTime()}`);
        config = await res.json();
        updateConfigUI();
    } catch (e) {
        console.error('Failed to fetch config', e);
    }
}

async function fetchBooks() {
    // 顺序执行时不显示加载动画，避免列表闪烁
    if (!isSequentialMode) {
        bookListEl.innerHTML = '<div class="loading-spinner"></div>';
    }
    try {
        const res = await fetch(`${API_BASE}/books?t=${new Date().getTime()}`);
        const data = await res.json();
        books = data.books || [];
        updateStats();
        renderBookList();
    } catch (e) {
        bookListEl.innerHTML = '<p style="text-align:center; color:var(--danger-color)">加载失败</p>';
    }
}

// ============================================================================
// 图书分析
// ============================================================================

async function analyzeBook(filename = null) {
    const targetBook = filename || window.getCurrentBookPath();
    if (!targetBook) return null;
    let analysisController = null;
    let analysisTaskId = null;

    if (!filename) {
        // 如果正在"开始分析"中且用户点击，则取消
        const activeController = currentAnalysisController || window.currentAnalysisController;
        if (activeController) {
            console.log('[analyzeBook] Aborting existing analysis');
            // 使用 cancelAllOperations 停止主任务以及并发的子任务（如目录识别）
            cancelAllOperations();
            showAnalysisLoading(false);
            fetch(`${API_BASE}/analyze/cancel`, { method: 'POST' }).catch(() => { });
            if (currentBook) loadCover(currentBook);
            return null;
        }

        // 互斥：检查是否有其他操作正在进行，需要用户确认
        const activeOp = getActiveOperation();
        if (activeOp) {
            const confirmed = await confirmCancelOperation('信息及目录分析');
            if (!confirmed) return null;
        }

        // 取消其他正在进行的操作
        cancelAllOperations();

        analysisController = new AbortController();
        analysisTaskId = (window.currentAnalysisTaskId || 0) + 1;
        window.currentAnalysisTaskId = analysisTaskId;
        currentAnalysisController = analysisController;
        window.currentAnalysisController = analysisController;  // 同步到 window
        showAnalysisLoading(true);
        analysisResultEl.classList.add('hidden');
    }

    const engine = engineSelect.value;
    const enableSearch = isWebSearchEnabled;

    const uiMetadata = !filename ? {
        title: document.getElementById('meta-title').value.trim(),
        author: document.getElementById('meta-author').value.trim(),
        publisher: document.getElementById('meta-publisher').value.trim(),
        series: document.getElementById('meta-series').value.trim(),
        tags: document.getElementById('meta-tags').value.trim()
    } : null;

    try {
        // 获取开关状态。优先使用前端当前状态，避免偏好请求延迟导致联动不触发。
        let isEnhancedEnabled = window.isEnhancedModeEnabled === true;
        let isTocEnabled = window.isTocEnabled === true;
        try {
            const prefRes = await fetch(`${API_BASE}/user_preferences`);
            const prefs = await prefRes.json();
            if (typeof window.isEnhancedModeEnabled !== 'boolean') {
                isEnhancedEnabled = prefs.enhancedModeEnabled === true;
            }
            if (typeof window.isTocEnabled !== 'boolean') {
                isTocEnabled = prefs.tocEnabled === true;
            }
        } catch (e) {
            console.error('Failed to load preferences:', e);
        }

        // 智能联动：手动点击 "分析" 按钮时，不应跳过任何步骤
        // 只有在特定自动化场景下才考虑跳过，但目前 analyzeBook 主要用于强制分析
        const shouldSkipMetadata = false;
        const shouldSkipSummary = false;
        const shouldSkipToc = false;

        // 判断当前模式：在库管理模式使用不同的 API
        const isManageMode = typeof currentMode !== 'undefined' && currentMode === 'manage';

        // 准备请求
        // 主元数据分析 (只有在未手动识别/编辑过时才执行)
        let metadataPromise;
        if (shouldSkipMetadata) {
            console.log('[analyzeBook] Skipping metadata - already identified or manually edited');
            metadataPromise = Promise.resolve({ metadata: null, skipped: true });
        } else {
            // 所有模式统一使用 analyze API（包含目录建议和简介）
            // 后端 resolve_file_path 会处理 source_dir 和 target_dir 的查找逻辑
            console.log('[analyzeBook] Using unified analyze API (+suggestions)');
            metadataPromise = fetchJson(`${API_BASE}/analyze`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    filename: targetBook,
                    engine: engine,
                    enable_search: enableSearch,
                    user_metadata: uiMetadata
                }),
                signal: filename ? undefined : analysisController?.signal
            }, '信息及目录分析失败');
        }

        // 有条件的增强简介请求 (只有在未手动生成过时才执行，且非离线模式)
        let summaryPromise = Promise.resolve(null);
        if (targetBook && isEnhancedEnabled && window.fetchEnhancedSummary && !shouldSkipSummary && engine !== 'offline') {
            if (!filename && window.showEnhancedSummaryLoading) {
                window.showEnhancedSummaryLoading(targetBook, '增强简介生成中，完成后会自动刷新...');
            }
            summaryPromise = window.fetchEnhancedSummary(targetBook, engine, currentMode)
                .catch(e => {
                    console.error("Enhanced summary failed:", e);
                    return { warning: formatApiErrorMessage(e, '增强简介生成失败') };
                });
        } else if (shouldSkipSummary) {
            console.log('[analyzeBook] Skipping enhanced summary - already generated');
        }

        // 有条件的目录提取 (只有在未手动提取过时才执行)
        let tocPromise = Promise.resolve(null);
        if (targetBook && isTocEnabled && window.extractToc && !shouldSkipToc) {
            // 调用 extractToc 但不自动切换标签，跳过互斥检查，且静默运行
            tocPromise = (async () => {
                try {
                    await window.extractToc(false, true, true, targetBook);  // skipMutexCheck = true, silent = true
                    return { success: true };
                } catch (e) {
                    console.error("TOC extraction failed:", e);
                    return null;
                }
            })();
        } else if (shouldSkipToc) {
            console.log('[analyzeBook] Skipping TOC extraction - already extracted');
        }

        // 并行执行
        const [data, enhanced, tocResult] = await Promise.all([metadataPromise, summaryPromise, tocPromise]);

        if (!filename && window.isCurrentBookTarget && !window.isCurrentBookTarget(targetBook)) {
            console.log('[analyzeBook] Ignoring stale analysis result for:', targetBook);
            return null;
        }

        // 如果后端返回了警告（例如 AI 失败降级到本地分析），显示提示
        if (data && data.warning) {
            showNotification(data.warning, 6000, 'warning');
        }

        // 单独存储增强简介，不覆盖 data.summary
        // data.summary = 来自元数据分析的原始简短简介
        // enhanced.summary = 详细的增强简介
        const enhancedSummary = (enhanced && enhanced.summary) ? enhanced.summary : null;
        if (!filename && enhanced && enhanced.warning) {
            showNotification(enhanced.warning, 6000, 'warning');
        }
        if (!filename && window.clearEnhancedSummaryLoading) {
            window.clearEnhancedSummaryLoading(targetBook);
        }

        // 处理元数据 UI 更新 (如果不是批处理，或非静默更新)
        if (!filename && data && data.metadata && !data.skipped) {
            if (data.metadata.title) document.getElementById('meta-title').value = data.metadata.title;
            if (data.metadata.author) document.getElementById('meta-author').value = data.metadata.author;
            if (data.metadata.publisher) document.getElementById('meta-publisher').value = data.metadata.publisher;
            if (data.metadata.series) document.getElementById('meta-series').value = data.metadata.series;
            if (data.metadata.tags) document.getElementById('meta-tags').value = data.metadata.tags;

            applyFilenameTemplate();
            bookOperationStatus.metadataIdentified = true;
            // 点亮保存按钮
            enableSaveButton();

            if (data.metadata.title && !isBatchRunning) {
                await findAndDisplaySimilarFiles(data.metadata.title, targetBook);
            }
        }

        if (!filename) {
            // 只有当有新的有效简介时才更新，防止离线模式或AI失败导致简介丢失
            const newSummary = enhancedSummary || data.summary;
            let summaryToRender = enhancedSummary;

            if (newSummary) {
                window.currentBookSummary = newSummary;
                if (enhancedSummary) {
                    bookOperationStatus.summaryGenerated = true;
                    enableSaveButton();
                }
            } else {
                console.log('Analysis returned empty summary, displaying existing:', window.currentBookSummary);
                // 使用现有简介进行渲染，避免UI被清空
                if (window.currentBookSummary) {
                    summaryToRender = window.currentBookSummary;
                }
            }

            // 渲染结果 (优先使用新结果，若无则使用保留结果)
            if (data) {
                renderAnalysisResult(data, summaryToRender);
            }

            if (!enhancedSummary && enhanced && enhanced.warning && window.renderEnhancedSummaryWarning) {
                window.renderEnhancedSummaryWarning(enhanced.warning, targetBook);
            }
        }

        // 将 enhancedSummary 添加到返回值以供批处理模式使用
        if (data && enhancedSummary) {
            data.enhancedSummary = enhancedSummary;
        }

        return data;
    } catch (e) {
        if (e.name === 'AbortError') {
            console.log('分析已被用户中止');
            return null;
        }
        if (!filename) {
            showNotification(`分析失败: ${formatApiErrorMessage(e, '分析失败')}`, 8000, 'error');
        }
        throw e;
    } finally {
        if (!filename) {
            const isCurrentAnalysis = currentAnalysisController === analysisController
                || window.currentAnalysisController === analysisController;
            const isLatestAnalysisTask = analysisTaskId === null
                || window.currentAnalysisTaskId === analysisTaskId;
            const isCurrentTarget = !window.isCurrentBookTarget
                || window.isCurrentBookTarget(targetBook);
            if (window.clearEnhancedSummaryLoading) {
                window.clearEnhancedSummaryLoading(targetBook);
            }
            if (isLatestAnalysisTask && isCurrentTarget) {
                showAnalysisLoading(false);
                window.currentAnalysisTaskId = null;
            }
            if (isCurrentAnalysis) {
                currentAnalysisController = null;
                window.currentAnalysisController = null;
            }
        }
    }
}

// ============================================================================
// 图书操作
// ============================================================================

async function moveBook(destination, filename = null, batchMetadata = null, batchSummary = '') {
    const targetBook = filename || window.getCurrentBookPath();
    if (!targetBook) return;

    if (!filename) {
        showTransferStatus('正在转移图书...');
    }

    try {
        let metadata = null;
        let summary = '';

        if (!filename && document.getElementById('meta-filename')) {
            metadata = {
                title: document.getElementById('meta-title').value.trim(),
                author: document.getElementById('meta-author').value.trim(),
                publisher: document.getElementById('meta-publisher').value.trim(),
                series: document.getElementById('meta-series').value.trim(),
                tags: document.getElementById('meta-tags').value.trim(),
                new_filename: document.getElementById('meta-filename').value.replace(/\.[^/.]+$/, "")
            };
            summary = window.currentBookSummary;
        } else if (batchMetadata) {
            metadata = batchMetadata;
            summary = batchSummary;
        }

        let endpoint = '/move';
        let body = { filename: targetBook, destination: destination };

        if (metadata) {
            endpoint = '/rename_and_move';
            body = {
                original_filename: targetBook,
                metadata: metadata,
                destination: destination,
                summary: summary
            };
        }

        const res = await fetch(`${API_BASE}${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });

        if (!res.ok) throw new Error(await res.text());

        if (!filename) {
            const bookIndex = books.findIndex(b => b.name === targetBook);
            if (bookIndex !== -1) {
                books.splice(bookIndex, 1);
            }

            renderBookList();
            updateStats();

            if (isSequentialMode) {
                processNextSequential();
            } else {
                const nextBook = books.find(b => b.status === 'pending');
                if (nextBook) {
                    selectBook(nextBook.name);
                } else {
                    currentBook = null;
                    bookDetailEl.classList.add('hidden');
                    emptyStateEl.classList.remove('hidden');
                }
            }

            fetchBooks().catch(console.error);
        }
        return true;
    } catch (e) {
        if (!filename) alert(`移动失败: ${e.message}`);
        throw e;
    } finally {
        if (!filename) {
            hideTransferStatus();
        }
    }
}

async function skipBook(filename = null) {
    const targetBook = filename || window.getCurrentBookPath();
    if (!targetBook) return;

    // 检查当前图书状态，决定是跳过还是取消跳过
    const bookObj = books.find(b => b.name === targetBook);
    if (bookObj && bookObj.status === 'skipped') {
        // 已跳过，执行取消跳过
        return unskipBook(targetBook);
    }

    // 在顺序模式下，跳过确认对话框，直接跳过并处理下一本
    // 首先取消正在进行的 AI 分析和其他请求
    if (!filename && isSequentialMode) {
        // 取消正在进行的分析
        if (currentAnalysisController || window.currentAnalysisController) {
            (currentAnalysisController || window.currentAnalysisController).abort();
            currentAnalysisController = null;
            window.currentAnalysisController = null;
        }
        // 取消识别请求
        if (currentIdentifyController || window.currentIdentifyController) {
            (currentIdentifyController || window.currentIdentifyController).abort();
            currentIdentifyController = null;
            window.currentIdentifyController = null;
        }
        // 取消增强简介请求
        if (currentEnhancedSummaryController || window.currentEnhancedSummaryController) {
            (currentEnhancedSummaryController || window.currentEnhancedSummaryController).abort();
            currentEnhancedSummaryController = null;
            window.currentEnhancedSummaryController = null;
        }
        // 重置 UI 状态
        showAnalysisLoading(false);
    } else if (!filename && !confirm(`确定要跳过 "${targetBook}" 吗？`)) {
        return;
    }

    try {
        await fetch(`${API_BASE}/skip`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename: targetBook })
        });

        if (!filename) {
            const bookObj = books.find(b => b.name === targetBook);
            if (bookObj) bookObj.status = 'skipped';
            renderBookList();
            updateStats();

            if (isSequentialMode) {
                processNextSequential();
            } else {
                const nextBook = books.find(b => b.status === 'pending');
                if (nextBook) {
                    selectBook(nextBook.name);
                } else {
                    currentBook = null;
                    bookDetailEl.classList.add('hidden');
                    emptyStateEl.classList.remove('hidden');
                }
            }
        }
    } catch (e) {
        console.error('Skip failed', e);
    }
}

async function unskipBook(filename) {
    const targetBook = filename || window.getCurrentBookPath();
    if (!targetBook) return;

    try {
        await fetch(`${API_BASE}/unskip`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename: targetBook })
        });

        const bookObj = books.find(b => b.name === targetBook);
        if (bookObj) bookObj.status = 'pending';
        renderBookList();
        updateStats();

        // 重新选择该书以更新按钮状态
        selectBook(targetBook);
        showNotification('已取消跳过');
    } catch (e) {
        console.error('Unskip failed', e);
        showNotification('取消跳过失败', 3000, 'error');
    }
}
window.unskipBook = unskipBook;

async function deleteBook() {
    const bookPath = getCurrentBookPath() || currentBook;
    if (!bookPath) {
        showNotification('请先选择一本图书', 3000, 'error');
        return;
    }

    const displayName = bookPath.split('/').pop() || bookPath;
    if (!confirm(`⚠️ 确定要删除 "${displayName}" 吗？\n\n此操作将永久删除源文件，无法恢复！`)) {
        return;
    }

    try {
        const res = await fetch(`${API_BASE}/delete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename: bookPath })
        });

        if (!res.ok) {
            const error = await res.json();
            throw new Error(error.detail || '删除失败');
        }

        // Handle both modes
        if (currentMode === 'manage') {
            // 库管理模式：从 libraryBooks 中移除并刷新
            const bookIndex = libraryBooks.findIndex(b => b.path === bookPath);
            if (bookIndex !== -1) {
                libraryBooks.splice(bookIndex, 1);
                libraryStats.total--;
            }
            renderBookList();
            // 清除当前选中
            currentBook = null;
            window.currentBook = null;
            window.currentBookPath = null;
            bookDetailEl.classList.add('hidden');
            emptyStateEl.classList.remove('hidden');
        } else {
            // 整理模式：原始逻辑
            const bookIndex = books.findIndex(b => b.name === bookPath);
            if (bookIndex !== -1) {
                books.splice(bookIndex, 1);
            }
            renderBookList();
            updateStats();

            if (isSequentialMode) {
                processNextSequential();
            } else {
                const nextBook = books.find(b => b.status === 'pending');
                if (nextBook) {
                    selectBook(nextBook.name);
                } else {
                    currentBook = null;
                    bookDetailEl.classList.add('hidden');
                    emptyStateEl.classList.remove('hidden');
                }
            }
        }

        showNotification('文件已删除');
    } catch (e) {
        showNotification(`删除失败: ${e.message}`);
        console.error('Delete failed', e);
    }
}

async function browseDirectory(path) {
    pickerListEl.innerHTML = '<div style="padding:10px">加载中...</div>';
    try {
        const res = await fetch(`${API_BASE}/browse`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: path })
        });
        const data = await res.json();
        currentBrowsePath = data.current_path;
        renderDirectoryList(data.items);
        pickerCurrentPathEl.textContent = currentBrowsePath;
    } catch (e) {
        pickerListEl.innerHTML = '<div style="padding:10px; color:red">加载失败</div>';
    }
}

async function saveConfigPayload(payload) {
    const res = await fetch(`${API_BASE}/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });

    if (!res.ok) {
        throw new Error('保存失败');
    }

    // 刷新本地配置
    await fetchConfig();
}

async function loadInternalMetadata(filename) {
    try {
        const res = await fetch(`${API_BASE}/metadata/${encodeURIComponent(filename)}`);
        if (res.ok) {
            const data = await res.json();
            if (data.title) document.getElementById('meta-title').value = data.title;
            if (data.author) document.getElementById('meta-author').value = data.author;
            if (data.publisher) document.getElementById('meta-publisher').value = data.publisher;
            if (data.series) document.getElementById('meta-series').value = data.series;
            if (data.tags) document.getElementById('meta-tags').value = data.tags;
            return data;
        }
        return null;
    } catch (e) {
        console.error('Failed to load metadata', e);
    }
}

async function findAndDisplaySimilarFiles(title, currentPath = null) {
    const query = getSearchQueryFromTitle(title);
    if (!query) return;

    try {
        const activePath = currentPath || (window.getCurrentBookPath ? window.getCurrentBookPath() : null);
        const res = await fetch(`${API_BASE}/find_similar`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: query, current_path: activePath })
        });

        if (!res.ok) return;

        const data = await res.json();
        const matches = (data.matches || []).filter(match => {
            if (!activePath || !match || !match.path) return true;
            if (!window.normalizeBookTarget) return match.path !== activePath;
            return window.normalizeBookTarget(match.path) !== window.normalizeBookTarget(activePath);
        });
        if (matches.length > 0) {
            displaySimilarFiles(matches);
        } else {
            const container = document.getElementById('similar-files-container');
            if (container) container.remove();
        }
    } catch (e) {
        console.error('Failed to find similar files', e);
    }
}

function getSearchQueryFromTitle(title) {
    let query = title;
    const colonIndex = title.indexOf('：');
    const colonIndex2 = title.indexOf(':');
    const parenIndex = title.indexOf('（');
    const parenIndex2 = title.indexOf('(');

    const indices = [colonIndex, colonIndex2, parenIndex, parenIndex2].filter(i => i > 0);
    if (indices.length > 0) {
        const minIndex = Math.min(...indices);
        query = title.substring(0, minIndex).trim();
    }
    return query;
}

// ============================================================================
// 库管理 API (v0.4.0)
// ============================================================================

async function fetchLibraryBooks() {
    try {
        const res = await fetch(`${API_BASE}/library`);
        if (!res.ok) {
            throw new Error(`HTTP error! status: ${res.status}`);
        }
        const data = await res.json();

        libraryBooks = data.books || [];
        libraryStats = {
            total: (data.stats && data.stats.total) || 0,
            enhanced: (data.stats && data.stats.enhanced) || 0,
            not_enhanced: (data.stats && data.stats.not_enhanced) || 0
        };

        return data;
    } catch (e) {
        showNotification('获取在库图书失败: ' + formatApiErrorMessage(e, '获取在库图书失败'), 5000, 'error');
        console.error('Fetch library failed:', e);
        return null;
    }
}

function getCoverUrl(path) {
    if (!path) return null;
    return `${API_BASE}/cover?path=${encodeURIComponent(path)}`;
}

async function fetchLibraryBookDetails(path, skipFileRead = false) {
    try {
        let url = `${API_BASE}/library/book_details?path=${encodeURIComponent(path)}`;
        if (skipFileRead) {
            url += '&skip_file_read=true';
        }
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await response.json();
    } catch (e) {
        console.error('Fetch book details failed:', e);
        return null;
    }
}

async function fetchEnhancedSummary(filename = null, engine = null, mode = 'organize') {
    const targetBook = filename || window.getCurrentBookPath();
    if (!targetBook) return null;
    let summaryController = null;

    // 记录请求时的书籍，用于后续验证，避免切书后旧结果覆盖新 UI。
    const requestedBook = targetBook;
    const isCurrentInteractiveBook = window.isCurrentBookTarget
        ? window.isCurrentBookTarget(targetBook)
        : (window.getCurrentBookPath && window.getCurrentBookPath() === targetBook);

    // 当前书籍的增强简介请求必须纳入全局取消机制。
    let summaryTask = null;
    if (isCurrentInteractiveBook) {
        if (currentEnhancedSummaryController) {
            currentEnhancedSummaryController.abort();
        }
        summaryTask = window.beginBookScopedTask
            ? window.beginBookScopedTask('enhanced-summary', requestedBook)
            : null;
        summaryController = summaryTask ? summaryTask.controller : new AbortController();
        currentEnhancedSummaryController = summaryController;
        window.currentEnhancedSummaryController = summaryController;  // 同步到 window
    }

    // 如果未提供，使用当前引擎
    const selectedEngine = engine || document.getElementById('engine-select').value;
    // 直接访问全局 currentMode (定义在 state.js)
    const modeToSend = (typeof currentMode !== 'undefined') ? currentMode : 'organize';
    const selectedMode = mode || modeToSend;

    try {
        const data = await fetchJson(`${API_BASE}/enhanced_summary`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                filename: targetBook,
                engine: selectedEngine,
                mode: selectedMode // 如果后端支持，传递 mode 参数
            }),
            signal: isCurrentInteractiveBook
                ? (summaryTask ? summaryTask.signal : summaryController?.signal)
                : undefined
        }, '增强简介生成失败');

        // 验证当前书籍是否仍是请求时的书籍
        if (isCurrentInteractiveBook && summaryTask && !summaryTask.isCurrent()) {
            console.log('增强简介结果已过期，用户已切换到其他书籍');
            return null;
        }

        return data;
    } catch (e) {
        if (e.name === 'AbortError') {
            console.log('增强简介请求已取消');
            return null;
        }
        throw new Error(formatApiErrorMessage(e, '生成增强简介失败'));
    } finally {
        const isCurrentSummary = currentEnhancedSummaryController === summaryController
            || window.currentEnhancedSummaryController === summaryController;
        if (summaryTask) {
            summaryTask.finish();
        }
        if (isCurrentInteractiveBook && isCurrentSummary) {
            currentEnhancedSummaryController = null;
            window.currentEnhancedSummaryController = null;
        }
    }
}

async function saveMetadata() {
    if (!currentBook) return;

    const btn = document.getElementById('btn-save');
    const originalBtnContent = btn ? btn.innerHTML : '';
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<div class="spinner-small"></div> 保存中...';
    }

    try {
        const metadata = {
            title: document.getElementById('meta-title').value.trim(),
            author: document.getElementById('meta-author').value.trim(),
            publisher: document.getElementById('meta-publisher').value.trim(),
            series: document.getElementById('meta-series').value.trim(),
            tags: document.getElementById('meta-tags').value.trim(),
            new_filename: document.getElementById('meta-filename').value.replace(/\.[^/.]+$/, "")
        };

        const summary = window.currentBookSummary || "";

        const res = await fetch(`${API_BASE}/rename_only`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                original_filename: currentBook,
                metadata: metadata,
                summary: summary
            })
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || '保存失败');
        }
        const data = await res.json();

        showNotification(data.message || '保存成功', 3000, 'success');

        // 如果文件名已更改，则更新（从 transferBook 统一）
        if (data.new_filename && data.new_filename !== currentBook) {
            currentBook = data.new_filename;
            if (typeof currentBookFilename !== 'undefined') {
                currentBookFilename = data.new_filename;
            }
            if (currentFilenameEl) {
                currentFilenameEl.textContent = data.new_filename;
            }
            document.getElementById('meta-filename').value = data.new_filename;
        }

        // 根据模式刷新列表 - 在库模式下保留树状态
        if (typeof currentMode !== 'undefined' && currentMode === 'manage') {
            // 库模式：使用保留状态的刷新
            // 传递更新后的路径，确保能正确选中新图书
            if (window.refreshLibraryTreeWithState) {
                await window.refreshLibraryTreeWithState(currentBook);
            }
        } else {
            // 整理模式：标准刷新
            await fetchBooks();
        }

        // 保存成功后重置保存按钮为非活动状态
        if (btn) {
            btn.className = 'btn-save-inactive';
            btn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> 保存';
            btn.disabled = true;  // 保存后保持禁用，直到下次编辑
        }

    } catch (e) {
        showNotification(`保存失败: ${e.message}`, 4000, 'error');
        if (btn) {
            btn.innerHTML = originalBtnContent;
            btn.disabled = false;  // 仅在错误时重新启用，以便用户重试
        }
    }
}
window.saveMetadata = saveMetadata;
window.fetchEnhancedSummary = fetchEnhancedSummary;

// ============================================================================
// Calibre PDF 转换 API (NotebookLM 预集成功能)
// ============================================================================

/**
 * 检查 Calibre 安装状态
 * @returns {Promise<{installed: boolean, path: string, message: string}>}
 */
async function checkCalibreStatus() {
    try {
        const res = await fetch(`${API_BASE}/calibre/status`);
        if (!res.ok) throw new Error('检查 Calibre 状态失败');
        return await res.json();
    } catch (e) {
        console.error('Check Calibre status failed:', e);
        return { installed: false, path: '', message: e.message };
    }
}

/**
 * 将 EPUB 转换为 PDF
 * @param {string} filename - EPUB 文件名
 * @returns {Promise<{success: boolean, pdf_path: string, message: string}>}
 */
async function convertEpubToPdf(filename) {
    try {
        const res = await fetch(`${API_BASE}/calibre/convert`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename: filename })
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || '转换失败');
        }

        return await res.json();
    } catch (e) {
        console.error('Convert to PDF failed:', e);
        throw e;
    }
}

window.checkCalibreStatus = checkCalibreStatus;
window.convertEpubToPdf = convertEpubToPdf;
