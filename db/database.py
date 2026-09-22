import sqlite3
import json
import os
from typing import List, Dict, Any, Optional

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DB_DIR, "reports.db")
PDF_DIR = os.path.join(DB_DIR, "pdfs")

def init_db():
    """데이터베이스 및 디렉토리 초기화"""
    os.makedirs(DB_DIR, exist_ok=True)
    os.makedirs(PDF_DIR, exist_ok=True)
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # 리포트 메타데이터 및 본문 저장 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,          -- company(기업), industry(산업), market(시황)
                title TEXT NOT NULL,
                company_or_sector TEXT,         -- 대상 종목명 또는 산업명
                broker TEXT,                    -- 증권사명
                author TEXT,                    -- 애널리스트/작성자
                report_date TEXT NOT NULL,      -- YYYY-MM-DD
                pdf_url TEXT UNIQUE NOT NULL,   -- 리포트 원문 다운로드 링크 (고유 식별자)
                local_pdf_path TEXT,            -- 로컬 저장 경로
                summary_text TEXT,              -- 본문 요약 / 앞부분
                full_text TEXT,                 -- 본문 전체 텍스트
                processed INTEGER DEFAULT 0,    -- NLP 처리 여부 (0: 미처리, 1: 완료, -1: 실패)
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 리포트별 추출 키워드 저장 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS report_keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_id INTEGER NOT NULL,
                keyword TEXT NOT NULL,
                count INTEGER DEFAULT 1,
                FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE
            )
        """)
        
        # 인덱스 생성
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_reports_date ON reports(report_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_reports_category ON reports(category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_keywords_keyword ON report_keywords(keyword)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_keywords_report_id ON report_keywords(report_id)")
        
        # 트렌드 분석 캐시 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trend_cache (
                cache_key TEXT PRIMARY KEY,
                data_json TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 리포트별 AI 심층 요약 저장 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS report_ai_summaries (
                report_id INTEGER PRIMARY KEY,
                model_name TEXT NOT NULL,
                summary_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE
            )
        """)
        
        conn.commit()

def save_report(report_data: Dict[str, Any]) -> Optional[int]:
    """리포트 메타데이터 저장 (중복 시 무시)"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO reports 
                (category, title, company_or_sector, broker, author, report_date, pdf_url)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                report_data.get("category"),
                report_data.get("title"),
                report_data.get("company_or_sector", ""),
                report_data.get("broker", ""),
                report_data.get("author", ""),
                report_data.get("report_date"),
                report_data.get("pdf_url")
            ))
            conn.commit()
            return cursor.lastrowid if cursor.rowcount > 0 else None
        except Exception as e:
            print(f"Error saving report: {e}")
            return None

def update_report_text(report_id: int, local_pdf_path: str, full_text: str, summary_text: str = ""):
    """PDF 추출 텍스트 업데이트"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE reports 
            SET local_pdf_path = ?, full_text = ?, summary_text = ?, processed = 1
            WHERE id = ?
        """, (local_pdf_path, full_text, summary_text, report_id))
        conn.commit()

def save_report_keywords(report_id: int, keywords_with_count: List[tuple]):
    """리포트 키워드 빈도 저장"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM report_keywords WHERE report_id = ?", (report_id,))
        cursor.executemany("""
            INSERT INTO report_keywords (report_id, keyword, count)
            VALUES (?, ?, ?)
        """, [(report_id, kw, cnt) for kw, cnt in keywords_with_count])
        conn.commit()

def get_unprocessed_reports(limit: int = 50) -> List[Dict[str, Any]]:
    """텍스트 미추출 리포트 조회"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM reports WHERE processed = 0 ORDER BY report_date DESC LIMIT ?", (limit,))
        return [dict(row) for row in cursor.fetchall()]

def get_all_reports(limit: int = 100, category: Optional[str] = None, keyword: Optional[str] = None) -> List[Dict[str, Any]]:
    """리포트 목록 조회 (필터 지원 및 AI 요약 연동)"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = """
            SELECT 
                r.id, r.category, r.title, r.company_or_sector, r.broker, r.author, 
                r.report_date, r.pdf_url, r.summary_text, r.processed,
                s.summary_json as ai_summary_json, s.model_name as ai_model
            FROM reports r
            LEFT JOIN report_ai_summaries s ON r.id = s.report_id
            WHERE 1=1
        """
        params = []
        
        if category:
            query += " AND r.category = ?"
            params.append(category)
        if keyword:
            query += " AND (r.title LIKE ? OR r.company_or_sector LIKE ? OR r.summary_text LIKE ?)"
            kw_param = f"%{keyword}%"
            params.extend([kw_param, kw_param, kw_param])
            
        query += " ORDER BY r.report_date DESC, r.id DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        results = []
        for row in cursor.fetchall():
            item = dict(row)
            if item.get("ai_summary_json"):
                try:
                    item["ai_summary"] = json.loads(item["ai_summary_json"])
                except Exception:
                    item["ai_summary"] = None
            else:
                item["ai_summary"] = None
            item.pop("ai_summary_json", None)
            results.append(item)
        return results

def get_processed_reports_for_analysis(start_date: Optional[str] = None, end_date: Optional[str] = None, category: Optional[str] = None) -> List[Dict[str, Any]]:
    """트렌드 분석용 텍스트 추출 완료 리포트 조회"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT id, category, title, company_or_sector, broker, report_date, full_text FROM reports WHERE processed = 1 AND full_text IS NOT NULL AND length(full_text) > 50"
        params = []
        
        if start_date:
            query += " AND report_date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND report_date <= ?"
            params.append(end_date)
        if category:
            query += " AND category = ?"
            params.append(category)
            
        query += " ORDER BY report_date ASC"
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

def set_trend_cache(cache_key: str, data: Any):
    """트렌드 분석 결과 캐싱"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO trend_cache (cache_key, data_json, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (cache_key, json.dumps(data, ensure_ascii=False)))
        conn.commit()

def get_trend_cache(cache_key: str) -> Optional[Any]:
    """캐시된 트렌드 분석 결과 조회"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT data_json FROM trend_cache WHERE cache_key = ?", (cache_key,))
        row = cursor.fetchone()
        if row:
            return json.loads(row[0])
        return None

def get_report_by_id(report_id: int) -> Optional[Dict[str, Any]]:
    """단일 리포트 상세 조회 (본문 포함)"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM reports WHERE id = ?", (report_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def save_report_ai_summary(report_id: int, model_name: str, summary_data: Dict[str, Any]):
    """리포트 AI 요약 결과 저장"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO report_ai_summaries (report_id, model_name, summary_json, created_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """, (report_id, model_name, json.dumps(summary_data, ensure_ascii=False)))
        conn.commit()

def get_report_ai_summary(report_id: int) -> Optional[Dict[str, Any]]:
    """리포트 AI 요약 결과 조회"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT summary_json, model_name, created_at FROM report_ai_summaries WHERE report_id = ?", (report_id,))
        row = cursor.fetchone()
        if row:
            data = json.loads(row["summary_json"])
            data["_model"] = row["model_name"]
            data["_created_at"] = row["created_at"]
            return data
        return None
