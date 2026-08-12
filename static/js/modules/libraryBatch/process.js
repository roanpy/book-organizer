/**
 * process.js - 批量处理逻辑
 * 
 * 处理批量增强和批量转换上传的核心逻辑。
 * 依赖: state.js, api.js, libraryBatch/selection.js, libraryBatch/modal.js
 */

// ============================================================================
// 批量信息增强
// ============================================================================

/**
 * 开始批量信息增强
 * 根据增强简介开关决定处理方式：
 * - 开关开启：使用合并API同时获取元数据和增强简介，节省约30-40% Token
 * - 开关关闭：跳过AI调用，仅更新已有信息
 */
async function startBatchEnhance() {
    const state = window.getLibraryBatchState();
    const batchProcessingQueue = state.queue;

    if (batchProcessingQueue.length === 0) {
        showNotification('没有需要处理的图书', 2000, 'warning');
        return;
    }

    window.setLibraryBatchState({ isProcessing: true, shouldStop: false });

    document.getElementById('lib-batch-start').classList.add('hidden');
    document.getElementById('lib-batch-stop').classList.remove('hidden');

    // 获取增强简介开关状态
    let isEnhancedEnabled = true;  // 默认开启
    try {
        const prefsRes = await fetch(`${API_BASE}/user_preferences`);
        const prefs = await prefsRes.json();
        isEnhancedEnabled = prefs.enhancedModeEnabled !== false;  // 默认 true
    } catch (e) {
        console.warn('获取用户偏好失败，使用默认设置:', e);
    }

    let processed = 0;
    const engine = document.getElementById('engine-select')?.value || 'deepseek';

    for (const item of batchProcessingQueue) {
        const currentState = window.getLibraryBatchState();
        if (currentState.shouldStop) {
            window.updateBatchProgress(processed, '已停止');
            break;
        }

        try {
            window.updateRowStatus(item.path, 'processing');
            window.updateBatchProgress(processed, `正在处理: ${item.name}`);

            let metadata = {};
            let enhancedSummary = '';

            if (isEnhancedEnabled) {
                // 增强简介开启：使用合并API
                const response = await fetch(`${API_BASE}/batch_enhance_single`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        filename: item.path,
                        engine: engine
                    })
                });

                if (!response.ok) {
                    const errData = await response.json();
                    throw new Error(errData.detail || '分析失败');
                }

                const result = await response.json();
                metadata = result.metadata || {};
                enhancedSummary = result.summary || '';

                // 使用后端返回的目录状态（后端在增强时已自动提取目录）
                if (result.has_toc) {
                    item.has_toc = true;
                }
            } else {
                // 增强简介关闭：跳过AI调用，尝试加载已有数据库信息
                console.log(`[BatchEnhance] 增强简介已关闭，跳过 AI 调用: ${item.name}`);
                // 从现有书籍信息中获取元数据（如果有）
                if (window.fetchLibraryBookDetails) {
                    try {
                        const details = await window.fetchLibraryBookDetails(item.path);
                        if (details) {
                            metadata = {
                                title: details.title || '',
                                author: details.author || '',
                                publisher: details.publisher || '',
                                series: details.series || '',
                                tags: details.tags || ''
                            };
                            // 注意：API 返回的是 summary 而非 enhanced_summary
                            enhancedSummary = details.summary || '';
                        }
                    } catch (e) {
                        console.warn('加载已有信息失败:', e);
                    }
                }
            }

            // 保存到数据库和文件 (只有在有新数据或更新时)
            const saveResponse = await fetch(`${API_BASE}/rename_only`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    original_filename: item.path,
                    metadata: {
                        title: metadata.title || '',
                        author: metadata.author || '',
                        publisher: metadata.publisher || '',
                        series: metadata.series || '',
                        tags: metadata.tags || '',
                        new_filename: item.name.replace(/\.[^/.]+$/, "")
                    },
                    summary: enhancedSummary
                })
            });

            if (!saveResponse.ok) {
                const errorData = await saveResponse.json();
                throw new Error(errorData.detail || '保存失败');
            }

            const saveData = await saveResponse.json();

            // 更新 item.path (如果发生了重命名)
            if (saveData.new_filename) {
                item.path = saveData.new_filename;
            }

            // 重新获取该书详情，以刷新 has_toc 和 has_enhanced_summary 状态
            let hasEnhancedSummary = !!enhancedSummary;  // 默认使用本次生成的结果
            let hasToc = item.has_toc;  // 保持原有 TOC 状态

            if (window.fetchLibraryBookDetails) {
                try {
                    const freshDetails = await window.fetchLibraryBookDetails(item.path);
                    console.log(`[BatchEnhance] 刷新书籍详情: ${item.name}`, freshDetails);
                    if (freshDetails) {
                        hasEnhancedSummary = freshDetails.has_enhanced || !!freshDetails.summary;
                        hasToc = (freshDetails.toc && freshDetails.toc.length > 0) || !!freshDetails.toc_text;
                        if (freshDetails.summary) enhancedSummary = freshDetails.summary;
                    }
                } catch (e) {
                    console.warn(`[BatchEnhance] 刷新书籍详情失败: ${item.name}`, e);
                }
            }

            // 使用新的 API：传递状态覆盖对象，确保在 updateRowStatus 内部正确更新
            window.updateRowStatus(item.path, 'done', 'enhance', true, {
                has_enhanced_summary: hasEnhancedSummary,
                has_toc: hasToc
            });

        } catch (e) {
            console.error(`处理 ${item.name} 失败:`, e);
            window.updateRowStatus(item.path, 'error');
        }

        processed++;
        window.updateBatchProgress(processed, `已完成 ${processed}/${batchProcessingQueue.length}`);
    }

    window.setLibraryBatchState({ isProcessing: false });
    document.getElementById('lib-batch-start').classList.remove('hidden');
    document.getElementById('lib-batch-stop').classList.add('hidden');

    // 刷新库列表以更新增强状态
    if (window.fetchLibrary) {
        await window.fetchLibrary();
    }

    const finalState = window.getLibraryBatchState();
    if (!finalState.shouldStop) {
        window.updateBatchProgress(batchProcessingQueue.length, '全部完成');
        showNotification(`批量增强完成: ${processed} 本`, 3000, 'success');
    }
}

