import asyncio
import json
import os
import queue
import re
import time
from multiprocessing import Process, Queue
from threading import Lock
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException

from book_organizer import (
    _cleanup_suggestions,
    _find_heuristic_matches,
    extract_core_content,
    extract_metadata,
    find_similar_files,
    get_ai_analysis,
    get_enhanced_mode_analysis,
    get_unified_analysis,
    identify_book_metadata,
)
from book_organizer.ai_engines import (
    get_batch_enhance_analysis,
    get_batch_organize_analysis,
)
from book_organizer.ai_engines.dispatcher import format_ai_error
from book_organizer.config import get_content_search_config, load_ai_config, load_config
from book_organizer.database import get_db, get_toc_db
from book_organizer.file_ops import get_target_categories, resolve_file_path
from book_organizer.gemini_client import create_gemini_model
from book_organizer.library_path_repair import path_is_inside

# Logger
from book_organizer.logger import logger
from book_organizer.metadata_sync import ensure_extracted_toc_in_db
from book_organizer.summary_utils import (
    choose_enhanced_summary,
    extract_embedded_enhanced_summary,
    should_sync_embedded_summary,
)
from book_organizer.toc_extractor import (
    ai_extract_toc_from_content,
    ai_organize_toc,
    extract_content_pages,
    extract_toc,
    format_toc_text,
    sanitize_toc_result,
)

from . import internal_error, log_internal_error
from .models import (
    AIExtractTOCRequest,
    AnalyzeRequest,
    BatchEnhanceSingleRequest,
    BatchOrganizeSingleRequest,
    EnhancedSummaryRequest,
    ExtractTOCRequest,
    IdentifyMetadataRequest,
)

router = APIRouter()

# Globals for analysis process
current_analysis_process = None
current_analysis_queue = None
_analysis_lock = Lock()


def _cleanup_analysis_resources(process=None, result_queue=None) -> None:
    """Stop and release one analysis worker without touching a newer request."""
    global current_analysis_process, current_analysis_queue

    process = process or current_analysis_process
    result_queue = result_queue or current_analysis_queue
    if process:
        process.join(timeout=1)
        if process.is_alive():
            process.terminate()
            process.join(timeout=1)
        if process.is_alive():
            process.kill()
            process.join(timeout=1)
    if result_queue:
        try:
            result_queue.close()
            result_queue.join_thread()
        except (OSError, ValueError):
            pass
    with _analysis_lock:
        if current_analysis_process is process:
            current_analysis_process = None
        if current_analysis_queue is result_queue:
            current_analysis_queue = None


def shutdown_analysis() -> None:
    _cleanup_analysis_resources()


def _toc_needs_ai_cleanup(raw_result: Dict[str, Any]) -> bool:
    """Return True when a built-in TOC is absent or too weak to use directly."""
    if not raw_result.get("success"):
        return True

    toc_items = raw_result.get("toc") or []
    titles = []
    for item in toc_items:
        title = re.sub(r"\s+", " ", str(item.get("title", ""))).strip()
        if title:
            titles.append(title)

    unique_titles = list(dict.fromkeys(titles))
    if len(unique_titles) < 4:
        return True

    front_matter_pattern = re.compile(
        r"^(版权|版權|目录|目錄|contents|封面|扉页|扉頁|推荐序|推薦序|序|序言|"
        r"前言|引言|导言|導言|致谢|致謝|附录|附錄|参考文献|參考文獻|索引)$",
        re.I,
    )
    chapter_pattern = re.compile(
        r"(第[一二三四五六七八九十百千万零〇两\d]+[章节篇部卷]|"
        r"\b(chapter|part|section)\s+\d+|\d+[\.\、]\s*\S)",
        re.I,
    )
    body_like_count = sum(
        1
        for title in unique_titles
        if chapter_pattern.search(title) or not front_matter_pattern.match(title)
    )

    if len(unique_titles) < 6 and body_like_count < 3:
        return True
    if len(unique_titles) < 12 and body_like_count / max(len(unique_titles), 1) < 0.35:
        return True

    return False


