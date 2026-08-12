/**
 * ui.js - UI 渲染和交互函数
 * 
 * 界面渲染、通知、模态框等。
 * 依赖: state.js
 */

// ============================================================================
// 通知和状态
// ============================================================================

function showTransferStatus(message) {
    if (transferStatusEl && transferStatusTextEl) {
        transferStatusTextEl.textContent = message;
        transferStatusEl.classList.remove('hidden');
    }
}

/**
 * 点亮保存按钮（用于 AI 识别完成后）
 */
function enableSaveButton() {
    const btnSave = document.getElementById('btn-save');
    if (btnSave) {
        btnSave.disabled = false;
        btnSave.className = 'btn-success';
    }
}
window.enableSaveButton = enableSaveButton;

function hideTransferStatus() {
    if (transferStatusEl) {
        transferStatusEl.classList.add('hidden');
    }
}

function showNotification(message, duration = 2000, type = 'normal') {
    if (transferStatusEl && transferStatusTextEl) {
        transferStatusTextEl.textContent = message;
        transferStatusEl.classList.remove('hidden');

        // Reset classes
        transferStatusTextEl.classList.remove('text-danger', 'text-success', 'text-warning');

        if (type === 'error') {
            transferStatusTextEl.classList.add('text-danger');
        } else if (type === 'success') {
            transferStatusTextEl.classList.add('text-success');
        } else if (type === 'warning') {
            transferStatusTextEl.classList.add('text-warning');
        }

        if (notificationTimeout) clearTimeout(notificationTimeout);

        if (duration > 0) {
            notificationTimeout = setTimeout(() => {
                transferStatusEl.classList.add('hidden');
                // Optional: remove classes after hiding
            }, duration);
        }
    }
}

function showAnalysisLoading(isLoading) {
    if (isLoading) {
        analysisLoadingEl.classList.remove('hidden');
        analyzeBtn.disabled = false;
        analyzeBtn.innerHTML = '<i class="fa-solid fa-stop"></i> 停止分析';
        analyzeBtn.classList.add('analyzing');
    } else {
        analysisLoadingEl.classList.add('hidden');
        analyzeBtn.disabled = false;
        analyzeBtn.classList.remove('analyzing');
        if (typeof window.updateAnalyzeButtonLabel === 'function') {
            window.updateAnalyzeButtonLabel();
        } else {
            analyzeBtn.innerHTML = '<i class="fa-solid fa-play"></i> 开始信息及目录分析';
        }
    }
}

function setEnhancedSummaryButtonLoading(isLoading) {
    const btn = document.getElementById('btn-gen-summary');
    if (!btn) return;

    if (isLoading) {
        btn.dataset.originalContent = btn.dataset.originalContent || btn.innerHTML;
        btn.innerHTML = '<div class="spinner-small"></div> 生成中... <i class="fa-solid fa-stop" style="margin-left:4px"></i>';
        btn.classList.add('analyzing');
    } else {
        btn.classList.remove('analyzing');
        btn.innerHTML = btn.dataset.originalContent || '<i class="fa-solid fa-file-lines"></i> 增强简介';
        delete btn.dataset.originalContent;
    }
}

function showEnhancedSummaryLoading(targetBook = null, message = '增强简介生成中...') {
    if (targetBook && window.isCurrentBookTarget && !window.isCurrentBookTarget(targetBook)) return;

    const summaryResultEl = document.getElementById('ai-summary-result');
    const emptyState = document.querySelector('.empty-ai-state');
    const safeMessage = escapeHtml(String(message || '增强简介生成中...'));
    if (emptyState) emptyState.classList.add('hidden');
    if (summaryResultEl) {
        summaryResultEl.dataset.loadingTarget = targetBook || '';
        summaryResultEl.innerHTML = `
            <div class="summary-status">
                <div class="spinner-small"></div>
                <span>${safeMessage}</span>
            </div>
        `;
        summaryResultEl.classList.remove('hidden');
    }
    setEnhancedSummaryButtonLoading(true);
}

function clearEnhancedSummaryLoading(targetBook = null) {
    const summaryResultEl = document.getElementById('ai-summary-result');
    if (summaryResultEl && targetBook && summaryResultEl.dataset.loadingTarget) {
        const loadingTarget = summaryResultEl.dataset.loadingTarget;
        const sameTarget = window.normalizeBookTarget
            ? window.normalizeBookTarget(loadingTarget) === window.normalizeBookTarget(targetBook)
            : loadingTarget === targetBook;
        if (!sameTarget) return;
        if (sameTarget) delete summaryResultEl.dataset.loadingTarget;
    }
    setEnhancedSummaryButtonLoading(false);
}

function renderEnhancedSummaryWarning(message, targetBook = null) {
    if (targetBook && window.isCurrentBookTarget && !window.isCurrentBookTarget(targetBook)) return;

    const summaryResultEl = document.getElementById('ai-summary-result');
    const emptyState = document.querySelector('.empty-ai-state');
    const displayMessage = typeof window.formatApiErrorMessage === 'function'
        ? window.formatApiErrorMessage(message, '增强简介未生成')
        : String(message || '增强简介未生成');
    const safeMessage = escapeHtml(displayMessage);
    if (emptyState) emptyState.classList.add('hidden');
    if (summaryResultEl) {
        summaryResultEl.innerHTML = `
            <div class="summary-status warning">
                <i class="fa-solid fa-triangle-exclamation"></i>
                <span>${safeMessage}</span>
            </div>
        `;
        summaryResultEl.classList.remove('hidden');
    }
}

window.showEnhancedSummaryLoading = showEnhancedSummaryLoading;
window.clearEnhancedSummaryLoading = clearEnhancedSummaryLoading;
window.renderEnhancedSummaryWarning = renderEnhancedSummaryWarning;

// ============================================================================
// 图书列表渲染
// ============================================================================

function renderBookList() {
    bookListEl.innerHTML = '';

    if (currentMode === 'manage') {
        renderLibraryTree(libraryBooks);
        return;
    }

    if (books.length === 0) {
        bookListEl.innerHTML = '<p class="empty-list-message">暂无图书</p>';
        return;
    }

    // 应用筛选过滤
    let filteredBooks = books;
    if (currentStatsFilter === 'skipped') {
        filteredBooks = books.filter(b => b.status === 'skipped');
    }

    // 🆕 应用搜索过滤（入库模式：仅搜索文件名）
    if (window.sidebarSearchQuery) {
        const keywords = window.sidebarSearchQuery.toLowerCase().split(/\s+/).filter(k => k);
        filteredBooks = filteredBooks.filter(book => {
            const filename = book.name.toLowerCase();
            return keywords.every(kw => filename.includes(kw));
        });
    }

    if (filteredBooks.length === 0) {
        bookListEl.innerHTML = '<p class="empty-list-message">无匹配图书</p>';
        return;
    }

    filteredBooks.forEach(bookObj => {
        const name = bookObj.name;
        const status = bookObj.status;

        const div = document.createElement('div');
        div.className = `book-item ${currentBook === name ? 'active' : ''}`;

        let icon = '<i class="fa-solid fa-book"></i>';
        if (status === 'skipped') icon = '<i class="fa-solid fa-ban icon-skipped"></i>';
        if (status === 'processed') icon = '<i class="fa-solid fa-check icon-processed"></i>';

        div.innerHTML = `${icon} <span>${escapeHtml(name)}</span>`;
        if (status === 'skipped' || status === 'processed') div.classList.add('dimmed');

        div.onclick = () => selectBook(name);
        bookListEl.appendChild(div);
    });
}

// ============================================================================
// 选书公共辅助函数 (Phase 2.1 Refactor)
// ============================================================================

/**
 * 取消所有正在进行的请求（选书时调用）
 * @param {boolean} skipAnalysisAbort - 是否跳过取消分析（顺序模式下使用）
 */
function cancelPendingRequests(skipAnalysisAbort = false) {
    if (!skipAnalysisAbort) {
        cancelAllOperations();
        showAnalysisLoading(false);
        // 强制终止后端分析进程（不等待响应）
        fetch(`${API_BASE}/analyze/cancel`, { method: 'POST' }).catch(() => { });
    } else {
        // 仅取消识别和增强简介，保留分析（用于Library模式）
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
    }
}

/**
 * 重置UI到初始状态（选书时调用）
 */
function resetBookDetailUI() {
    closeCoverZoom();
    emptyStateEl.classList.add('hidden');
    bookDetailEl.classList.remove('hidden');
    analysisResultEl.classList.add('hidden');

    // 清空增强信息区域
    const summaryResultEl = document.getElementById('ai-summary-result');
    if (summaryResultEl) summaryResultEl.classList.add('hidden');

    // 清除相似文件警告
    const similarContainer = document.getElementById('similar-files-container');
    if (similarContainer) similarContainer.remove();
}

/**
 * 重置保存按钮到未激活状态
 */
function resetSaveButton() {
    const btnSave = document.getElementById('btn-save');
    if (btnSave) {
        btnSave.className = 'btn-save-inactive';
        btnSave.disabled = true;
        btnSave.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> 保存';
    }
}

/**
 * 清空元数据表单字段
 */
function clearMetadataFields() {
    document.getElementById('meta-title').value = '';
    document.getElementById('meta-author').value = '';
    document.getElementById('meta-publisher').value = '';
    document.getElementById('meta-series').value = '';
    document.getElementById('meta-tags').value = '';
}

// ============================================================================
// 选书函数
// ============================================================================

