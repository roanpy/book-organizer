/**
 * modal.js - 批量处理弹窗
 * 
 * 处理批量处理弹窗的渲染、状态更新和交互。
 * 依赖: state.js, api.js, libraryBatch/selection.js, libraryBatch/hover-popup.js
 */

// ============================================================================
// 批量处理弹窗
// ============================================================================

/**
 * 打开批量处理弹窗
 * @param {string} type - 'enhance' | 'convert'
 */
function openLibraryBatchModal(type) {
    const state = window.getLibraryBatchState();
    window.setLibraryBatchState({ currentType: type, shouldStop: false });

    // 构建处理队列
    const queue = Array.from(window.selectedLibraryBooks).map(path => {
        const book = libraryBooks.find(b => b.path === path);
        return {
            path: path,
            name: book ? book.name : path.split('/').pop(),
            rating: book ? book.rating : 0,
            has_enhanced_summary: book ? book.has_enhanced_summary : false,
            has_toc: book ? book.has_toc : false,
            status: 'pending',
            enhanceStatus: null,
            convertStatus: null
        };
    });
    window.setLibraryBatchState({ queue: queue });

    const modal = document.getElementById('library-batch-modal');
    const title = document.getElementById('lib-batch-title');

    if (type === 'enhance') {
        title.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> 批量信息增强';
        document.getElementById('col-enhance').classList.remove('hidden');
        document.getElementById('col-convert').classList.add('hidden');
    } else {
        title.innerHTML = '<i class="fa-solid fa-file-export"></i> 批量转换';
        document.getElementById('col-enhance').classList.add('hidden');
        document.getElementById('col-convert').classList.remove('hidden');
    }

    renderBatchList();
    updateBatchProgress(0, `准备中 (共 ${queue.length} 本)...`);

    document.getElementById('lib-batch-start').classList.remove('hidden');
    document.getElementById('lib-batch-stop').classList.add('hidden');

    modal.classList.remove('hidden');
}

/**
 * 关闭批量处理弹窗
 */
function closeLibraryBatchModal() {
    const modal = document.getElementById('library-batch-modal');
    modal.classList.add('hidden');

    const state = window.getLibraryBatchState();
    if (state.isProcessing) {
        window.setLibraryBatchState({ shouldStop: true });
    }

    if (typeof refreshLibraryTreeWithState === 'function') {
        refreshLibraryTreeWithState();
    }
}

// ============================================================================
// 列表渲染
// ============================================================================

/**
 * 渲染批量处理列表
 */