@router.post("/api/identify_metadata")
def identify_metadata_endpoint(request: IdentifyMetadataRequest) -> Dict[str, Any]:
    try:
        config = load_config()
        result = identify_book_metadata(
            request.engine,
            config,
            request.filename,
            request.enable_search,
            request.user_metadata,
        )

        if "error" in result:
            # Check for file not found error specifically
            if "文件不存在" in str(result["error"]):
                raise HTTPException(status_code=404, detail="文件不存在")
            raise HTTPException(
                status_code=500, detail=format_ai_error(result["error"])
            )

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise internal_error("identify metadata", e, format_ai_error(e))


def _run_analysis_in_process(
    result_queue,
    file_path,
    request_filename,
    request_engine,
    request_enable_search,
    request_metadata_identified,
    request_user_metadata,
    target_dir,
    config,
):
    """在子进程中运行分析"""
    try:
        categories = get_target_categories(target_dir)

        # 1. 提取内部元数据
        internal_metadata = extract_metadata(file_path)

        ai_analysis_failed = False
        ai_failure_reason = ""
        ai_result = {}
        # 初始元数据：用户提供的优先，其次是文件内置的
        final_metadata = request_user_metadata or internal_metadata

        # 决定是否使用 AI
        use_ai = request_engine != "offline"

        if use_ai:
            try:
                # 如果尚未确认元数据且未提供完整的用户元数据，尝试 AI 识别
                if not request_metadata_identified:
                    print("  ✨ Triggering explicit metadata identification")

                    id_result = identify_book_metadata(
                        request_engine,
                        config,
                        request_filename,
                        request_enable_search,
                        request_user_metadata,
                    )

                    if "error" in id_result:
                        # 记录错误但不完全中断，尝试继续后续步骤（可能导致分类不准）
                        print("  ⚠️ Metadata identification failed")
                        # 保持使用 fallback metadata
                    else:
                        print("  ✅ Metadata identified successfully")
                        final_metadata = id_result

                # 准备上下文信息
                filename_info_str = f"""
文件名: {request_filename}
识别的元数据 (已完善):
- 书名: {final_metadata.get("title", "未知")}
- 作者: {final_metadata.get("author", "未知")}
- 出版社: {final_metadata.get("publisher", "未知")}
"""
                print("  ✨ Using categorization analysis")
                ai_result = get_ai_analysis(
                    request_engine,
                    config,
                    filename_info_str,
                    categories,
                    request_enable_search,
                    metadata=final_metadata,
                )

                if "error" in ai_result:
                    raise Exception(ai_result["error"])

                ai_result["metadata"] = final_metadata

            except Exception as e:
                print(f"  ❌ AI analysis failed ({type(e).__name__})")
                ai_analysis_failed = True
                ai_failure_reason = format_ai_error(e)
                use_ai = False  # 降级到离线逻辑

        # 离线逻辑 / 兜底逻辑
        if not use_ai:
            print("  🛠️ Using offline/fallback logic")
            # 尝试从数据库恢复已有的增强简介 (防止覆盖)
            existing_summary = ""
            try:
                # 在子进程中需要独立连接数据库
                from book_organizer.database import get_db

                db = get_db()
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT summary_json FROM enhanced_summaries WHERE filename = ? OR file_path LIKE ? ORDER BY updated_at DESC LIMIT 1",
                        (request_filename, f"%{request_filename}"),
                    )
                    row = cursor.fetchone()
                    if row and row[0]:
                        data = json.loads(row[0])
                        existing_summary = data.get("summary", "")
            except Exception as e:
                logger.warning(
                    "Failed to recover existing summary (%s)", type(e).__name__
                )

            # 优先使用数据库中的增强简介，其次是元数据中的描述
            summary_to_use = (
                existing_summary
                if existing_summary
                else final_metadata.get("description", "")
            )

            ai_result = {
                "summary": summary_to_use,
                "category": "",  # 将由 heuristic 填补
                "tags": final_metadata.get("tags", []),
                "metadata": final_metadata,
                "suggestions": [],  # 将由 heuristic 填补
            }
            if ai_analysis_failed:
                ai_result["warning"] = (
                    f"AI 分析失败 ({ai_failure_reason})，已自动显示本地结果"
                )

        # Heuristics & Cleanup (Common for both AI and Offline)

        # 准备用于启发式匹配的文件名信息，如果有元数据则优先使用书名作者
        filename_info_for_heuristic = request_filename
        if final_metadata and final_metadata.get("title"):
            filename_info_for_heuristic = (
                f"{final_metadata.get('title')} {final_metadata.get('author', '')}"
            )

        # 始终运行启发式匹配，作为兜底或增强
        heuristic_matches = _find_heuristic_matches(
            filename_info_for_heuristic, categories
        )

        # [ENHANCEMENT] Find directory of similar files for suggestion
        # 如果找到了相似文件，直接推荐该文件所在的目录
        try:
            # 注意：find_similar_files(target_dir, query) 返回 [{"path": "...", "filename": "..."}]
            # 剥离扩展名以进行更精准的相似度匹配
            search_query = os.path.splitext(os.path.basename(request_filename))[0]
            similar_files = find_similar_files(config["target_dir"], search_query)

            for item in similar_files:
                rel_path = item.get("path")
                if rel_path:
                    rel_dir = os.path.dirname(rel_path)
                    # 如果有子目录且不重复，加入建议
                    if rel_dir and rel_dir != "." and rel_dir not in heuristic_matches:
                        print(
                            f"  💡 Found similar book directory suggestion: {rel_dir}"
                        )
                        heuristic_matches.append(rel_dir)

        except Exception as sim_e:
            print(
                f"  ⚠️ Failed to find similar suggestions ({type(sim_e).__name__})"
            )

        raw_suggestions = ai_result.get("suggestions", [])
        validated_ai_suggestions = [s for s in raw_suggestions if s in categories]

        # 合并建议：AI 建议 + 启发式建议 (去重)
        final_suggestions = _cleanup_suggestions(
            heuristic_matches + validated_ai_suggestions
        )

        result_queue.put(
            {
                "metadata": ai_result.get("metadata", final_metadata),
                "summary": ai_result.get("summary", ""),
                "suggestions": final_suggestions,
                "warning": ai_result.get("warning"),  # 传递前端显示的警告
            }
        )
    except Exception as e:
        log_internal_error("book analysis worker", e)
        result_queue.put({"error": format_ai_error(e)})


