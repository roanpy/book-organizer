/**
 * selection.js - 在库管理多选功能
 * 
 * 处理图书和文件夹的多选、状态更新等。
 * 依赖: state.js
 */

// ============================================================================
// 状态管理
// ============================================================================

// 已选中的图书路径集合
let selectedLibraryBooks = new Set();

// 批量处理队列
let batchProcessingQueue = [];

// 批量处理状态
let isLibraryBatchProcessing = false;
let shouldStopLibraryBatch = false;
let currentBatchType = null; // 'enhance' | 'convert'

// ============================================================================
// 多选功能
// ============================================================================

/**
 * 切换单本书的选中状态
 * @param {string} path - 图书路径
 * @param {boolean} checked - 是否选中
 */
function toggleBookSelection(path, checked) {
    if (checked) {
        selectedLibraryBooks.add(path);
    } else {
        selectedLibraryBooks.delete(path);
    }
    updateSelectionToolbar();
    updateFolderCheckboxStates();
}

/**
 * 切换文件夹的选中状态（级联选择所有子文件）
 * @param {string} folderPath - 文件夹路径
 * @param {boolean} checked - 是否选中
 */
function toggleFolderSelection(folderPath, checked) {
    // 使用当前过滤后的图书列表，确保只选择当前视图中可见的图书
    const booksSource = window.currentFilteredLibraryBooks || libraryBooks;

    // 找到该文件夹下的所有图书
    const folderBooks = booksSource.filter(book => {
        const category = book.category || '';
        return category === folderPath || category.startsWith(folderPath + '/');
    });

    folderBooks.forEach(book => {
        if (checked) {
            selectedLibraryBooks.add(book.path);
        } else {
            selectedLibraryBooks.delete(book.path);
        }
        // 更新对应的 checkbox
        const checkbox = document.querySelector(`.book-checkbox[data-path="${CSS.escape(book.path)}"]`);
        if (checkbox) checkbox.checked = checked;
    });

    updateSelectionToolbar();
    updateFolderCheckboxStates();
}

/**
 * 更新文件夹 checkbox 状态（基于子文件选中情况）
 */
function updateFolderCheckboxStates() {
    // 使用当前过滤后的图书列表计算复选框状态
    const booksSource = window.currentFilteredLibraryBooks || libraryBooks;

    document.querySelectorAll('.folder-checkbox').forEach(folderCheckbox => {
        const folderPath = folderCheckbox.dataset.folderPath;
        const folderBooks = booksSource.filter(book => {
            const category = book.category || '';
            return category === folderPath || category.startsWith(folderPath + '/');
        });

        if (folderBooks.length === 0) return;

        const selectedCount = folderBooks.filter(b => selectedLibraryBooks.has(b.path)).length;

        if (selectedCount === 0) {
            folderCheckbox.checked = false;
            folderCheckbox.indeterminate = false;
        } else if (selectedCount === folderBooks.length) {
            folderCheckbox.checked = true;
            folderCheckbox.indeterminate = false;
        } else {
            folderCheckbox.checked = false;
            folderCheckbox.indeterminate = true;
        }
    });
}

// 暴露给全局，以便 ui.js 在渲染树后调用
window.updateFolderCheckboxStates = updateFolderCheckboxStates;

/**
 * 更新选择工具栏显示
 */
function updateSelectionToolbar() {
    // 侧边栏工具栏已移除，现在使用顶部下拉菜单
    const badgeEl = document.getElementById('lib-selected-badge');
    const menuCountEl = document.getElementById('lib-selected-count-menu');
    const selectionItem = document.getElementById('lib-selection-item');

    // Check current mode based on UI state
    // 入库整理模式下，不应显示在库管理的选择信息
    const isOrganizeMode = document.getElementById('organize-mode-btn')?.classList.contains('active');

    const count = selectedLibraryBooks.size;

    // 更新顶部菜单的 badge
    if (badgeEl) {
        if (isOrganizeMode) {
            badgeEl.classList.add('hidden');
        } else {
            badgeEl.textContent = count;
            badgeEl.classList.toggle('hidden', count === 0);
        }
    }

    // 更新下拉菜单中的选中数量
    if (menuCountEl) {
        menuCountEl.textContent = count;
    }

    // 显示/隐藏选中数量项 - 使用 style.display 确保可靠控制
    if (selectionItem) {
        if (isOrganizeMode || count === 0) {
            selectionItem.style.display = 'none';
        } else {
            selectionItem.style.display = '';
        }
    }

    // 更新批量选项的可用状态
    updateBatchMenuVisibility(count > 0);
}

/**
 * 更新顶部批量下拉菜单的可见性
 * @param {boolean} hasSelection - 是否有选中的图书
 */
