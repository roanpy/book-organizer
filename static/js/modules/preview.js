/**
 * preview.js - Read-only PDF/EPUB/TXT/MD preview.
 *
 * 依赖: api.js, state.js
 */

const BOOK_DIRECT_PREVIEW_FORMATS = new Set(['pdf', 'epub', 'txt', 'md', 'markdown']);
let bookPreviewSequence = 0;
let activePreviewTarget = null;
let activePreviewObservers = [];
let previewFullscreenFallback = false;

function escapePreviewHtml(value) {
    if (typeof escapeHtmlText === 'function') return escapeHtmlText(value);
    const div = document.createElement('div');
    div.textContent = value == null ? '' : String(value);
    return div.innerHTML;
}

function getBookPreviewExtension(path) {
    const cleanPath = String(path || '').split(/[?#]/)[0];
    const dotIndex = cleanPath.lastIndexOf('.');
    return dotIndex >= 0 ? cleanPath.slice(dotIndex + 1).toLowerCase() : '';
}

function isBookPreviewSupported(path) {
    return !!path;
}

function getBookPreviewBasename(path) {
    return String(path || '').split('/').pop() || '当前文件';
}

function getPreviewFallbackConfirmMessage(resolution, originalPath) {
    const sourceExt = getBookPreviewExtension(originalPath).toUpperCase() || '当前格式';

    if (resolution?.source === 'same_name_pdf') {
        const pdfName = resolution.filename || getBookPreviewBasename(resolution.preview_path || '');
        return `${sourceExt} 暂不支持直接预览。\n\n已找到同名 PDF：${pdfName}\n是否打开这个 PDF 预览？`;
    }

    if (resolution?.action === 'convert') {
        return `${sourceExt} 暂不支持直接预览，且未找到同名 PDF。\n\n将按设置目录导出 PDF 后打开，可能耗时较长。\n是否继续？`;
    }

    return '';
}

function updatePreviewButton(target = null) {
    const btn = document.getElementById('btn-preview-book');
    if (!btn) return;

    const bookPath = target || (typeof getCurrentBookPath === 'function' ? getCurrentBookPath() : null);
    const hasBook = !!bookPath;
    btn.classList.toggle('hidden', !hasBook);
    btn.disabled = !hasBook;

    if (hasBook) {
        const ext = getBookPreviewExtension(bookPath).toUpperCase() || '文件';
        btn.title = BOOK_DIRECT_PREVIEW_FORMATS.has(ext.toLowerCase())
            ? `${ext} 预览`
            : `${ext} 将优先打开同名 PDF，必要时导出 PDF`;
    } else {
        btn.title = '选择图书后预览';
    }
}
window.updatePreviewButton = updatePreviewButton;

function cleanupBookPreviewRuntime() {
    activePreviewObservers.forEach((observer) => observer.disconnect());
    activePreviewObservers = [];
}

function getPreviewEls() {
    return {
        modal: document.getElementById('book-preview-modal'),
        content: document.getElementById('book-preview-content'),
        title: document.getElementById('book-preview-title'),
        status: document.getElementById('book-preview-status'),
    };
}

function setBookPreviewLoading(title = '预览', detail = '') {
    cleanupBookPreviewRuntime();
    const { title: titleEl, content, status } = getPreviewEls();

    if (titleEl) titleEl.textContent = title;
    if (status) status.textContent = detail;
    if (content) {
        content.innerHTML = `
            <div class="preview-loading">
                <div class="spinner"></div>
                ${detail ? `<p>${escapePreviewHtml(detail)}</p>` : ''}
            </div>
        `;
    }
}

function renderBookPreviewError(message) {
    cleanupBookPreviewRuntime();
    const { content, status } = getPreviewEls();
    if (status) status.textContent = '';
    if (content) {
        content.innerHTML = `
            <div class="preview-empty-state">
                <i class="fa-solid fa-triangle-exclamation"></i>
                <p>${escapePreviewHtml(message || '预览加载失败')}</p>
            </div>
        `;
    }
}

function renderPreviewToc(tocEntries, emptyText = '无内置目录') {
    const entries = Array.isArray(tocEntries) ? tocEntries : [];
    if (!entries.length) {
        return `
            <div class="book-preview-toc-empty">
                <i class="fa-solid fa-list-ol"></i>
                <span>${escapePreviewHtml(emptyText)}</span>
            </div>
        `;
    }

    return `
        <ol class="book-preview-toc-list">
            ${entries.map((entry) => {
                const level = Math.max(0, Math.min(Number(entry.level || 0), 6));
                const dataAttrs = [
                    entry.page ? `data-page="${Number(entry.page)}"` : '',
                    Number.isInteger(entry.target_index) ? `data-chapter-index="${entry.target_index}"` : '',
                    entry.anchor ? `data-anchor="${escapePreviewHtml(entry.anchor)}"` : '',
                ].filter(Boolean).join(' ');
                return `
                    <li class="book-preview-toc-level-${level}">
                        <button type="button" ${dataAttrs} title="${escapePreviewHtml(entry.title || '')}">
                            ${escapePreviewHtml(entry.title || '')}
                        </button>
                    </li>
                `;
            }).join('')}
        </ol>
    `;
}

function renderPreviewLayout({ tocEntries = [], tocTitle = '目录', bodyHtml = '', emptyTocText = '无内置目录' }) {
    const { content } = getPreviewEls();
    if (!content) return null;

    content.innerHTML = `
        <div class="book-preview-shell">
            <aside class="book-preview-toc-panel">
                <div class="book-preview-toc-title">${escapePreviewHtml(tocTitle)}</div>
                <nav id="book-preview-toc" class="book-preview-toc">
                    ${renderPreviewToc(tocEntries, emptyTocText)}
                </nav>
            </aside>
            <main id="book-preview-main" class="book-preview-main">
                ${bodyHtml}
            </main>
        </div>
    `;
    return {
        toc: document.getElementById('book-preview-toc'),
        main: document.getElementById('book-preview-main'),
    };
}

function setPreviewStatus(text) {
    const statusEl = document.getElementById('book-preview-status');
    if (statusEl) statusEl.textContent = text || '';
}

function renderPdfPreview(info, requestedPath) {
    cleanupBookPreviewRuntime();
    const { title } = getPreviewEls();
    const filename = info?.filename || requestedPath;
    const pageCount = Math.max(1, Number(info?.page_count || 1));
    const tocEntries = Array.isArray(info?.toc) ? info.toc : [];

    if (title) title.textContent = filename;
    setPreviewStatus(`PDF · ${pageCount} 页 · 目录 ${tocEntries.length} 条`);

    const pagesHtml = Array.from({ length: pageCount }, (_, index) => {
        const page = index + 1;
        return `
            <section class="pdf-preview-page" id="pdf-preview-page-${page}" data-page="${page}">
                <div class="pdf-preview-page-label">第 ${page} 页</div>
                <div class="pdf-preview-page-placeholder">
                    <div class="spinner-small"></div>
                </div>
            </section>
        `;
    }).join('');

    const layout = renderPreviewLayout({
        tocEntries,
        tocTitle: 'PDF 目录',
        emptyTocText: '无内置目录',
        bodyHtml: `
            <div class="pdf-preview-reader" data-page-count="${pageCount}">
                <div class="pdf-preview-toolbar">
                    <button class="btn-secondary btn-sm" id="pdf-preview-prev" title="上一页">
                        <i class="fa-solid fa-chevron-left"></i>
                    </button>
                    <span id="pdf-preview-page-label">1 / ${pageCount}</span>
                    <button class="btn-secondary btn-sm" id="pdf-preview-next" title="下一页">
                        <i class="fa-solid fa-chevron-right"></i>
                    </button>
                </div>
                <div class="pdf-preview-pages">
                    ${pagesHtml}
                </div>
            </div>
        `,
    });
    bindPdfPreviewControls(layout, requestedPath, pageCount);
}

function bindPdfPreviewControls(layout, requestedPath, pageCount) {
    if (!layout?.main) return;
    const mainEl = layout.main;
    const pages = Array.from(mainEl.querySelectorAll('.pdf-preview-page'));
    const labelEl = document.getElementById('pdf-preview-page-label');
    const prevBtn = document.getElementById('pdf-preview-prev');
    const nextBtn = document.getElementById('pdf-preview-next');
    let currentPage = 1;

    const updateCurrentPage = (page) => {
        currentPage = Math.max(1, Math.min(Number(page || 1), pageCount));
        if (labelEl) labelEl.textContent = `${currentPage} / ${pageCount}`;
        if (prevBtn) prevBtn.disabled = currentPage <= 1;
        if (nextBtn) nextBtn.disabled = currentPage >= pageCount;
        setPreviewStatus(`PDF · ${currentPage} / ${pageCount}`);
    };

    const loadPageImage = (pageEl) => {
        if (!pageEl || pageEl.dataset.loaded === 'true') return;
        const page = Number(pageEl.dataset.page || 1);
        pageEl.dataset.loaded = 'true';
        const placeholder = pageEl.querySelector('.pdf-preview-page-placeholder');
        const image = document.createElement('img');
        image.alt = `第 ${page} 页`;
        image.loading = 'lazy';
        image.onload = () => {
            image.classList.add('loaded');
            if (placeholder && placeholder.contains(image)) {
                placeholder.replaceWith(image);
            } else if (placeholder) {
                placeholder.replaceWith(image);
            }
        };
        image.onerror = () => {
            if (placeholder) {
                placeholder.innerHTML = '<span class="text-muted">页面加载失败</span>';
            }
        };
        if (placeholder) {
            placeholder.innerHTML = '';
            placeholder.appendChild(image);
        }
        image.src = `${API_BASE}/preview/pdf/page?path=${encodeURIComponent(requestedPath)}&page=${page}`;
        if (image.complete && image.naturalWidth > 0) {
            image.onload();
        }
    };

    const preloadAroundPage = (page) => {
        [page, page + 1, page - 1].forEach((candidate) => {
            if (candidate < 1 || candidate > pageCount) return;
            loadPageImage(document.getElementById(`pdf-preview-page-${candidate}`));
        });
    };

    const goToPage = (page) => {
        const safePage = Math.max(1, Math.min(Number(page || 1), pageCount));
        const pageEl = document.getElementById(`pdf-preview-page-${safePage}`);
        if (pageEl) {
            preloadAroundPage(safePage);
            pageEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
        updateCurrentPage(safePage);
    };

    if (prevBtn) prevBtn.onclick = () => goToPage(currentPage - 1);
    if (nextBtn) nextBtn.onclick = () => goToPage(currentPage + 1);
    if (layout.toc) {
        layout.toc.onclick = (event) => {
            const btn = event.target.closest('button[data-page]');
            if (btn) goToPage(Number(btn.dataset.page || 1));
        };
    }

    const imageObserver = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (entry.isIntersecting) loadPageImage(entry.target);
        });
    }, { root: mainEl, rootMargin: '900px 0px' });

    const pageObserver = new IntersectionObserver((entries) => {
        const visible = entries
            .filter((entry) => entry.isIntersecting)
            .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (visible) {
            const page = Number(visible.target.dataset.page || 1);
            updateCurrentPage(page);
            preloadAroundPage(page);
        }
    }, { root: mainEl, threshold: [0.35, 0.65] });

    pages.forEach((pageEl) => {
        imageObserver.observe(pageEl);
        pageObserver.observe(pageEl);
    });
    activePreviewObservers.push(imageObserver, pageObserver);
    goToPage(1);
}

