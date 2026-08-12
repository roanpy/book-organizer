/* Lightweight local UI translation. No network service or extra dependency. */
(function () {
    const translations = {
        '联网搜索': 'Web Search',
        '增强模式': 'Enhanced Mode',
        '识别目录': 'Detect TOC',
        '内容与搜索': 'Content & Search',
        '数据库增强': 'Database Enrichment',
        '离线模式': 'Offline Mode',
        '未配置': 'Not Configured',
        '本地功能可用': 'Local Features Available',
        '批量': 'Batch',
        '核心规则': 'Core Rules',
        '增强规则': 'Enhanced Rules',
        '附加规则': 'Additional Rules',
        '历史参考': 'History Reference',
        '字段提取': 'Field Extraction',
        '内容与搜索控制': 'Content & Search Controls',
        '目录规则': 'TOC Rules',
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
        '开始信息分析': 'Analyze Information',
        '停止分析': 'Stop Analysis',
        '图书信息': 'Book Information',
        '大小': 'Size',
        '修改时间': 'Modified',
        '类型': 'Type',
        '预览不可用 (文件可能未下载)': 'Preview unavailable (the file may not be downloaded)',
        '书名': 'Title',
        '作者': 'Author',
        '支持多作者用 & 分隔': 'separate multiple authors with &',
        '出版社': 'Publisher',
        '丛书/系列': 'Series',
        '标签 (逗号分隔)': 'Tags (comma-separated)',
        '目标文件名预览': 'Target Filename Preview',
        '点击上方按钮生成增强简介': 'Use the button above to generate an enhanced summary',
        '例如: 时代的喧嚣': 'Example: Designing Reliable Systems',
        '例如: [日] 村上春树': 'Example: Alex Morgan',
        '例如: 中信出版社': 'Example: Northstar Press',
        '例如: 理想国译丛': 'Example: Systems Library',
        '例如: 文学, 诗歌': 'Example: systems, design',
        '识别信息': 'Identify Info',
        '增强简介': 'Enhanced Summary',
        '图书目录': 'Table of Contents',
        '预览': 'Preview',
        '导出': 'Export',
        '保存': 'Save',
        '显示来源': 'Display Source',
        '数据库': 'Database',
        '正在检查数据库健康状态...': 'Checking database health...',
        '数据库健康检查暂不可用。': 'Database health check is temporarily unavailable.',
        '数据库完整，已扫描': 'Database is healthy. Scanned',
        '个文件。': ' files.',
        '数据库需关注：': 'Database needs attention: ',
        '项（只读检查，不会自动修改）。': ' issues (read-only; no automatic changes).',
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
        '格式转换': 'Format Conversion',
        '需转换格式': 'Conversion Formats',
        '以下格式将在导出时转换为 PDF，结果保存到配置的导出目录；未配置时保存在源文件旁边。': 'These formats are converted to PDF on export. Files are saved to the configured export folder, or beside the source file when no folder is configured.',
        '将选中格式批量导出为 PDF（需安装 Calibre）': 'Export selected formats to PDF in batches (Calibre required)',
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
    const exactTranslations = {
        '出版': 'Publisher',
        '丛书': 'Series',
        '标签': 'Tags'
    };

    const requestedLocale = new URLSearchParams(window.location.search).get('locale');
    const systemLocale = requestedLocale || navigator.language || navigator.userLanguage || 'en-US';
    const isChinese = /^zh(?:[-_]|$)/i.test(systemLocale);
    const locale = isChinese ? 'zh-CN' : 'en';
    const pairs = Object.entries(translations).sort((a, b) => b[0].length - a[0].length);

    function translate(value) {
        if (isChinese || typeof value !== 'string') return value;
        const trimmed = value.trim();
        if (exactTranslations[trimmed]) {
            return value.replace(trimmed, exactTranslations[trimmed]);
        }
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
