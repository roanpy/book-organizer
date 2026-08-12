/**
 * records.js - 操作记录查看模块
 * 
 * 处理转移记录和保存记录的查看、筛选和搜索。
 * 依赖: state.js, api.js
 */

// ============================================================================
// 状态
// ============================================================================

let currentRecordsTab = 'transfers';
let recordsCache = { transfers: [], summaries: [] };
let currentPage = 1;
let totalPages = 1;
const PAGE_SIZE = 50;

// ============================================================================
// 弹窗控制
// ============================================================================

window.openRecordsModal = () => {
    document.getElementById('records-modal').classList.remove('hidden');
    // Always default to transfers tab when opening
    switchRecordsTab('transfers');
};

window.closeRecordsModal = () => {
    document.getElementById('records-modal').classList.add('hidden');
};

// ============================================================================
// 标签页切换
// ============================================================================

window.switchRecordsTab = (tabName) => {
    currentRecordsTab = tabName;

    // 更新标签按钮状态
    document.querySelectorAll('#records-modal .tab-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.getAttribute('onclick').includes(`'${tabName}'`)) {
            btn.classList.add('active');
        }
    });

    // 切换内容区域
    document.querySelectorAll('#records-modal .tab-content').forEach(c => c.classList.remove('active'));
    document.getElementById(`records-tab-${tabName}`).classList.add('active');

    // 加载对应数据
    loadRecords();
};

// ============================================================================
// 数据加载
// ============================================================================

window.loadRecords = async (resetPage = true) => {
    if (resetPage) currentPage = 1;

    const startDate = document.getElementById('records-date-start').value;
    const endDate = document.getElementById('records-date-end').value;
    const search = document.getElementById('records-search').value.trim();

    if (currentRecordsTab === 'transfers') {
        await loadTransferRecords(startDate, endDate, search);
    } else {
        await loadSummaryRecords(startDate, endDate, search);
    }

    updatePaginationUI();
};

window.changePage = (delta) => {
    const newPage = currentPage + delta;
    if (newPage >= 1 && newPage <= totalPages) {
        currentPage = newPage;
        loadRecords(false); // 不重置页码
    }
};

function updatePaginationUI() {
    const prevBtn = document.getElementById('page-prev');
    const nextBtn = document.getElementById('page-next');
    const pageInfo = document.getElementById('page-info');

    if (prevBtn) prevBtn.disabled = currentPage <= 1;
    if (nextBtn) nextBtn.disabled = currentPage >= totalPages;
    if (pageInfo) pageInfo.textContent = `${currentPage} / ${totalPages}`;
}

async function loadTransferRecords(startDate, endDate, search) {
    const loading = document.getElementById('transfers-loading');
    const tbody = document.getElementById('transfers-tbody');
    const empty = document.getElementById('transfers-empty');
    const table = document.getElementById('transfers-table');
    const countEl = document.getElementById('records-count');

    loading.classList.remove('hidden');
    table.classList.add('hidden');
    empty.classList.add('hidden');

    try {
        const params = new URLSearchParams();
        if (startDate) params.append('start_date', startDate);
        if (endDate) params.append('end_date', endDate);
        if (search) params.append('search', search);
        params.append('page', currentPage);
        params.append('page_size', PAGE_SIZE);

        const data = await fetchJson(`${API_BASE}/records/transfers?${params}`, {}, '加载转移记录失败');

        loading.classList.add('hidden');

        // 更新分页状态
        totalPages = data.total_pages || 1;

        if (!data.records || data.records.length === 0) {
            empty.classList.remove('hidden');
            countEl.textContent = '共 0 条记录';
            totalPages = 1;
            return;
        }

        table.classList.remove('hidden');
        countEl.textContent = `共 ${data.total || data.records.length} 条记录`;

        tbody.innerHTML = data.records.map((r, i) => `
            <tr>
                <td>${(currentPage - 1) * PAGE_SIZE + i + 1}</td>
                <td class="truncate-cell" title="${escapeHtmlLocal(r.title || r.new_filename)}">${escapeHtmlLocal(r.title || '未知')}</td>
                <td class="truncate-cell" title="${escapeHtmlLocal(r.author || '')}">${escapeHtmlLocal(r.author || '-')}</td>
                <td class="truncate-cell" title="${escapeHtmlLocal(r.destination_category || '')}">${escapeHtmlLocal(r.destination_category || '-')}</td>
                <td>${formatTime(r.transferred_at)}</td>
                <td>
                    <button class="btn-detail" 
                        onmouseenter="showRecordDetail(event, 'transfer', ${i})" 
                        onmouseleave="hideRecordDetail()">
                        <i class="fa-solid fa-eye"></i>
                    </button>
                </td>
            </tr>
        `).join('');

        recordsCache.transfers = data.records;

    } catch (e) {
        loading.classList.add('hidden');
        empty.classList.remove('hidden');
        console.error('Failed to load transfer records:', e);
    }
}