async function renderEpubPreview(manifest, requestedPath, sequence) {
    cleanupBookPreviewRuntime();
    const { title } = getPreviewEls();
    const chapters = Array.isArray(manifest?.chapters) ? manifest.chapters : [];
    const tocEntries = Array.isArray(manifest?.toc) ? manifest.toc : [];
    const displayTitle = manifest?.title || manifest?.filename || 'EPUB 预览';

    if (title) title.textContent = displayTitle;
    setPreviewStatus(`EPUB · ${chapters.length} 章 · 目录 ${tocEntries.length} 条`);

    if (!chapters.length) {
        renderBookPreviewError('未读取到可预览正文');
        return;
    }

    const chaptersHtml = chapters.map((chapter) => `
        <section class="epub-preview-chapter" id="epub-preview-chapter-${chapter.index}" data-index="${chapter.index}" data-path="${escapePreviewHtml(requestedPath)}">
            <h4>${escapePreviewHtml(chapter.title || `章节 ${Number(chapter.index) + 1}`)}</h4>
            <div class="epub-preview-chapter-body">
                <div class="preview-loading compact"><div class="spinner-small"></div></div>
            </div>
        </section>
    `).join('');

    const layout = renderPreviewLayout({
        tocEntries,
        tocTitle: 'EPUB 目录',
        emptyTocText: '无内置目录',
        bodyHtml: `<article class="epub-preview-reader">${chaptersHtml}</article>`,
    });
    bindEpubPreviewControls(layout, requestedPath, sequence);
}