@router.post("/api/analyze/cancel")
async def cancel_analysis() -> Dict[str, str]:
    with _analysis_lock:
        process = current_analysis_process
        result_queue = current_analysis_queue
    if process and process.is_alive():
        print("[Server] Terminating analysis process...")
        _cleanup_analysis_resources(process, result_queue)
        return {"status": "cancelled", "message": "Analysis process terminated"}

    return {"status": "no_process", "message": "No analysis in progress"}


@router.post("/api/analyze")
async def analyze_book(request: AnalyzeRequest) -> Dict[str, Any]:
    global current_analysis_process, current_analysis_queue

    if current_analysis_process and current_analysis_process.is_alive():
        logger.info("[Server] Terminating previous analysis process...")
        _cleanup_analysis_resources(current_analysis_process, current_analysis_queue)

    config = load_config()
    source_dir = config.get("source_dir")
    target_dir = config.get("target_dir")

    if not source_dir:
        raise HTTPException(status_code=400, detail="Source directory not configured")

    file_path = resolve_file_path(request.filename, config)
    if not file_path:
        raise HTTPException(status_code=404, detail="File not found")

    result_queue = Queue()
    process = Process(
        target=_run_analysis_in_process,
        args=(
            result_queue,
            file_path,
            request.filename,
            request.engine,
            request.enable_search,
            request.metadata_identified,
            request.user_metadata,
            target_dir,
            config,
        ),
    )
    with _analysis_lock:
        current_analysis_queue = result_queue
        current_analysis_process = process
    process.start()

    def wait_for_result():
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            try:
                return result_queue.get(timeout=0.25)
            except (queue.Empty, OSError, ValueError):
                if not process.is_alive():
                    return {"error": "Analysis cancelled"}
        return {"error": "Analysis timeout"}

    try:
        result = await asyncio.to_thread(wait_for_result)
    finally:
        _cleanup_analysis_resources(process, result_queue)

    if "error" in result:
        error = str(result["error"])
        if error == "Analysis cancelled":
            raise HTTPException(status_code=409, detail="分析已取消")
        if error == "Analysis timeout":
            raise HTTPException(status_code=504, detail="分析超时，请稍后重试")
        raise HTTPException(status_code=500, detail=format_ai_error(error))

    return result