function selectBook(filename, options = {}) {
    // 设置全局路径供 app.js 使用
    window.currentBookPath = filename;

    // options.skipReset: 在顺序模式下跳过清空元数据，避免 UI 闪烁
    const skipReset = options.skipReset || false;

    console.log('[selectBook] Called for:', filename, 'skipReset:', skipReset, 'isSequentialMode:', isSequentialMode);

    // 切换书籍时，取消正在进行的请求
    // 避免旧请求的结果覆盖新书籍的 UI
    // 取消所有正在进行的操作（切换图书时互斥）
    if (!skipReset) {
        cancelAllOperations();
        showAnalysisLoading(false);
        // 强制终止后端分析进程（不等待响应）
        fetch(`${API_BASE}/analyze/cancel`, { method: 'POST' }).catch(() => { });
    }

    // 重置操作完成状态（新图书需要重新进行各项操作）
    resetBookOperationStatus();

    // 立即开始加载新书籍的封面 - 在其他操作之前优先加载
    // 这确保封面请求尽早发出，不会被其他操作延迟
    loadCover(filename);

    currentBook = filename;
    window.currentBook = filename;
    window.currentBookPath = null;
    window.currentBookFilename = filename;
    if (typeof window.updatePreviewButton === 'function') {
        window.updatePreviewButton(filename);
    }
    renderBookList();

    closeCoverZoom();

    emptyStateEl.classList.add('hidden');
    bookDetailEl.classList.remove('hidden');

    currentFilenameEl.textContent = filename;
    const bookObj = currentMode === 'manage'
        ? libraryBooks.find(b => b.name === filename)
        : books.find(b => b.name === filename);

    const size = bookObj && bookObj.size ? bookObj.size : '未知';
    const mtime = bookObj && bookObj.mtime ? bookObj.mtime : '未知';
    currentParsedInfoEl.textContent = `大小: ${size} | 修改时间: ${mtime} | 类型: ${filename.split('.').pop().toUpperCase()}`;

    // 隐藏分析结果和增强信息（即使在顺序模式下也要清空，避免显示上一本书的内容）
    analysisResultEl.classList.add('hidden');

    // 清空增强信息区域，避免显示上一本书的内容
    const summaryResultEl = document.getElementById('ai-summary-result');
    if (summaryResultEl) summaryResultEl.classList.add('hidden');

    // 加载该书的目录数据（如果已存在）
    if (typeof window.loadTocForBook === 'function') {
        window.loadTocForBook(filename);
    }

    if (!skipReset) {
        if (currentMode === 'manage') {
            aiSummaryEl.textContent = bookObj && bookObj.has_enhanced_summary ? "已增强 (请实现详情加载)" : "未增强";
        } else {
            aiSummaryEl.textContent = "等待分析...";
        }

        suggestionListEl.innerHTML = '';
    }

    analysisLoadingEl.classList.add('hidden');

    // Show/Hide buttons based on mode
    if (currentMode === 'manage') {
        skipBtn.classList.add('hidden');
        deleteBtn.classList.add('hidden');
    } else {
        skipBtn.classList.remove('hidden');
        deleteBtn.classList.remove('hidden');

        // 根据图书状态动态切换跳过按钮文本
        if (bookObj && bookObj.status === 'skipped') {
            skipBtn.innerHTML = '<i class="fa-solid fa-rotate-left"></i> 取消跳过';
            skipBtn.classList.add('unskip-mode');
        } else {
            skipBtn.innerHTML = '<i class="fa-solid fa-forward"></i> 跳过';
            skipBtn.classList.remove('unskip-mode');
        }
    }

    const similarContainer = document.getElementById('similar-files-container');
    if (similarContainer) {
        similarContainer.remove();
    }

    // Note: loadCover is now called earlier in this function (right after aborting analysis)

    // 在顺序模式下不清空元数据字段（会立即被 AI 分析填充）
    if (!skipReset) {
        document.getElementById('meta-title').value = '';
        document.getElementById('meta-author').value = '';
        document.getElementById('meta-publisher').value = '';
        document.getElementById('meta-series').value = '';
        document.getElementById('meta-tags').value = '';
    }
    document.getElementById('meta-filename').value = filename;
    currentBookFilename = filename;
    window.currentBookFilename = filename;

    // Note: metadataIdentified is reset via resetBookOperationStatus() at the top of this function
    window.currentBookSummary = '';

    // 在顺序模式下跳过异步加载内部元数据（AI 分析会处理）
    if (!skipReset) {
        const requestedBook = filename;
        window.loadInternalMetadata(filename).then(metadata => {
            if (window.isCurrentBookTarget && !window.isCurrentBookTarget(requestedBook)) {
                return;
            }
            if (!metadata) {
                const summaryResultEl = document.getElementById('ai-summary-result');
                if (summaryResultEl) summaryResultEl.classList.add('hidden');
                return;
            }

            // 后端会自动在数据库与文件内置三段简介之间选择有效版本。
            // 文件 description 仅作为兜底，避免旧数据库遮住新版内置简介。
            const summaryToRender = metadata.db_summary || metadata.description || '';
            if (summaryToRender) {
                renderEnhancedSummary(summaryToRender, false, {
                    selectedSource: metadata.summary_source || 'auto',
                    databaseSummary: metadata.db_summary_raw || metadata.db_summary || '',
                    embeddedSummary: metadata.embedded_summary || ''
                });
            } else {
                const summaryResultEl = document.getElementById('ai-summary-result');
                if (summaryResultEl) summaryResultEl.classList.add('hidden');
            }
        });
    }

    // Set Save button to disabled/inactive by default when a book is selected
    const btnSave = document.getElementById('btn-save');
    if (btnSave) {
        btnSave.className = 'btn-save-inactive';
        btnSave.disabled = true;
        btnSave.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> 保存';
    }

    // 更新导出按钮可见性（仅 EPUB 且 Calibre 可用时显示）
    if (window.updateConvertPdfButton) {
        window.updateConvertPdfButton();
    }
}

// ============================================================================
// 分析结果渲染
// ============================================================================

function renderAnalysisResult(data, enhancedSummary = null) {
    analysisResultEl.classList.remove('hidden');
    analysisResultEl.classList.remove('hidden');
    // Display original short summary in AI Analysis section
    aiSummaryEl.textContent = data.summary || "无简介";

    // Auto-fill metadata inputs if available
    if (data.metadata) {
        const m = data.metadata;
        if (m.title) document.getElementById('meta-title').value = m.title;
        if (m.author) document.getElementById('meta-author').value = m.author;
        if (m.publisher) document.getElementById('meta-publisher').value = m.publisher;
        if (m.series) document.getElementById('meta-series').value = m.series;
        if (m.tags) document.getElementById('meta-tags').value = m.tags;

        // Update filename preview
        if (window.applyFilenameTemplate) {
            window.applyFilenameTemplate();
        }

        // Enable save button after AI fills metadata
        const btnSave = document.getElementById('btn-save');
        if (btnSave) {
            btnSave.disabled = false;
            btnSave.className = 'btn-success';
        }
    }

    // Display enhanced summary in the dedicated section if available
    // enhancedSummary is passed separately, not from data.summary
    if (enhancedSummary) {
        // Display enhanced summary WITHOUT enabling save button
        // (enableSave = false, so user must manually save)
        renderEnhancedSummary(enhancedSummary, false);
    } else {
        // Hide enhanced summary section if no enhanced summary
        const summaryResultEl = document.getElementById('ai-summary-result');
        if (summaryResultEl) summaryResultEl.classList.add('hidden');
        const emptyState = document.querySelector('.empty-ai-state');
        if (emptyState) emptyState.classList.remove('hidden');
    }

    suggestionListEl.innerHTML = '';
    if (data.suggestions && data.suggestions.length > 0) {
        data.suggestions.forEach(path => {
            const li = document.createElement('li');
            li.className = 'suggestion-item';
            li.innerHTML = `
                <span class="path-text">${escapeHtml(path)}</span>
                <button class="btn-move" onclick="moveBook('${path.replace(/'/g, "\\'")}')">移动</button>
            `;
            suggestionListEl.appendChild(li);
        });
    } else {
        suggestionListEl.innerHTML = '<li class="empty-suggestion">无推荐目录</li>';
    }
}

function renderDirectoryList(items) {
    pickerListEl.innerHTML = '';
    items.forEach(item => {
        const div = document.createElement('div');
        div.className = 'dir-item';
        div.innerHTML = `<i class="fa-solid fa-folder"></i> ${escapeHtml(item.name)}`;
        div.onclick = () => {
            const newPath = item.name === '..' ? item.path : item.path;
            browseDirectory(newPath);
        };
        pickerListEl.appendChild(div);
    });
}

function displaySimilarFiles(matches) {
    const oldContainer = document.getElementById('similar-files-container');
    if (oldContainer) oldContainer.remove();

    const container = document.createElement('div');
    container.id = 'similar-files-container';
    container.className = 'similar-files-container';

    const title = document.createElement('div');
    title.className = 'similar-files-title';

    // Build count badge with tooltip showing all other similar books
    let countBadge = '';
    if (matches.length > 1) {
        const otherMatches = matches.slice(1);
        const duplicateList = otherMatches.map(d =>
            `${escapeHtml(d.filename)}<br><span class="path-subtitle">${escapeHtml(d.path)}</span>`
        ).join('<br><br>');
        const tooltipContent = `<strong>其他相似图书 (${otherMatches.length})：</strong><br><br>${duplicateList}`;
        countBadge = `<span class="count-badge has-tooltip duplicate-warning" data-tooltip="${tooltipContent.replace(/"/g, '&quot;')}">+${matches.length - 1}</span>`;
    }

    title.innerHTML = `<i class="fa-solid fa-exclamation-triangle"></i> 发现相似图书`;
    container.appendChild(title);

    const match = matches[0];
    const fileInfo = document.createElement('div');
    fileInfo.className = 'similar-file-info';
    fileInfo.innerHTML = `
        <div>
            <div><strong>${escapeHtml(match.filename)}</strong> ${countBadge}</div>
            <div class="similar-file-path">${escapeHtml(match.path)}</div>
        </div>
    `;
    container.appendChild(fileInfo);

    const parsedInfo = document.getElementById('current-parsed-info');
    if (parsedInfo && parsedInfo.parentNode) {
        parsedInfo.parentNode.insertBefore(container, parsedInfo.nextSibling);
    }
}

// ============================================================================
// 统计和封面
// ============================================================================

function updateStats() {
    if (!statTotalEl) return;
    const total = books.length;
    const skipped = books.filter(b => b.status === 'skipped').length;

    statTotalEl.textContent = total;
    statSkippedEl.textContent = skipped;
}

// 当前正在加载的封面文件名，用于防止竞态条件
let currentCoverFilename = null;
let currentCoverAbortController = null;
// 持有当前有效的封面 Blob URL，避免被立即回收导致放大功能失效
let activeCoverBlobUrl = null;