function bindEpubPreviewControls(layout, requestedPath, sequence) {
    if (!layout?.main) return;
    const mainEl = layout.main;
    const chapters = Array.from(mainEl.querySelectorAll('.epub-preview-chapter'));

    const loadChapter = async (section) => {
        if (!section || section.dataset.loaded === 'true') return;
        section.dataset.loaded = 'true';
        const index = Number(section.dataset.index || 0);
        try {
            const data = await fetchJson(
                `${API_BASE}/preview/epub/chapter?path=${encodeURIComponent(requestedPath)}&index=${index}`,
                {},
                'EPUB 章节加载失败'
            );
            if (sequence !== bookPreviewSequence || activePreviewTarget !== requestedPath) return;
            const body = section.querySelector('.epub-preview-chapter-body');
            if (body) body.innerHTML = data?.html || '<p class="text-muted">空章节</p>';
        } catch (e) {
            const body = section.querySelector('.epub-preview-chapter-body');
            if (body) body.innerHTML = `<p class="text-muted">${escapePreviewHtml(formatApiErrorMessage(e, '章节加载失败'))}</p>`;
        }
    };

    const goToChapter = (index) => {
        const section = document.getElementById(`epub-preview-chapter-${index}`);
        if (section) {
            loadChapter(section);
            section.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    };

    if (layout.toc) {
        layout.toc.onclick = (event) => {
            const btn = event.target.closest('button[data-chapter-index]');
            if (btn) goToChapter(Number(btn.dataset.chapterIndex || 0));
        };
    }

    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (entry.isIntersecting) loadChapter(entry.target);
        });
    }, { root: mainEl, rootMargin: '700px 0px' });

    chapters.forEach((section) => observer.observe(section));
    activePreviewObservers.push(observer);
    goToChapter(0);
}

