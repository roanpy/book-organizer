# -*- coding: utf-8 -*-
"""
Google Drive 集成模块

提供 OAuth 2.0 认证和文件上传到 Google Drive 的功能。
用于将转换后的 PDF 上传到云端，便于与 NotebookLM 等服务集成。
"""

import os
from typing import Optional

from google.auth.transport.requests import Request

# Google API 依赖
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# 权限范围：仅请求对应用创建文件的访问权限（最小权限原则）
# 不请求 userinfo.email，避免 SCOPE 冲突且更安全
SCOPES = ["https://www.googleapis.com/auth/drive.file"]

# 配置目录
APP_DIR = os.path.join(os.path.expanduser("~"), ".book_organizer")
TOKEN_FILE = os.path.join(APP_DIR, "google_drive_token.json")

# 默认凭据文件位置
CLIENT_SECRETS_FILE = os.path.join(APP_DIR, "client_secrets.json")  # 用户上传的应用凭据
DEFAULT_CREDENTIALS_PATH = os.path.join(
    APP_DIR, "google_credentials.json"
)  # 生成的用户 Token


def get_credentials_path() -> str:
    """获取 OAuth 凭据文件路径"""
    # 1. 优先使用用户上传到配置目录的凭据 (生产环境/打包应用)
    if os.path.exists(CLIENT_SECRETS_FILE):
        return CLIENT_SECRETS_FILE

    # 2. 回退到项目 data 目录 (开发环境)
    # 注意：在打包应用中，__file__ 路径可能在临时目录，data 可能不可访问
    # 这个逻辑主要用于开发调试
    try:
        project_data = os.path.join(os.path.dirname(__file__), "..", "..", "data")
        if os.path.exists(project_data):
            for f in os.listdir(project_data):
                if f.startswith("client_secret") and f.endswith(".json"):
                    return os.path.join(project_data, f)
    except Exception:
        pass

    return ""


def check_google_drive_status() -> dict:
    """
    检查 Google Drive 连接状态。

    Returns:
        dict: {
            "configured": bool,     # 是否已配置凭据
            "authenticated": bool,  # 是否已完成授权
            "user_email": str,      # 已授权用户的邮箱（如有）
            "message": str
        }
    """
    credentials_path = get_credentials_path()

    # 检查凭据文件
    if not credentials_path or not os.path.exists(credentials_path):
        return {
            "configured": False,
            "authenticated": False,
            "user_email": "",
            "message": "未找到 Google 凭据文件",
        }

    # 检查 token
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
            if creds and creds.valid:
                # Token 有效，无需调用 userinfo API（避免额外权限请求）
                return {
                    "configured": True,
                    "authenticated": True,
                    "user_email": "",
                    "message": "已连接 Google Drive",
                }
            elif creds and creds.expired and creds.refresh_token:
                # Token 过期但可刷新
                creds.refresh(Request())
                save_token(creds)
                return {
                    "configured": True,
                    "authenticated": True,
                    "user_email": "",
                    "message": "Token 已自动刷新",
                }
        except Exception as e:
            return {
                "configured": True,
                "authenticated": False,
                "user_email": "",
                "message": f"Token 无效: {str(e)}",
            }

    return {
        "configured": True,
        "authenticated": False,
        "user_email": "",
        "message": "凭据已配置，请点击授权连接",
    }


def save_token(creds: Credentials) -> None:
    """保存授权 Token 到本地"""
    os.makedirs(APP_DIR, exist_ok=True)
    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())


def start_oauth_flow() -> dict:
    """
    启动 OAuth 2.0 授权流程。

    会在本地启动临时 HTTP 服务器接收回调，
    并自动打开浏览器让用户授权。

    Returns:
        dict: {"success": bool, "message": str, "user_email": str}
    """
    credentials_path = get_credentials_path()

    if not credentials_path or not os.path.exists(credentials_path):
        return {
            "success": False,
            "message": "未找到凭据文件，请先配置 credentials.json",
        }

    try:
        flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
        # 使用本地服务器方式，自动打开浏览器
        creds = flow.run_local_server(port=0, open_browser=True)

        # 保存 token
        save_token(creds)

        # 授权成功，无需调用 userinfo API
        return {"success": True, "message": "授权成功", "user_email": ""}
    except Exception as e:
        return {"success": False, "message": f"授权失败: {str(e)}"}