async function loadSummaryRecords(startDate, endDate, search) {
    const loading = document.getElementById('summaries-loading');
    const tbody = document.getElementById('summaries-tbody');
    const empty = document.getElementById('summaries-empty');
    const table = document.getElementById('summaries-table');
    const countEl = document.getElementById('records-count');

    loading.classList.remove('hidden');
    table.classList.add('hidden');
    empty.classList.add('hidden');

    try {
        const params = new URLSearchParams();
        if (startDate) params.append('start_date', startDate);
        if (endDate) params.append('end_date', endDate);
        if (search) params.append('search', search);
        params.append('page', currentPage);
        params.append('page_size', PAGE_SIZE);

        const data = await fetchJson(`${API_BASE}/records/summaries?${params}`, {}, '加载摘要记录失败');

        loading.classList.add('hidden');

        // 更新分页状态
        totalPages = data.total_pages || 1;

        if (!data.records || data.records.length === 0) {
            empty.classList.remove('hidden');
            countEl.textContent = '共 0 条记录';
            totalPages = 1;
            return;
        }

        table.classList.remove('hidden');
        countEl.textContent = `共 ${data.total || data.records.length} 条记录`;

        tbody.innerHTML = data.records.map((r, i) => `
            <tr>
                <td>${(currentPage - 1) * PAGE_SIZE + i + 1}</td>
                <td class="truncate-cell" title="${escapeHtmlLocal(r.title || r.filename)}">${escapeHtmlLocal(r.title || '未知')}</td>
                <td class="truncate-cell" title="${escapeHtmlLocal(r.author || '')}">${escapeHtmlLocal(r.author || '-')}</td>
                <td class="truncate-cell" title="${escapeHtmlLocal(r.category || '')}">${escapeHtmlLocal(r.category || '-')}</td>
                <td>${formatTime(r.updated_at || r.created_at)}</td>
                <td>
                    <button class="btn-detail" 
                        onmouseenter="showRecordDetail(event, 'summary', ${i})" 
                        onmouseleave="hideRecordDetail()">
                        <i class="fa-solid fa-eye"></i>
                    </button>
                </td>
            </tr>
        `).join('');

        recordsCache.summaries = data.records;

    } catch (e) {
        loading.classList.add('hidden');
        empty.classList.remove('hidden');
        console.error('Failed to load summary records:', e);
    }
}

// ============================================================================
// 详情悬停提示 - 支持鼠标移入后保持显示
// ============================================================================

let detailTooltip = null;
let hideTooltipTimer = null;

function createTooltipIfNeeded() {
    if (!detailTooltip) {
        detailTooltip = document.createElement('div');
        detailTooltip.className = 'record-detail-tooltip';
        document.body.appendChild(detailTooltip);

        // 鼠标进入 tooltip 时取消隐藏
        detailTooltip.addEventListener('mouseenter', () => {
            if (hideTooltipTimer) {
                clearTimeout(hideTooltipTimer);
                hideTooltipTimer = null;
            }
        });

        // 鼠标离开 tooltip 时隐藏
        detailTooltip.addEventListener('mouseleave', () => {
            hideRecordDetail();
        });
    }
}