function renderTextPreview(data) {
    cleanupBookPreviewRuntime();
    const { title } = getPreviewEls();
    const tocEntries = Array.isArray(data?.toc) ? data.toc : [];
    const displayTitle = data?.filename || '文本预览';
    const formatLabel = data?.format === 'markdown' ? 'Markdown' : 'TXT';

    if (title) title.textContent = displayTitle;
    setPreviewStatus(`${formatLabel} · ${data?.char_count || 0} 字符 · ${data?.encoding || ''}`);

    const layout = renderPreviewLayout({
        tocEntries,
        tocTitle: `${formatLabel} 目录`,
        emptyTocText: '未识别到标题',
        bodyHtml: `<article class="text-preview-reader ${data?.format === 'markdown' ? 'markdown-preview-reader' : ''}">${data?.html || ''}</article>`,
    });

    if (layout?.toc) {
        layout.toc.onclick = (event) => {
            const btn = event.target.closest('button[data-anchor]');
            if (!btn) return;
            const target = document.getElementById(btn.dataset.anchor);
            if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        };
    }
}

async function openBookPreview(target = null) {
    const bookPath = target || (typeof getCurrentBookPath === 'function' ? getCurrentBookPath() : null);
    if (!bookPath) {
        showNotification('请先选择一本图书', 3000, 'warning');
        return;
    }
    if (!isBookPreviewSupported(bookPath)) {
        showNotification('当前格式暂不支持预览', 3000, 'warning');
        return;
    }

    const { modal } = getPreviewEls();
    if (!modal) return;

    const isDirectPreview = BOOK_DIRECT_PREVIEW_FORMATS.has(getBookPreviewExtension(bookPath));
    const sequence = ++bookPreviewSequence;
    activePreviewTarget = bookPath;
    if (isDirectPreview) {
        modal.classList.remove('hidden');
        setBookPreviewLoading(getBookPreviewBasename(bookPath), '正在准备预览...');
    } else {
        showNotification('正在检查可用预览方式...', 2000, 'info');
    }

    try {
        const resolution = await fetchJson(
            `${API_BASE}/preview/resolve?path=${encodeURIComponent(bookPath)}`,
            {},
            '预览解析失败'
        );
        if (sequence !== bookPreviewSequence || activePreviewTarget !== bookPath) return;

        if (!resolution?.success || resolution.action === 'unsupported') {
            throw new Error(resolution?.message || '当前格式暂不支持预览');
        }

        const fallbackConfirmMessage = !isDirectPreview
            ? getPreviewFallbackConfirmMessage(resolution, bookPath)
            : '';
        if (fallbackConfirmMessage && !confirm(fallbackConfirmMessage)) {
            if (sequence === bookPreviewSequence) {
                activePreviewTarget = null;
                cleanupBookPreviewRuntime();
                modal.classList.add('hidden');
            }
            showNotification('已取消预览', 2000, 'info');
            return;
        }

        modal.classList.remove('hidden');
        setBookPreviewLoading(resolution.filename || getBookPreviewBasename(bookPath), '正在加载预览...');

        let previewPath = resolution.preview_path || resolution.path || bookPath;
        if (resolution.action === 'convert') {
            setBookPreviewLoading(resolution.filename || '导出 PDF', '正在按配置目录导出 PDF...');
            if (typeof window.convertEpubToPdf !== 'function') {
                throw new Error('导出功能未初始化');
            }
            const convertResult = await window.convertEpubToPdf(resolution.path || bookPath);
            if (!convertResult?.success || !convertResult.pdf_path) {
                throw new Error(convertResult?.message || 'PDF 导出失败');
            }
            previewPath = convertResult.pdf_path;
            if (sequence !== bookPreviewSequence) return;
            showNotification(`PDF 已生成: ${previewPath.split('/').pop()}`, 4000, 'success');
        }

        activePreviewTarget = previewPath;
        const info = await fetchJson(
            `${API_BASE}/preview/info?path=${encodeURIComponent(previewPath)}`,
            {},
            '预览信息加载失败'
        );
        if (sequence !== bookPreviewSequence || activePreviewTarget !== previewPath) return;

        if (info.format === 'pdf') {
            renderPdfPreview(info, previewPath);
            return;
        }

        if (info.format === 'epub') {
            const manifest = await fetchJson(
                `${API_BASE}/preview/epub/manifest?path=${encodeURIComponent(previewPath)}`,
                {},
                'EPUB 目录加载失败'
            );
            if (sequence !== bookPreviewSequence || activePreviewTarget !== previewPath) return;
            await renderEpubPreview(manifest, previewPath, sequence);
            return;
        }

        if (info.format === 'txt' || info.format === 'markdown') {
            const data = await fetchJson(
                `${API_BASE}/preview/text?path=${encodeURIComponent(previewPath)}`,
                {},
                '文本预览加载失败'
            );
            if (sequence !== bookPreviewSequence || activePreviewTarget !== previewPath) return;
            renderTextPreview(data);
            return;
        }

        throw new Error('当前格式暂不支持预览');
    } catch (e) {
        if (sequence !== bookPreviewSequence) return;
        const message = formatApiErrorMessage(e, '预览加载失败');
        renderBookPreviewError(message);
        showNotification(message, 5000, 'error');
    }
}
window.openBookPreview = openBookPreview;

