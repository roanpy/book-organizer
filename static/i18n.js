/* Lightweight local UI translation. No network service or extra dependency. */
(function () {
    const translations = {
        '联网搜索': 'Web Search',
        '增强模式': 'Enhanced Mode',
        '识别目录': 'Detect TOC',
        '内容与搜索': 'Content & Search',
        '数据库增强': 'Database Enrichment',
        '自动上传到 Google Drive': 'Auto-upload to Google Drive',
        '离线模式': 'Offline Mode',
        '选择 AI 模型': 'Choose AI Model',
        '处理模式': 'Processing Mode',
        '批量增强': 'Batch Enrichment',
        '批量转换': 'Batch Conversion',
        '批量处理': 'Batch Processing',
        '顺序处理': 'Sequential Processing',
        '请先选择图书': 'Select books first',
        'AI配置': 'AI Settings',
        '云同步': 'Cloud Sync',
        '刷新': 'Refresh',
        '设置': 'Settings',
        '帮助': 'Help',
        '记录': 'Records',
        '入库整理': 'Organize',
        '在库管理': 'Library',
        '待入库': 'Inbox',
        '图书馆': 'Library',
        '总数': 'Total',
        '跳过': 'Skipped',
        '已增强': 'Enriched',
        '未增强': 'Not Enriched',
        '搜索... (空格支持多条件, +数字代表星级筛选)': 'Search... (space separates terms, +number filters ratings)',
        '清空': 'Clear',
        '请从左侧选择一本书开始整理': 'Select a book from the left to begin',
        '解析信息...': 'Reading metadata...',
        '点击查看大图': 'View full cover',
        'AI 分析': 'AI Analysis',
        '开始信息及简介分析': 'Analyze Info & Summary',
        '停止分析': 'Stop Analysis',
        '图书信息': 'Book Information',
        '书名': 'Title',
        '作者': 'Author',
        '识别信息': 'Identify Info',
        '增强简介': 'Enhanced Summary',
        '图书目录': 'Table of Contents',
        '预览': 'Preview',
        '导出': 'Export',
        '保存': 'Save',
        '显示来源': 'Display Source',
        '数据库': 'Database',
        '文件内置': 'Embedded',
        '系统设置': 'System Settings',
        '通用设置': 'General',
        'AI 模型': 'AI Models',
        '识别格式': 'Recognized Formats',
        '高级功能': 'Advanced',
        '目录配置': 'Folder Configuration',
        '设置源目录、目标目录及相关路径': 'Configure source, target, and related folders',
        '源目录 (Source)': 'Source Folder',
        '目标目录 (Target)': 'Target Folder',
        '数据目录 (Data Directory)': 'Data Directory',
        '默认路径: ~/.book_organizer': 'Default: ~/.book_organizer',
        '浏览': 'Browse',
        'PDF 导出目录 (Calibre 转换)': 'PDF Export Folder (Calibre)',
        '留空则使用源文件目录': 'Leave blank to use the source folder',
        'iCloud 同步': 'Folder Sync',
        '跨设备共享数据库、AI 规则和偏好；API Key 默认只保存在本机': 'Share the database, AI rules, and preferences across devices; API keys stay local by default',
        '同步设置': 'Sync Settings',
        '同步目录': 'Sync Folder',
        '敏感凭据同步': 'Sensitive Credential Sync',
        '验证连接': 'Test Connection',
        '配置 / 修改': 'Configure / Edit',
        '添加自定义 Provider': 'Add Custom Provider',
        '支持 OpenRouter, Groq, Azure, Claude 等任意 LiteLLM 兼容的 API': 'Supports OpenRouter, Groq, Azure, Claude, and other LiteLLM-compatible APIs',
        '已纳入格式': 'Enabled Formats',
        '格式数量': 'Format Counts',
        '输入格式，例如 epub 或 .pdf': 'Enter a format, such as epub or .pdf',
        '添加': 'Add',
        '搜索与内容展示': 'Search & Content',
        '目标区域重复图书搜索': 'Search for Similar Books',
        '优先加载简介/目录': 'Preferred Summary/TOC Source',
        '元数据': 'Metadata',
        '文件写入': 'File Writes',
        'EPUB 元数据写入': 'Write EPUB Metadata',
        'EPUB 增强简介写入': 'Write EPUB Enhanced Summary',
        'PDF 元数据写入': 'Write PDF Metadata',
        'PDF 增强简介写入': 'Write PDF Enhanced Summary',
        '外部集成与转换': 'Integrations & Conversion',
        'Google Drive 集成': 'Google Drive Integration',
        '未连接': 'Not Connected',
        '授权连接': 'Authorize',
        '断开': 'Disconnect',
        '上传凭据 (client_secrets.json)': 'Upload Credentials (client_secrets.json)',
        '如何获取配置?': 'How do I configure this?',
        '目标文件夹': 'Destination Folder',
        '根目录 (我的云端硬盘)': 'Root (My Drive)',
        'PDF 转换后自动上传': 'Upload after PDF conversion',
        '需转换格式': 'Conversion Formats',
        '输入格式 (如 epub)': 'Enter a format (for example, epub)',
        '保存设置': 'Save Settings',
        '保存高级设置': 'Save Advanced Settings',
        '保存识别格式': 'Save Formats',
        '取消': 'Cancel',
        '关闭': 'Close',
        '删除': 'Delete',
        '加载中...': 'Loading...',
        '分析中...': 'Analyzing...',
        '连接失败': 'Connection failed',
        '连接成功': 'Connection successful',
        '：': ': '
    };

    const requestedLocale = new URLSearchParams(window.location.search).get('locale');
    const systemLocale = requestedLocale || navigator.language || navigator.userLanguage || 'en-US';
    const isChinese = /^zh(?:[-_]|$)/i.test(systemLocale);
    const locale = isChinese ? 'zh-CN' : 'en';
    const pairs = Object.entries(translations).sort((a, b) => b[0].length - a[0].length);

    function translate(value) {
        if (isChinese || typeof value !== 'string') return value;
        return pairs.reduce((text, [source, target]) => text.replaceAll(source, target), value);
    }

    function translateRoot(root) {
        const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
        const nodes = [];
        while (walker.nextNode()) nodes.push(walker.currentNode);
        nodes.forEach(node => {
            if (!node.parentElement || ['SCRIPT', 'STYLE'].includes(node.parentElement.tagName)) return;
            const translated = translate(node.nodeValue);
            if (translated !== node.nodeValue) node.nodeValue = translated;
        });
        root.querySelectorAll?.('[title], [aria-label], [placeholder], [data-tooltip]').forEach(element => {
            ['title', 'aria-label', 'placeholder', 'data-tooltip'].forEach(attribute => {
                if (element.hasAttribute(attribute)) {
                    const current = element.getAttribute(attribute);
                    const translated = translate(current);
                    if (translated !== current) element.setAttribute(attribute, translated);
                }
            });
        });
    }

    function initialize() {
        document.documentElement.lang = locale;
        if (isChinese) return;
        translateRoot(document.body);
        new MutationObserver(mutations => mutations.forEach(mutation => {
            if (mutation.type === 'characterData') {
                const current = mutation.target.nodeValue;
                const translated = translate(current);
                if (translated !== current) mutation.target.nodeValue = translated;
            } else if (mutation.type === 'childList') {
                mutation.addedNodes.forEach(node => {
                    if (node.nodeType === Node.ELEMENT_NODE) translateRoot(node);
                    if (node.nodeType === Node.TEXT_NODE) node.nodeValue = translate(node.nodeValue);
                });
            } else {
                const value = mutation.target.getAttribute(mutation.attributeName);
                const translated = translate(value);
                if (translated !== value) mutation.target.setAttribute(mutation.attributeName, translated);
            }
        })).observe(document.body, {
            subtree: true,
            childList: true,
            characterData: true,
            attributes: true,
            attributeFilter: ['title', 'aria-label', 'placeholder', 'data-tooltip']
        });
    }

    window.BookOrganizerI18n = { locale, isChinese, translate };
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initialize, { once: true });
    } else {
        initialize();
    }
})();
