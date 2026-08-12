@echo off
REM ==========================================
REM      Book Organizer - Windows Build
REM ==========================================
REM
REM 版本: 0.6.2 (2026-01-05)
REM 功能: 构建独立 Windows 应用 (.exe)
REM
REM 主要特性:
REM   - 自动创建虚拟环境并安装依赖
REM   - 使用 PyInstaller 打包
REM   - 自动优化体积 (删除不必要的 Google API 定义)
REM   - 包含所有 AI 引擎支持 (Gemini/DeepSeek/Ollama/自定义)
REM   - 包含 Google Drive 集成和 Calibre PDF 转换支持
REM
REM 使用方法:
REM   scripts\build_windows.bat
REM
REM 输出:
REM   dist\BookOrganizer\BookOrganizer.exe
REM
REM ==========================================

echo ==========================================
echo      Book Organizer - Windows Build v0.6.2
echo ==========================================

REM 导航到项目根目录
cd /d "%~dp0\.."

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    pause
    exit /b 1
)

echo [OK] Python found.

REM Create virtual environment if it doesn't exist
if not exist venv (
    echo [INFO] Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo [INFO] Activating virtual environment...
call venv\Scripts\activate

REM Install dependencies
echo [INFO] Installing dependencies...
pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
if exist requirements-build.txt (
    pip install -r requirements-build.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
) else (
    pip install pyinstaller pywebview -i https://pypi.tuna.tsinghua.edu.cn/simple
)
pip check

REM Clean old build files
echo [INFO] Cleaning old build files...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM Build the executable
echo [INFO] Building Executable (using spec file)...
pyinstaller --noconfirm --clean BookOrganizer.spec

if not exist "dist\BookOrganizer\BookOrganizer.exe" (
    echo.
    echo [ERROR] Build failed!
    pause
    exit /b 1
)

echo.
echo [INFO] Optimizing build size...

REM Clean up unused Google API docs, keeping only drive.v3.json
set "GDOCS_PATH=dist\BookOrganizer\_internal\googleapiclient\discovery_cache\documents"
if exist "%GDOCS_PATH%" (
    echo   Cleaning Google API definition files...
    powershell -Command "Get-ChildItem -Path '%GDOCS_PATH%' -Filter '*.json' | Where-Object { $_.Name -ne 'drive.v3.json' } | Remove-Item -Force"
    echo   [OK] Cleaned Google API docs
)

REM Clean up dist-info folders
for /d %%d in ("dist\BookOrganizer\_internal\google_api_python_client-*.dist-info") do (
    rmdir /s /q "%%d" 2>nul
)

echo.
echo ==========================================
echo [SUCCESS] Build Complete!
echo.
echo Executable: dist\BookOrganizer\BookOrganizer.exe
echo.
echo Next Steps:
echo 1. Test the application
echo 2. Verify AI features (Gemini/DeepSeek/Ollama)
echo 3. Test enhanced summary generation
echo 4. Verify PDF/EPUB metadata read/write
echo 5. Verify Google Drive integration
echo ==========================================
pause