function loadCover(filename) {
    console.log('[loadCover] Called for:', filename);

    // 返回Promise以便外部可以等待
    return new Promise((resolve) => {
        // 如果正在加载同一本书的封面，并且封面已经显示，则跳过重新加载
        if (currentCoverFilename === filename && !bookCoverEl.classList.contains('hidden')) {
            console.log('[loadCover] Already loaded, skipping');
            resolve(true);
            return;
        }

        // 取消之前的封面请求
        if (currentCoverAbortController) {
            console.log('[loadCover] Aborting previous cover request');
            currentCoverAbortController.abort();
        }

        // 记录当前正在加载的文件名
        currentCoverFilename = filename;
        currentCoverAbortController = new AbortController();

        // 核心修复：清理上一个封面的 Blob URL (如果存在)，防止内存泄漏
        // 必须在开始新加载前清理，而不是在当前图片加载后清理，以支持点击放大
        if (activeCoverBlobUrl) {
            URL.revokeObjectURL(activeCoverBlobUrl);
            activeCoverBlobUrl = null;
        }

        // 先设置占位符
        bookCoverEl.classList.add('hidden');
        bookIconPlaceholderEl.classList.remove('hidden');

        // 根据文件扩展名设置正确的图标
        const iconEl = document.getElementById('book-type-icon');
        if (iconEl) {
            const ext = filename.split('.').pop().toLowerCase();
            if (ext === 'epub') {
                iconEl.className = 'fa-solid fa-book';
            } else if (ext === 'mobi' || ext === 'azw3' || ext === 'azw') {
                iconEl.className = 'fa-brands fa-amazon';
            } else if (ext === 'pdf') {
                iconEl.className = 'fa-solid fa-file-pdf';
            } else if (ext === 'md' || ext === 'markdown') {
                iconEl.className = 'fa-brands fa-markdown';
            } else if (ext === 'txt') {
                iconEl.className = 'fa-solid fa-file-lines';
            } else {
                iconEl.className = 'fa-solid fa-file';
            }
            iconEl.style.color = ''; // 重置颜色
            iconEl.title = ''; // 重置提示
        }

        const encodedName = encodeURIComponent(filename);
        // 添加时间戳避免浏览器缓存问题
        const coverUrl = `/api/cover/${encodedName}?t=${Date.now()}`;
        console.log('[loadCover] Loading from:', coverUrl);

        // 使用 fetch API 来获得更好的控制
        // priority: 'high' 告诉浏览器优先处理此请求
        fetch(coverUrl, {
            signal: currentCoverAbortController.signal,
            priority: 'high',
            cache: 'no-store'
        })
            .then(response => {
                if (!response.ok) throw new Error('Cover not found');
                return response.blob();
            })
            .then(blob => {
                console.log('[loadCover] Cover loaded, currentCoverFilename:', currentCoverFilename);
                // 检查是否仍在加载同一本书
                if (currentCoverFilename !== filename) {
                    console.log('[loadCover] Book changed during load, ignoring stale response');
                    resolve(false);
                    return;
                }
                // 创建 blob URL 并设置到封面元素
                const blobUrl = URL.createObjectURL(blob);
                activeCoverBlobUrl = blobUrl; // 保存引用，保持 URL 有效

                // 修复：移除 onload 中的自动清理，改为手动管理生命周期
                // 这样 zoom.js 才能复用这个 Blob URL 实现秒开
                bookCoverEl.onload = null;
                bookCoverEl.src = blobUrl;
                bookCoverEl.classList.remove('hidden');
                bookIconPlaceholderEl.classList.add('hidden');
                console.log('[loadCover] Cover displayed successfully');
                resolve(true);
            })
            .catch(error => {
                if (error.name === 'AbortError') {
                    console.log('[loadCover] Cover request aborted');
                    resolve(false);
                    return;
                }
                console.log('[loadCover] Cover load error:', error);
                if (currentCoverFilename !== filename) {
                    resolve(false);
                    return;
                }
                // Keep placeholder but update icon to indicate potential sync issue
                const iconEl = document.getElementById('book-type-icon');
                if (iconEl) {
                    iconEl.className = 'fa-solid fa-cloud-arrow-down';
                    iconEl.style.color = 'var(--text-muted)';
                    iconEl.title = '预览不可用 (文件可能未下载)';
                }
                resolve(false);
            });
    });
}

// ============================================================================
// 配置 UI
// ============================================================================

function updateConfigUI() {
    document.getElementById('cfg-source').value = config.source_dir || '';
    document.getElementById('cfg-target').value = config.target_dir || '';
    document.getElementById('cfg-data-dir').value = config.data_dir || '';

    updateModelCard('gemini', config.gemini);
    updateModelCard('deepseek', config.deepseek);
    updateModelCard('ollama', config.ollama);

    const beta = config.beta_features || {};
    document.getElementById('beta-similar-search').checked = beta.enable_similar_search || false;
    document.getElementById('beta-metadata-write-epub').checked = beta.enable_metadata_write_epub || false;
    document.getElementById('beta-summary-write-epub').checked = beta.enable_summary_write_epub || false;
    document.getElementById('beta-metadata-write-pdf').checked = beta.enable_metadata_write_pdf || false;
    document.getElementById('beta-summary-write-pdf').checked = beta.enable_summary_write_pdf || false;

    // PDF 导出目录
    const pdfExportDirEl = document.getElementById('cfg-pdf-export-dir');
    if (pdfExportDirEl) {
        pdfExportDirEl.value = beta.pdf_export_dir || '';
    }

    // 数据优先级按钮组
    const priorityValue = beta.data_priority || 'database';
    const priorityGroup = document.getElementById('beta-data-priority-group');
    if (priorityGroup) {
        priorityGroup.querySelectorAll('.btn-toggle').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.value === priorityValue);
        });
    }
}

function updateModelCard(provider, modelConfig) {
    const statusEl = document.getElementById(`status-${provider}`);
    const keyInput = document.getElementById(`cfg-${provider}-key`);
    const urlInput = document.getElementById(`cfg-${provider}-url`);
    const modelSelect = document.getElementById(`cfg-${provider}-model`);

    if (modelConfig && modelConfig.model_name) {
        statusEl.textContent = `已配置: ${modelConfig.model_name}`;
        statusEl.classList.add('active');

        if (keyInput) keyInput.value = modelConfig.api_key || modelConfig.api_key_masked || '';
        if (urlInput) urlInput.value = modelConfig.url || '';

        if (modelConfig.model_name) {
            modelSelect.innerHTML = `<option value="${escapeHtml(modelConfig.model_name)}">${escapeHtml(modelConfig.model_name)}</option>`;
            modelSelect.value = modelConfig.model_name;
        }
    } else {
        statusEl.textContent = '未配置';
        statusEl.classList.remove('active');
        if (keyInput) keyInput.value = '';
        if (urlInput) urlInput.value = '';
        modelSelect.innerHTML = '<option value="">请先验证</option>';
    }
}

// ============================================================================
// Tooltip
// ============================================================================

function initGlobalTooltip() {
    let tooltip = document.getElementById('global-tooltip');
    if (!tooltip) {
        tooltip = document.createElement('div');
        tooltip.id = 'global-tooltip';
        tooltip.className = 'global-tooltip';
        document.body.appendChild(tooltip);
    }

    let activeElement = null;

    document.addEventListener('mouseover', (e) => {
        const target = e.target.closest('.has-tooltip');
        if (target) {
            activeElement = target;
            const content = target.dataset.tooltip;
            const isWarning = target.classList.contains('duplicate-warning');

            if (content) {
                tooltip.innerHTML = content;
                if (isWarning) {
                    tooltip.classList.add('warning');
                } else {
                    tooltip.classList.remove('warning');
                }
                tooltip.classList.toggle('header-tooltip', target.classList.contains('btn-icon-only'));

                const isEnabledState = target.classList.contains('active') || content.includes('已开启');
                if (isEnabledState) {
                    tooltip.classList.add('active');
                } else {
                    tooltip.classList.remove('active');
                }

                tooltip.classList.add('visible');
                updateTooltipPosition(target, tooltip);
            }
        }
    });

    document.addEventListener('mouseout', (e) => {
        const target = e.target.closest('.has-tooltip');
        if (target && target === activeElement) {
            activeElement = null;
            tooltip.classList.remove('visible');
        }
    });

    window.addEventListener('scroll', () => {
        if (activeElement) {
            tooltip.classList.remove('visible');
            activeElement = null;
        }
    }, true);
}

function updateTooltipPosition(target, tooltip) {
    const rect = target.getBoundingClientRect();
    const tooltipRect = tooltip.getBoundingClientRect();

    // Check if target is a header icon button or AI config button - tooltip goes below
    const isHeaderIcon = target.classList.contains('btn-icon-only');
    const isAIConfigBtn = target.id === 'ai-config-btn';
    const showBelow = isHeaderIcon || isAIConfigBtn;

    // Add special class for AI config tooltip
    if (isAIConfigBtn) {
        tooltip.classList.add('ai-config-tooltip');
    } else {
        tooltip.classList.remove('ai-config-tooltip');
    }

    let top, left;

    if (showBelow) {
        // Position below the icon
        top = rect.bottom + 8;
        left = rect.left + (rect.width / 2) - (tooltipRect.width / 2);

        // Keep within viewport
        if (left < 10) left = 10;
        if (left + tooltipRect.width > window.innerWidth - 10) {
            left = window.innerWidth - tooltipRect.width - 10;
        }
    } else {
        // Default: position to the right
        top = rect.top + (rect.height / 2) - (tooltipRect.height / 2);
        left = rect.right + 12;

        if (left + tooltipRect.width > window.innerWidth - 20) {
            left = rect.left - tooltipRect.width - 12;
        }

        if (top + tooltipRect.height > window.innerHeight - 20) {
            top = window.innerHeight - tooltipRect.height - 20;
        }

        if (top < 20) {
            top = 20;
        }
    }

    tooltip.style.top = `${top}px`;
    tooltip.style.left = `${left}px`;
}

// ============================================================================
// v0.4.0 Library UI
// ============================================================================

// Track expanded folder paths for state preservation
window.expandedLibraryFolders = new Set();

// Helper: Build folder path from parent path and folder name
function buildFolderPath(parentPath, folderName) {
    return parentPath ? `${parentPath}/${folderName}` : folderName;
}

// Helper: Refresh library tree while preserving selection and expansion state
async function refreshLibraryTreeWithState(newPathOverride = null) {
    // 优先使用传入的新路径（如保存后的新文件名），否则使用当前选中路径
    const selectedPath = newPathOverride || currentBook;
    const data = await fetchLibraryBooks();
    if (data) {
        updateLibraryStats();
        renderBookList();
        // Restore selection if still exists
        if (selectedPath) {
            const bookItem = document.querySelector(`.library-book-item[data-path="${CSS.escape(selectedPath)}"]`);
            if (bookItem) {
                bookItem.classList.add('active');
                bookItem.scrollIntoView({ block: 'nearest' });
            }
        }
    }
}
window.refreshLibraryTreeWithState = refreshLibraryTreeWithState;

// Helper: Update library stats display
function updateLibraryStats() {
    const libTotalEl = document.getElementById('lib-total');
    const libEnhancedEl = document.getElementById('lib-enhanced');
    const libNotEnhancedEl = document.getElementById('lib-not-enhanced');
    if (libTotalEl) libTotalEl.textContent = libraryStats.total;
    if (libEnhancedEl) libEnhancedEl.textContent = libraryStats.enhanced;
    if (libNotEnhancedEl) libNotEnhancedEl.textContent = libraryStats.not_enhanced;
}
window.updateLibraryStats = updateLibraryStats;

