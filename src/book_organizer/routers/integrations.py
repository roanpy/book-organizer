import os

from fastapi import APIRouter, HTTPException

from book_organizer.config import load_config
from book_organizer.file_ops import resolve_file_path

# Calibre
from book_organizer.pdf_converter import (
    convert_to_pdf,
    get_calibre_status_detail,
    is_convertible_format,
)

from .models import ConvertToPdfRequest

router = APIRouter()

# ============================================================
# Calibre PDF Conversion
# ============================================================


@router.get("/api/calibre/status")
def get_calibre_status():
    return get_calibre_status_detail()


@router.post("/api/calibre/convert")
def convert_to_pdf_endpoint(request: ConvertToPdfRequest):
    config = load_config()
    file_path = resolve_file_path(request.filename, config)

    if not file_path:
        raise HTTPException(status_code=404, detail=f"文件不存在: {request.filename}")

    if not is_convertible_format(file_path):
        ext = os.path.splitext(file_path.lower())[1]
        if ext == ".pdf":
            raise HTTPException(status_code=400, detail="已经是 PDF 格式，无需转换")
        raise HTTPException(status_code=400, detail=f"不支持的格式: {ext}")

    beta_features = config.get("beta_features", {})
    output_dir = beta_features.get("pdf_export_dir", "")
    if request.output_dir:
        requested_dir = os.path.realpath(os.path.expanduser(request.output_dir))
        configured_dir = os.path.realpath(os.path.expanduser(output_dir)) if output_dir else ""
        if not configured_dir or requested_dir != configured_dir:
            raise HTTPException(status_code=400, detail="请先在设置中配置 PDF 导出目录")

    output_dir = output_dir if output_dir else None

    result = convert_to_pdf(file_path, output_dir)

    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["message"])

    return result
