# -*- coding: utf-8 -*-
"""
数据库模块 - 处理 AI 分析结果的持久化存储

使用统一的 book_data.db 数据库文件,包含：
- enhanced_summaries 表：增强简介数据
- book_tocs 表：图书目录数据
"""

import json
import logging
import os
import shutil
import sqlite3
import threading
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# 统一的数据库文件名
UNIFIED_DB_NAME = "book_data.db"

# 旧的数据库文件名（用于迁移）
OLD_SUMMARIES_DB = "enhanced_summaries.db"
OLD_TOCS_DB = "book_tocs.db"


class KnowledgeCoreDB:
    """
    核心知识库数据库 (Knowledge Core)

    采用关系型设计,支持全文搜索和未来向量扩展.
    替代旧的 BookDataDB (KV 模式).
    """

    def __init__(self, db_dir=None):
        if not db_dir:
            try:
                from .config import load_config

                config = load_config()

                # 优先使用 data_dir（本机主存储路径）
                # 同步只是后台推送，不改变本机的读写路径
                data_dir = config.get("data_dir")
                if data_dir and os.path.exists(data_dir):
                    base_dir = data_dir
                else:
                    # 默认目录
                    base_dir = os.path.join(os.path.expanduser("~"), ".book_organizer")
            except Exception as e:
                print(f"Error loading config for DB: {e}")
                base_dir = os.path.join(os.path.expanduser("~"), ".book_organizer")
        else:
            base_dir = db_dir

        os.makedirs(base_dir, exist_ok=True)
        self.db_dir = base_dir
        self.db_path = os.path.join(base_dir, UNIFIED_DB_NAME)

        # 线程锁 (Reentrant Lock) - 确保应用层串行化
        self._thread_lock = threading.RLock()
        # 全局连接对象
        self._global_conn = None

        # 初始化/升级数据库
        self._init_db()

    def _init_global_conn(self):
        """初始化全局单例连接

        使用 WAL 模式提高并发性能，依赖 SQLite 内置锁机制。
        """
        if self._global_conn:
            return

        # 建立 SQLite 连接
        # check_same_thread=False 允许在多线程中复用这个连接 (受 self._thread_lock 保护)
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10.0)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")  # 提高并发读写性能
        conn.row_factory = sqlite3.Row
        self._global_conn = conn
        logger.info(f"✓ Database connected: {self.db_path}")

    def reset_connection(self):
        """Close the cached SQLite connection so the next operation reopens it."""
        with self._thread_lock:
            if self._global_conn is not None:
                try:
                    self._global_conn.close()
                except sqlite3.Error:
                    logger.warning(
                        "Failed to close stale SQLite connection", exc_info=True
                    )
                finally:
                    self._global_conn = None

    @contextmanager
    def _get_conn(self):
        """
        获取数据库连接上下文

        ⚠️ 核心参考方法：所有数据库操作都通过此方法获取连接，
        采用单例模式 + 互斥锁保护，请勿随意修改锁定逻辑。

        使用 @contextmanager 保持与旧代码 `with self._get_conn() as conn:` 的兼容性。
        """
        # 1. 获取线程锁，强制串行化所有 DB 操作
        with self._thread_lock:
            # 2. 懒加载连接
            if self._global_conn is None:
                self._init_global_conn()

            conn = self._global_conn
            try:
                yield conn
                # 3. 自动提交
                conn.commit()
            except Exception as e:
                # 异常回滚
                try:
                    conn.rollback()
                except sqlite3.Error:
                    logger.warning("SQLite rollback failed", exc_info=True)
                if isinstance(e, sqlite3.OperationalError) and "disk I/O error" in str(
                    e
                ):
                    try:
                        conn.close()
                    except sqlite3.Error:
                        logger.warning(
                            "Failed to close SQLite connection after disk I/O error",
                            exc_info=True,
                        )
                    self._global_conn = None
                raise
            # 注意：不关闭连接

    def _init_db(self):
        """初始化表结构 (Schema V2)"""
        try:
            # 使用上下文管理器获取连接
            with self._get_conn() as conn:
                cursor = conn.cursor()

                # 1. Books 表 (核心元数据)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS books (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_hash TEXT,             -- 文件哈希 (用于同步/去重)
                        filename TEXT NOT NULL,
                        file_path TEXT UNIQUE NOT NULL,
                        title TEXT,
                        author TEXT,
                        publisher TEXT,
                        meta_json TEXT,             -- 原始元数据备份
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_books_filename ON books(filename)"
                )
                self._migrate_books_to_path_identity(conn, cursor)

                # 2. Chapters 表 (扁平化目录)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS chapters (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        book_id INTEGER NOT NULL,
                        title TEXT,
                        level INTEGER DEFAULT 1,
                        page_start INTEGER,
                        page_end INTEGER,
                        content_summary TEXT,       -- 章节摘要 (AI)
                        FOREIGN KEY(book_id) REFERENCES books(id) ON DELETE CASCADE
                    )
                """)
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_chapters_book_id ON chapters(book_id)"
                )

                # 3. Enhanced Insights 表 (AI 分析结果)
                # 灵活存储：通过 insight_type 区分 "summary", "character_map" 等
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS enhanced_insights (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        book_id INTEGER NOT NULL,
                        insight_type TEXT NOT NULL, -- e.g. 'summary', 'key_concepts', 'haiku'
                        content TEXT,               -- 主要文本内容
                        json_data TEXT,             -- 结构化数据 (JSON)
                        prompt_ver TEXT,            -- Prompt 版本
                        vector_embedding BLOB,      -- 向量数据 (预留)
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(book_id) REFERENCES books(id) ON DELETE CASCADE
                    )
                """)
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_insights_book_id ON enhanced_insights(book_id)"
                )

                # 4. FTS5 全文索引 (搜索书名、章节名、Insight内容)
                # 注意：FTS5 是虚表,需要通过触发器或应用层维护同步
                try:
                    cursor.execute("""
                        CREATE VIRTUAL TABLE IF NOT EXISTS fts_index USING fts5(
                            title,
                            content,
                            source_table UNINDEXED, -- 'books', 'chapters', 'insights'
                            source_id UNINDEXED
                        )
                    """)
                except Exception as e:
                    logger.warning(f"FTS5 not supported on this SQLite version: {e}")

                # 兼容旧表 (用于平滑迁移,应用层仍可能读写这些表直到完全重构)
                self._init_legacy_tables(cursor)

                conn.commit()

                # 尝试迁移旧数据
                self._migrate_legacy_data(conn)

        except Exception as e:
            logger.error(f"Failed to init KnowledgeDB: {e}")

    def _migrate_books_to_path_identity(self, conn, cursor):
        """Use portable file paths, not basenames, as the book identity."""
        row = cursor.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='books'"
        ).fetchone()
        table_sql = (row[0] if row else "").lower().replace("\n", " ")
        if "filename text unique" not in table_sql:
            return

        conn.commit()
        backup_path = f"{self.db_path}.before_path_identity.backup"
        backup_conn = sqlite3.connect(backup_path)
        try:
            conn.backup(backup_conn)
        finally:
            backup_conn.close()
        cursor.execute("PRAGMA foreign_keys = OFF")
        try:
            cursor.execute("DROP TABLE IF EXISTS books_by_path")
            cursor.execute("""
                CREATE TABLE books_by_path (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_hash TEXT,
                    filename TEXT NOT NULL,
                    file_path TEXT UNIQUE NOT NULL,
                    title TEXT,
                    author TEXT,
                    publisher TEXT,
                    meta_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                INSERT INTO books_by_path
                    (id, file_hash, filename, file_path, title, author, publisher,
                     meta_json, created_at, updated_at)
                SELECT id, file_hash, filename,
                       COALESCE(NULLIF(file_path, ''), filename),
                       title, author, publisher, meta_json, created_at, updated_at
                FROM books
            """)
            cursor.execute("DROP TABLE books")
            cursor.execute("ALTER TABLE books_by_path RENAME TO books")
            cursor.execute("CREATE INDEX idx_books_filename ON books(filename)")
            conn.commit()
        finally:
            cursor.execute("PRAGMA foreign_keys = ON")

    def _init_legacy_tables(self, cursor):
        """保留旧表结构以确保兼容性"""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS enhanced_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE NOT NULL,
                filename TEXT NOT NULL,
                title TEXT,
                author TEXT,
                category TEXT,
                summary_json TEXT NOT NULL,
                rating INTEGER DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 尝试添加 rating 字段 (如果表已存在)
        self._migrate_add_rating_column(cursor)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS book_tocs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                file_path TEXT UNIQUE NOT NULL,
                toc_json TEXT NOT NULL,
                extraction_method TEXT,
                entry_count INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self._migrate_book_tocs_to_path_identity(cursor)
        # 转移记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transfer_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER,
                original_filename TEXT NOT NULL,
                new_filename TEXT NOT NULL,
                destination_category TEXT,
                title TEXT,
                author TEXT,
                publisher TEXT,
                series TEXT,
                tags TEXT,
                summary TEXT,
                transferred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(book_id) REFERENCES books(id) ON DELETE SET NULL
            )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_transfer_logs_time ON transfer_logs(transferred_at)"
        )

    def _migrate_book_tocs_to_path_identity(self, cursor):
        """Allow same-name books in different folders without losing TOCs."""
        row = cursor.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='book_tocs'"
        ).fetchone()
        table_sql = (row[0] if row else "").lower().replace("\n", " ")
        if "filename text unique" not in table_sql:
            return

        cursor.execute("DROP TABLE IF EXISTS book_tocs_by_path")
        cursor.execute("""
            CREATE TABLE book_tocs_by_path (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                file_path TEXT UNIQUE NOT NULL,
                toc_json TEXT NOT NULL,
                extraction_method TEXT,
                entry_count INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            INSERT OR IGNORE INTO book_tocs_by_path
                (id, filename, file_path, toc_json, extraction_method, entry_count,
                 created_at, updated_at)
            SELECT id, filename, COALESCE(NULLIF(file_path, ''), filename), toc_json,
                   extraction_method, entry_count, created_at, updated_at
            FROM book_tocs
            ORDER BY updated_at DESC, id DESC
        """)
        cursor.execute("DROP TABLE book_tocs")
        cursor.execute("ALTER TABLE book_tocs_by_path RENAME TO book_tocs")
        cursor.execute("CREATE INDEX idx_book_tocs_filename ON book_tocs(filename)")

    def _migrate_add_rating_column(self, cursor):
        """为旧表添加 rating 字段"""
        try:
            # 检查列是否存在
            cursor.execute("PRAGMA table_info(enhanced_summaries)")
            columns = [col[1] for col in cursor.fetchall()]
            if "rating" not in columns:
                logger.info("Adding 'rating' column to enhanced_summaries table...")
                cursor.execute(
                    "ALTER TABLE enhanced_summaries ADD COLUMN rating INTEGER DEFAULT NULL"
                )
        except Exception as e:
            logger.warning(f"Failed to add rating column: {e}")

    def update_book_rating(self, filename, rating, file_path=None):
        """更新图书评分 (1-5)，如果记录不存在则创建"""
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                stored_file_path = file_path
                if file_path:
                    from .library_path_repair import portable_library_path

                    stored_file_path = portable_library_path(file_path)
                where_clause = "file_path = ?" if stored_file_path else "filename = ?"
                identity = stored_file_path or filename
                if rating is None or rating == 0:
                    cursor.execute(
                        f"""
                        UPDATE enhanced_summaries
                        SET rating = NULL, updated_at = CURRENT_TIMESTAMP
                        WHERE {where_clause}
                    """,
                        (identity,),
                    )
                else:
                    cursor.execute(
                        f"""
                        UPDATE enhanced_summaries
                        SET rating = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE {where_clause}
                    """,
                        (rating, identity),
                    )

                if cursor.rowcount == 0:
                    # 记录不存在，需要插入
                    if not file_path:
                        # 如果没有提供路径，无法插入（因为 file_path 是 UNIQUE NOT NULL）
                        # 尝试只用 filename 作为占位符，但这很危险
                        logger.warning(
                            f"Cannot rate new book {filename} without file_path"
                        )
                        return False

                    logger.info(f"Inserting new record for rated book: {filename}")
                    # 插入新记录，summary_json 为空对象
                    cursor.execute(
                        """
                        INSERT INTO enhanced_summaries (filename, file_path, summary_json, rating, created_at, updated_at)
                        VALUES (?, ?, '{}', ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                        (filename, stored_file_path, rating),
                    )

                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to update rating for {filename}: {e}")
            return False

    def get_book_rating(self, filename):
        """获取图书评分，支持多种路径匹配策略"""
        try:
            basename = os.path.basename(filename)
            with self._get_conn() as conn:
                cursor = conn.cursor()
                row = None
                if filename != basename:
                    from .library_path_repair import portable_library_path

                    stored_path = portable_library_path(filename)
                    cursor.execute(
                        "SELECT rating FROM enhanced_summaries WHERE file_path = ?",
                        (stored_path,),
                    )
                    row = cursor.fetchone()
                if not row:
                    cursor.execute(
                        "SELECT rating FROM enhanced_summaries WHERE filename = ?",
                        (basename,),
                    )
                    rows = cursor.fetchall()
                    row = rows[0] if len(rows) == 1 else None

                if row:
                    return row["rating"]
                return None
        except Exception as e:
            logger.error(f"Failed to get rating for {filename}: {e}")
            return None

    def _migrate_legacy_data(self, conn):
        """将旧表数据迁移到新 Schema (如果 books 表为空)"""
        cursor = conn.cursor()

        # 检查是否已迁移
        cursor.execute("SELECT count(*) FROM books")
        if cursor.fetchone()[0] > 0:
            return

        logger.info("Migrating legacy data to Knowledge Core schema...")

        # 1. 迁移 enhanced_summaries -> books + insights
        cursor.execute("SELECT * FROM enhanced_summaries")
        summaries = cursor.fetchall()

        for row in summaries:
            try:
                # 插入 books
                # 注意：这里我们还没有 file_hash,暂时留空
                cursor.execute(
                    """
                    INSERT INTO books (filename, file_path, title, author, meta_json, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        row["filename"],
                        row["file_path"],
                        row["title"],
                        row["author"],
                        row["summary_json"],  # 暂存完整 json 到 meta_json
                        row["updated_at"],
                    ),
                )
                book_id = cursor.lastrowid

                # 插入 insights (type='full_response')
                cursor.execute(
                    """
                    INSERT INTO enhanced_insights (book_id, insight_type, content, json_data)
                    VALUES (?, 'legacy_summary', ?, ?)
                """,
                    (book_id, "Legacy Summary", row["summary_json"]),
                )

            except sqlite3.IntegrityError:
                logger.warning(
                    f"Skipping duplicate book during migration: {row['filename']}"
                )
                continue

        # 2. 迁移 book_tocs -> chapters
        cursor.execute("SELECT * FROM book_tocs")
        tocs = cursor.fetchall()

        for row in tocs:
            # 找到对应的 book_id
            cursor.execute(
                "SELECT id FROM books WHERE file_path = ?", (row["file_path"],)
            )
            book_row = cursor.fetchone()
            if not book_row:
                cursor.execute(
                    "SELECT id FROM books WHERE filename = ?", (row["filename"],)
                )
                matches = cursor.fetchall()
                book_row = matches[0] if len(matches) == 1 else None

            if book_row:
                book_id = book_row[0]
                toc_data = json.loads(row["toc_json"])

                # 递归插入章节
                self._insert_toc_chapters(cursor, book_id, toc_data)

        conn.commit()
        logger.info("Migration completed.")

    def _insert_toc_chapters(self, cursor, book_id, toc_list):
        """递归插入目录章节"""
        for item in toc_list:
            title = item.get("title", "")
            level = item.get("level", 1)
            page = item.get("page")  # 可能为 None

            cursor.execute(
                """
                INSERT INTO chapters (book_id, title, level, page_start)
                VALUES (?, ?, ?, ?)
            """,
                (book_id, title, level, page),
            )

            # 我们不递归处理子项,因为现在的 toc_list 已经是扁平的吗？
            # 检查 extract_toc 输出：它是扁平列表,只是带有 level 属性.
            # 所以不需要递归调用自身,只需遍历列表即可.
            # Wait, extract_epub_toc returns a flat list with levels. extract_pdf_toc too.
            # So simple iteration is correct.

    # ========================================================================
    # 新 API (基于新 Schema)
    # ========================================================================

    def add_book(self, filename: str, path: str, metadata: dict = None) -> int:
        """添加或更新书籍"""
        from .library_path_repair import portable_library_path

        path = portable_library_path(path)
        meta_str = json.dumps(metadata) if metadata else "{}"
        title = metadata.get("title") if metadata else None
        author = metadata.get("author") if metadata else None

        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO books (filename, file_path, title, author, meta_json, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(file_path) DO UPDATE SET
                    filename=excluded.filename,
                    title=COALESCE(excluded.title, books.title),
                    author=COALESCE(excluded.author, books.author),
                    meta_json=excluded.meta_json,
                    updated_at=CURRENT_TIMESTAMP
                RETURNING id
            """,
                (filename, path, title, author, meta_str),
            )
            return cursor.fetchone()[0]

    def add_insight(
        self, book_id: int, type: str, content: str, json_data: dict = None
    ):
        """添加 AI 分析洞察"""
        json_str = json.dumps(json_data) if json_data else None
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO enhanced_insights (book_id, insight_type, content, json_data)
                VALUES (?, ?, ?, ?)
            """,
                (book_id, type, content, json_str),
            )

    # ========================================================================
    # 兼容性层 (适配旧代码)
    # ========================================================================

    def save_summary(self, file_path, summary_data):
        """兼容旧 API: 保存到旧表 + 同步到新表"""
        try:
            from .library_path_repair import portable_library_path

            stored_file_path = portable_library_path(file_path)
            # 1. 保存到旧表 (保持现有 UI 无损)
            # 这里为了简单,我们直接重用原有的 SQL 逻辑
            filename = os.path.basename(file_path)
            metadata = summary_data.get("metadata", {})
            title = metadata.get("title", "")
            author = metadata.get("author", "")
            category = summary_data.get("category", "")
            summary_json = json.dumps(summary_data, ensure_ascii=False)

            with self._get_conn() as conn:
                cursor = conn.cursor()
                # Update Legacy
                cursor.execute(
                    """
                    INSERT INTO enhanced_summaries (file_path, filename, title, author, category, summary_json, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(file_path) DO UPDATE SET
                        filename=excluded.filename,
                        title=excluded.title,
                        author=excluded.author,
                        category=excluded.category,
                        summary_json=excluded.summary_json,
                        updated_at=CURRENT_TIMESTAMP
                """,
                    (stored_file_path, filename, title, author, category, summary_json),
                )

                # Sync to New Schema
                # Upsert Book
                cursor.execute(
                    """
                    INSERT INTO books (filename, file_path, title, author, meta_json, updated_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(file_path) DO UPDATE SET
                        filename=excluded.filename,
                        title=COALESCE(excluded.title, books.title),
                        author=COALESCE(excluded.author, books.author),
                        meta_json=excluded.meta_json,
                        updated_at=CURRENT_TIMESTAMP
                """,
                    (filename, stored_file_path, title, author, summary_json),
                )

                # Get Book ID
                cursor.execute(
                    "SELECT id FROM books WHERE file_path = ?", (stored_file_path,)
                )
                book_id = cursor.fetchone()[0]

                # Insert Insight
                cursor.execute(
                    """
                    INSERT INTO enhanced_insights (book_id, insight_type, content, json_data)
                    VALUES (?, 'summary_v1', ?, ?)
                """,
                    (book_id, summary_data.get("summary", ""), summary_json),
                )

                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save summary: {e}")
            return False

    def get_summary(self, file_path):
        """Return the path-matched summary, with unique-name legacy fallback."""
        filename = os.path.basename(file_path)
        from .library_path_repair import portable_library_path

        stored_file_path = portable_library_path(file_path)
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT summary_json FROM enhanced_summaries
                WHERE file_path = ?
                ORDER BY updated_at DESC LIMIT 1
            """,
                (stored_file_path,),
            )
            row = cursor.fetchone()

            if not row:
                cursor.execute(
                    """
                    SELECT summary_json FROM enhanced_summaries
                    WHERE filename = ?
                    ORDER BY updated_at DESC
                """,
                    (filename,),
                )
                rows = cursor.fetchall()
                row = rows[0] if len(rows) == 1 else None

            return json.loads(row["summary_json"]) if row else None

    def update_summary_filename(self, old_filename, new_filename, new_path=None):
        """兼容旧 API - 更新文件名关联

        支持匹配 basename 或完整相对路径, 解决在库管理模式下
        filename 可能是相对路径 (如 Python/OldBook.epub) 的问题.
        """
        new_basename = os.path.basename(new_filename)
        stored_new_path = new_path if new_path else new_filename
        try:
            from .library_path_repair import portable_library_path

            stored_old_path = portable_library_path(old_filename)
            stored_new_path = portable_library_path(stored_new_path)
        except Exception:
            stored_old_path = old_filename
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE enhanced_summaries SET filename=?, file_path=?, updated_at=CURRENT_TIMESTAMP
                               WHERE file_path=?""",
                (
                    new_basename,
                    stored_new_path,
                    stored_old_path,
                ),
            )
            cursor.execute(
                """UPDATE books SET filename=?, file_path=?, updated_at=CURRENT_TIMESTAMP
                               WHERE file_path=?""",
                (
                    new_basename,
                    stored_new_path,
                    stored_old_path,
                ),
            )
            conn.commit()
        return True

    def delete_book_records(self, filename: str, file_path: str = None) -> dict:
        """删除图书相关的所有数据库记录（增强简介+目录）

        Args:
            filename: 文件名（可以是 basename 或相对路径）
            file_path: 完整文件路径（可选，用于更精确匹配）

        Returns:
            dict: 删除结果统计 {'summaries': int, 'tocs': int, 'books': int}
        """
        basename = os.path.basename(filename)
        stats = {"summaries": 0, "tocs": 0, "books": 0}

        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()

                # 1. 删除 enhanced_summaries（匹配 basename 或 file_path）
                if file_path:
                    from .library_path_repair import portable_library_path

                    stored_file_path = portable_library_path(file_path)
                    cursor.execute(
                        """
                        DELETE FROM enhanced_summaries
                        WHERE file_path = ?
                    """,
                        (stored_file_path,),
                    )
                else:
                    cursor.execute(
                        """
                        DELETE FROM enhanced_summaries WHERE filename = ?
                    """,
                        (basename,),
                    )
                stats["summaries"] = cursor.rowcount

                # 2. 删除 book_tocs
                if file_path:
                    cursor.execute(
                        "DELETE FROM book_tocs WHERE file_path = ?",
                        (stored_file_path,),
                    )
                else:
                    cursor.execute(
                        "DELETE FROM book_tocs WHERE filename = ?", (basename,)
                    )
                stats["tocs"] = cursor.rowcount

                # 3. 删除 books 表记录（新 Schema）
                if file_path:
                    cursor.execute(
                        "DELETE FROM books WHERE file_path = ?", (stored_file_path,)
                    )
                else:
                    cursor.execute("DELETE FROM books WHERE filename = ?", (basename,))
                stats["books"] = cursor.rowcount

                conn.commit()

            logger.info(
                f"Deleted book records for '{basename}': "
                f"summaries={stats['summaries']}, tocs={stats['tocs']}, books={stats['books']}"
            )
            return stats

        except Exception as e:
            logger.error(f"Failed to delete book records for {filename}: {e}")
            return stats

    def get_all_summaries(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            # 排序确保最新的记录优先被索引 (应用于 /api/library 的索引构建)
            cursor.execute("""
                SELECT file_path, filename, title, author, category, rating
                FROM enhanced_summaries
                ORDER BY updated_at DESC
            """)
            return [dict(row) for row in cursor.fetchall()]

    # TOC methods compatibility
    def save_toc(self, file_path: str, toc_data: dict) -> bool:
        try:
            from .library_path_repair import portable_library_path

            stored_file_path = portable_library_path(file_path)
        except Exception:
            stored_file_path = file_path

        try:
            from book_organizer.toc_extractor import strip_toc_storage_noise

            toc_data = strip_toc_storage_noise(toc_data)
        except Exception:
            pass

        filename = os.path.basename(file_path)
        toc_items = toc_data.get("toc", []) or []
        toc_text = toc_data.get("toc_text", "") or ""
        if toc_text:
            stored_toc = {
                "toc": toc_items,
                "toc_text": toc_text,
                "ai_processed": toc_data.get("ai_processed", False),
                "modes_used": toc_data.get("modes_used", []),
            }
        else:
            stored_toc = toc_items
        toc_json = json.dumps(stored_toc, ensure_ascii=False)
        method = toc_data.get("method", "builtin")
        entry_count = toc_data.get("entry_count", 0)
        if not entry_count:
            if toc_items:
                entry_count = len(toc_items)
            elif toc_text:
                entry_count = len(
                    [line for line in toc_text.splitlines() if line.strip()]
                )

        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                # Legacy
                cursor.execute(
                    """
                    INSERT INTO book_tocs (filename, file_path, toc_json, extraction_method, entry_count, updated_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(file_path) DO UPDATE SET
                        filename=excluded.filename,
                        toc_json=excluded.toc_json,
                        extraction_method=excluded.extraction_method,
                        entry_count=excluded.entry_count,
                        updated_at=CURRENT_TIMESTAMP
                """,
                    (filename, stored_file_path, toc_json, method, entry_count),
                )

                # New Schema
                # Ensure book exists
                cursor.execute(
                    """INSERT INTO books (filename, file_path) VALUES (?, ?)
                       ON CONFLICT(file_path) DO UPDATE SET filename=excluded.filename""",
                    (filename, stored_file_path),
                )
                cursor.execute(
                    "SELECT id FROM books WHERE file_path = ?", (stored_file_path,)
                )
                book_id_row = cursor.fetchone()

                if book_id_row:
                    book_id = book_id_row[0]
                    # Clear old chapters
                    cursor.execute("DELETE FROM chapters WHERE book_id = ?", (book_id,))
                    # Insert new
                    self._insert_toc_chapters(cursor, book_id, toc_items)

                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save TOC: {e}")
            return False

    def get_toc(self, file_path: str) -> dict:
        """获取目录数据，支持多种路径匹配策略"""
        filename = os.path.basename(file_path)
        with self._get_conn() as conn:
            cursor = conn.cursor()
            from .library_path_repair import portable_library_path

            stored_file_path = portable_library_path(file_path)
            cursor.execute(
                "SELECT toc_json, extraction_method, entry_count FROM book_tocs WHERE file_path = ?",
                (stored_file_path,),
            )
            row = cursor.fetchone()

            if not row:
                cursor.execute(
                    "SELECT toc_json, extraction_method, entry_count FROM book_tocs WHERE filename = ?",
                    (filename,),
                )
                rows = cursor.fetchall()
                row = rows[0] if len(rows) == 1 else None

            if row:
                stored_toc = json.loads(row["toc_json"])
                toc_text = ""
                if isinstance(stored_toc, dict):
                    toc = stored_toc.get("toc", []) or []
                    toc_text = stored_toc.get("toc_text", "") or ""
                elif isinstance(stored_toc, list):
                    toc = stored_toc
                elif isinstance(stored_toc, str):
                    toc = []
                    toc_text = stored_toc
                else:
                    toc = []
                result = {
                    "success": True,
                    "toc": toc,
                    "toc_text": toc_text,
                    "method": row["extraction_method"],
                    "entry_count": row["entry_count"],
                }
                try:
                    from book_organizer.toc_extractor import strip_toc_storage_noise

                    result = strip_toc_storage_noise(result)
                except Exception:
                    pass
                return result
            return None

    def update_toc_filename(
        self, old_filename: str, new_filename: str, new_path: str = None
    ) -> bool:
        new_basename = os.path.basename(new_filename)
        from .library_path_repair import portable_library_path

        old_path = portable_library_path(old_filename)
        new_stored_path = portable_library_path(new_path if new_path else new_filename)
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE book_tocs SET filename=?, file_path=? WHERE file_path=?",
                (new_basename, new_stored_path, old_path),
            )
            conn.commit()
        return True

    def get_all_toc_filenames(self) -> list:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT filename FROM book_tocs")
            return [row[0] for row in cursor.fetchall()]

    def get_all_toc_records(self) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute("SELECT filename, file_path FROM book_tocs").fetchall()
            return [dict(row) for row in rows]

    # ========================================================================
    # 转移记录方法
    # ========================================================================

    def save_transfer_log(
        self,
        original_filename: str,
        new_filename: str,
        destination_category: str,
        metadata: dict,
        summary: str = "",
    ) -> bool:
        """保存转移记录到数据库.

        Args:
            original_filename: 原始文件名
            new_filename: 新文件名
            destination_category: 目标分类目录
            metadata: 元数据字典 (title, author, publisher, series, tags)
            summary: 图书简介

        Returns:
            bool: 是否保存成功
        """
        try:
            # 尝试查找关联的 book_id
            book_id = None
            with self._get_conn() as conn:
                cursor = conn.cursor()
                from .library_path_repair import portable_library_path

                stored_path = portable_library_path(new_filename)
                cursor.execute("SELECT id FROM books WHERE file_path = ?", (stored_path,))
                row = cursor.fetchone()
                if not row:
                    cursor.execute(
                        "SELECT id FROM books WHERE filename = ?",
                        (os.path.basename(new_filename),),
                    )
                    rows = cursor.fetchall()
                    row = rows[0] if len(rows) == 1 else None
                if row:
                    book_id = row[0]

                cursor.execute(
                    """
                    INSERT INTO transfer_logs (
                        book_id, original_filename, new_filename,
                        destination_category, title, author,
                        publisher, series, tags, summary
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        book_id,
                        original_filename,
                        new_filename,
                        destination_category,
                        metadata.get("title", ""),
                        metadata.get("author", ""),
                        metadata.get("publisher", ""),
                        metadata.get("series", ""),
                        metadata.get("tags", ""),
                        summary,
                    ),
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save transfer log: {e}")
            return False

    def get_transfer_logs(self, limit: int = 50, days: int = None) -> list:
        """获取转移记录列表.

        Args:
            limit: 最大返回数量
            days: 限制最近 N 天内的记录 (可选)

        Returns:
            list: 转移记录列表
        """
        with self._get_conn() as conn:
            cursor = conn.cursor()
            if days:
                cursor.execute(
                    """
                    SELECT * FROM transfer_logs
                    WHERE transferred_at >= datetime('now', ?)
                    ORDER BY transferred_at DESC LIMIT ?
                """,
                    (f"-{days} days", limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM transfer_logs
                    ORDER BY transferred_at DESC LIMIT ?
                """,
                    (limit,),
                )
            return [dict(row) for row in cursor.fetchall()]

    def get_transfer_log_count(self) -> int:
        """获取转移记录总数."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT count(*) FROM transfer_logs")
            return cursor.fetchone()[0]


# ============================================================================
# 兼容性包装类（保持旧 API 兼容）
# ============================================================================

_core_db_instance = None
_db_singleton_lock = threading.Lock()


def _get_shared_core_db(db_dir=None):
    """获取共享的核心数据库实例 (单例模式)"""
    global _core_db_instance
    with _db_singleton_lock:
        if _core_db_instance is None:
            _core_db_instance = KnowledgeCoreDB(db_dir)
        return _core_db_instance


class EnhancedSummariesDB:
    """兼容性包装类 - 保持旧 API 不变"""

    def __init__(self, db_dir=None):
        # 使用共享的核心 DB 实例，避免多重锁冲突
        self._db = _get_shared_core_db(db_dir)
        self.db_path = self._db.db_path

    def save_summary(self, file_path, summary_data):
        return self._db.save_summary(file_path, summary_data)

    def get_summary(self, file_path):
        return self._db.get_summary(file_path)

    def update_filename(self, old_filename, new_filename, new_path=None):
        return self._db.update_summary_filename(old_filename, new_filename, new_path)

    def get_all_summaries(self):
        return self._db.get_all_summaries()

    def update_book_rating(self, filename, rating, file_path=None):
        return self._db.update_book_rating(filename, rating, file_path)

    def get_book_rating(self, filename):
        return self._db.get_book_rating(filename)


class BookTocDB:
    """兼容性包装类 - 保持旧 API 不变"""

    def __init__(self, db_dir=None):
        # 使用共享的核心 DB 实例，避免多重锁冲突
        self._db = _get_shared_core_db(db_dir)
        self.db_path = self._db.db_path

    def save_toc(self, file_path: str, toc_data: dict) -> bool:
        return self._db.save_toc(file_path, toc_data)

    def get_toc(self, file_path: str) -> dict:
        return self._db.get_toc(file_path)

    def update_filename(
        self, old_filename: str, new_filename: str, new_path: str = None
    ) -> bool:
        return self._db.update_toc_filename(old_filename, new_filename, new_path)

    def get_all_filenames(self) -> list:
        return self._db.get_all_toc_filenames()

    def get_all_records(self) -> list[dict]:
        return self._db.get_all_toc_records()


# ============================================================================
# 数据库迁移和全局实例管理
# ============================================================================


def move_database(new_dir):
    """复制数据库文件到新目录（不删除原文件，用户验证后手动删除）"""
    global _db_instance, _toc_db_instance
    if not new_dir:
        new_dir = os.path.join(os.path.expanduser("~"), ".book_organizer")

    current_db = get_db()  # Returns EnhancedSummariesDB
    current_path = current_db.db_path

    if not os.path.exists(current_path):
        return False, "原数据库文件不存在"

    target_path = os.path.join(new_dir, UNIFIED_DB_NAME)
    if os.path.abspath(current_path) == os.path.abspath(target_path):
        return True, "路径相同,无需移动"

    try:
        os.makedirs(new_dir, exist_ok=True)
        shutil.copy2(current_path, target_path)
        if os.path.exists(target_path) and os.path.getsize(target_path) > 0:
            # 重置数据库单例，使其在下次访问时使用新路径
            _db_instance = None
            _toc_db_instance = None
            global _core_db_instance
            _core_db_instance = None
            # 注意：不删除原文件，用户验证无误后手动删除
            return (
                True,
                f"数据库已复制到: {target_path}（原文件保留，请验证后手动删除）",
            )
        else:
            return False, "复制失败"
    except Exception as e:
        return False, str(e)


# 全局实例
_db_instance = None
_toc_db_instance = None


def get_db():
    """获取增强简介数据库实例"""
    global _db_instance
    from .config import load_config

    if _db_instance is None:
        config = load_config()
        db_dir = config.get("data_dir")
        _db_instance = EnhancedSummariesDB(db_dir)
    return _db_instance


def get_toc_db():
    """获取目录数据库实例"""
    global _toc_db_instance
    from .config import load_config

    if _toc_db_instance is None:
        config = load_config()
        db_dir = config.get("data_dir")
        _toc_db_instance = BookTocDB(db_dir)
    return _toc_db_instance


def close_db():
    """关闭数据库连接（通常在程序退出时调用）"""
    global _db_instance
    if _db_instance and _db_instance._db:
        # Close SQLite connection
        if _db_instance._db._global_conn:
            try:
                _db_instance._db._global_conn.close()
                logger.info("Database connection closed.")
            except Exception as e:
                logger.warning(f"Error closing database: {e}")
            _db_instance._db._global_conn = None

    # Reset core instance
    global _core_db_instance
    _core_db_instance = None


def reset_db_instances():
    """重置所有数据库单例，使其在下次访问时重新根据配置初始化。

    用于同步配置变更后强制切换数据库路径。
    """
    global _db_instance, _toc_db_instance, _core_db_instance

    # 先关闭现有连接
    if _db_instance and _db_instance._db:
        if _db_instance._db._global_conn:
            try:
                _db_instance._db._global_conn.close()
            except Exception:
                pass
            _db_instance._db._global_conn = None

    if _core_db_instance and _core_db_instance._global_conn:
        try:
            _core_db_instance._global_conn.close()
        except Exception:
            pass

    # 重置单例
    _db_instance = None
    _toc_db_instance = None
    _core_db_instance = None
    logger.info("Database instances reset for path switch.")