// ============================================================================
// 批量转换上传
// ============================================================================

/**
 * 开始批量转换上传
 */
async function startBatchConvert() {
    const state = window.getLibraryBatchState();
    const batchProcessingQueue = state.queue;

    if (batchProcessingQueue.length === 0) {
        showNotification('没有需要处理的图书', 2000, 'warning');
        return;
    }

    window.setLibraryBatchState({ isProcessing: true, shouldStop: false });

    document.getElementById('lib-batch-start').classList.add('hidden');
    document.getElementById('lib-batch-stop').classList.remove('hidden');

    const needUpload = window.isGDriveConnected && window.isGDriveConnected() &&
        document.getElementById('gdrive-auto-upload')?.checked;

    let processed = 0;

    for (const item of batchProcessingQueue) {
        const currentState = window.getLibraryBatchState();
        if (currentState.shouldStop) {
            window.updateBatchProgress(processed, '已停止');
            break;
        }

        try {
            window.updateRowStatus(item.path, 'processing', 'convert');
            window.updateBatchProgress(processed, `正在处理: ${item.name}`);

            // 判断是否需要转换
            const ext = item.name.split('.').pop().toLowerCase();
            const convertFormats = window.convertFormats || ['epub', 'mobi', 'azw3', 'azw'];
            const needsConversion = convertFormats.includes(ext);

            if (needsConversion) {
                // 调用转换 API
                const convertResponse = await fetch(`${API_BASE}/calibre/convert`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filename: item.path })
                });

                if (!convertResponse.ok) {
                    const error = await convertResponse.json();
                    throw new Error(error.detail || '转换失败');
                }

                const convertResult = await convertResponse.json();
                window.updateRowStatus(item.path, 'done', 'convert');

                // 上传
                if (needUpload && convertResult.pdf_path) {
                    // 如果后端已经自动上传了，直接标记成功
                    if (convertResult.uploaded_to_drive) {
                        window.updateRowStatus(item.path, 'done', 'upload');
                        window.updateBatchProgress(processed, `处理完成: ${item.name} (自动上传成功)`);
                    } else {
                        // 否则前端触发上传
                        window.updateRowStatus(item.path, 'processing', 'upload');

                        const uploadResponse = await fetch(`${API_BASE}/google_drive/upload`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ file_path: convertResult.pdf_path })
                        });

                        if (uploadResponse.ok) {
                            window.updateRowStatus(item.path, 'done', 'upload');
                        } else {
                            window.updateRowStatus(item.path, 'error', 'upload');
                        }
                    }
                }
            } else {
                // 无需转换
                window.updateRowStatus(item.path, 'skipped', 'convert');

                // 直接上传原文件
                if (needUpload) {
                    window.updateRowStatus(item.path, 'processing', 'upload');

                    const uploadResponse = await fetch(`${API_BASE}/google_drive/upload`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ file_path: item.path })
                    });

                    if (uploadResponse.ok) {
                        window.updateRowStatus(item.path, 'done', 'upload');
                    } else {
                        window.updateRowStatus(item.path, 'error', 'upload');
                    }
                }
            }

        } catch (e) {
            console.error(`处理 ${item.name} 失败:`, e);
            window.updateRowStatus(item.path, 'error', 'convert');
        }

        processed++;
        window.updateBatchProgress(processed, `已完成 ${processed}/${batchProcessingQueue.length}`);
    }

    window.setLibraryBatchState({ isProcessing: false });
    document.getElementById('lib-batch-start').classList.remove('hidden');
    document.getElementById('lib-batch-stop').classList.add('hidden');

    // 刷新库列表以更新转换状态
    if (window.fetchLibrary) {
        await window.fetchLibrary();
    }

    const finalState = window.getLibraryBatchState();
    if (!finalState.shouldStop) {
        window.updateBatchProgress(batchProcessingQueue.length, '全部完成');
        showNotification(`批量处理完成: ${processed} 本`, 3000, 'success');
    }
}

// ============================================================================
// 控制函数
// ============================================================================

/**
 * 停止批量处理
 */
function stopLibraryBatch() {
    window.setLibraryBatchState({ shouldStop: true });
    showNotification('正在停止...', 2000, 'warning');
}

/**
 * 开始批量处理（统一入口）
 */
function startLibraryBatch() {
    const state = window.getLibraryBatchState();
    if (state.currentType === 'enhance') {
        startBatchEnhance();
    } else if (state.currentType === 'convert') {
        startBatchConvert();
    }
}

// ============================================================================
// 导出到全局
// ============================================================================

window.startLibraryBatch = startLibraryBatch;
window.stopLibraryBatch = stopLibraryBatch;
window.startBatchEnhance = startBatchEnhance;
window.startBatchConvert = startBatchConvert;