def _get_existing_summary(filename: str) -> Optional[str]:
    try:
        config = load_config()
        db = get_db()
        file_path = resolve_file_path(filename, config)
        summary_data = db.get_summary(file_path or filename)
        db_summary = (summary_data or {}).get("summary", "")

        embedded_summary = ""
        metadata = {}
        if file_path and os.path.exists(file_path):
            try:
                metadata = extract_metadata(file_path) or {}
                embedded_summary = extract_embedded_enhanced_summary(metadata)
            except Exception as e:
                logger.warning(
                    "Error reading embedded summary (%s)", type(e).__name__
                )

        if (
            file_path
            and embedded_summary
            and should_sync_embedded_summary(db_summary, embedded_summary)
        ):
            summary_metadata = dict(metadata)
            summary_metadata.pop("description", None)
            db.save_summary(
                file_path,
                {
                    "metadata": summary_metadata,
                    "summary": embedded_summary,
                    "category": "Library",
                },
            )

        return choose_enhanced_summary(
            db_summary,
            embedded_summary,
            config.get("beta_features", {}).get("data_priority", "database"),
        )
    except Exception as e:
        logger.warning("Error fetching existing summary (%s)", type(e).__name__)
    return None


@router.post("/api/enhanced_summary")
def generate_enhanced_summary_endpoint(request: EnhancedSummaryRequest):
    try:
        if request.engine == "offline":
            existing_summary = _get_existing_summary(request.filename)
            return {
                "summary": existing_summary or "",
                "title": "",
                "author": "",
                "category": "",
                "warning": "离线模式无法生成增强简介"
                + (" (已显示现有简介)" if existing_summary else ""),
            }
        config = load_config()
        file_path = resolve_file_path(request.filename, config)

        if not file_path:
            raise HTTPException(status_code=404, detail="文件不存在")

        metadata = extract_metadata(file_path)

        ctrl_config = get_content_search_config()
        content_max_chars = int(ctrl_config.get("standard_mode_chars", 2000))
        content = extract_core_content(file_path, max_chars=content_max_chars + 1000)

        result = get_enhanced_mode_analysis(
            request.engine,
            config,
            request.filename,
            content,
            metadata,
        )

        if "error" in result:
            raise RuntimeError(str(result["error"]))

        return result

    except Exception as e:
        existing_summary = _get_existing_summary(request.filename)
        log_internal_error("generate enhanced summary", e)

        return {
            "summary": existing_summary or "",
            "title": "",
            "author": "",
            "category": "",
            "warning": f"{format_ai_error(e)} "
            + ("已保留原有数据" if existing_summary else "无法生成"),
        }


@router.post("/api/batch_enhance_single")
def batch_enhance_single_endpoint(request: BatchEnhanceSingleRequest):
    try:
        config = load_config()
        file_path = resolve_file_path(request.filename, config)
        if not file_path:
            raise HTTPException(
                status_code=404, detail=f"文件不存在: {request.filename}"
            )

        internal_metadata = extract_metadata(file_path)
        file_content = ""
        if request.engine != "offline":
            ctrl_config = get_content_search_config()
            content_max_chars = int(ctrl_config.get("standard_mode_chars", 2000))
            file_content = extract_core_content(
                file_path, max_chars=content_max_chars + 1000
            )

        result = get_batch_enhance_analysis(
            request.engine, config, request.filename, file_content, internal_metadata
        )

        if "error" in result:
            raise HTTPException(
                status_code=500, detail=format_ai_error(result["error"])
            )

        has_toc = False
        toc_entry_count = 0
        try:
            toc_result = ensure_extracted_toc_in_db(file_path)
            if toc_result.get("entry_count", 0) > 0:
                has_toc = True
                toc_entry_count = toc_result.get("entry_count", 0)
                print(f"  📚 已提取并保存目录 ({toc_entry_count} 条)")
        except Exception as e:
            logger.warning("目录提取失败 (%s)", type(e).__name__)

        result["has_toc"] = has_toc
        result["toc_entry_count"] = toc_entry_count

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise internal_error("batch enhance book", e, format_ai_error(e))


