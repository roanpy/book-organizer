# -*- coding: utf-8 -*-
"""
转移模块 - 处理图书重命名、移动和转移记录

包含：
- 图书重命名和移动
- 启发式路径匹配
- 转移记录日志
"""

import os
import re
import shutil
from pathlib import Path

from .library_path_repair import path_is_in_book_roots, path_is_inside


def _get_deps():
    """延迟导入依赖"""
    from .config import load_config, save_history_item
    from .database import get_db, get_toc_db
    from .file_ops import truncate_filename_smart
    from .metadata import write_epub_metadata, write_pdf_metadata

    return (
        load_config,
        save_history_item,
        truncate_filename_smart,
        write_epub_metadata,
        write_pdf_metadata,
        get_db,
        get_toc_db,
    )


def _find_heuristic_matches(filename_info, categories):
    """基于启发式规则寻找匹配的目录。

    Args:
        filename_info: 文件名信息字符串
        categories: 可用分类列表

    Returns:
        匹配的目录列表
    """
    from .local_utils import auto_categorize

    matches = []

    # 1. 精准实体匹配 (作者/系列)
    author_marker = "作者: '"
    author_start = filename_info.find(author_marker)
    author_end = filename_info.find("'", author_start + len(author_marker))
    author = (
        filename_info[author_start + len(author_marker) : author_end].strip()
        if author_start >= 0 and author_end > author_start + len(author_marker)
        else ""
    )

    series_text = Path(filename_info).stem if "/" not in filename_info else filename_info
    series = ""
    for opening, closing in (("(", ")"), ("（", "）")):
        start = series_text.find(opening)
        end = series_text.find(closing, start + 1) if start >= 0 else -1
        if start >= 0 and end > start + 1:
            series = series_text[start + 1 : end].strip()
            break

    entities_to_check = []
    if author:
        entities_to_check.append(author)
    if series:
        entities_to_check.append(series)

    for entity in entities_to_check:
        if len(entity) > 1:
            for category in categories:
                if entity.lower() in os.path.basename(category).lower():
                    matches.append(category)

    # 2. 规则驱动匹配 (包含内置规则和从历史记录中学习到的规则)
    # auto_categorize 会自动使用 get_dynamic_rules()
    suggested_cat = auto_categorize(filename_info)
    if suggested_cat:
        for category in categories:
            # 检查分类名是否在路径中匹配
            if suggested_cat.lower() in category.lower() or category.lower().endswith(
                suggested_cat.lower()
            ):
                if category not in matches:
                    matches.append(category)

    return matches


def _cleanup_suggestions(suggestions):
    """清理建议列表，去重并移除父目录。

    ✅ 稳定方法：自 v0.3.23 创建以来未经修改，简洁的去重逻辑。

    Args:
        suggestions: 原始建议列表

    Returns:
        清理后的建议列表
    """
    if not suggestions:
        return []

    unique_suggestions = list(dict.fromkeys(suggestions))
    parents_to_remove = set()

    for s1 in unique_suggestions:
        for s2 in unique_suggestions:
            if s1 != s2 and s2.startswith(s1 + os.path.sep):
                parents_to_remove.add(s1)

    final_suggestions = [s for s in unique_suggestions if s not in parents_to_remove]
    return final_suggestions


def write_transfer_log(
    original_filename: str,
    new_filename: str,
    destination_category: str,
    metadata: dict,
    summary: str = "",
) -> None:
    """将图书转移信息写入数据库。

    Args:
        original_filename: 原始文件名
        new_filename: 新文件名
        destination_category: 目标分类目录
        metadata: 元数据字典 (title, author, publisher, series, tags)
        summary: 图书简介
    """
    _, _, _, _, _, get_db_func, _ = _get_deps()

    try:
        db = get_db_func()
        # 使用 KnowledgeCoreDB 的 save_transfer_log 方法
        db._db.save_transfer_log(
            original_filename, new_filename, destination_category, metadata, summary
        )
    except Exception as e:
        print(f"  ⚠️ 写入转移记录失败: {e}")


