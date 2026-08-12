import json
import logging
import os
import shutil
import sqlite3
import threading
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from .config import load_config
from .database import get_db
from .file_ops import get_configured_book_extensions

logger = logging.getLogger(__name__)


class DBSyncManager:
    def __init__(self):
        self.db = get_db()

    def _refresh_db_connection(self) -> None:
        """Reconnect before sync checks in case a cloud sync replaced the DB file."""
        self.db = get_db()
        core_db = getattr(self.db, "_db", None)
        if hasattr(core_db, "reset_connection"):
            core_db.reset_connection()

    @property
    def target_dir(self):
        config = load_config()
        # 修复：主库维护应基于 target_dir (Book Library)，而不是 source_dir (Downloads)
        return config.get("target_dir", "")

    def get_fuzzy_key(self, filename):
        """标准化文件名以便进行模糊匹配"""
        files_stem = Path(filename).stem
        split_chars = [":", "：", "(", "（", "-", "—"]
        min_idx = len(files_stem)
        found = False
        for char in split_chars:
            try:
                idx = files_stem.index(char)
                if idx < min_idx:
                    min_idx = idx
                    found = True
            except ValueError:
                pass
        key = files_stem[:min_idx] if found else files_stem
        return key.strip().lower()

    def backup_db(self):
        """数据库备份逻辑 (✅ 稳定方法)

        使用 SQLite Online Backup API 进行安全备份，支持 WAL 模式。
        自 v0.6.7 修复数据库损坏问题后逻辑保持稳定。
        """
        db_path = self.db.db_path
        if os.path.exists(db_path):
            # [Backup Fix] Use rolling backup (single file) to prevent disk usage bloat
            bak_path = db_path + ".backup"

            # Remove previous backup if exists to ensure clean state for SQLite API
            if os.path.exists(bak_path):
                try:
                    os.remove(bak_path)
                except OSError:
                    pass
            try:
                # 为了安全起见，在 WAL 模式下使用 SQLite 在线备份 API
                # EnhancedSummariesDB -> KnowledgeCoreDB -> _get_conn
                # 我们需要访问底层的核心 DB 实例
                core_db = self.db._db

                with core_db._get_conn() as source_conn:
                    dest_conn = sqlite3.connect(bak_path)
                    try:
                        source_conn.backup(dest_conn)
                    finally:
                        dest_conn.close()

                logger.info(f"Database backed up successfully to {bak_path}")
                return bak_path
            except Exception as e:
                logger.error(
                    f"Backup failed using sqlite3 API, falling back to shutil: {e}"
                )
                # 如果 API 失败（例如由于严格锁定），降级使用 copy
                # 虽然 copy 可能不那么安全，但作为最后手段
                # 如果备份失败，同步可能在没有备份的情况下继续？
                # 让我们尝试 shutil 作为最后的手段，但记录警告
                shutil.copy2(db_path, bak_path)
                return bak_path
        return None

    def analyze(self) -> Dict[str, Any]:
        """分析数据库和文件系统的差异 (✅ 稳定方法)

        1. 扫描文件系统 (Truth)
        2. 扫描数据库
        3. 自动匹配移动、更名和重复记录。

        ⚠️ 核心参考方法：同步逻辑极其复杂，涉及路径匹配权重，修改需谨慎。
        """
        """
        分析数据库和文件系统的差异。
        返回操作映射列表。
        """
        if not os.path.exists(self.target_dir):
            return {"error": "Target directory not found"}
        self._refresh_db_connection()

        # 1. 扫描文件系统
        fs_files_by_name = {}
        fs_files_by_stem = defaultdict(list)
        all_fs_paths = set()
        allowed_extensions = get_configured_book_extensions(load_config())

        for root, dirs, files in os.walk(self.target_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for f in files:
                if f.startswith(".") or not f.lower().endswith(allowed_extensions):
                    continue
                full_path = os.path.join(root, f)
                all_fs_paths.add(full_path)

                if f not in fs_files_by_name:
                    fs_files_by_name[f] = []
                fs_files_by_name[f].append(full_path)

                key = self.get_fuzzy_key(f)
                if len(key) >= 2:
                    fs_files_by_stem[key].append(full_path)

        # 2. 扫描数据库
        operations = []

        # 我们需要在分析过程中手动进行查重，以生成"删除重复"的操作
        with self.db._db._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, filename, file_path, category, updated_at FROM enhanced_summaries"
            )
            rows = [dict(row) for row in cursor.fetchall()]

            # 按文件名分组
            filename_groups = defaultdict(list)
            for r in rows:
                filename_groups[r["filename"]].append(r)

            # A. 处理重复项
            records_to_check = []

            for fname, group in filename_groups.items():
                if len(group) > 1:
                    # 倒序排列
                    group.sort(key=lambda x: str(x["updated_at"]), reverse=True)
                    keep = group[0]
                    remove = group[1:]

                    records_to_check.append(keep)

                    for rm in remove:
                        operations.append(
                            {
                                "type": "DELETE_DUPLICATE",
                                "record_id": rm["id"],
                                "filename": rm["filename"],
                                "description": f"删除重复旧记录 (Updated: {rm['updated_at']})",
                                "category": "duplicate",
                            }
                        )
                else:
                    records_to_check.append(group[0])

            # B. 检查同步状态
            db_active_paths = {}  # 用于检测冲突
            # 注意：在没有模拟的情况下，我们无法完全提前准确预测冲突布局，
            # 但我们可以进行逐条记录分析。

            for rec in records_to_check:
                rid = rec["id"]
                fname = rec["filename"]
                fpath = rec["file_path"]

                # 解析绝对路径
                abs_fpath = fpath
                if fpath and not os.path.isabs(fpath):
                    abs_fpath = os.path.join(self.target_dir, fpath)
                elif not fpath:
                    abs_fpath = os.path.join(
                        self.target_dir, rec["category"] or "", fname
                    )

                db_active_paths[abs_fpath] = rid

                # 1. 精确匹配
                if os.path.exists(abs_fpath) and os.path.basename(abs_fpath) == fname:
                    continue

                # 2. 修复尝试
                new_path = None
                new_name = None
                reason = ""
                category = ""

                # 2a. 路径不匹配 - 改进：优先匹配同一目录或相关路径
                if fname in fs_files_by_name:
                    candidates = fs_files_by_name[fname]
                    expected_dir = os.path.dirname(abs_fpath)

                    # 优先级 1: 精确目录匹配
                    best_candidate = None
                    for c in candidates:
                        if os.path.dirname(c) == expected_dir:
                            best_candidate = c
                            break

                    # 优先级 2: 父目录名称相同 (如 "01_思维")
                    if not best_candidate:
                        expected_parent_name = os.path.basename(expected_dir)
                        for c in candidates:
                            if (
                                os.path.basename(os.path.dirname(c))
                                == expected_parent_name
                            ):
                                best_candidate = c
                                break

                    # 兜底：使用第一个候选项 (如果模糊则警告)
                    if not best_candidate:
                        best_candidate = candidates[0]
                        if len(candidates) > 1:
                            logger.warning(
                                f"[Sync] Ambiguous filename '{fname}': {len(candidates)} matches, using first."
                            )

                    new_path = best_candidate
                    new_name = fname
                    reason = f"更新路径: {os.path.relpath(new_path, self.target_dir)}"
                    category = "path_fix"

                # 2b. 模糊匹配
                else:
                    key = self.get_fuzzy_key(fname)
                    matches = fs_files_by_stem.get(key, [])

                    match_found = None
                    if matches:
                        expected_dir = os.path.dirname(abs_fpath)
                        for m in matches:
                            if os.path.dirname(m) == expected_dir:
                                match_found = m
                                reason = f"文件名修正 (同目录): {os.path.basename(m)}"
                                category = "rename"
                                break

                        if not match_found and len(matches) == 1:
                            match_found = matches[0]
                            reason = (
                                f"模糊匹配 (唯一候选): {os.path.basename(match_found)}"
                            )
                            category = "rename"

                    if match_found:
                        new_path = match_found
                        new_name = os.path.basename(new_path)

                if new_path:
                    # 检查冲突 (幽灵检测)
                    # 如果 new_path 已经被活动集合中的"其他人"占用了怎么办？
                    # 因为我们是迭代处理，如果我们发现另一条记录指向这里...
                    # 如果不构建完整的图，很难精确映射。
                    # 但如果我们生成一个 UPDATE 操作，我们可以在运行时检查冲突。
                    # 或者对照 `db_active_paths` 检查。

                    # 逻辑：如果 `new_path` 匹配另一条记录 X 的 `abs_fpath`，且 X != rid。
                    # 等等：如果那条记录也在移动，`db_active_paths` 的键可能已经过时。
                    # 但通常，"幽灵"指向的是一条有效记录当前所在的位置。

                    operations.append(
                        {
                            "type": "UPDATE",
                            "record_id": rid,
                            "filename": fname,
                            "description": reason,
                            "data": {"new_filename": new_name, "new_path": new_path},
                            "category": category,
                        }
                    )

        return {
            "success": True,
            "operations": operations,
            "stats": {"total_records": len(rows), "proposed_ops": len(operations)},
        }

    def execute(self, selected_ops: List[Dict]) -> Dict[str, Any]:
        """执行同步操作 (✅ 稳定方法)

        根据 analyze 的结果执行数据库更新或删除。
        执行前会自动调用 backup_db 确保安全。
        """
        """
        执行选定的操作。
        selected_ops: analyze 返回的操作字典列表（或子集）
        """
        if not selected_ops:
            return {"success": True, "message": "No operations selected"}
        self._refresh_db_connection()

        bak_file = self.backup_db()
        updates = 0
        deletes = 0
        errors = 0

        with self.db._db._get_conn() as conn:
            cursor = conn.cursor()

            for op in selected_ops:
                rid = op["record_id"]
                otype = op["type"]

                try:
                    if otype == "DELETE_DUPLICATE":
                        cursor.execute(
                            "DELETE FROM enhanced_summaries WHERE id=?", (rid,)
                        )
                        deletes += 1

                    elif otype == "UPDATE":
                        data = op["data"]
                        new_name = data["new_filename"]
                        full_path = data["new_path"]

                        # 如果适用，转换为相对路径
                        save_path = full_path
                        if full_path.startswith(self.target_dir):
                            save_path = os.path.relpath(full_path, self.target_dir)

                        # 尝试更新
                        try:
                            cursor.execute(
                                """
                                UPDATE enhanced_summaries
                                SET filename=?, file_path=?, updated_at=CURRENT_TIMESTAMP
                                WHERE id=?
                            """,
                                (new_name, save_path, rid),
                            )

                            # Update books table casually
                            if new_name != op["filename"]:
                                cursor.execute(
                                    """
                                    UPDATE OR IGNORE books
                                    SET filename=?, file_path=?, updated_at=CURRENT_TIMESTAMP
                                    WHERE filename=?
                                """,
                                    (new_name, save_path, op["filename"]),
                                )

                            updates += 1

                        except sqlite3.IntegrityError:
                            # Collision! This record is trying to take a slot taken by another.
                            # Usually means this is a ghost that should be deleted.
                            logger.info(
                                f"[Sync] IntegrityError on Update id={rid}. Deleting as ghost."
                            )
                            cursor.execute(
                                "DELETE FROM enhanced_summaries WHERE id=?", (rid,)
                            )
                            deletes += 1

                except Exception as e:
                    logger.error(f"Error executing op {op}: {e}")
                    errors += 1

            conn.commit()

        return {
            "success": True,
            "message": f"Sync Completed. Updates: {updates}, Deletes: {deletes}, Errors: {errors}",
            "backup_path": bak_file,
        }

    def analyze_duplicates(self) -> Dict[str, Any]:
        """
        Find duplicate books in the library based on fuzzy name matching.
        """
        if not os.path.exists(self.target_dir):
            return {"error": "Target directory not found"}
        self._refresh_db_connection()

        # 1. Scan Filesystem deeply
        # We focus on filesystem truth, but enrich with DB data
        files_by_key = defaultdict(list)
        allowed_extensions = get_configured_book_extensions(load_config())

        for root, dirs, files in os.walk(self.target_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for f in files:
                if f.startswith(".") or not f.lower().endswith(allowed_extensions):
                    continue

                full_path = os.path.join(root, f)
                key = self.get_fuzzy_key(f)

                if len(key) < 2:  # Skip too short keys to avoid false positives
                    continue

                files_by_key[key].append(
                    {
                        "filename": f,
                        "path": full_path,
                        "rel_path": os.path.relpath(full_path, self.target_dir),
                        "ext": os.path.splitext(f)[1].lower(),
                        "size": os.path.getsize(full_path),
                    }
                )

        # 2. Filter groups > 1

        # Pre-fetch DB info for efficiency
        db_map = {}
        with self.db._db._get_conn() as conn:
            cursor = conn.cursor()

            # Fetch Summaries
            try:
                cursor.execute("SELECT file_path, summary_json FROM enhanced_summaries")
                for row in cursor.fetchall():
                    p = row[0]
                    if p:
                        if p and not os.path.isabs(p):
                            p = os.path.join(self.target_dir, p)
                        # Initialize
                        if p not in db_map:
                            db_map[p] = {}
                        # Check summary length (heuristic)
                        s_json = row[1]
                        has_summ = False
                        if s_json:
                            try:
                                has_summ = len(s_json) > 50  # Simple length check
                            except Exception:
                                pass
                        db_map[p]["has_summary"] = has_summ
                        db_map[p]["toc_count"] = 0  # Default
            except Exception as e:
                logger.error(f"Error fetching summaries: {e}")

            # Fetch TOCs
            try:
                cursor.execute("SELECT file_path, entry_count FROM book_tocs")
                for row in cursor.fetchall():
                    p = row[0]
                    if p:
                        if p and not os.path.isabs(p):
                            p = os.path.join(self.target_dir, p)
                        if p not in db_map:
                            db_map[p] = {"has_summary": False}
                        db_map[p]["toc_count"] = row[1] or 0
            except Exception as e:
                logger.error(f"Error fetching TOCs: {e}")

        # 3. Filter and Split based on Ignores
        active_groups = []
        ignored_groups = []

        ignore_rules = self._load_ignores()
        # Create a set of frozen sets for fast lookup of ignored combinations
        # We use sorted tuple of paths as the signature
        ignored_signatures = {}
        for rule in ignore_rules:
            sig = tuple(sorted(rule["paths"]))
            ignored_signatures[sig] = rule

        for key, items in files_by_key.items():
            if len(items) > 1:
                # Enrich items (same as before)
                for item in items:
                    info = db_map.get(item["path"])
                    if info:
                        item["has_summary"] = info.get("has_summary", False)
                        item["toc_count"] = info.get("toc_count", 0)
                    else:
                        item["has_summary"] = False
                        item["toc_count"] = 0

                # Check if ignored
                current_sig = tuple(
                    sorted([i["rel_path"] for i in items])
                )  # 使用相对路径，跨设备兼容

                group_data = {"key": key, "items": items, "signature": current_sig}

                if current_sig in ignored_signatures:
                    # Enrich with rule ID for unignoring
                    group_data["ignore_rule_id"] = ignored_signatures[current_sig]["id"]
                    ignored_groups.append(group_data)
                else:
                    active_groups.append(group_data)

        return {
            "success": True,
            "groups": active_groups,  # Backwards compat if needed, but we'll use active_groups
            "active_groups": active_groups,
            "ignored_groups": ignored_groups,
            "count": len(active_groups),
        }

    # --- Ignore Persistence ---

    # --- Ignore Persistence ---

    def _get_ignore_file(self):
        # 始终使用本地文件作为操作对象，确保单一数据源
        return os.path.join(os.path.dirname(self.db.db_path), "dedup_ignores.json")

    def _get_cloud_ignore_file(self):
        config = load_config()
        sync_config = config.get("sync", {})
        if sync_config.get("enabled") and sync_config.get("path"):
            sync_path = os.path.expanduser(sync_config["path"])  # 支持 ~ 路径
            return os.path.join(sync_path, "dedup_ignores.json")
        return None

    def _sync_ignores_from_cloud_if_newer(self, local_path, cloud_path):
        """如果云端文件更新，则拉取到本地"""
        if not cloud_path or not os.path.exists(cloud_path):
            return

        try:
            should_pull = False
            if not os.path.exists(local_path):
                should_pull = True
            else:
                local_mtime = os.path.getmtime(local_path)
                cloud_mtime = os.path.getmtime(cloud_path)
                # 简单的时间戳仲裁：云端更新则拉取
                if cloud_mtime > local_mtime:
                    should_pull = True

            if should_pull:
                shutil.copy2(cloud_path, local_path)
                logger.info(
                    f"Synced dedup_ignores from cloud: {cloud_path} -> {local_path}"
                )
        except Exception as e:
            logger.error(f"Error syncing ignores from cloud: {e}")

    def _load_ignores(self) -> List[Dict]:
        local_p = self._get_ignore_file()
        cloud_p = self._get_cloud_ignore_file()

        # 1. 尝试从云端同步最新版
        if cloud_p:
            self._sync_ignores_from_cloud_if_newer(local_p, cloud_p)

        # 2. 加载本地文件
        if not os.path.exists(local_p):
            return []
        try:
            with open(local_p, "r", encoding="utf-8") as f:
                rules = json.load(f)

            # 3. 迁移：将旧的绝对路径转换为相对路径
            migrated = False
            for rule in rules:
                new_paths = []
                for p in rule.get("paths", []):
                    if os.path.isabs(p) and p.startswith(self.target_dir):
                        # 转换为相对路径
                        new_paths.append(os.path.relpath(p, self.target_dir))
                        migrated = True
                    else:
                        new_paths.append(p)
                rule["paths"] = sorted(new_paths)

            # 如果有迁移，保存回文件
            if migrated:
                logger.info("Migrated dedup_ignores from absolute to relative paths")
                self._save_ignores(rules)

            return rules
        except Exception as e:
            logger.error(f"Failed to load ignores: {e}")
            return []

    def _save_ignores(self, rules: List[Dict]):
        local_p = self._get_ignore_file()
        try:
            # 1. 保存到本地
            with open(local_p, "w", encoding="utf-8") as f:
                json.dump(rules, f, ensure_ascii=False, indent=2)

            # 2. 如果已开启同步，立即推送到云端
            cloud_p = self._get_cloud_ignore_file()
            if cloud_p and os.path.exists(os.path.dirname(cloud_p)):
                shutil.copy2(local_p, cloud_p)
                logger.info(f"Pushed dedup_ignores to cloud: {local_p} -> {cloud_p}")

        except Exception as e:
            logger.error(f"Failed to save ignores: {e}")

    def ignore_group(self, paths: List[str]) -> Dict[str, Any]:
        """Ignore a specific combination of duplicate files."""
        if not paths or len(paths) < 2:
            return {
                "success": False,
                "message": "Need at least 2 paths to ignore group",
            }

        import uuid

        rules = self._load_ignores()

        # Check if already exists?
        new_sig = tuple(sorted(paths))
        for r in rules:
            if tuple(sorted(r["paths"])) == new_sig:
                return {"success": True, "message": "Already ignored"}

        # 存储相对路径，确保跨设备兼容
        rel_paths = [
            os.path.relpath(p, self.target_dir) if os.path.isabs(p) else p
            for p in paths
        ]
        new_rule = {
            "id": str(uuid.uuid4()),
            "paths": sorted(rel_paths),
            "created_at": datetime.now().isoformat(),
        }
        rules.append(new_rule)
        self._save_ignores(rules)
        return {"success": True, "rule_id": new_rule["id"]}

    def unignore_group(self, rule_id: str) -> Dict[str, Any]:
        """Unignore a group by ID."""
        rules = self._load_ignores()
        original_len = len(rules)
        rules = [r for r in rules if r["id"] != rule_id]

        if len(rules) < original_len:
            self._save_ignores(rules)
            return {"success": True, "message": "Unignored"}
        return {"success": False, "message": "Rule not found"}

    def delete_file(self, path: str) -> Dict[str, Any]:
        """
        Delete a file from filesystem and cleanup DB.
        """
        try:
            # 1. Resolve path (security check: must be in target_dir)
            if not os.path.isabs(path):
                path = os.path.join(self.target_dir, path)

            from .library_path_repair import path_is_inside

            path = os.path.abspath(path)
            if not path_is_inside(path, self.target_dir):
                return {
                    "success": False,
                    "message": "Security Error: Cannot delete files outside library",
                }

            if not os.path.exists(path):
                return {"success": False, "message": "File not found"}

            # 2. Delete File
            os.remove(path)

            # 3. Cleanup DB
            with self.db._db._get_conn() as conn:
                cursor = conn.cursor()
                # Find by path (try relative too)
                rel_path = os.path.relpath(path, self.target_dir)
                cursor.execute(
                    "DELETE FROM enhanced_summaries WHERE file_path = ? OR file_path = ?",
                    (path, rel_path),
                )
                cursor.execute(
                    "DELETE FROM books WHERE file_path = ? OR file_path = ?",
                    (path, rel_path),
                )
                # Note: TOC table usually cascades or we leave it (it's weak ref)

            return {"success": True, "message": "已删除"}
        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return {"success": False, "message": str(e)}


# Global Instance (lazy initialization to avoid DB connection at import time)
_sync_manager = None
_sync_manager_lock = threading.Lock()


def get_sync_manager():
    global _sync_manager
    with _sync_manager_lock:
        if _sync_manager is None:
            _sync_manager = DBSyncManager()
    return _sync_manager


class _LazySyncManagerProxy:
    def __getattr__(self, name):
        return getattr(get_sync_manager(), name)


# Backward-compatible alias for `from book_organizer.sync_manager import sync_manager`.
sync_manager = _LazySyncManagerProxy()


def __getattr__(name):
    if name == "sync_manager":
        return sync_manager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