window.showRecordDetail = (event, type, index) => {
    const record = type === 'transfer' ? recordsCache.transfers[index] : recordsCache.summaries[index];
    if (!record) return;

    // 取消之前的隐藏计时器
    if (hideTooltipTimer) {
        clearTimeout(hideTooltipTimer);
        hideTooltipTimer = null;
    }

    createTooltipIfNeeded();

    let html = '';

    if (type === 'transfer') {
        html = `
            <div class="detail-label">原文件名</div>
            <div class="detail-content">${escapeHtmlLocal(record.original_filename || '-')}</div>
            <div class="detail-label">新文件名</div>
            <div class="detail-content">${escapeHtmlLocal(record.new_filename || '-')}</div>
            ${record.publisher ? `<div class="detail-label">出版社</div><div class="detail-content">${escapeHtmlLocal(record.publisher)}</div>` : ''}
            ${record.series ? `<div class="detail-label">丛书</div><div class="detail-content">${escapeHtmlLocal(record.series)}</div>` : ''}
            ${record.tags ? `<div class="detail-label">标签</div><div class="detail-content">${escapeHtmlLocal(record.tags)}</div>` : ''}
            ${record.summary ? `<div class="detail-label">简介</div><div class="detail-content">${escapeHtmlLocal(record.summary)}</div>` : ''}
        `;
    } else {
        // Summary record - parse summary_json if available
        let summaryText = '';
        if (record.summary_json) {
            try {
                const parsed = typeof record.summary_json === 'string' ? JSON.parse(record.summary_json) : record.summary_json;
                summaryText = parsed.summary || '';
            } catch (e) {
                summaryText = record.summary_json?.substring?.(0, 500) || '';
            }
        }

        html = `
            <div class="detail-label">文件名</div>
            <div class="detail-content">${escapeHtmlLocal(record.filename || '-')}</div>
            <div class="detail-label">文件路径</div>
            <div class="detail-content">${escapeHtmlLocal(record.file_path || '-')}</div>
            ${summaryText ? `<div class="detail-label">增强简介</div><div class="detail-content">${escapeHtmlLocal(summaryText)}</div>` : ''}
        `;
    }

    detailTooltip.innerHTML = html;
    detailTooltip.style.display = 'block';

    // 定位
    const rect = event.target.getBoundingClientRect();

    // 先设置位置再获取尺寸
    detailTooltip.style.left = '0px';
    detailTooltip.style.top = '0px';
    const tooltipRect = detailTooltip.getBoundingClientRect();

    let left = rect.left - tooltipRect.width - 10;
    if (left < 10) left = rect.right + 10;

    let top = rect.top;
    if (top + tooltipRect.height > window.innerHeight - 10) {
        top = window.innerHeight - tooltipRect.height - 10;
    }
    if (top < 10) top = 10;

    detailTooltip.style.left = `${left}px`;
    detailTooltip.style.top = `${top}px`;
};

window.hideRecordDetail = () => {
    // 使用延迟隐藏，给用户时间移入 tooltip
    if (hideTooltipTimer) {
        clearTimeout(hideTooltipTimer);
    }
    hideTooltipTimer = setTimeout(() => {
        if (detailTooltip) {
            detailTooltip.style.display = 'none';
        }
        hideTooltipTimer = null;
    }, 150);
};

// ============================================================================
// 工具函数
// ============================================================================

function escapeHtmlLocal(str) {
    return window.escapeHtml(str);
}

function formatTime(timeStr) {
    if (!timeStr) return '-';
    try {
        const date = new Date(timeStr);
        return date.toLocaleString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    } catch (e) {
        return timeStr;
    }
}

// ============================================================================
// 初始化
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    // 设置默认日期
    initDefaultDates();

    // 绑定按钮事件
    const recordsBtn = document.getElementById('records-btn');
    if (recordsBtn) {
        recordsBtn.addEventListener('click', openRecordsModal);
    }

    const closeBtn = document.getElementById('close-records');
    if (closeBtn) {
        closeBtn.addEventListener('click', closeRecordsModal);
    }

    // 回车搜索
    const searchInput = document.getElementById('records-search');
    if (searchInput) {
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') loadRecords();
        });
    }
});

function initDefaultDates() {
    const today = new Date();
    const thirtyDaysAgo = new Date(today);
    thirtyDaysAgo.setDate(today.getDate() - 30);

    const startInput = document.getElementById('records-date-start');
    const endInput = document.getElementById('records-date-end');

    if (startInput) startInput.value = formatDateForInput(thirtyDaysAgo);
    if (endInput) endInput.value = formatDateForInput(today);
}

function formatDateForInput(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}