async function switchMode(mode) {
    if (mode === currentMode) return;

    // 切换模式时取消所有正在进行的操作
    cancelAllOperations();
    resetBookOperationStatus();

    // 🆕 切换模式时清空搜索条件
    clearSidebarSearch();

    // 同时清除后端分析进程
    fetch(`${API_BASE}/analyze/cancel`, { method: 'POST' }).catch(() => { });

    currentMode = mode;
    window.currentMode = mode;
    currentBook = null;
    currentBookFilename = null;
    window.currentBookPath = null;
    window.currentBook = null;
    window.currentBookFilename = null;
    window.currentBookSummary = '';
    if (typeof window.updatePreviewButton === 'function') {
        window.updatePreviewButton(null);
    }

    // 更新 body 的 data-mode 属性，用于 CSS 控制元素显隐
    document.body.dataset.mode = mode;

    // Update Tabs
    document.getElementById('organize-mode-btn').classList.toggle('active', mode === 'organize');
    document.getElementById('manage-mode-btn').classList.toggle('active', mode === 'manage');

    // Update Stats
    document.getElementById('stats-bar').classList.toggle('hidden', mode !== 'organize');
    document.getElementById('library-stats').classList.toggle('hidden', mode !== 'manage');

    document.getElementById('sidebar-title').innerHTML = mode === 'organize'
        ? '<i class="fa-solid fa-layer-group"></i><span class="badge-text">待入库</span>'
        : '<i class="fa-solid fa-book-bookmark"></i><span class="badge-text">图书馆</span>';

    // 根据模式更新批量下拉菜单内容
    if (typeof updateBatchDropdownForMode === 'function') {
        updateBatchDropdownForMode(mode === 'manage' ? 'library' : 'inbound');
    }

    // 在库管理模式下禁用跳过按钮
    if (skipBtn) {
        if (mode === 'manage') {
            skipBtn.disabled = true;
            skipBtn.classList.add('disabled');
            skipBtn.classList.add('hidden');  // 库管理模式下隐藏
            skipBtn.title = '跳过功能仅在入库整理模式下可用';
        } else {
            skipBtn.disabled = false;
            skipBtn.classList.remove('disabled');
            skipBtn.classList.remove('hidden');
            skipBtn.title = '跳过';
        }
    }

    // 在库管理模式下显示删除按钮
    const deleteBtn = document.getElementById('delete-btn');
    if (deleteBtn) {
        if (mode === 'manage') {
            deleteBtn.classList.remove('hidden');  // 库管理模式显示删除按钮
        } else {
            deleteBtn.classList.add('hidden');  // 入库模式隐藏（由其他逻辑控制）
        }
    }

    // 更新评分组件可见性
    const ratingContainer = document.getElementById('book-rating-container');
    if (ratingContainer) {
        if (mode === 'manage') {
            ratingContainer.classList.remove('hidden');
        } else {
            ratingContainer.classList.add('hidden');
        }
    }

    // Logic Switch
    if (mode === 'manage') {
        const data = await fetchLibraryBooks();
        if (data) {
            document.getElementById('lib-total').textContent = libraryStats.total;
            document.getElementById('lib-enhanced').textContent = libraryStats.enhanced;
            document.getElementById('lib-not-enhanced').textContent = libraryStats.not_enhanced;
            renderBookList();
        }
    } else {
        renderBookList();
    }

    // 更新标签文本（根据模式和数据源显示不同文本）
    if (typeof window.updateContentTabLabels === 'function') {
        window.updateContentTabLabels();
    }
}


function renderLibraryTree(books) {
    if (!books || books.length === 0) {
        bookListEl.innerHTML = '<div style="text-align:center; padding:20px; color:var(--text-muted)">图书馆为空</div>';
        return;
    }

    // 应用筛选过滤
    let filteredBooks = books;
    if (currentStatsFilter === 'enhanced') {
        filteredBooks = books.filter(b => b.has_enhanced_summary);
    } else if (currentStatsFilter === 'not_enhanced') {
        filteredBooks = books.filter(b => !b.has_enhanced_summary);
    }

    // 🆕 应用搜索过滤（在库模式：搜索文件名 + 元数据 + 评分）
    if (window.sidebarSearchQuery) {
        let query = window.sidebarSearchQuery.trim();

        // 1. 提取评分过滤指令 (+0 到 +5)
        let targetRating = null;
        const ratingMatch = query.match(/\+(\d)/);
        if (ratingMatch) {
            const val = parseInt(ratingMatch[1]);
            if (val >= 0 && val <= 5) {
                targetRating = val;
                // 从查询字符串中移除评分指令，只保留关键词
                query = query.replace(/\+\d/, '').trim();
            }
        }

        const keywords = query.toLowerCase().split(/\s+/).filter(k => k);

        filteredBooks = filteredBooks.filter(book => {
            // A. 评分过滤 (如果有)
            if (targetRating !== null) {
                const bookRating = book.rating || 0; // Normalize null/undefined to 0
                if (bookRating !== targetRating) {
                    return false;
                }
            }

            // B. 关键词过滤 (如果有)
            if (keywords.length === 0) return true; // 只搜了评分

            // 搜索字段：文件名、书名、作者、出版社、标签
            const searchableText = [
                book.name || '',
                book.title || '',
                book.author || '',
                book.publisher || '',
                ...(book.tags || [])
            ].join(' ').toLowerCase();

            return keywords.every(kw => searchableText.includes(kw));
        });
    }

    // 更新全局过滤列表，供批量选择使用
    window.currentFilteredLibraryBooks = filteredBooks;

    if (filteredBooks.length === 0) {
        bookListEl.innerHTML = '<div style="text-align:center; padding:20px; color:var(--text-muted)">无匹配图书</div>';
        return;
    }

    const treeData = buildLibraryTree(filteredBooks);
    const treeContainer = document.createElement('div');
    treeContainer.className = 'library-tree';

    // Render Root Files first (if any) or just render children
    // Usually books are in subfolders.

    renderRecursiveTree(treeData, treeContainer, 0);

    bookListEl.innerHTML = '';
    bookListEl.appendChild(treeContainer);

    // 渲染完成后，根据已选文件更新文件夹复选框状态
    if (typeof window.updateFolderCheckboxStates === 'function') {
        window.updateFolderCheckboxStates();
    }
}

function buildLibraryTree(books) {
    const root = { name: "root", children: {}, files: [] };

    books.forEach(book => {
        const parts = book.category === 'Uncategorized' || book.category === '.'
            ? []
            : book.category.split('/').filter(p => p && p !== '.');

        let current = root;
        parts.forEach(part => {
            if (!current.children[part]) {
                current.children[part] = { name: part, children: {}, files: [], count: 0 };
            }
            current = current.children[part];
        });

        current.files.push(book);

        // Update counts up the tree? Or just local count?
        // Let's keep smooth local count.
    });

    // Helper to calculate total count recursively
    function calcCount(node) {
        let total = node.files.length;
        Object.values(node.children).forEach(child => {
            total += calcCount(child);
        });
        node.totalCount = total;
        return total;
    }
    calcCount(root);

    return root;
}

function renderRecursiveTree(node, container, level, parentPath = '') {
    // 1. Render Folders
    const sortedFolders = Object.keys(node.children).sort();

    sortedFolders.forEach(folderName => {
        const childNode = node.children[folderName];
        const folderPath = buildFolderPath(parentPath, folderName);
        const folderId = 'folder-' + folderPath.replace(/[^a-zA-Z0-9]/g, '_');

        const folderDiv = document.createElement('div');
        folderDiv.className = 'library-folder';
        folderDiv.dataset.folderPath = folderPath;
        // Padding based on level
        folderDiv.style.paddingLeft = `${15 + (level * 15)}px`;

        folderDiv.innerHTML = `
            <input type="checkbox" class="folder-checkbox" data-folder-path="${escapeHtml(folderPath)}" onclick="event.stopPropagation(); toggleFolderSelection('${folderPath.replace(/'/g, "\\'")}', this.checked)">
            <span class="folder-icon"><i class="fa-solid fa-folder"></i></span>
            <span class="folder-name" title="${escapeHtml(folderName)}">${escapeHtml(folderName)}</span>
            <span class="folder-count">${childNode.totalCount}</span>
            <i class="fa-solid fa-chevron-right folder-arrow"></i>
        `;

        const subItemsDiv = document.createElement('div');
        subItemsDiv.id = folderId;
        subItemsDiv.className = 'library-subitems';

        // Check if this folder should be expanded (from saved state or default for level < 1)
        const shouldExpand = window.expandedLibraryFolders.has(folderPath) ||
            (level < 1 && window.expandedLibraryFolders.size === 0);

        if (shouldExpand) {
            folderDiv.classList.add('expanded');
            subItemsDiv.classList.add('expanded');
            window.expandedLibraryFolders.add(folderPath);
        }

        folderDiv.onclick = (e) => {
            e.stopPropagation();
            const isExpanded = folderDiv.classList.toggle('expanded');
            subItemsDiv.classList.toggle('expanded');
            // Track expansion state
            if (isExpanded) {
                window.expandedLibraryFolders.add(folderPath);
            } else {
                window.expandedLibraryFolders.delete(folderPath);
            }
        };

        container.appendChild(folderDiv);
        container.appendChild(subItemsDiv);

        // Recurse with folder path
        renderRecursiveTree(childNode, subItemsDiv, level + 1, folderPath);
    });

    // 2. Render Files
    node.files.sort((a, b) => a.name.localeCompare(b.name)).forEach(book => {
        const itemDiv = document.createElement('div');
        itemDiv.className = 'library-book-item';
        itemDiv.dataset.path = book.path; // Add data attribute for selection restoration
        // Padding: level + 1 (files are inside the folder)
        itemDiv.style.paddingLeft = `${15 + ((level + 1) * 15)}px`;

        if (currentBook === book.path) {
            itemDiv.classList.add('active');
            // Auto scroll to active item?
            setTimeout(() => itemDiv.scrollIntoView({ block: 'nearest' }), 100);
        }

        // Add enhanced class for green text styling
        if (book.has_enhanced_summary) {
            itemDiv.classList.add('has-enhanced');
        }

        // 增强简介图标（与抬头增强模式图标一致）
        const enhancedIcon = book.has_enhanced_summary
            ? '<i class="fa-solid fa-file-lines enhanced-icon" title="已增强"></i>'
            : '';

        // 目录图标
        const tocIcon = book.has_toc
            ? '<i class="fa-solid fa-list-ol toc-icon" title="有目录"></i>'
            : '';

        // 评分图标逻辑 (星号内嵌数字)
        // 默认图标 (灰色实心星 或 绿色实心星 - 由 CSS .library-book-item.has-enhanced .item-icon 控制颜色)
        // 如果有评分，在星号中间显示数字
        let iconHtml = '';
        const rating = book.rating;
        const iconClass = book.has_enhanced_summary ? 'fa-solid fa-star' : 'fa-solid fa-star'; // 始终实心，颜色由CSS控制
        const emptyClass = 'fa-regular fa-star'; // 无评分时空心

        if (rating && rating > 0) {
            // 有评分：实心星 + 数字
            iconHtml = `
                <span class="rating-icon-wrapper">
                    <i class="${iconClass} item-icon"></i>
                    <span class="rating-num">${rating}</span>
                </span>`;
        } else {
            // 无评分：空心星 (颜色随状态)
            iconHtml = `<i class="${emptyClass} item-icon"></i>`;
        }

        // 多选 checkbox
        const isSelected = window.selectedLibraryBooks && window.selectedLibraryBooks.has(book.path);
        const checkboxHtml = `<input type="checkbox" class="book-checkbox" data-path="${escapeHtml(book.path)}" ${isSelected ? 'checked' : ''} onclick="event.stopPropagation(); toggleBookSelection('${book.path.replace(/'/g, "\\'")}', this.checked)">`;

        itemDiv.innerHTML = `
            ${checkboxHtml}
            ${iconHtml}
            <span class="book-name-text" title="${escapeHtml(book.name)}">${escapeHtml(book.name)}</span>
            ${enhancedIcon}${tocIcon}
        `;

        itemDiv.onclick = (e) => {
            e.stopPropagation();
            // Remove active from all others
            document.querySelectorAll('.library-book-item').forEach(el => el.classList.remove('active'));
            itemDiv.classList.add('active');
            selectLibraryBook(book);
        };

        container.appendChild(itemDiv);
    });
}

