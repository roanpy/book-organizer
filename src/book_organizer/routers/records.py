# -*- coding: utf-8 -*-
"""Transfer records router - transfer logs and summary records."""

from typing import Any, Dict

from fastapi import APIRouter

from book_organizer.database import get_db

router = APIRouter(tags=["records"])


@router.get("/api/records/transfers")
def get_transfer_records(
    start_date: str = None,
    end_date: str = None,
    search: str = None,
    page: int = 1,
    page_size: int = 50,
) -> Dict[str, Any]:
    try:
        db = get_db()
        with db._db._get_conn() as conn:
            cursor = conn.cursor()
            where_clauses = []
            params = []

            if start_date and end_date:
                where_clauses.append(
                    "date(transferred_at) >= ? AND date(transferred_at) <= ?"
                )
                params.extend([start_date, end_date])
            elif start_date:
                where_clauses.append("date(transferred_at) >= ?")
                params.append(start_date)

            if search:
                search_term = f"%{search}%"
                where_clauses.append("""(
                    original_filename LIKE ? OR
                    new_filename LIKE ? OR
                    title LIKE ? OR
                    author LIKE ?
                )""")
                params.extend([search_term, search_term, search_term, search_term])

            where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

            cursor.execute(f"SELECT COUNT(*) FROM transfer_logs {where_sql}", params)
            total = cursor.fetchone()[0]

            offset = (page - 1) * page_size
            cursor.execute(
                f"""
                SELECT id, book_id, original_filename, new_filename,
                       destination_category, title, author, publisher,
                       series, tags, summary, transferred_at
                FROM transfer_logs {where_sql}
                ORDER BY transferred_at DESC
                LIMIT ? OFFSET ?
            """,
                params + [page_size, offset],
            )
            records = [dict(row) for row in cursor.fetchall()]

        return {
            "records": records,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        }
    except Exception as e:
        print(f"Error fetching records: {e}")
        return {"records": [], "total": 0, "error": str(e)}


@router.get("/api/records/summaries")
def get_summary_records(
    start_date: str = None,
    end_date: str = None,
    search: str = None,
    page: int = 1,
    page_size: int = 50,
) -> Dict[str, Any]:
    try:
        db = get_db()
        with db._db._get_conn() as conn:
            cursor = conn.cursor()
            where_clauses = []
            params = []

            if start_date and end_date:
                where_clauses.append("date(updated_at) >= ? AND date(updated_at) <= ?")
                params.extend([start_date, end_date])
            elif start_date:
                where_clauses.append("date(updated_at) >= ?")
                params.append(start_date)

            if search:
                search_term = f"%{search}%"
                where_clauses.append("""(
                    filename LIKE ? OR
                    title LIKE ? OR
                    author LIKE ?
                )""")
                params.extend([search_term, search_term, search_term])

            where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

            cursor.execute(
                f"SELECT COUNT(*) FROM enhanced_summaries {where_sql}", params
            )
            total = cursor.fetchone()[0]

            offset = (page - 1) * page_size
            cursor.execute(
                f"""
                SELECT id, file_path, filename, title, author, category,
                       summary_json, created_at, updated_at
                FROM enhanced_summaries {where_sql}
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
            """,
                params + [page_size, offset],
            )
            records = [dict(row) for row in cursor.fetchall()]

        return {
            "records": records,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        }
    except Exception as e:
        return {"records": [], "total": 0, "error": str(e)}