function setBookPreviewFullscreenState(active) {
    const { modal } = getPreviewEls();
    const btn = document.getElementById('toggle-book-preview-fullscreen');
    if (modal) modal.classList.toggle('is-fullscreen', !!active);
    if (btn) {
        btn.innerHTML = active
            ? '<i class="fa-solid fa-compress"></i>'
            : '<i class="fa-solid fa-expand"></i>';
        btn.title = active ? '退出全屏' : '全屏';
    }
}

async function toggleBookPreviewFullscreen() {
    const modalContent = document.querySelector('#book-preview-modal .book-preview-modal-content');
    if (!modalContent) return;

    if (document.fullscreenElement) {
        await document.exitFullscreen().catch(() => {});
        previewFullscreenFallback = false;
        setBookPreviewFullscreenState(false);
        return;
    }

    if (previewFullscreenFallback) {
        previewFullscreenFallback = false;
        setBookPreviewFullscreenState(false);
        return;
    }

    if (modalContent.requestFullscreen) {
        try {
            await modalContent.requestFullscreen();
            setBookPreviewFullscreenState(true);
            return;
        } catch (e) {
            console.warn('[Preview] Fullscreen API failed, using CSS fallback', e);
        }
    }
    previewFullscreenFallback = true;
    setBookPreviewFullscreenState(true);
}
window.toggleBookPreviewFullscreen = toggleBookPreviewFullscreen;