function updateBatchMenuVisibility(hasSelection) {
    const enhanceItem = document.getElementById('lib-batch-enhance-menu');
    const convertItem = document.getElementById('lib-batch-convert-menu');
    const hintItem = document.getElementById('lib-no-selection-hint');

    if (hasSelection) {
        if (enhanceItem) enhanceItem.classList.remove('disabled');
        if (convertItem) convertItem.classList.remove('disabled');
        if (hintItem) hintItem.classList.add('hidden');
    } else {
        if (enhanceItem) enhanceItem.classList.add('disabled');
        if (convertItem) convertItem.classList.add('disabled');
        if (hintItem) hintItem.classList.remove('hidden');
    }
}

/**
 * 根据模式更新批量下拉菜单
 * @param {string} mode - 'library' | 'inbound'
 */
function updateBatchDropdownForMode(mode) {
    const inboundItems = document.querySelectorAll('.dropdown-item.inbound-only');
    const libraryItems = document.querySelectorAll('.dropdown-item.library-only');
    const badgeEl = document.getElementById('lib-selected-badge');
    const selectionInfoEl = document.getElementById('lib-selection-item');
    const selectionCountEl = document.getElementById('lib-selected-count-menu');

    if (mode === 'library') {
        // 在库管理模式：隐藏入库选项，显示在库选项
        inboundItems.forEach(item => item.classList.add('hidden'));
        libraryItems.forEach(item => item.classList.remove('hidden'));
        // 根据选中数量更新 badge 和菜单项
        const count = selectedLibraryBooks ? selectedLibraryBooks.size : 0;
        if (badgeEl) {
            badgeEl.textContent = count;
            badgeEl.classList.toggle('hidden', count === 0);
        }
        if (selectionCountEl) {
            selectionCountEl.textContent = count;
        }
        // 使用 style.display 控制显隐，更可靠
        if (selectionInfoEl) {
            selectionInfoEl.style.display = count > 0 ? '' : 'none';
        }
        updateBatchMenuVisibility(count > 0);
    } else {
        // 入库管理模式：显示入库选项，隐藏在库选项和所有选择相关显示
        inboundItems.forEach(item => item.classList.remove('hidden'));
        libraryItems.forEach(item => item.classList.add('hidden'));
        if (badgeEl) badgeEl.classList.add('hidden');
        // 强制隐藏选择信息
        if (selectionInfoEl) selectionInfoEl.style.display = 'none';
    }
}

/**
 * 初始化顶部菜单项的点击事件
 */
function initBatchMenuEvents() {
    const enhanceItem = document.getElementById('lib-batch-enhance-menu');
    const convertItem = document.getElementById('lib-batch-convert-menu');

    if (enhanceItem) {
        enhanceItem.addEventListener('click', (e) => {
            e.stopPropagation();
            if (!enhanceItem.classList.contains('disabled') && selectedLibraryBooks.size > 0) {
                openLibraryBatchModal('enhance');
            }
        });
    }

    if (convertItem) {
        convertItem.addEventListener('click', (e) => {
            e.stopPropagation();
            if (!convertItem.classList.contains('disabled') && selectedLibraryBooks.size > 0) {
                openLibraryBatchModal('convert');
            }
        });
    }
}

// 在 DOMContentLoaded 时初始化
document.addEventListener('DOMContentLoaded', initBatchMenuEvents);

/**
 * 清除所有选择
 */
function clearLibrarySelection() {
    selectedLibraryBooks.clear();

    // 清除所有 checkbox
    document.querySelectorAll('.book-checkbox').forEach(cb => cb.checked = false);
    document.querySelectorAll('.folder-checkbox').forEach(cb => {
        cb.checked = false;
        cb.indeterminate = false;
    });

    updateSelectionToolbar();
}

// ============================================================================
// 导出到全局
// ============================================================================

window.selectedLibraryBooks = selectedLibraryBooks;
window.batchProcessingQueue = batchProcessingQueue;
window.toggleBookSelection = toggleBookSelection;
window.toggleFolderSelection = toggleFolderSelection;
window.clearLibrarySelection = clearLibrarySelection;
window.updateBatchDropdownForMode = updateBatchDropdownForMode;
window.updateBatchMenuVisibility = updateBatchMenuVisibility;

// 导出状态变量访问器
window.getLibraryBatchState = () => ({
    isProcessing: isLibraryBatchProcessing,
    shouldStop: shouldStopLibraryBatch,
    currentType: currentBatchType,
    queue: batchProcessingQueue
});

window.setLibraryBatchState = (state) => {
    if (typeof state.isProcessing !== 'undefined') isLibraryBatchProcessing = state.isProcessing;
    if (typeof state.shouldStop !== 'undefined') shouldStopLibraryBatch = state.shouldStop;
    if (typeof state.currentType !== 'undefined') currentBatchType = state.currentType;
    if (typeof state.queue !== 'undefined') batchProcessingQueue = state.queue;
};
