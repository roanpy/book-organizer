from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ConfigUpdate(BaseModel):
    source_dir: Optional[str] = None
    target_dir: Optional[str] = None
    data_dir: Optional[str] = None
    book_extensions: Optional[List[str]] = None
    gemini: Optional[dict] = None
    deepseek: Optional[dict] = None
    ollama: Optional[dict] = None
    volcengine: Optional[dict] = None
    beta_features: Optional[dict] = None
    custom_providers: Optional[dict] = None


class AnalyzeRequest(BaseModel):
    filename: str
    engine: str
    enable_search: bool = False
    metadata_identified: bool = False
    user_metadata: Optional[dict] = None


class MoveRequest(BaseModel):
    filename: str
    destination: str


class BrowseRequest(BaseModel):
    path: Optional[str] = None


class ModelRequest(BaseModel):
    api_key: Optional[str] = None
    url: Optional[str] = None


class UpdateRatingRequest(BaseModel):
    filename: str
    rating: int  # 0-5
    file_path: Optional[str] = None


class TestConnectionRequest(BaseModel):
    provider: str
    api_key: Optional[str] = None
    url: Optional[str] = None


class TestCustomProviderRequest(BaseModel):
    provider: str
    model_name: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    supports_json_mode: Optional[bool] = True


class SyncConfigUpdate(BaseModel):
    enabled: bool
    path: str
    overwrite_cloud: bool = False
    use_cloud: Optional[bool] = (
        None  # None=auto, True=download cloud, False=upload local
    )
    sync_database: Optional[str] = "auto"
    sync_config: Optional[str] = "auto"
    auto_check: bool = True
    sync_sensitive_credentials: Optional[bool] = None


class SyncValidateRequest(BaseModel):
    path: str


class SkipRequest(BaseModel):
    filename: str


class UserPreferencesUpdate(BaseModel):
    enhancedModeEnabled: Optional[bool] = None
    selectedEngine: Optional[str] = None
    webSearchEnabled: Optional[bool] = None
    tocEnabled: Optional[bool] = None


class OptimizeRulesRequest(BaseModel):
    enabled: bool
    max_rules: int = 50
    auto_age_out: bool = True


class ExtractTOCRequest(BaseModel):
    filename: str
    max_pages: int = 20


class AIExtractTOCRequest(BaseModel):
    filename: str
    engine: str


class IdentifyMetadataRequest(BaseModel):
    filename: str
    engine: str
    enable_search: bool = False
    user_metadata: Optional[dict] = None


class RenameAndMoveRequest(BaseModel):
    original_filename: str
    metadata: dict
    destination: str
    summary: Optional[str] = ""


class RenameOnlyRequest(BaseModel):
    original_filename: str
    metadata: dict
    summary: Optional[str] = ""


class FindSimilarRequest(BaseModel):
    query: str
    current_path: Optional[str] = None
    exclude_paths: Optional[List[str]] = None


class WriteMetadataRequest(BaseModel):
    filename: str
    metadata: dict


class EnhancedSummaryRequest(BaseModel):
    filename: str
    engine: str


class BatchEnhanceSingleRequest(BaseModel):
    filename: str
    engine: str


class BatchOrganizeSingleRequest(BaseModel):
    filename: str
    engine: str
    enable_enhanced_summary: bool = True
    enable_online_search: bool = False


class ConvertToPdfRequest(BaseModel):
    filename: str
    output_dir: Optional[str] = None


class DriveUploadRequest(BaseModel):
    file_path: str
    folder_id: Optional[str] = None


class DirectUploadRequest(BaseModel):
    file_path: str


class ExecuteSyncRequest(BaseModel):
    operations: List[Dict[str, Any]]


class DeleteFileRequest(BaseModel):
    path: str


class IgnoreGroupRequest(BaseModel):
    paths: List[str]


class UnignoreGroupRequest(BaseModel):
    id: str


class ISBNLookupRequest(BaseModel):
    isbn: str = ""
    title: Optional[str] = None
    file_path: Optional[str] = None
    api: str = "openlibrary"


class LocalCategorizeRequest(BaseModel):
    title: str
    tags: List[str] = Field(default_factory=list)


class LocalDuplicateRequest(BaseModel):
    title: str
    threshold: float = 0.8


class LocalIdentifyRequest(BaseModel):
    file_path: Optional[str] = None
    filename: Optional[str] = None


class LocalSuggestDirsRequest(BaseModel):
    title: str
    author: Optional[str] = None
