/**
 * hover-popup.js - Hover 浮动弹窗
 * 
 * 处理鼠标悬停时的简介/目录预览弹窗。
 * 依赖: state.js, api.js
 */

// ============================================================================
// 状态管理
// ============================================================================

// 用于存储正在获取的数据，避免重复请求
let hoverPopupCache = {};
let hoverPopupTimer = null;
let hoverPopupHideTimer = null;
let currentHoverElement = null;

function escapePopupHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

// ============================================================================
// Hover 浮动弹窗
// ============================================================================

/**
 * 显示 hover 浮动弹窗
 */
async function showBatchHoverPopup(e) {
    const target = e.currentTarget;
    const path = target.dataset.path;
    const type = target.dataset.type; // 'summary' | 'toc'

    currentHoverElement = target;

    // 延迟显示避免快速滑过触发
    hoverPopupTimer = setTimeout(async () => {
        // 获取或创建浮动弹窗
        let popup = document.getElementById('batch-hover-popup');
        if (!popup) {
            popup = document.createElement('div');
            popup.id = 'batch-hover-popup';
            popup.className = 'batch-hover-popup';
            popup.innerHTML = `
                <div class="hover-popup-content">
                    <div class="hover-popup-header" id="hover-popup-title">加载中...</div>
                    <div class="hover-popup-body" id="hover-popup-body">
                        <div class="loading-placeholder"><div class="spinner"></div></div>
                    </div>
                </div>
            `;
            document.body.appendChild(popup);
        }

        // 重置内容为加载状态
        const titleEl = document.getElementById('hover-popup-title');
        const bodyEl = document.getElementById('hover-popup-body');
        titleEl.textContent = type === 'summary' ? '增强简介' : '目录详情';
        bodyEl.innerHTML = '<div class="loading-placeholder"><div class="spinner"></div> 分析加载中...</div>';

        // 定位弹窗
        const updatePosition = () => {
            const rect = target.getBoundingClientRect();
            popup.style.top = `${rect.bottom + 8}px`;
            // 确保不超出右边界
            let left = rect.left - 150;
            if (left + 320 > window.innerWidth) left = window.innerWidth - 330;
            if (left < 10) left = 10;
            popup.style.left = `${left}px`;
        };
        updatePosition();
        popup.classList.add('visible');

        // 交互处理
        popup.onmouseenter = () => {
            if (hoverPopupTimer) {
                clearTimeout(hoverPopupTimer);
                hoverPopupTimer = null;
            }
            if (hoverPopupHideTimer) {
                clearTimeout(hoverPopupHideTimer);
                hoverPopupHideTimer = null;
            }
        };
        popup.onmouseleave = () => {
            hideBatchHoverPopup();
        };

        // 检查缓存
        const cacheKey = `${type}:${path}`;
        if (hoverPopupCache[cacheKey]) {
            renderPopupContent(titleEl, bodyEl, type, hoverPopupCache[cacheKey]);
            return;
        }

        // 动态获取数据 - 从数据库加载，不触发生成
        try {
            let data = null;

            if (window.fetchLibraryBookDetails) {
                const details = await window.fetchLibraryBookDetails(path, true);
                console.log('[Batch Hover] API Response for', path, ':', details);

                if (type === 'summary') {
                    data = details?.summary || null;
                    console.log('[Batch Hover] Summary extracted:', data ? 'Found' : 'Not found', data?.substring(0, 100));
                } else if (type === 'toc') {
                    if (details && details.toc && details.toc.length > 0) {
                        data = { type: 'array', content: details.toc };
                        console.log('[Batch Hover] TOC array extracted:', details.toc.length, 'items');
                    } else if (details && details.toc_text) {
                        data = { type: 'text', content: details.toc_text };
                        console.log('[Batch Hover] TOC text extracted');
                    }
                }
            }

            if (data) {
                hoverPopupCache[cacheKey] = data;
                renderPopupContent(titleEl, bodyEl, type, data);
            } else {
                bodyEl.innerHTML = '<div class="empty-state-text">暂无数据</div>';
            }
        } catch (err) {
            console.error('Fetch popup details failed:', err);
            bodyEl.innerHTML = `<div class="error-text">加载失败: ${escapePopupHtml(err.message)}</div>`;
        }

    }, 300);
}

/**
 * 渲染弹窗内容
 */