function renderBatchList() {
    const tbody = document.getElementById('lib-batch-list');
    if (!tbody) return;

    tbody.innerHTML = '';

    const state = window.getLibraryBatchState();
    const batchProcessingQueue = state.queue;

    batchProcessingQueue.forEach((item, index) => {
        const tr = document.createElement('tr');
        tr.dataset.path = item.path;
        tr.dataset.index = index;

        // 书名
        const tdName = document.createElement('td');
        tdName.className = 'batch-book-name';
        tdName.textContent = item.name;
        tdName.title = item.path;
        tr.appendChild(tdName);

        // 评分
        const tdRating = document.createElement('td');
        tdRating.className = 'batch-rating';
        if (item.rating && item.rating > 0) {
            tdRating.innerHTML = `<span class="rating-badge">★${item.rating}</span>`;
        } else {
            tdRating.innerHTML = '<span class="rating-empty">☆</span>';
        }
        tr.appendChild(tdRating);

        // 简介按钮 (hover)
        const tdSummary = document.createElement('td');
        tdSummary.className = 'batch-info-cell';
        if (item.has_enhanced_summary) {
            const btn = document.createElement('span');
            btn.className = 'batch-info-icon has-data';
            btn.innerHTML = '<i class="fa-solid fa-file-lines"></i>';
            btn.dataset.path = item.path;
            btn.dataset.type = 'summary';
            btn.addEventListener('mouseenter', window.showBatchHoverPopup);
            btn.addEventListener('mouseleave', window.hideBatchHoverPopup);
            tdSummary.appendChild(btn);
        } else {
            tdSummary.innerHTML = '<i class="fa-solid fa-file-lines" style="opacity:0.2;color:var(--text-muted)"></i>';
        }
        tr.appendChild(tdSummary);

        // 目录按钮 (hover)
        const tdToc = document.createElement('td');
        tdToc.className = 'batch-info-cell';
        if (item.has_toc) {
            const btn = document.createElement('span');
            btn.className = 'batch-info-icon has-data';
            btn.innerHTML = '<i class="fa-solid fa-list-ol"></i>';
            btn.dataset.path = item.path;
            btn.dataset.type = 'toc';
            btn.addEventListener('mouseenter', window.showBatchHoverPopup);
            btn.addEventListener('mouseleave', window.hideBatchHoverPopup);
            tdToc.appendChild(btn);
        } else {
            tdToc.innerHTML = '<i class="fa-solid fa-list-ol" style="opacity:0.2;color:var(--text-muted)"></i>';
        }
        tr.appendChild(tdToc);

        // 状态列
        if (state.currentType === 'enhance') {
            const tdEnhance = document.createElement('td');
            tdEnhance.className = 'batch-status';
            tdEnhance.id = `enhance-status-${index}`;
            tdEnhance.innerHTML = renderStatusIcon(item.status);
            tr.appendChild(tdEnhance);
        }

        if (state.currentType === 'convert') {
            const tdConvert = document.createElement('td');
            tdConvert.className = 'batch-status';
            tdConvert.id = `convert-status-${index}`;
            tdConvert.innerHTML = renderStatusIcon(item.convertStatus || 'pending');
            tr.appendChild(tdConvert);

        }

        // 操作
        const tdAction = document.createElement('td');
        const btnCancel = document.createElement('button');
        btnCancel.className = 'btn-text btn-sm';
        btnCancel.innerHTML = '<i class="fa-solid fa-xmark"></i> 取消';
        btnCancel.onclick = () => removeFromBatch(item.path);
        tdAction.appendChild(btnCancel);
        tr.appendChild(tdAction);

        tbody.appendChild(tr);
    });
}

/**
 * 渲染状态图标
 */
function renderStatusIcon(status) {
    switch (status) {
        case 'pending': return '<span class="status-pending">⏸</span>';
        case 'processing': return '<span class="status-processing"><i class="fa-solid fa-spinner fa-spin"></i></span>';
        case 'done': return '<span class="status-done">✅</span>';
        case 'error': return '<span class="status-error">❌</span>';
        case 'skipped': return '<span class="status-skipped">⏭</span>';
        default: return '<span class="status-pending">-</span>';
    }
}

// ============================================================================
// 状态更新
// ============================================================================

/**
 * 从批量处理中移除一本书
 */
function removeFromBatch(path) {
    const state = window.getLibraryBatchState();
    const queue = state.queue;

    const index = queue.findIndex(item => item.path === path);
    if (index > -1) {
        queue.splice(index, 1);
    }

    window.selectedLibraryBooks.delete(path);

    const checkbox = document.querySelector(`.book-checkbox[data-path="${CSS.escape(path)}"]`);
    if (checkbox) checkbox.checked = false;

    updateSelectionToolbar();
    updateFolderCheckboxStates();
    renderBatchList();

    if (!state.isProcessing) {
        updateBatchProgress(0, `准备中 (共 ${queue.length} 本)...`);
    }

    if (queue.length === 0) {
        closeLibraryBatchModal();
    }
}

/**
 * 更新批量处理进度
 */
function updateBatchProgress(current, statusText) {
    const progressBar = document.getElementById('lib-batch-progress');
    const statusEl = document.getElementById('lib-batch-status');

    const state = window.getLibraryBatchState();
    const total = state.queue.length;
    const percent = total > 0 ? (current / total) * 100 : 0;

    if (progressBar) progressBar.style.width = `${percent}%`;
    if (statusEl) statusEl.textContent = statusText || `${current}/${total}`;
}