async function selectLibraryBook(book) {
    const requestedBookPath = book.path;
    // 设置全局路径供 app.js 使用 (核心修复)
    window.currentBookPath = requestedBookPath;

    // 重置操作完成状态（新图书需要重新进行各项操作）
    resetBookOperationStatus();

    // 切换书籍时，取消正在进行的请求
    // 注意：顺序模式下不取消分析控制器，以保持顺序处理继续运行
    const activeController = currentAnalysisController || window.currentAnalysisController;
    if (!isSequentialMode && activeController) {
        console.log('[selectLibraryBook] Aborting previous analysis (not in sequential mode)');
        activeController.abort();
        currentAnalysisController = null;
        window.currentAnalysisController = null;
        showAnalysisLoading(false);

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
    if (window.cancelBookScopedTask) {
        window.cancelBookScopedTask('summary-load');
        window.cancelBookScopedTask('toc-load');
        window.cancelBookScopedTask('toc-extract');
        window.cancelBookScopedTask('enhanced-summary');
    }

    // Use relative path for identification
    // CRITICAL: Set BOTH window.currentBook AND module-level currentBook
    window.currentBook = requestedBookPath;
    currentBook = requestedBookPath;  // Sync module-level variable for generateEnhancedSummary etc.
    // Set global currentBookFilename for rating logic
    window.currentBookFilename = book.name;
    currentBookFilename = book.name;  // Sync module-level variable
    if (typeof window.updatePreviewButton === 'function') {
        window.updatePreviewButton(requestedBookPath);
    }
    // If we send basename, backend might fail if file is in subdir.
    // But backend identify_book_metadata logic joins target_dir + filename.
    // If filename is relative path "Sub/foo.pdf", join works.
    // If filename is just "foo.pdf", join works ONLY if file is in root.
    // So we MUST send path.
    // Note: setBookRating now uses window.currentBookPath for file_path.

    // Reset metadata identification flag to ensure "Start Analysis" triggers fresh AI identification
    // Note: metadataIdentified is reset via resetBookOperationStatus() called elsewhere

    // Don't re-render list, just update details

    // Load Details
    closeCoverZoom();
    emptyStateEl.classList.add('hidden');
    bookDetailEl.classList.remove('hidden');

    currentFilenameEl.textContent = book.name;
    const size = book.size ? (book.size / 1024 / 1024).toFixed(2) + ' MB' : '未知';
    currentParsedInfoEl.textContent = `大小: ${size} | 分类: ${book.category}`;

    // Reset inputs to loading state
    document.getElementById('meta-title').value = '...';
    document.getElementById('meta-author').value = '';

    // Render Rating
    renderBookRating(book.rating || 0);
    document.getElementById('meta-publisher').value = '';
    document.getElementById('meta-series').value = '';
    document.getElementById('meta-tags').value = '';

    // Reset Save Button
    const btnSave = document.getElementById('btn-save');
    if (btnSave) {
        btnSave.disabled = true;
        btnSave.className = 'btn-secondary'; // or whatever the disabled class is
    }

    // Hide Analysis Result, Show "Loading..."
    analysisResultEl.classList.add('hidden');
    aiSummaryEl.textContent = "正在获取详情...";
    window.currentBookSummary = '';
    const summaryResultEl = document.getElementById('ai-summary-result');
    if (summaryResultEl) summaryResultEl.classList.add('hidden');
    const summaryEmptyState = document.querySelector('.empty-ai-state');
    if (summaryEmptyState) summaryEmptyState.classList.remove('hidden');

    // Clear previous similar files warning
    const similarFilesContainer = document.getElementById('similar-files-container');
    if (similarFilesContainer) similarFilesContainer.remove();

    // Load Cover with path
    loadCover(requestedBookPath);

    // Fetch details from backend
    const details = await fetchLibraryBookDetails(requestedBookPath);
    if (window.isCurrentBookTarget && !window.isCurrentBookTarget(requestedBookPath)) {
        return;
    }
    if (details) {
        const meta = details.metadata || {};
        document.getElementById('meta-title').value = meta.title || '';
        document.getElementById('meta-author').value = meta.author || '';
        document.getElementById('meta-publisher').value = meta.publisher || '';
        document.getElementById('meta-series').value = meta.series || '';
        document.getElementById('meta-tags').value = meta.tags || '';

        // Update rating from server details (ensure persistence)
        if (details.rating !== undefined) {
            renderBookRating(details.rating);
            // Optionally update the book object in memory for next time
            book.rating = details.rating;
        }

        if (details.summary) {
            renderEnhancedSummary(details.summary, false, {
                selectedSource: details.summary_source || 'database',
                databaseSummary: details.database_summary || '',
                embeddedSummary: details.embedded_summary || ''
            });
        } else {
            aiSummaryEl.textContent = book.has_enhanced_summary ? "已增强 (无简介文本)" : "未分析";
            // Check if we should hide the result element if no summary
            const summaryResultEl = document.getElementById('ai-summary-result');
            if (summaryResultEl && !details.summary) summaryResultEl.classList.add('hidden');
        }

        // Dedicated endpoints own the final source selection. Waiting here prevents
        // the detail response from overwriting a faster summary/TOC response.
        const detailLoads = [];
        if (typeof window.loadTocForBook === 'function') {
            detailLoads.push(window.loadTocForBook(requestedBookPath));
        }
        if (typeof window.loadSummaryForBook === 'function') {
            detailLoads.push(window.loadSummaryForBook(requestedBookPath));
        }
        await Promise.all(detailLoads);
    } else {
        aiSummaryEl.textContent = "获取详情失败 (可能文件不可读)";
        document.getElementById('meta-title').value = '';
    }

    // Update preview
    applyFilenameTemplate();

    // 更新导出按钮可见性（仅 EPUB 且 Calibre 可用时显示）
    if (window.updateConvertPdfButton) {
        window.updateConvertPdfButton();
    }
}

// Make globally available for inline event handlers
window.applyFilenameTemplate = function () {
    const title = document.getElementById('meta-title').value.trim();
    const author = document.getElementById('meta-author').value.trim();
    const publisher = document.getElementById('meta-publisher').value.trim();
    const series = document.getElementById('meta-series').value.trim();
    const tags = document.getElementById('meta-tags').value.trim();

    // Try to get template from global config or default
    let template = "{title} - {author}";
    try {
        if (window.aiConfig && window.aiConfig.filename_template) {
            template = window.aiConfig.filename_template;
        }
    } catch (e) {
        console.warn("Error reading aiConfig:", e);
    }

    let newName = template
        .replace('{title}', title || '未命名')
        .replace('{author}', author || '佚名')
        .replace('{publisher}', publisher)
        .replace('{series}', series)
        .replace('{tags}', tags);

    // Extension
    let ext = "";
    if (currentBook) {
        const lastDotIndex = currentBook.lastIndexOf('.');
        if (lastDotIndex > 0) {
            ext = currentBook.substring(lastDotIndex);
        }
    }

    // Simple cleanup of empty brackets/double spaces
    // Remove empty brackets like [] () caused by missing optional fields
    newName = newName.replace(/\[\s*\]/g, '').replace(/\(\s*\)/g, '').replace(/（\s*）/g, '');

    // Remove double spaces
    newName = newName.replace(/\s+/g, ' ').trim();

    const finalName = newName + ext;
    const metaFilenameEl = document.getElementById('meta-filename');
    if (metaFilenameEl) {
        metaFilenameEl.value = finalName;
        // console.log("Filename preview updated:", finalName);
    }
};

// This function is assumed to be the main initialization function,
// based on the user's provided context for the change.
// Enhanced mode initialization is now handled by app.js init() function to avoid conflicts.
// The initEnhancedMode function remains available globally.


// ============================================================================
// Enhanced Mode Initialization (Backend-Based Persistence)
// ============================================================================

async function initEnhancedMode() {
    const btn = document.getElementById('enhanced-mode-btn');
    const icon = document.querySelector('#enhanced-mode-btn i');
    const text = document.getElementById('enhanced-mode-text');
    const genBtn = document.getElementById('btn-gen-summary');

    if (!btn || !icon || !text) return;

    let isEnabled = false;

    try {
        // Load from backend instead of localStorage
        const res = await fetch(`${API_BASE}/user_preferences`);
        const prefs = await res.json();
        isEnabled = prefs.enhancedModeEnabled;
    } catch (e) {
        console.error('Failed to load enhanced mode preference:', e);
        isEnabled = false; // default
    }

    // Apply initial state
    if (isEnabled) {
        btn.classList.add('active');
        icon.className = 'fa-solid fa-wand-magic-sparkles';
        text.textContent = '已开启增强';
        if (genBtn) {
            genBtn.disabled = false;
            genBtn.className = 'btn-primary';
            genBtn.title = '生成增强简介';
        }
    } else {
        btn.classList.remove('active');
        icon.className = 'fa-solid fa-wand-magic-sparkles';
        text.textContent = '已关闭增强';
        if (genBtn) {
            genBtn.disabled = true;
            genBtn.className = 'btn-secondary';
            genBtn.title = '需开启增强模式';
        }
    }

    // Toggle handler
    btn.addEventListener('click', async () => {
        isEnabled = !isEnabled;

        if (isEnabled) {
            btn.classList.add('active');
            icon.className = 'fa-solid fa-wand-magic-sparkles';
            text.textContent = '已开启增强';
            if (genBtn) {
                genBtn.disabled = false;
                genBtn.className = 'btn-primary';
                genBtn.title = '生成增强简介';
            }
        } else {
            btn.classList.remove('active');
            icon.className = 'fa-solid fa-wand-magic-sparkles';
            text.textContent = '已关闭增强';
            if (genBtn) {
                genBtn.disabled = true;
                genBtn.className = 'btn-secondary';
                genBtn.title = '需开启增强模式';
            }
        }

        try {
            // Save to backend instead of localStorage
            await fetch(`${API_BASE}/user_preferences`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enhancedModeEnabled: isEnabled })
            });
        } catch (e) {
            console.error('Failed to save enhanced mode preference:', e);
        }

        if (window.updateAIStatusIndicators) window.updateAIStatusIndicators();
    });
}
window.initEnhancedMode = initEnhancedMode;