def get_authenticated_service():
    """获取已认证的 Google Drive 服务实例"""
    if not os.path.exists(TOKEN_FILE):
        return None

    try:
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            save_token(creds)

        if creds and creds.valid:
            return build("drive", "v3", credentials=creds)
    except Exception:
        pass

    return None


def list_folders(parent_id: str = "root") -> dict:
    """
    列出 Google Drive 中的文件夹。

    Args:
        parent_id: 父文件夹 ID，默认为根目录

    Returns:
        dict: {"success": bool, "folders": list, "message": str}
    """
    service = get_authenticated_service()
    if not service:
        return {"success": False, "folders": [], "message": "未授权"}

    try:
        query = f"'{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        results = (
            service.files()
            .list(q=query, pageSize=50, fields="files(id, name)")
            .execute()
        )

        folders = results.get("files", [])
        return {
            "success": True,
            "folders": folders,
            "message": f"找到 {len(folders)} 个文件夹",
        }
    except Exception as e:
        return {"success": False, "folders": [], "message": str(e)}


# 默认上传文件夹名称
DEFAULT_FOLDER_NAME = "NotebookLLM"


def get_or_create_default_folder() -> dict:
    """
    获取或创建默认上传文件夹 (NotebookLLM)。

    Returns:
        dict: {"success": bool, "folder_id": str, "message": str}
    """
    service = get_authenticated_service()
    if not service:
        return {"success": False, "folder_id": "", "message": "未授权"}

    try:
        # 先查找是否已存在
        query = f"name='{DEFAULT_FOLDER_NAME}' and 'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        folders = results.get("files", [])

        if folders:
            # 文件夹已存在
            return {
                "success": True,
                "folder_id": folders[0]["id"],
                "message": f"使用已有文件夹: {DEFAULT_FOLDER_NAME}",
            }

        # 创建新文件夹
        folder_metadata = {
            "name": DEFAULT_FOLDER_NAME,
            "mimeType": "application/vnd.google-apps.folder",
        }
        folder = service.files().create(body=folder_metadata, fields="id").execute()

        return {
            "success": True,
            "folder_id": folder.get("id"),
            "message": f"已创建文件夹: {DEFAULT_FOLDER_NAME}",
        }
    except Exception as e:
        return {"success": False, "folder_id": "", "message": str(e)}


def upload_file(
    file_path: str, folder_id: Optional[str] = None, file_name: Optional[str] = None
) -> dict:
    """
    上传文件到 Google Drive。

    Args:
        file_path: 本地文件路径
        folder_id: 目标文件夹 ID（None 表示根目录）
        file_name: 上传后的文件名（None 表示使用原文件名）

    Returns:
        dict: {
            "success": bool,
            "file_id": str,
            "web_link": str,
            "message": str
        }
    """
    service = get_authenticated_service()
    if not service:
        return {"success": False, "message": "未授权，请先连接 Google Drive"}

    if not os.path.exists(file_path):
        return {"success": False, "message": f"文件不存在: {file_path}"}

    try:
        # 文件元数据
        file_metadata = {"name": file_name or os.path.basename(file_path)}
        if folder_id:
            file_metadata["parents"] = [folder_id]

        # 上传文件
        media = MediaFileUpload(file_path, resumable=True)
        file = (
            service.files()
            .create(body=file_metadata, media_body=media, fields="id, webViewLink")
            .execute()
        )

        return {
            "success": True,
            "file_id": file.get("id"),
            "web_link": file.get("webViewLink", ""),
            "message": f"上传成功: {file_metadata['name']}",
        }
    except Exception as e:
        return {"success": False, "message": f"上传失败: {str(e)}"}


def disconnect() -> dict:
    """
    断开 Google Drive 连接（删除本地 Token）。

    Returns:
        dict: {"success": bool, "message": str}
    """
    try:
        if os.path.exists(TOKEN_FILE):
            os.remove(TOKEN_FILE)
        return {"success": True, "message": "已断开连接"}
    except Exception as e:
        return {"success": False, "message": str(e)}
