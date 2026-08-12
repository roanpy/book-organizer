/**
 * zoom.js - 封面缩放功能
 * 
 * 封面图片缩放、拖拽和预览。
 * 依赖: state.js
 */

function updateZoomTransform() {
    const zoomImg = document.getElementById('cover-zoom-image');
    zoomImg.style.transform = `translate(${currentTranslateX}px, ${currentTranslateY}px) scale(${currentZoom})`;
    zoomImg.style.cursor = currentZoom > 1 ? (isDragging ? 'grabbing' : 'grab') : 'default';
}

window.openCoverZoom = () => {
    const coverImg = document.getElementById('book-cover');
    const zoomImg = document.getElementById('cover-zoom-image');
    const modal = document.getElementById('cover-zoom-modal');
    const container = document.getElementById('zoom-container');

    // 检查封面图片是否可见且有有效的src
    if (!coverImg.classList.contains('hidden') && coverImg.src && coverImg.naturalWidth > 0) {
        // 优化策略：优先复用已加载的 Blob URL，实现零延迟查看，即使用户正在进行分析也能瞬间打开
        if (coverImg.src && coverImg.src.startsWith('blob:')) {
            // 直接复用内存中的 blob，无需再次请求服务器
            zoomImg.src = coverImg.src;
        } else {
            // Fallback: 只有在没有缓存 blob 的情况下才尝试从服务器请求
            const bookPath = typeof getCurrentBookPath === 'function' ? getCurrentBookPath() : (window.currentBookPath || window.currentBook);
            if (bookPath) {
                const encodedPath = encodeURIComponent(bookPath);
                zoomImg.src = `/api/cover/${encodedPath}?t=${Date.now()}`;
            } else {
                zoomImg.src = coverImg.src;
            }
        }

        currentZoom = 1;
        currentTranslateX = 0;
        currentTranslateY = 0;
        isDragging = false;

        updateZoomTransform();
        modal.classList.remove('hidden');

        setTimeout(() => {
            if (container) container.scrollTop = 0;
        }, 50);
    }
};

window.closeCoverZoom = () => {
    const modal = document.getElementById('cover-zoom-modal');
    if (modal && !modal.classList.contains('hidden')) {
        modal.classList.add('hidden');
    }
};

window.zoomCover = (delta) => {
    currentZoom = Math.max(0.5, Math.min(5, currentZoom + delta));
    updateZoomTransform();
};

window.resetZoom = () => {
    currentZoom = 1;
    currentTranslateX = 0;
    currentTranslateY = 0;
    updateZoomTransform();
};

window.openInNewWindow = () => {
    const coverImg = document.getElementById('book-cover');
    if (coverImg && coverImg.src) {
        window.open(coverImg.src, '_blank');
    }
};

function setupZoomInteractions() {
    const zoomImg = document.getElementById('cover-zoom-image');
    const modal = document.getElementById('cover-zoom-modal');

    zoomImg.addEventListener('mousedown', (e) => {
        if (currentZoom <= 1) return;
        e.preventDefault();
        isDragging = true;
        startX = e.clientX - currentTranslateX;
        startY = e.clientY - currentTranslateY;
        updateZoomTransform();
    });

    window.addEventListener('mousemove', (e) => {
        if (!isDragging) return;
        e.preventDefault();
        currentTranslateX = e.clientX - startX;
        currentTranslateY = e.clientY - startY;
        updateZoomTransform();
    });

    window.addEventListener('mouseup', () => {
        if (isDragging) {
            isDragging = false;
            updateZoomTransform();
        }
    });

    zoomImg.addEventListener('dragstart', (e) => e.preventDefault());

    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            closeCoverZoom();
        }
    });
}