// Metadata Input Handler (Wrapper) - Enable save button when user modifies metadata
function handleMetadataInput() {
    // 标记用户手动编辑过元数据（用于智能联动）
    if (window.bookOperationStatus) {
        window.bookOperationStatus.metadataManuallyEdited = true;
    }

    // Enable save button when metadata changes
    const btnSave = document.getElementById('btn-save');
    if (btnSave) {
        btnSave.disabled = false;
        btnSave.className = 'btn-success';
    }

    if (window.applyFilenameTemplate) {
        window.applyFilenameTemplate();
    }
}

// Generate Enhanced Summary UI Handler
async function generateEnhancedSummary() {
    if (!currentBook) {
        alert('请先选择一本图书');
        return;
    }
    const targetBook = currentBook;

    const summaryResultEl = document.getElementById('ai-summary-result');
    const emptyState = document.querySelector('.empty-ai-state');
    const btn = document.getElementById('btn-gen-summary');

    if (!btn || !summaryResultEl) return;

    // 如果正在生成中且用户点击，则取消操作
    if (btn.classList.contains('analyzing')) {
        // 取消当前正在进行的请求
        if (currentEnhancedSummaryController || window.currentEnhancedSummaryController) {
            (currentEnhancedSummaryController || window.currentEnhancedSummaryController).abort();
            currentEnhancedSummaryController = null;
            window.currentEnhancedSummaryController = null;
        }
        btn.innerHTML = '<i class="fa-solid fa-file-lines"></i> 增强简介';
        btn.classList.remove('analyzing');
        showNotification('已取消生成', 2000);
        if (emptyState) emptyState.classList.remove('hidden');
        summaryResultEl.classList.add('hidden');
        return;
    }

    // 互斥：检查是否有其他操作正在进行，需要用户确认
    const activeOp = getActiveOperation();
    if (activeOp) {
        const confirmed = await confirmCancelOperation('增强简介生成');
        if (!confirmed) return;
    }

    // 取消其他正在进行的操作
    cancelAllOperations();

    // UI Loading - don't disable, let user click to cancel
    const originalText = btn.innerHTML;
    if (window.showEnhancedSummaryLoading) {
        window.showEnhancedSummaryLoading(targetBook, '增强简介生成中，完成后会自动刷新...');
    } else {
        btn.innerHTML = '<div class="spinner-small"></div> 生成中... <i class="fa-solid fa-stop" style="margin-left:4px"></i>';
        btn.classList.add('analyzing');
        if (emptyState) emptyState.classList.add('hidden');
        summaryResultEl.classList.remove('hidden');
    }

    try {
        // Call API (defined in api.js)
        const engine = document.getElementById('engine-select').value;
        const data = await window.fetchEnhancedSummary(targetBook, engine, window.currentMode);

        if (window.isCurrentBookTarget && !window.isCurrentBookTarget(targetBook)) {
            return;
        }

        if (data && data.summary) {
        renderEnhancedSummary(data.summary, true, {
            selectedSource: data.source || 'database',
            databaseSummary: data.database_summary || data.summary || '',
            embeddedSummary: data.embedded_summary || ''
        });

            // CRITICAL: Update global state so saveMetadata() picks it up
            window.currentBookSummary = data.summary;
            enableSaveButton(); // Ensure user can save the new summary

            showNotification('增强简介生成成功');
            // 设置操作完成状态（用于智能联动）
            bookOperationStatus.summaryGenerated = true;
        } else {
            const warning = data && data.warning ? data.warning : '生成结果为空';
            if (window.renderEnhancedSummaryWarning) {
                window.renderEnhancedSummaryWarning(warning, targetBook);
            } else {
                summaryResultEl.innerHTML = '<p style="color:var(--warning-color); padding:20px; text-align:center;">生成结果为空</p>';
            }
        }
    } catch (e) {
        if (e.name === 'AbortError') {
            return;
        }
        console.error(e);
        const message = formatApiErrorMessage(e, '增强简介生成失败');
        showNotification(`生成失败: ${message}`, 5000, 'error');
        if (window.renderEnhancedSummaryWarning) {
            window.renderEnhancedSummaryWarning(message, targetBook);
        }
    } finally {
        // api.js handles controller cleanup
        if (window.clearEnhancedSummaryLoading) {
            window.clearEnhancedSummaryLoading(targetBook);
        } else {
            btn.innerHTML = originalText;
            btn.classList.remove('analyzing');
        }
    }
}

function parseMarkdown(text) {
    if (!text) return '';
    let html = text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");

    // Bold
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/__(.*?)__/g, '<strong>$1</strong>');

    // Italic
    html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');

    // Process lines for lists and paragraphs
    const lines = html.split('\n');
    let inList = false;
    let result = '';

    lines.forEach(line => {
        const trimmed = line.trim();
        // List items
        if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
            if (!inList) {
                result += '<ul>';
                inList = true;
            }
            result += `<li>${trimmed.substring(2)}</li>`;
        } else {
            if (inList) {
                result += '</ul>';
                inList = false;
            }

            // Headings (basic manual parsing)
            if (trimmed.startsWith('### ')) {
                result += `<h4>${trimmed.substring(4)}</h4>`;
            } else if (trimmed.startsWith('## ')) {
                result += `<h3>${trimmed.substring(3)}</h3>`;
            } else if (trimmed.startsWith('# ')) {
                result += `<h2>${trimmed.substring(2)}</h2>`;
            } else if (trimmed) {
                result += `<p>${trimmed}</p>`;
            }
        }
    });

    if (inList) result += '</ul>';

    return result;
}

function renderSummarySourceSwitcher(sourceData = {}) {
    if (window.setContentSourceButtons) {
        window.setContentSourceButtons('summary', sourceData.selectedSource || 'database');
    }
    const databaseSummary = sourceData.databaseSummary || '';
    const embeddedSummary = sourceData.embeddedSummary || '';
    const hasDatabase = Boolean(databaseSummary.trim());
    const hasEmbedded = Boolean(embeddedSummary.trim());

    if (!hasDatabase && !hasEmbedded) return '';

    return '';
}

window.switchEnhancedSummarySource = function (source) {
    const sources = window.currentSummarySources || {};
    const summary = source === 'metadata' ? sources.embeddedSummary : sources.databaseSummary;
    if (!summary) {
        showNotification(source === 'metadata' ? '文件内置暂无增强简介' : '数据库暂无增强简介', 2000, 'warning');
        return;
    }
    renderEnhancedSummary(summary, false, {
        ...sources,
        selectedSource: source
    });
};