function renderPopupContent(titleEl, bodyEl, type, data) {
    if (type === 'summary') {
        titleEl.textContent = '增强简介';
        bodyEl.innerHTML = escapePopupHtml(data).replace(/\n/g, '<br>');
    } else if (type === 'toc') {
        if (data.type === 'array') {
            const tocArray = data.content;
            titleEl.textContent = `目录 (${tocArray.length} 章)`;
            let html = '<ul class="toc-list">';
            tocArray.forEach(item => {
                const indent = item.level ? (item.level - 1) * 20 : 0;
                html += `<li style="padding-left:${indent}px">${escapePopupHtml(item.title)} <span class="toc-page">${escapePopupHtml(item.page || '')}</span></li>`;
            });
            html += '</ul>';
            bodyEl.innerHTML = html;
        } else if (data.type === 'text') {
            titleEl.textContent = '目录 (AI 整理)';
            const escapedText = escapePopupHtml(data.content)
                .replace(/\n/g, '<br>');
            bodyEl.innerHTML = `<div class="toc-text-content">${escapedText}</div>`;
        }
    }
}

/**
 * 隐藏 hover 浮动弹窗（延迟执行，允许鼠标移动到弹窗）
 */
function hideBatchHoverPopup() {
    if (hoverPopupTimer) {
        clearTimeout(hoverPopupTimer);
        hoverPopupTimer = null;
    }

    if (hoverPopupHideTimer) {
        clearTimeout(hoverPopupHideTimer);
    }

    hoverPopupHideTimer = setTimeout(() => {
        currentHoverElement = null;
        const popup = document.getElementById('batch-hover-popup');
        if (popup) {
            popup.classList.remove('visible');
        }
        hoverPopupHideTimer = null;
    }, 200);
}

// ============================================================================
// 详情弹窗（点击查看完整内容）
// ============================================================================

/**
 * 显示图书增强简介
 */
async function showBatchItemSummary(path) {
    try {
        const response = await fetch(`${API_BASE}/library/book_details?path=${encodeURIComponent(path)}`);
        if (!response.ok) throw new Error('获取详情失败');

        const data = await response.json();
        if (data.enhanced_summary) {
            showBatchDetailPopup('增强简介', data.enhanced_summary);
        } else {
            showNotification('暂无增强简介', 2000, 'warning');
        }
    } catch (e) {
        console.error('获取简介失败:', e);
        showNotification('获取简介失败', 2000, 'error');
    }
}

/**
 * 显示图书目录
 */
async function showBatchItemToc(path) {
    try {
        const response = await fetch(`${API_BASE}/library/book_details?path=${encodeURIComponent(path)}`);
        if (!response.ok) throw new Error('获取详情失败');

        const data = await response.json();
        if (data.toc) {
            showBatchDetailPopup('图书目录', data.toc);
        } else {
            showNotification('暂无目录信息', 2000, 'warning');
        }
    } catch (e) {
        console.error('获取目录失败:', e);
        showNotification('获取目录失败', 2000, 'error');
    }
}

/**
 * 显示详情弹窗
 */
function showBatchDetailPopup(title, content) {
    let popup = document.getElementById('batch-detail-popup');
    if (!popup) {
        popup = document.createElement('div');
        popup.id = 'batch-detail-popup';
        popup.className = 'batch-detail-popup';
        popup.innerHTML = `
            <div class="popup-content">
                <div class="popup-header">
                    <h4 id="popup-title"></h4>
                    <button class="btn-close" onclick="closeBatchDetailPopup()">
                        <i class="fa-solid fa-xmark"></i>
                    </button>
                </div>
                <div class="popup-body" id="popup-body"></div>
            </div>
        `;
        document.body.appendChild(popup);
    }

    document.getElementById('popup-title').textContent = title;
    document.getElementById('popup-body').innerHTML = content.replace(/\n/g, '<br>');
    popup.classList.add('visible');
}

function closeBatchDetailPopup() {
    const popup = document.getElementById('batch-detail-popup');
    if (popup) popup.classList.remove('visible');
}

// ============================================================================
// 导出到全局
// ============================================================================

window.hoverPopupCache = hoverPopupCache;
window.showBatchHoverPopup = showBatchHoverPopup;
window.hideBatchHoverPopup = hideBatchHoverPopup;
window.showBatchItemSummary = showBatchItemSummary;
window.showBatchItemToc = showBatchItemToc;
window.showBatchDetailPopup = showBatchDetailPopup;
window.closeBatchDetailPopup = closeBatchDetailPopup;