@router.post("/api/batch_organize_single")
def batch_organize_single_endpoint(request: BatchOrganizeSingleRequest):
    try:
        config = load_config()
        source_dir = config.get("source_dir")
        target_dir = config.get("target_dir")

        if not source_dir:
            raise HTTPException(status_code=400, detail="源目录未配置")

        file_path = resolve_file_path(request.filename, config)
        if not file_path:
            raise HTTPException(
                status_code=404, detail=f"文件不存在: {request.filename}"
            )
        if not path_is_inside(file_path, source_dir):
            raise HTTPException(status_code=403, detail="文件不在入库源目录内")

        categories = get_target_categories(target_dir) if target_dir else []

        ctrl_config = get_content_search_config()
        file_content = ""
        if request.engine != "offline":
            if request.enable_online_search:
                content_max_chars = int(ctrl_config.get("search_mode_chars", 800))
            else:
                content_max_chars = int(ctrl_config.get("standard_mode_chars", 2000))
            file_content = extract_core_content(
                file_path, max_chars=content_max_chars + 1000
            )

        internal_metadata = extract_metadata(file_path)

        result = get_batch_organize_analysis(
            request.engine,
            config,
            request.filename,
            file_content,
            internal_metadata,
            categories,
            request.enable_enhanced_summary,
            request.enable_online_search,
        )

        if "error" in result:
            raise HTTPException(
                status_code=500, detail=format_ai_error(result["error"])
            )

        has_toc = False
        toc_entry_count = 0
        try:
            toc_result = ensure_extracted_toc_in_db(file_path)
            if toc_result.get("entry_count", 0) > 0:
                has_toc = True
                toc_entry_count = toc_result.get("entry_count", 0)
        except Exception as e:
            print(f"  ⚠️ 目录提取检查失败 ({type(e).__name__})")

        result["has_toc"] = has_toc
        result["toc_entry_count"] = toc_entry_count

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise internal_error("batch organize book", e, format_ai_error(e))


@router.post("/api/toc/extract")
def extract_toc_endpoint(request: ExtractTOCRequest) -> Dict[str, Any]:
    try:
        config = load_config()
        file_path = resolve_file_path(request.filename, config)

        if not file_path:
            raise HTTPException(status_code=404, detail="File not found")

        result = extract_toc(file_path, max_pages=request.max_pages)
        if result["success"]:
            # Save to DB
            toc_db = get_toc_db()
            toc_db.save_toc(file_path, result)

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise internal_error("extract table of contents", e, "目录提取失败")