function closeBookPreview() {
    bookPreviewSequence += 1;
    activePreviewTarget = null;
    cleanupBookPreviewRuntime();

    if (document.fullscreenElement) {
        document.exitFullscreen().catch(() => {});
    }
    previewFullscreenFallback = false;
    setBookPreviewFullscreenState(false);

    const { modal, content, status } = getPreviewEls();
    if (modal) modal.classList.add('hidden');
    if (content) content.innerHTML = '';
    if (status) status.textContent = '';
}
window.closeBookPreview = closeBookPreview;

function initBookPreview() {
    updatePreviewButton(null);

    const closeBtn = document.getElementById('close-book-preview');
    if (closeBtn) closeBtn.onclick = closeBookPreview;

    const fullscreenBtn = document.getElementById('toggle-book-preview-fullscreen');
    if (fullscreenBtn) fullscreenBtn.onclick = toggleBookPreviewFullscreen;

    const modal = document.getElementById('book-preview-modal');
    if (modal) {
        modal.addEventListener('click', (event) => {
            if (event.target === modal) closeBookPreview();
        });
    }

    document.addEventListener('fullscreenchange', () => {
        const modalContent = document.querySelector('#book-preview-modal .book-preview-modal-content');
        setBookPreviewFullscreenState(document.fullscreenElement === modalContent || previewFullscreenFallback);
    });

    document.addEventListener('keydown', (event) => {
        if (event.key !== 'Escape') return;
        const previewModal = document.getElementById('book-preview-modal');
        if (!previewModal || previewModal.classList.contains('hidden')) return;

        if (previewFullscreenFallback) {
            previewFullscreenFallback = false;
            setBookPreviewFullscreenState(false);
            return;
        }
        if (!document.fullscreenElement) {
            closeBookPreview();
        }
    });
}
window.initBookPreview = initBookPreview;