// Modified: Added enableSave parameter to control save button state
function renderEnhancedSummary(summaryText, enableSave = false, sourceData = null) {
    const summaryResultEl = document.getElementById('ai-summary-result');
    const emptyState = document.querySelector('.empty-ai-state');
    let effectiveSummaryText = String(summaryText || '');
    let effectiveSelectedSource = sourceData?.selectedSource || 'database';

    if (sourceData && !effectiveSummaryText.trim()) {
        const databaseSummary = sourceData.databaseSummary || '';
        const embeddedSummary = sourceData.embeddedSummary || '';
        if (String(databaseSummary).trim()) {
            effectiveSelectedSource = 'database';
            effectiveSummaryText = databaseSummary;
        } else if (String(embeddedSummary).trim()) {
            effectiveSelectedSource = 'metadata';
            effectiveSummaryText = embeddedSummary;
        }
    }

    const normalizedSourceData = sourceData ? {
        selectedSource: effectiveSelectedSource,
        databaseSummary: sourceData.databaseSummary || '',
        embeddedSummary: sourceData.embeddedSummary || ''
    } : null;

    if (emptyState) emptyState.classList.add('hidden');
    if (summaryResultEl) {
        summaryResultEl.classList.remove('hidden');

        // Split content into sections based on keywords
        // Keywords: "图书简介：", "详细要点：", "具体应用："
        // Note: AI might return standard colons or Chinese colons, with or without markdown
        let intro = '';
        let points = '';
        let applications = '';

        let text = effectiveSummaryText;

        // Regex to find keywords (robust against markdown)
        const regexPoints = /(详细要点|Detailed Points)/i;
        const regexApps = /(具体应用|Specific Applications)/i;

        let matchPoints = text.match(regexPoints);
        let matchApps = text.match(regexApps);

        let idxPoints = matchPoints ? matchPoints.index : -1;
        let idxApps = matchApps ? matchApps.index : -1;

        // Fallback: simple indexOf if regex fails (unlikely given the simple regex, but safe)
        if (idxPoints === -1) idxPoints = Math.max(text.indexOf('详细要点'), text.indexOf('Detailed Points'));
        if (idxApps === -1) idxApps = Math.max(text.indexOf('具体应用'), text.indexOf('Specific Applications'));

        // Fallback to simple render if structure is completely missing
        if (idxPoints === -1 && idxApps === -1) {
            // Aggressively clean "Book Summary" prefix
            // Remove anything that looks like "Book Summary:" at the start
            let cleanText = text.replace(/^[\s\*\#\>]*图书简介[\s\*\#\>]*[:：]?\s*/i, '');
            // Also try removing "Book Summary" if it appears without colon
            if (cleanText.startsWith('图书简介')) cleanText = cleanText.substring(4).trim();
            // Remove potential leading colon
            if (cleanText.startsWith('：') || cleanText.startsWith(':')) cleanText = cleanText.substring(1).trim();

            summaryResultEl.innerHTML = `
                <div class="enhanced-summary-text">${parseMarkdown(cleanText)}</div>
                ${normalizedSourceData ? renderSummarySourceSwitcher(normalizedSourceData) : ''}
            `;
        } else {
            // Extract sections

            // 1. Intro
            let start = 0;
            let end = idxPoints !== -1 ? idxPoints : text.length;
            intro = text.substring(start, end).trim();

            // Aggressive Intro Cleaning
            intro = intro.replace(/^[\s\*\#\>]*图书简介[\s\*\#\>]*[:：]?\s*/i, '');
            if (intro.startsWith('图书简介')) intro = intro.substring(4).trim();
            if (intro.startsWith('：') || intro.startsWith(':')) intro = intro.substring(1).trim();

            // 2. Points
            if (idxPoints !== -1) {
                let pEnd = idxApps !== -1 ? idxApps : text.length;
                points = text.substring(idxPoints, pEnd).trim();
                // Aggressive cleaning of header
                points = points.replace(/^[\s\*\#\>]*(\d+\.?\s*)?(详细要点|Detailed Points)[\s\*\#\>]*[:：]?\s*/i, '').trim();
            }

            // 3. Apps
            if (idxApps !== -1) {
                applications = text.substring(idxApps).trim();
                applications = applications.replace(/^[\s\*\#\>]*(\d+\.?\s*)?(具体应用|Specific Applications)[\s\*\#\>]*[:：]?\s*/i, '').trim();
            }

            // Helper to render section
            const renderSection = (title, icon, content) => {
                if (!content) return '';
                return `
                    <div class="summary-section">
                        <h4><i class="${icon}"></i> ${title}</h4>
                        <div class="section-content">${parseMarkdown(content)}</div>
                    </div>
                `;
            };

            let html = '';
            html += renderSection('图书简介', 'fa-solid fa-book-open', intro);
            html += renderSection('详细要点', 'fa-solid fa-list-check', points);
            html += renderSection('具体应用', 'fa-solid fa-lightbulb', applications);

            // Add a footer with "Regenerate" button
            html += `
                <div class="ai-actions" style="margin-top:15px; text-align:right;">
                    <button class="btn-secondary btn-sm" onclick="generateEnhancedSummary()">
                        <i class="fa-solid fa-rotate-right"></i> 重新生成
                    </button>
                    <button class="btn-primary btn-sm" onclick="copyEnhancedSummary()">
                        <i class="fa-regular fa-copy"></i> 复制全部
                    </button>
                </div>
            `;
            if (normalizedSourceData) {
                html += renderSummarySourceSwitcher(normalizedSourceData);
            }

            summaryResultEl.innerHTML = html;
        }
    }

    // Update global state for saving
    window.currentBookSummary = effectiveSummaryText;
    if (normalizedSourceData) {
        window.currentSummarySources = normalizedSourceData;
    } else {
        window.currentSummarySources = {
            selectedSource: 'database',
            databaseSummary: effectiveSummaryText || '',
            embeddedSummary: ''
        };
    }

    // Enable save button ONLY if explicitly requested (e.g. newly generated)
    if (enableSave) {
        const btnSave = document.getElementById('btn-save');
        if (btnSave) {
            btnSave.disabled = false;
            btnSave.className = 'btn-success';
        }
    }
}

// Helper to copy summary
window.copyEnhancedSummary = function () {
    if (window.currentBookSummary) {
        navigator.clipboard.writeText(window.currentBookSummary).then(() => {
            showNotification('已复制到剪贴板');
        }).catch(err => {
            console.error('Copy failed', err);
            showNotification('复制失败');
        });
    }
};

// ============================================================================
// 🆕 Sidebar Search Functions
// ============================================================================

/**
 * 清空搜索框和搜索状态
 */
function clearSidebarSearch() {
    window.sidebarSearchQuery = '';
    const searchInput = document.getElementById('sidebar-search-input');
    const clearBtn = document.getElementById('sidebar-search-clear');
    if (searchInput) searchInput.value = '';
    if (clearBtn) clearBtn.classList.add('hidden');
    if (window.searchDebounceTimer) {
        clearTimeout(window.searchDebounceTimer);
        window.searchDebounceTimer = null;
    }
}

/**
 * 初始化搜索框事件
 */
function initSidebarSearch() {
    const searchInput = document.getElementById('sidebar-search-input');
    const clearBtn = document.getElementById('sidebar-search-clear');

    if (!searchInput) return;

    // 输入事件（debounce 3秒）
    searchInput.addEventListener('input', (e) => {
        const query = e.target.value.trim();

        // 显示/隐藏清空按钮
        clearBtn.classList.toggle('hidden', query.length === 0);

        // 清除之前的定时器
        if (window.searchDebounceTimer) {
            clearTimeout(window.searchDebounceTimer);
        }

        // 500ms后自动搜索 (用户也可按 Enter 立即搜索)
        window.searchDebounceTimer = setTimeout(() => {
            window.sidebarSearchQuery = query;
            renderBookList();
        }, 500);
    });

    // 回车立即搜索
    searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            if (window.searchDebounceTimer) {
                clearTimeout(window.searchDebounceTimer);
            }
            window.sidebarSearchQuery = e.target.value.trim();
            renderBookList();
        }
    });

    // 清空按钮
    clearBtn.addEventListener('click', () => {
        searchInput.value = '';
        clearBtn.classList.add('hidden');
        window.sidebarSearchQuery = '';
        if (window.searchDebounceTimer) {
            clearTimeout(window.searchDebounceTimer);
        }
        renderBookList();
    });
}

// Attach btn-save listener
document.addEventListener('DOMContentLoaded', () => {
    const btnSave = document.getElementById('btn-save');
    if (btnSave) {
        btnSave.addEventListener('click', () => {
            if (window.saveMetadata) window.saveMetadata();
        });
    }

    // 自动上传按钮点击事件
    const autoUploadIcon = document.getElementById('auto-upload-icon');
    if (autoUploadIcon) {
        autoUploadIcon.addEventListener('click', () => {
            if (window.toggleAutoUpload) window.toggleAutoUpload();
        });
    }

    // Note: btn-gen-summary listener is also set in HTML onclick, 
    // but good to have safety here or just rely on global export.

    // 统计徽章点击事件绑定
    initStatsClickHandlers();

    // 评分组件点击事件绑定
    initRatingHandlers();

    // 🆕 搜索框事件绑定
    initSidebarSearch();
});

// ============================================================================
// 评分系统
// ============================================================================

/**
 * 初始化评分星星的点击事件
 */
function initRatingHandlers() {
    // Star clicks
    const stars = document.querySelectorAll('.rating-star');
    stars.forEach(star => {
        star.addEventListener('click', (e) => {
            if (currentMode !== 'manage') return; // 只在库管理模式有效
            const val = parseInt(e.target.dataset.value);
            setBookRating(val);
        });
    });

    // Clear rating click
    const clearBtn = document.querySelector('.rating-clear');
    if (clearBtn) {
        clearBtn.addEventListener('click', (e) => {
            if (currentMode !== 'manage') return;
            e.stopPropagation();
            setBookRating(0);
        });
    }
}

/**
 * 渲染评分组件 UI
 * @param {number} rating 0-5
 */
function renderBookRating(rating) {
    const stars = document.querySelectorAll('.rating-star');
    stars.forEach(star => {
        const val = parseInt(star.dataset.value);
        if (rating > 0 && val <= rating) {
            star.textContent = '★'; // 实心
            star.classList.add('active');
        } else {
            star.textContent = '☆'; // 空心
            star.classList.remove('active');
        }
    });
}

/**
 * 设置并保存图书评分
 * @param {number} rating 1-5
 */
async function setBookRating(rating) {
    if (!window.currentBookFilename) {
        showNotification('未选择图书', 2000, 'error');
        return;
    }

    // 乐观更新 UI
    renderBookRating(rating);

    try {
        const payload = {
            filename: window.currentBookFilename,
            rating: rating
        };

        // 如果 currentBookFilename 是全路径，可能需要取 basename？
        // 后端 update_book_rating 使用 filename 匹配。
        // 在 selectLibraryBook 中我们设置了 window.currentBookFilename = book.path
        // 但数据库主要是存 basename 或 rel_path? 
        // 实际上数据库 enhanced_summaries.filename 存的是文件名 (basename)
        // 让我们确认一下。
        // 在 db.py: cursor.execute("SELECT * FROM enhanced_summaries WHERE filename = ?", (filename,))
        // 而入库时：db.save_enhanced_summary(filename, ...)
        // 通常是 basename。
        // 让我们处理一下路径，只发 basename
        // 但是如果在库管理模式，book.path 是相对路径，可能包含子目录。
        // 我们这里也应该传不带路径的文件名。

        let targetFilename = payload.filename.split('/').pop();

        const res = await fetch(`${API_BASE}/library/book/rating`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                filename: targetFilename,
                rating: rating,
                file_path: window.currentBookPath // Use correct relative path from global state
            })
        });

        const data = await res.json();

        if (data.success) {
            showNotification(`评分已更新: ${rating}星`, 1500, 'success');

            // 1. Update global books array (Persistence Fix for List/Tree View)
            // This ensures that if the tree is re-rendered (e.g. folder toggle), the icon persists.
            if (window.books) {
                const bookObj = window.books.find(b => b.path === window.currentBookPath);
                if (bookObj) {
                    bookObj.rating = rating;
                    bookObj.has_enhanced_summary = true; // Rating record implies existence
                }
            }

            // 2. Update current DOM list icon (Optimistic UI)
            updateBookListIcon(window.currentBookPath, rating);
        } else {
            throw new Error(data.message || '保存失败');
        }
    } catch (e) {
        console.error('Failed to save rating:', e);
        showNotification(`评分保存失败: ${e.message}`, 5000, 'error');
        // 回滚 UI? 暂时不处理
    }
}

/**
 * 更新左侧列表中特定图书的图标
 */
/**
 * 更新左侧列表中特定图书的图标
 */
function updateBookListIcon(path, rating) {
    // 找到对应的 item
    try {
        const itemDiv = document.querySelector(`.library-book-item[data-path="${CSS.escape(path)}"]`);
        if (!itemDiv) return;

        // 查找或创建 wrapper
        let iconWrapper = itemDiv.querySelector('.rating-icon-wrapper');
        let simpleIcon = itemDiv.querySelector('.item-icon');

        // 如果存在简单的 item-icon (非 wrapper 内部)，由于我们要显示数字，可能需要替换它
        // 注意：checkbox 是 .book-checkbox，不应该被误删

        const iconClass = 'fa-solid fa-star';
        const emptyClass = 'fa-regular fa-star';

        const nameSpan = itemDiv.querySelector('.book-name-text');
        if (!nameSpan) return;

        if (rating > 0) {
            // 需要显示数字，必须使用 wrapper
            const newHtml = `
                    <i class="${iconClass} item-icon"></i>
                    <span class="rating-num">${rating}</span>
            `;

            if (iconWrapper) {
                // 已有 wrapper，直接更新内容
                iconWrapper.innerHTML = newHtml;
            } else {
                // 没有 wrapper
                if (simpleIcon && simpleIcon.parentElement === itemDiv) {
                    // 有旧的简单 icon，替换它
                    const wrapper = document.createElement('span');
                    wrapper.className = 'rating-icon-wrapper';
                    wrapper.innerHTML = newHtml;
                    itemDiv.replaceChild(wrapper, simpleIcon);
                } else {
                    // 既没 wrapper 也没简单 icon (理论不应发生)，插入到 name 之前
                    // 但要小心 checkbox，应该插入在 checkbox 之后 (如果有)，name 之前
                    const wrapper = document.createElement('span');
                    wrapper.className = 'rating-icon-wrapper';
                    wrapper.innerHTML = newHtml;

                    // 检查是否有 checkbox
                    const checkbox = itemDiv.querySelector('.book-checkbox');
                    if (checkbox) {
                        checkbox.insertAdjacentElement('afterend', wrapper);
                    } else {
                        itemDiv.insertBefore(wrapper, nameSpan);
                    }
                }
            }
        } else {
            // rating = 0，显示空星，不需要数字
            // 理论上保持 wrapper 也可以，或者回退到简单 icon。
            // 为了布局稳定性，保持 wrapper 结构比较好，只是内容变了。
            const newHtml = `<i class="${emptyClass} item-icon"></i>`;

            if (iconWrapper) {
                // 这里如果不想要数字，可以清空 rating-num 或者移除它
                // 为了简单，直接替换内容，不放数字 span
                iconWrapper.innerHTML = `<i class="${emptyClass} item-icon"></i>`;
            } else {
                // 逻辑同上
                if (simpleIcon && simpleIcon.parentElement === itemDiv) {
                    simpleIcon.className = `${emptyClass} item-icon`;
                } else {
                    // 插入新的
                    const icon = document.createElement('i');
                    icon.className = `${emptyClass} item-icon`;
                    const checkbox = itemDiv.querySelector('.book-checkbox');
                    if (checkbox) {
                        checkbox.insertAdjacentElement('afterend', icon);
                    } else {
                        itemDiv.insertBefore(icon, nameSpan);
                    }
                }
            }
        }

    } catch (e) {
        console.error('Failed to update list icon:', e);
    }
}

function setStatsFilter(filterType) {
    // filterType: 'all' | 'skipped' | 'enhanced' | 'not_enhanced'
    if (filterType === 'all' || filterType === currentStatsFilter) {
        // 点击相同筛选或 all，清除筛选
        currentStatsFilter = null;
    } else {
        currentStatsFilter = filterType;
    }

    // 更新 UI 样式
    updateStatsActiveState();

    // 重新渲染列表
    renderBookList();
}
window.setStatsFilter = setStatsFilter;

function updateStatsActiveState() {
    // 清除所有 active 类
    document.querySelectorAll('.stat-clickable').forEach(el => {
        el.classList.remove('active');
    });

    // 添加当前筛选的 active 类
    if (currentStatsFilter) {
        const activeEl = document.querySelector(`.stat-clickable[data-filter="${currentStatsFilter}"]`);
        if (activeEl) activeEl.classList.add('active');
    }
}

function initStatsClickHandlers() {
    document.querySelectorAll('.stat-clickable').forEach(el => {
        el.addEventListener('click', (e) => {
            e.stopPropagation();
            const filterType = el.dataset.filter;
            setStatsFilter(filterType);
        });
    });
}
window.initStatsClickHandlers = initStatsClickHandlers;

// Export functions to window for global access (used by inline onclick handlers)
window.generateEnhancedSummary = generateEnhancedSummary;
window.handleMetadataInput = handleMetadataInput;
window.initEnhancedMode = initEnhancedMode;

// ============================================================================
// Calibre PDF 转换功能 (NotebookLM 预集成)
// ============================================================================

// 全局状态：Calibre 是否可用
let calibreAvailable = false;

/**
 * 初始化 Calibre 状态检测
 * 在页面加载时调用，检测本机是否安装 Calibre
 */
async function initCalibreStatus() {
    try {
        const status = await window.checkCalibreStatus();
        calibreAvailable = status.installed;
        console.log(`[Calibre] Status: ${status.installed ? 'Available' : 'Not installed'}`);
        if (status.installed) {
            console.log(`[Calibre] Path: ${status.path}`);
        }
        // Fix race condition: update button if a book is already selected
        if (window.updateConvertPdfButton) {
            window.updateConvertPdfButton();
        }
    } catch (e) {
        calibreAvailable = false;
        console.error('[Calibre] Status check failed:', e);
    }
}

/**
 * 更新导出按钮的可见性和行为
 * 
 * 逻辑:
 * - 需转换格式: 显示"导出" (有Calibre时可用)
 * - 不需转换格式: 
 *   - GDrive已连接+自动上传开启: 显示"上传云盘"
 *   - 否则: 按钮禁用(灰色)
 */
function updateConvertPdfButton() {
    const btn = document.getElementById('btn-export-pdf-new') || document.getElementById('btn-convert-pdf');
    if (!btn) {
        console.error('[Export Button] Button element NOT FOUND by ID');
        return;
    }

    const bookPath = window.currentBookPath || window.currentBook || currentBook;

    if (!bookPath) {
        btn.classList.add('hidden');
        btn.style.display = 'none';
        return;
    }

    const ext = bookPath.toLowerCase().substring(bookPath.lastIndexOf('.'));
    const needsConversion = window.isFormatNeedsConversion ? window.isFormatNeedsConversion(ext) : false;
    const gdriveEnabled = isGoogleDriveConnected && isAutoUploadEnabled;

    console.log(`[Export Button] Path: ${bookPath}, Ext: ${ext}, NeedsConv: ${needsConversion}, GDrive: ${gdriveEnabled}, Calibre: ${calibreAvailable}`);

    // 始终显示按钮
    btn.classList.remove('hidden');
    btn.style.display = 'inline-flex';

    // 移除所有状态类
    btn.classList.remove('btn-upload-disabled');
    btn.disabled = false;

    if (needsConversion) {
        // 需转换格式: 显示"导出"
        btn.innerHTML = '<i class="fa-solid fa-file-pdf"></i> 导出';
        btn.title = 'Calibre 转换为 PDF 格式';
        btn.setAttribute('data-action', 'convert');

        if (!calibreAvailable) {
            btn.classList.add('btn-upload-disabled');
            btn.disabled = true;
            btn.title = '需要安装 Calibre 才能转换此格式';
        }
    } else {
        // 不需转换格式
        if (gdriveEnabled) {
            // GDrive 可用: 显示"上传云盘"
            btn.innerHTML = '<i class="fa-brands fa-google-drive"></i> 上传云盘';
            btn.title = '复制到导出目录并上传 Google Drive';
            btn.setAttribute('data-action', 'upload');
        } else {
            // GDrive 不可用: 禁用按钮
            btn.innerHTML = '<i class="fa-brands fa-google-drive"></i> 上传云盘';
            btn.classList.add('btn-upload-disabled');
            btn.disabled = true;
            btn.title = '请先连接 Google Drive 并开启自动上传';
            btn.setAttribute('data-action', 'disabled');
        }
    }
}
window.updateConvertPdfButton = updateConvertPdfButton;

/**
 * 智能导出/上传处理函数
 * 根据按钮的 data-action 属性决定行为
 */
async function handleSmartExport() {
    const btn = document.getElementById('btn-export-pdf-new') || document.getElementById('btn-convert-pdf');
    if (!btn) return;

    const action = btn.getAttribute('data-action');
    const bookPath = window.currentBookPath || window.currentBook || currentBook;

    if (!bookPath) {
        showNotification('请先选择一本图书', 3000, 'error');
        return;
    }

    if (action === 'convert') {
        await convertToPdf();
    } else if (action === 'upload') {
        await directUploadToGDrive();
    }
}
window.handleSmartExport = handleSmartExport;

/**
 * 执行电子书转 PDF 转换
 */
async function convertToPdf() {
    const bookPath = window.currentBookPath || window.currentBook || currentBook;

    if (!bookPath) {
        showNotification('请先选择一本图书', 3000, 'error');
        return;
    }

    const ext = bookPath.toLowerCase().substring(bookPath.lastIndexOf('.'));
    if (!window.isFormatNeedsConversion || !window.isFormatNeedsConversion(ext)) {
        showNotification(`格式 ${ext} 无需转换`, 3000, 'warning');
        return;
    }

    const btn = document.getElementById('btn-export-pdf-new') || document.getElementById('btn-convert-pdf');
    if (!btn) return;

    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<div class="spinner-small"></div> 转换中...';

    try {
        const result = await window.convertEpubToPdf(bookPath);

        if (result.success) {
            showNotification(`PDF 已生成: ${result.pdf_path.split('/').pop()}`, 5000, 'success');
        } else {
            showNotification(`转换失败: ${result.message}`, 5000, 'error');
        }
    } catch (e) {
        showNotification(`转换失败: ${e.message}`, 5000, 'error');
        console.error('[Calibre] Convert failed:', e);
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}
window.convertToPdf = convertToPdf;

/**
 * 直接上传到 Google Drive (不转换格式)
 */
async function directUploadToGDrive() {
    const bookPath = window.currentBookPath || window.currentBook || currentBook;

    if (!bookPath) {
        showNotification('请先选择一本图书', 3000, 'error');
        return;
    }

    const btn = document.getElementById('btn-export-pdf-new') || document.getElementById('btn-convert-pdf');
    if (!btn) return;

    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<div class="spinner-small"></div> 上传中...';

    try {
        const res = await fetch(`${API_BASE}/direct_upload`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ file_path: bookPath })
        });

        const result = await res.json();

        if (!res.ok) {
            // HTTP error response (4xx, 5xx)
            const errorMsg = result.detail || result.message || '上传失败';
            showNotification(`上传失败: ${errorMsg}`, 5000, 'error');
            return;
        }

        if (result.success) {
            showNotification(`已上传: ${result.filename}`, 5000, 'success');
        } else {
            showNotification(`上传失败: ${result.message}`, 5000, 'error');
        }
    } catch (e) {
        showNotification(`上传失败: ${e.message}`, 5000, 'error');
        console.error('[GDrive] Direct upload failed:', e);
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}
window.directUploadToGDrive = directUploadToGDrive;

// 在 DOMContentLoaded 时初始化 Calibre 状态
document.addEventListener('DOMContentLoaded', () => {
    initCalibreStatus();
});
