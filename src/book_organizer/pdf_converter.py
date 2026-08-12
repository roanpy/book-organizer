# -*- coding: utf-8 -*-
"""
PDF 转换模块 - 使用 Calibre 将电子书转换为 PDF

支持多种电子书格式（EPUB/MOBI/AZW/AZW3 等）到 PDF 的转换。
此模块仅依赖本机安装的 Calibre，无需任何外部 API 认证。
"""

import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Optional

# Calibre 支持的可转换格式（不包括 PDF）
CONVERTIBLE_FORMATS = {
    ".epub",
    ".mobi",
    ".azw",
    ".azw3",
    ".fb2",
    ".lit",
    ".lrf",
    ".pdb",
}
CALIBRE_TOOL_NAMES = frozenset({"ebook-convert", "fetch-ebook-metadata"})
PAPER_SIZES = frozenset({"a4", "a5", "letter", "legal"})


# Calibre 在不同操作系统上的默认安装路径
CALIBRE_BIN_DIRS = {
    "Darwin": [  # macOS
        "/Applications/calibre.app/Contents/MacOS",
        os.path.expanduser("~/Applications/calibre.app/Contents/MacOS"),
        "/opt/homebrew/bin",
        "/usr/local/bin",
        "/usr/bin",
    ],
    "Windows": [
        r"C:\Program Files\Calibre2",
        r"C:\Program Files (x86)\Calibre2",
    ],
    "Linux": [
        "/usr/bin",
        "/usr/local/bin",
        os.path.expanduser("~/.local/bin"),
    ],
}


def find_calibre_tool(tool_name: str) -> tuple[bool, str]:
    """Find a Calibre CLI tool without bundling Calibre into the app."""
    if tool_name not in CALIBRE_TOOL_NAMES:
        return False, "不支持的 Calibre 工具"

    configured_dir = os.environ.get("BOOK_ORGANIZER_CALIBRE_BIN_DIR", "").strip()
    dirs_to_check = [configured_dir] if configured_dir else []
    dirs_to_check.extend(CALIBRE_BIN_DIRS.get(platform.system(), []))

    executable_name = f"{tool_name}.exe" if platform.system() == "Windows" else tool_name

    path_from_env = ""
    if tool_name == "ebook-convert":
        path_from_env = os.environ.get("BOOK_ORGANIZER_EBOOK_CONVERT", "").strip()
    elif tool_name == "fetch-ebook-metadata":
        path_from_env = os.environ.get("BOOK_ORGANIZER_FETCH_EBOOK_METADATA", "").strip()

    def validated(path: str) -> str:
        resolved = os.path.realpath(os.path.abspath(os.path.expanduser(path)))
        return resolved if os.path.isfile(resolved) and os.access(resolved, os.X_OK) else ""

    explicit_path = validated(path_from_env) if path_from_env else ""
    if explicit_path:
        return True, explicit_path

    path_from_path = shutil.which(executable_name)
    validated_path = validated(path_from_path) if path_from_path else ""
    if validated_path:
        return True, validated_path

    for bin_dir in dirs_to_check:
        if not bin_dir:
            continue
        candidate = os.path.join(os.path.expanduser(bin_dir), executable_name)
        validated_path = validated(candidate)
        if validated_path:
            return True, validated_path

    return False, f"未找到 Calibre {tool_name} 工具。请安装 Calibre 或设置工具路径。"


def get_calibre_tool_version(tool_path: str) -> str:
    try:
        result = subprocess.run(
            [tool_path, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return ""

    output = (result.stdout or result.stderr or "").strip()
    return output.splitlines()[0] if output else ""


def check_calibre_installed() -> tuple[bool, str]:
    """
    检测本机是否安装了 Calibre 的 ebook-convert 工具。

    Returns:
        tuple[bool, str]: (是否已安装, 可执行文件路径或错误信息)
    """
    return find_calibre_tool("ebook-convert")


def get_calibre_status_detail() -> dict:
    installed, path_or_msg = check_calibre_installed()
    return {
        "installed": installed,
        "path": path_or_msg if installed else "",
        "message": "Calibre 已安装" if installed else path_or_msg,
        "version": get_calibre_tool_version(path_or_msg) if installed else "",
        "convertible_formats": sorted(CONVERTIBLE_FORMATS) if installed else [],
    }


def is_convertible_format(filename: str) -> bool:
    """
    检查文件是否为可转换的电子书格式（非 PDF）。

    Args:
        filename: 文件名或路径

    Returns:
        bool: 是否可转换为 PDF
    """
    ext = os.path.splitext(filename.lower())[1]
    return ext in CONVERTIBLE_FORMATS


def convert_to_pdf(
    input_path: str,
    output_dir: Optional[str] = None,
    paper_size: str = "a4",
) -> dict:
    """
    将电子书文件转换为 PDF（支持 EPUB/MOBI/AZW 等格式）。

    Args:
        input_path: 电子书文件的绝对路径
        output_dir: PDF 输出目录（默认与源文件同目录）
        paper_size: PDF 纸张大小（默认 a4）

    Returns:
        dict: {
            "success": bool,
            "pdf_path": str (成功时),
            "message": str (状态/错误信息)
        }
    """
    if paper_size not in PAPER_SIZES:
        return {"success": False, "message": "不支持的 PDF 纸张尺寸"}

    # 验证输入文件
    input_path = os.path.abspath(input_path)
    if not os.path.isfile(input_path):
        return {"success": False, "message": f"文件不存在: {input_path}"}

    if not is_convertible_format(input_path):
        ext = os.path.splitext(input_path.lower())[1]
        if ext == ".pdf":
            return {"success": False, "message": "已经是 PDF 格式，无需转换"}
        return {"success": False, "message": f"不支持的格式: {ext}"}

    # 检查 Calibre
    installed, calibre_path = check_calibre_installed()
    if not installed:
        return {"success": False, "message": calibre_path}

    # 确定输出路径
    input_file = Path(input_path)
    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
    else:
        output_dir = input_file.parent

    pdf_filename = input_file.stem + ".pdf"
    pdf_path = output_dir / pdf_filename

    # 构建命令
    cmd = [
        calibre_path,
        str(input_path),
        str(pdf_path),
        f"--paper-size={paper_size}",
        "--pdf-page-numbers",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 分钟超时
        )

        if result.returncode == 0 and pdf_path.exists():
            return {
                "success": True,
                "pdf_path": str(pdf_path),
                "message": f"转换成功: {pdf_filename}",
            }
        else:
            error_msg = result.stderr.strip() if result.stderr else ""
            # 检查常见错误
            has_drm = "DRM" in error_msg.upper()
            return {
                "success": False,
                "message": "文件可能受 DRM 保护，无法转换" if has_drm else "转换失败，请查看应用日志",
            }

    except subprocess.TimeoutExpired:
        return {"success": False, "message": "转换超时（超过5分钟）"}
    except Exception:
        return {"success": False, "message": "转换异常，请查看应用日志"}


# 向后兼容的别名
convert_epub_to_pdf = convert_to_pdf