def rename_and_move_book(
    original_filename, new_metadata, destination_category, summary=""
):
    """重命名并移动图书。

    Args:
        original_filename: 原始文件名
        new_metadata: 包含 title, author 等的新元数据字典
        destination_category: 目标分类目录 (相对路径)
        summary: 图书简介

    Returns:
        dict: {"success": bool, "message": str}
    """
    (
        load_config,
        save_history_item,
        truncate_filename_smart,
        write_epub_metadata_func,
        write_pdf_metadata_func,
        get_db_func,
        get_toc_db_func,
    ) = _get_deps()

    config = load_config()
    target_dir = config.get("target_dir")
    source_dir = config.get("source_dir")
    if not target_dir:
        return {"success": False, "message": "目标目录未配置"}

    # 路径解析增强：支持从 Target 目 (Library) 移动
    source_path = os.path.join(source_dir, original_filename) if source_dir else None

    if not source_path or not os.path.exists(source_path):
        if target_dir:
            # 尝试在 target_dir 查找 (Library Mode)
            target_source_path = os.path.join(target_dir, original_filename)
            if os.path.exists(target_source_path):
                source_path = target_source_path

    if not source_path or not os.path.exists(source_path):
        # 尝试绝对路径
        if os.path.exists(original_filename):
            source_path = original_filename

    if not source_path or not os.path.exists(source_path):
        return {"success": False, "message": "源文件不存在"}
    if not path_is_in_book_roots(source_path, config):
        return {"success": False, "message": "源文件不在已配置的图书目录内"}

    ext = os.path.splitext(original_filename)[1]

    new_name_stem = new_metadata.get("new_filename")
    if not new_name_stem:
        author = new_metadata.get("author", "").strip()
        title = new_metadata.get("title", "").strip()
        if author and title:
            new_name_stem = f"[{author}] {title}"
        else:
            new_name_stem = os.path.splitext(original_filename)[0]

    new_name_stem = re.sub(r'[\\/*?:"<>|]', "", new_name_stem)
    new_name_stem = truncate_filename_smart(new_name_stem, ext)

    new_filename = new_name_stem + ext

    dest_dir_path = os.path.join(target_dir, destination_category)
    dest_path = os.path.join(dest_dir_path, new_filename)
    if not path_is_inside(dest_path, target_dir):
        return {"success": False, "message": "目标分类路径无效"}
    if os.path.exists(dest_path) and os.path.realpath(source_path) != os.path.realpath(
        dest_path
    ):
        return {"success": False, "message": "目标位置已存在同名文件"}

    try:
        os.makedirs(dest_dir_path, exist_ok=True)

        beta_features = config.get("beta_features", {})

        # Inject enhanced summary into metadata description ONLY if enabled for that format
        if summary:
            allow_write_summary_epub = beta_features.get(
                "enable_summary_write_epub", False
            )
            allow_write_summary_pdf = beta_features.get(
                "enable_summary_write_pdf", False
            )

            if ext.lower() == ".epub" and allow_write_summary_epub:
                new_metadata["description"] = summary
            elif ext.lower() == ".pdf" and allow_write_summary_pdf:
                new_metadata["description"] = summary

        # 元数据写入（如果开启）- 失败则停止转移
        if ext.lower() == ".epub":
            if beta_features.get("enable_metadata_write_epub", False):
                if not write_epub_metadata_func(source_path, new_metadata):
                    return {
                        "success": False,
                        "message": "EPUB 元数据写入失败，已取消转移操作",
                    }
        elif ext.lower() == ".pdf":
            if beta_features.get("enable_metadata_write_pdf", False):
                if not write_pdf_metadata_func(source_path, new_metadata):
                    return {
                        "success": False,
                        "message": "PDF 元数据写入失败，已取消转移操作",
                    }

        # 使用中转文件名策略处理重命名（避免产生 _1 后缀）
        # 步骤：源文件 → 临时位置 → 删除同名旧文件 → 重命名为正式名
        import uuid

        temp_name = f".tmp_{uuid.uuid4().hex[:8]}{ext}"
        temp_path = os.path.join(dest_dir_path, temp_name)
        final_new_filename = new_filename

        try:
            # 步骤1：先移动到临时文件名
            shutil.move(source_path, temp_path)

            # 步骤2：重命名为正式文件名。目标冲突已在移动前拒绝。
            os.rename(temp_path, dest_path)

        except Exception as e:
            # 如果出错，尝试恢复
            if os.path.exists(temp_path):
                try:
                    # 尝试将临时文件移回源位置
                    shutil.move(temp_path, source_path)
                except Exception:
                    pass
            return {"success": False, "message": f"移动失败: {e}"}

        save_history_item(
            original_filename,
            "processed",
            {
                "destination": destination_category,
                "renamed_to": os.path.basename(dest_path),
                "metadata": new_metadata,
            },
        )

        write_transfer_log(
            original_filename,
            final_new_filename,
            destination_category,
            new_metadata,
            summary,
        )

        # [NEW] 转移成功后，立即触发规则学习刷新，让推荐越来越准
        try:
            from .local_utils import get_dynamic_rules

            get_dynamic_rules(force_refresh=True)
            print("  🧠 已根据最新转移记录更新本地分类规则")
        except Exception as e:
            print(f"  ⚠️ 更新本地规则失败: {e}")

        # 写入增强模式数据库
        try:
            db = get_db_func()

            # 更新文件名关联（如果文件名发生变化）
            old_filename = os.path.basename(source_path)
            new_filename_base = os.path.basename(dest_path)
            if old_filename != new_filename_base:
                db.update_filename(source_path, new_filename_base, dest_path)

                # 同步更新 AI 目录数据库
                try:
                    toc_db = get_toc_db_func()
                    toc_db.update_filename(source_path, new_filename_base, dest_path)
                except Exception as e:
                    print(f"  ⚠️ 更新 TOC 数据库文件名失败: {e}")

            # Preserve existing summary if not provided
            final_summary = summary
            if not final_summary:
                existing_record = db.get_summary(dest_path)
                if existing_record:
                    final_summary = existing_record.get("summary", "")

            db.save_summary(
                dest_path,
                {
                    "metadata": new_metadata,
                    "summary": final_summary,
                    "category": destination_category,
                },
            )
            print(f"  ✓ 已保存增强信息到数据库: {os.path.basename(dest_path)}")

            # 自动提取并保存文件内置目录（如果有）
            try:
                from .toc_extractor import extract_toc

                toc_db = get_toc_db_func()

                toc_result = extract_toc(dest_path)
                if toc_result.get("success") and toc_result.get("entry_count", 0) > 0:
                    toc_db.save_toc(dest_path, toc_result)
                    print(
                        f"  📚 已提取并保存目录 ({toc_result['entry_count']} 条): {os.path.basename(dest_path)}"
                    )
            except Exception as e:
                print(f"  ⚠️ 目录提取失败: {e}")

        except Exception as e:
            print(f"  ⚠️ 保存增强信息失败: {e}")

        return {
            "success": True,
            "message": f"已移动并重命名为: {os.path.basename(dest_path)}",
        }

    except Exception as e:
        return {"success": False, "message": f"移动失败: {e}"}