@router.post("/api/toc/ai_extract")
def ai_extract_toc_endpoint(request: AIExtractTOCRequest) -> Dict[str, Any]:
    try:
        config = load_config()
        ai_config_data = load_ai_config()
        toc_rules = ai_config_data.get("toc_rules", {})

        organize_existing = toc_rules.get("organize_existing", {})
        extract_from_content = toc_rules.get("extract_from_content", {})

        from urllib.parse import unquote

        decoded_filename = unquote(request.filename).strip()
        file_path = resolve_file_path(decoded_filename, config)

        if not file_path:
            raise HTTPException(
                status_code=404, detail=f"文件不存在: {decoded_filename}"
            )

        def ai_call(prompt: str) -> str:
            try:
                engine_config = config.get(request.engine, {})
                if request.engine == "offline":
                    return ""
                if request.engine == "gemini":
                    model = create_gemini_model(
                        engine_config.get("api_key", ""),
                        engine_config.get("model_name", "gemini-2.5-flash"),
                    )
                    if model is None:
                        return ""
                    return model.generate_content(prompt).text.strip()
                elif request.engine == "deepseek":
                    from openai import OpenAI

                    client = OpenAI(
                        api_key=engine_config.get("api_key", ""),
                        base_url="https://api.deepseek.com/v1",
                    )
                    return (
                        client.chat.completions.create(
                            model=engine_config.get("model_name", "deepseek-chat"),
                            messages=[{"role": "user", "content": prompt}],
                        )
                        .choices[0]
                        .message.content.strip()
                    )
                elif request.engine == "ollama":
                    import ollama

                    client = ollama.Client(
                        host=engine_config.get("url", "http://localhost:11434")
                    )
                    return client.chat(
                        model=engine_config.get("model_name", "llama3"),
                        messages=[{"role": "user", "content": prompt}],
                    )["message"]["content"].strip()
                return ""
            except Exception as e:
                print(f"AI call failed ({type(e).__name__})")
                return ""

        raw_result = extract_toc(file_path)
        raw_has_toc = raw_result.get("success") and raw_result.get("toc")

        if raw_has_toc and not _toc_needs_ai_cleanup(raw_result):
            toc_db = get_toc_db()
            toc_db.save_toc(file_path, raw_result)
            return {
                "success": True,
                "method": raw_result.get("method", "raw"),
                "toc": raw_result.get("toc", []),
                "toc_text": format_toc_text(raw_result.get("toc", [])),
                "entry_count": raw_result.get("entry_count", 0),
                "ai_processed": False,
                "ai_skipped": True,
                "reason": "built-in TOC is usable",
            }

        results = []
        if organize_existing.get("enabled"):
            if raw_has_toc:
                prompt_template = organize_existing.get("prompt", "")
                if prompt_template:
                    organized = ai_organize_toc(
                        raw_result["toc"], prompt_template, ai_call
                    )
                    if organized:
                        results.append(("organized", organized))

        if extract_from_content.get("enabled"):
            pages = extract_from_content.get("pages", 10)
            content = extract_content_pages(file_path, pages)
            if content:
                prompt_template = extract_from_content.get("prompt", "")
                if prompt_template:
                    extracted = ai_extract_toc_from_content(
                        content, prompt_template, ai_call
                    )
                    if extracted:
                        results.append(("extracted", extracted))

        if len(results) == 0:
            if raw_result.get("success"):
                toc_db = get_toc_db()
                toc_db.save_toc(file_path, raw_result)
            return sanitize_toc_result(
                {
                    "success": raw_result.get("success", False),
                    "method": "raw",
                    "toc": raw_result.get("toc", []),
                    "toc_text": format_toc_text(raw_result.get("toc", [])),
                    "entry_count": raw_result.get("entry_count", 0),
                }
            )

        final_toc = "\n\n".join([r[1] for r in results])
        entry_count = len([line for line in final_toc.splitlines() if line.strip()])
        toc_db = get_toc_db()
        toc_data = {
            "success": True,
            "method": "ai",
            "toc": [],
            "toc_text": final_toc,
            "ai_processed": True,
            "modes_used": [r[0] for r in results],
            "entry_count": entry_count,
        }
        toc_data = sanitize_toc_result(toc_data)
        toc_db.save_toc(file_path, toc_data)

        return sanitize_toc_result(
            {
                "success": True,
                "method": "ai",
                "toc_text": final_toc,
                "modes_used": [r[0] for r in results],
                "entry_count": entry_count,
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise internal_error("AI table of contents analysis", e, format_ai_error(e))


@router.post("/api/analyze_full")
def analyze_full(request: AnalyzeRequest):
    config = load_config()
    file_path = resolve_file_path(request.filename, config)
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    internal_metadata = extract_metadata(file_path)
    ctrl_config = get_content_search_config()
    max_chars = int(ctrl_config.get("standard_mode_chars", 1500))
    content_sample = extract_core_content(file_path, max_chars=max_chars)

    target_dir = config.get("target_dir", "")
    categories = get_target_categories(target_dir)

    if not request.metadata_identified:
        print("  ✨ Using unified analysis (metadata + category)")
        ai_result = get_unified_analysis(
            request.engine,
            config,
            request.filename,
            content_sample,
            internal_metadata,
            request.user_metadata,
            categories,
            request.enable_search,
            metadata_identified=False,
        )
    else:
        print("  ✨ Using categorization analysis (metadata confirmed)")
        enhanced_filename_info = f"""
文件名: {request.filename}
识别的元数据 (已确认):
- 书名: {request.user_metadata.get("title") if request.user_metadata else internal_metadata.get("title", "未知")}
- 作者: {request.user_metadata.get("author") if request.user_metadata else internal_metadata.get("author", "未知")}
"""
        ai_result = get_ai_analysis(
            request.engine,
            config,
            enhanced_filename_info,
            categories,
            request.enable_search,
            metadata=request.user_metadata or internal_metadata,
        )

    if "error" in ai_result:
        raise HTTPException(
            status_code=500, detail=format_ai_error(ai_result["error"])
        )

    raw_suggestions = ai_result.get("suggestions", [])
    validated_ai_suggestions = [s for s in raw_suggestions if s in categories]
    heuristic_matches = _find_heuristic_matches(request.filename, categories)
    final_suggestions = _cleanup_suggestions(
        heuristic_matches + validated_ai_suggestions
    )

    return {
        "metadata": ai_result.get("metadata", internal_metadata),
        "summary": ai_result.get("summary", ""),
        "suggestions": final_suggestions,
    }
