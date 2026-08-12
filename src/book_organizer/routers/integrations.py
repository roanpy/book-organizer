import json
import os
import shutil

from fastapi import APIRouter, File, HTTPException, UploadFile

from book_organizer.config import load_config
from book_organizer.file_ops import resolve_file_path

# Google Drive
from book_organizer.google_drive import (
    CLIENT_SECRETS_FILE,
    check_google_drive_status,
    disconnect,
    get_authenticated_service,
    get_or_create_default_folder,
    list_folders,
    start_oauth_flow,
    upload_file,
)

# Calibre
from book_organizer.pdf_converter import (
    convert_to_pdf,
    get_calibre_status_detail,
    is_convertible_format,
)

from .models import ConvertToPdfRequest, DirectUploadRequest, DriveUploadRequest

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

    output_dir = request.output_dir
    if not output_dir:
        beta_features = config.get("beta_features", {})
        output_dir = beta_features.get("pdf_export_dir", "")

    output_dir = output_dir if output_dir else None

    result = convert_to_pdf(file_path, output_dir)

    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["message"])

    # Auto upload to Google Drive if configured
    beta_features = config.get("beta_features", {})
    gdrive_config = beta_features.get("google_drive", {})
    auto_upload = gdrive_config.get("auto_upload", False)

    if auto_upload and result.get("pdf_path"):
        if get_authenticated_service():
            folder_id = gdrive_config.get("target_folder_id", "")
            if not folder_id:
                folder_result = get_or_create_default_folder()
                if folder_result["success"]:
                    folder_id = folder_result["folder_id"]

            upload_result = upload_file(
                result["pdf_path"], folder_id if folder_id else None
            )
            if upload_result["success"]:
                result["uploaded_to_drive"] = True
                result["drive_link"] = upload_result.get("web_link", "")
                result["message"] += " | 已上传到 Google Drive"
            else:
                result["uploaded_to_drive"] = False
                result["upload_error"] = upload_result.get("message", "上传失败")

    return result


# ============================================================
# Google Drive
# ============================================================


@router.get("/api/google_drive/status")
def get_google_drive_status_endpoint():
    return check_google_drive_status()


@router.post("/api/google_drive/auth")
def start_google_drive_auth_endpoint():
    result = start_oauth_flow()
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["message"])
    return result


@router.post("/api/google_drive/disconnect")
def disconnect_google_drive_endpoint():
    return disconnect()


@router.get("/api/google_drive/folders")
def list_google_drive_folders_endpoint(parent_id: str = "root"):
    result = list_folders(parent_id)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["message"])
    return result


@router.post("/api/direct_upload")
def direct_upload_to_google_drive(request: DirectUploadRequest):
    config = load_config()
    target_dir = config.get("target_dir")
    beta_features = config.get("beta_features", {})

    source_path = resolve_file_path(request.file_path, config)

    if not source_path or not os.path.exists(source_path):
        # Try logic in server.py (Library mode fallback)
        if target_dir:
            target_path = os.path.join(target_dir, request.file_path)
            if os.path.exists(target_path):
                source_path = target_path

    if not source_path or not os.path.exists(source_path):
        if os.path.exists(request.file_path):
            source_path = request.file_path

    if not source_path or not os.path.exists(source_path):
        raise HTTPException(status_code=404, detail=f"文件不存在: {request.file_path}")

    filename = os.path.basename(source_path)
    export_dir = beta_features.get("pdf_export_dir", "")
    upload_source = source_path

    if export_dir and os.path.isdir(export_dir):
        export_path = os.path.join(export_dir, filename)
        if os.path.abspath(source_path) != os.path.abspath(export_path):
            shutil.copy2(source_path, export_path)
            upload_source = export_path

    service = get_authenticated_service()
    if not service:
        raise HTTPException(status_code=401, detail="Google Drive 未授权")

    gdrive_config = beta_features.get("google_drive", {})
    folder_id = gdrive_config.get("target_folder_id", "")
    if not folder_id:
        folder_result = get_or_create_default_folder()
        if folder_result["success"]:
            folder_id = folder_result["folder_id"]

    upload_result = upload_file(upload_source, folder_id if folder_id else None)

    if not upload_result["success"]:
        raise HTTPException(
            status_code=500, detail=upload_result.get("message", "上传失败")
        )

    return {
        "success": True,
        "filename": filename,
        "file_id": upload_result.get("file_id", ""),
        "web_link": upload_result.get("web_link", ""),
        "message": f"已上传: {filename}",
    }


@router.post("/api/google_drive/upload")
def upload_to_google_drive_endpoint(request: DriveUploadRequest):
    result = upload_file(request.file_path, request.folder_id)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["message"])
    return result


@router.post("/api/google_drive/upload_credentials")
async def upload_google_drive_credentials(file: UploadFile = File(...)):
    if not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Must be a JSON file")

    try:
        content = await file.read()
        try:
            secrets = json.loads(content)
            if "installed" not in secrets and "web" not in secrets:
                raise HTTPException(
                    status_code=400, detail="Invalid client_secrets.json format"
                )
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON content")

        os.makedirs(os.path.dirname(CLIENT_SECRETS_FILE), exist_ok=True)
        with open(CLIENT_SECRETS_FILE, "wb") as f:
            f.write(content)

        return {"success": True, "message": "Credentials uploaded successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
