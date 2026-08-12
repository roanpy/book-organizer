/**
 * libraryBatch.js - 在库批量处理主模块
 * 
 * 汇总导出批量处理相关的所有功能。
 * 子模块: libraryBatch/selection.js, libraryBatch/modal.js, libraryBatch/process.js
 */

/**
 * 刷新库树视图（保持选择状态）
 * 这是一个占位符，实际实现在 ui.js 中
 */
window.refreshLibraryTreeWithState = window.refreshLibraryTreeWithState || function () {
    if (window.fetchLibrary) {
        window.fetchLibrary();
    }
};

// ============================================================================
// 自定义格式列表（从 settings.js 暴露）
// ============================================================================

// 如果尚未定义，提供默认值
if (typeof window.convertFormats === 'undefined') {
    window.convertFormats = ['epub', 'mobi', 'azw3', 'azw', 'fb2', 'lit', 'lrf', 'pdb'];
}

// ============================================================================
// 重新导出（确保所有函数在此模块加载后可用）
// ============================================================================

// 这些函数已在子模块中导出到 window，这里仅做确认性声明
// selection.js 导出:
// - selectedLibraryBooks, toggleBookSelection, toggleFolderSelection
// - clearLibrarySelection, updateBatchDropdownForMode, updateBatchMenuVisibility
// - getLibraryBatchState, setLibraryBatchState

// modal.js 导出:
// - openLibraryBatchModal, closeLibraryBatchModal, removeFromBatch
// - updateBatchProgress, updateRowStatus, renderBatchList
// - showBatchItemSummary, showBatchItemToc, closeBatchDetailPopup

// process.js 导出:
// - startLibraryBatch, stopLibraryBatch
// - startBatchEnhance, startBatchConvert

console.log('[LibraryBatch] 模块已加载');