/**
 * 更新单行状态
 */
function updateRowStatus(path, status, column = 'enhance', forceRefreshIcons = false, itemState = null) {
    const state = window.getLibraryBatchState();
    const batchProcessingQueue = state.queue;

    const index = batchProcessingQueue.findIndex(item => item.path === path);
    if (index === -1) {
        console.warn('[updateRowStatus] 路径未找到:', path);
        return;
    }

    let statusEl;
    if (column === 'enhance') {
        statusEl = document.getElementById(`enhance-status-${index}`);
    } else if (column === 'convert') {
        statusEl = document.getElementById(`convert-status-${index}`);
    }

    if (statusEl) {
        statusEl.innerHTML = renderStatusIcon(status);
    }

    batchProcessingQueue[index].status = status;

    if (itemState) {
        if (typeof itemState.has_enhanced_summary !== 'undefined') {
            batchProcessingQueue[index].has_enhanced_summary = itemState.has_enhanced_summary;
        }
        if (typeof itemState.has_toc !== 'undefined') {
            batchProcessingQueue[index].has_toc = itemState.has_toc;
        }
    }

    const item = batchProcessingQueue[index];
    console.log(`[updateRowStatus] ${item.name}: status=${status}, has_enhanced_summary=${item.has_enhanced_summary}, has_toc=${item.has_toc}`);

    // 增强完成后，更新图标
    if (column === 'enhance' && (status === 'done' || forceRefreshIcons)) {
        const row = document.querySelector(`tr[data-index="${index}"]`);
        if (!row) return;

        // 清除缓存
        if (window.hoverPopupCache) {
            delete window.hoverPopupCache[`summary:${item.path}`];
            delete window.hoverPopupCache[`toc:${item.path}`];
        }

        // 更新简介图标
        const summaryCell = row.querySelectorAll('.batch-info-cell')[0];
        if (summaryCell) {
            if (item.has_enhanced_summary) {
                summaryCell.innerHTML = '';
                const btn = document.createElement('span');
                btn.className = 'batch-info-icon has-data';
                btn.innerHTML = '<i class="fa-solid fa-file-lines"></i>';
                btn.dataset.path = item.path;
                btn.dataset.type = 'summary';
                btn.addEventListener('mouseenter', window.showBatchHoverPopup);
                btn.addEventListener('mouseleave', window.hideBatchHoverPopup);
                summaryCell.appendChild(btn);
            } else {
                summaryCell.innerHTML = '<i class="fa-solid fa-file-lines" style="opacity:0.2;color:var(--text-muted)"></i>';
            }
        }

        // 更新目录图标
        const tocCell = row.querySelectorAll('.batch-info-cell')[1];
        if (tocCell) {
            if (item.has_toc) {
                tocCell.innerHTML = '';
                const btn = document.createElement('span');
                btn.className = 'batch-info-icon has-data';
                btn.innerHTML = '<i class="fa-solid fa-list-ol"></i>';
                btn.dataset.path = item.path;
                btn.dataset.type = 'toc';
                btn.addEventListener('mouseenter', window.showBatchHoverPopup);
                btn.addEventListener('mouseleave', window.hideBatchHoverPopup);
                tocCell.appendChild(btn);
            } else {
                tocCell.innerHTML = '<i class="fa-solid fa-list-ol" style="opacity:0.2;color:var(--text-muted)"></i>';
            }
        }
    }
}

// ============================================================================
// 导出到全局
// ============================================================================

window.openLibraryBatchModal = openLibraryBatchModal;
window.closeLibraryBatchModal = closeLibraryBatchModal;
window.removeFromBatch = removeFromBatch;
window.updateBatchProgress = updateBatchProgress;
window.updateRowStatus = updateRowStatus;
window.renderBatchList = renderBatchList;
