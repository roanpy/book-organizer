# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, copy_metadata


def keep_litellm_runtime_module(module_name):
    """Keep LiteLLM completion runtime, exclude optional proxy/UI server code."""
    excluded_prefixes = (
        'litellm.experimental_mcp_client',
        'litellm.proxy',
        'litellm.integrations.test_httpx',
        'litellm.tests',
        'litellm.types.proxy',
    )
    return not module_name.startswith(excluded_prefixes)

datas = [
    ('static', 'static'),
    ('data/README.md', 'data'),
    ('LICENSE', '.'),
    ('THIRD_PARTY_NOTICES.md', '.'),
    ('src/book_organizer', 'book_organizer'),
]
binaries = []
hiddenimports = ['uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.auto', 'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto', 'uvicorn.lifespan', 'uvicorn.lifespan.on', 'webview', 'pypdf', 'ebooklib', 'ebooklib.epub', 'fitz', 'pymupdf', 'pikepdf', 'litellm', 'tiktoken', 'tiktoken_ext', 'tiktoken_ext.openai_public', 'google.generativeai', 'google.auth.transport.requests', 'ollama', 'openai', 'ddgs', 'requests', 'book_organizer', 'book_organizer.routers', 'book_organizer.routers.config', 'book_organizer.routers.library', 'book_organizer.routers.analysis', 'book_organizer.routers.integrations', 'book_organizer.routers.sync', 'book_organizer.routers.models', 'book_organizer.config', 'book_organizer.ai_engines', 'book_organizer.metadata', 'book_organizer.file_ops', 'book_organizer.search', 'book_organizer.transfer', 'book_organizer.database', 'book_organizer.toc_extractor', 'book_organizer.pdf_converter', 'bs4', 'lxml']

# Preserve license metadata for bundled AGPL dependencies.
datas += copy_metadata('EbookLib')
datas += copy_metadata('PyMuPDF')

# Collect LiteLLM runtime resources. The app only calls litellm.completion();
# proxy/UI modules pull optional server dependencies and increase bundle noise.
tmp_ret = collect_all('litellm', filter_submodules=keep_litellm_runtime_module)
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

tmp_ret = collect_all('tiktoken')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]


a = Analysis(
    ['src/server.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'pandas', 'scipy', 'tkinter', 'unittest', 'test', 'tests', 'PIL.ImageQt', 'PIL.ImageTk', 'PIL.FpxImagePlugin'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='BookOrganizer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/icon.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='BookOrganizer',
)
app = BUNDLE(
    coll,
    name='BookOrganizer.app',
    icon='assets/icon.icns',
    bundle_identifier='com.peter.bookorganizer',
    info_plist={
        'CFBundleShortVersionString': '0.8.3',
        'CFBundleVersion': '0.8.3',
    },
)
