import sqlite3
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
from collections import defaultdict, Counter
import math
from db.database import DB_PATH, get_processed_reports_for_analysis, set_trend_cache, get_trend_cache
from processor.nlp_engine import extract_nouns_as_token_list

def get_overall_keyword_trends(top_n: int = 30) -> List[Dict[str, Any]]:
    """전체 리포트 대상 상위 빈출 키워드 집계"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT rk.keyword, SUM(rk.count) as total_count, COUNT(DISTINCT rk.report_id) as doc_count
            FROM report_keywords rk
            JOIN reports r ON rk.report_id = r.id
            WHERE r.processed = 1
            GROUP BY rk.keyword
            ORDER BY total_count DESC
            LIMIT ?
        """, (top_n,))
        
        results = []
        for kw, total_cnt, doc_cnt in cursor.fetchall():
            results.append({
                "text": kw,
                "value": total_cnt,
                "doc_count": doc_cnt
            })
        return results

def get_surge_keywords(top_n: int = 15) -> List[Dict[str, Any]]:
    """최근 리포트 vs 이전 리포트 비교를 통한 급상승(Surge) 키워드 발굴"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 처리된 리포트 날짜 목록 조회
        cursor.execute("""
            SELECT DISTINCT report_date 
            FROM reports 
            WHERE processed = 1 
            ORDER BY report_date DESC
        """)
        dates = [row["report_date"] for row in cursor.fetchall()]
        
        if not dates:
            return []
            
        # 최근 50% 일자와 이전 50% 일자로 분할 (또는 최근 7일)
        mid_idx = max(1, len(dates) // 2)
        recent_dates = dates[:mid_idx]
        past_dates = dates[mid_idx:] if len(dates) > 1 else []
        
        # 최근 기간 키워드 빈도
        cursor.execute(f"""
            SELECT rk.keyword, SUM(rk.count) as cnt
            FROM report_keywords rk
            JOIN reports r ON rk.report_id = r.id
            WHERE r.report_date IN ({','.join(['?']*len(recent_dates))})
            GROUP BY rk.keyword
        """, recent_dates)
        recent_counts = {row[0]: row[1] for row in cursor.fetchall()}
        
        # 이전 기간 키워드 빈도
        past_counts = {}
        if past_dates:
            cursor.execute(f"""
                SELECT rk.keyword, SUM(rk.count) as cnt
                FROM report_keywords rk
                JOIN reports r ON rk.report_id = r.id
                WHERE r.report_date IN ({','.join(['?']*len(past_dates))})
                GROUP BY rk.keyword
            """, past_dates)
            past_counts = {row[0]: row[1] for row in cursor.fetchall()}
            
        surge_scores = []
        for kw, r_cnt in recent_counts.items():
            if r_cnt < 2:  # 최소 출현 횟수
                continue
                
            p_cnt = past_counts.get(kw, 0)
            # 급상승 스코어: (최근 / (이전 + 1)) * log2(최근빈도 + 1)
            growth_ratio = (r_cnt + 1) / (p_cnt + 1)
            score = growth_ratio * math.log2(r_cnt + 2)
            
            surge_scores.append({
                "keyword": kw,
                "recent_count": r_cnt,
                "past_count": p_cnt,
                "growth_ratio": round(growth_ratio, 2),
                "surge_score": round(score, 2)
            })
            
        surge_scores.sort(key=lambda x: x["surge_score"], reverse=True)
        return surge_scores[:top_n]

def get_keyword_timeline(keywords: Optional[List[str]] = None, top_n_keywords: int = 5) -> Dict[str, Any]:
    """주요 키워드의 일자별 출현 빈도 시계열 데이터"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        if not keywords:
            # 상위 N개 키워드 자동 선정
            cursor.execute("""
                SELECT keyword 
                FROM report_keywords 
                GROUP BY keyword 
                ORDER BY SUM(count) DESC 
                LIMIT ?
            """, (top_n_keywords,))
            keywords = [row[0] for row in cursor.fetchall()]
            
        if not keywords:
            return {"dates": [], "series": []}
            
        # 전체 일자 목록
        cursor.execute("""
            SELECT DISTINCT report_date 
            FROM reports 
            WHERE processed = 1 
            ORDER BY report_date ASC
        """)
        all_dates = [row[0] for row in cursor.fetchall()]
        
        series = []
        for kw in keywords:
            cursor.execute("""
                SELECT r.report_date, SUM(rk.count)
                FROM report_keywords rk
                JOIN reports r ON rk.report_id = r.id
                WHERE rk.keyword = ? AND r.processed = 1
                GROUP BY r.report_date
            """, (kw,))
            date_counts = dict(cursor.fetchall())
            
            data_points = [date_counts.get(d, 0) for d in all_dates]
            series.append({
                "name": kw,
                "data": data_points
            })
            
        return {
            "dates": all_dates,
            "series": series
        }

def get_sector_keyword_analysis(top_sectors: int = 6) -> List[Dict[str, Any]]:
    """산업/섹터별 주요 관심 키워드 및 리포트 수 집계"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # 리포트 수가 많은 상위 섹터/종목 추출
        cursor.execute("""
            SELECT company_or_sector, COUNT(*) as report_count
            FROM reports
            WHERE processed = 1 AND company_or_sector IS NOT NULL AND company_or_sector != ''
            GROUP BY company_or_sector
            ORDER BY report_count DESC
            LIMIT ?
        """, (top_sectors,))
        sectors = cursor.fetchall()
        
        sector_results = []
        for sector_name, r_count in sectors:
            # 해당 섹터의 대표 키워드 TOP 5
            cursor.execute("""
                SELECT rk.keyword, SUM(rk.count) as total_cnt
                FROM report_keywords rk
                JOIN reports r ON rk.report_id = r.id
                WHERE r.company_or_sector = ? AND r.processed = 1
                GROUP BY rk.keyword
                ORDER BY total_cnt DESC
                LIMIT 5
            """, (sector_name,))
            top_kws = [f"{kw}({cnt})" for kw, cnt in cursor.fetchall()]
            
            sector_results.append({
                "sector": sector_name,
                "report_count": r_count,
                "top_keywords": top_kws
            })
            
        return sector_results

def get_summary_insights() -> Dict[str, Any]:
    """대시보드 상단 핵심 지표 및 인사이트 요약"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM reports")
        total_reports = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM reports WHERE processed = 1")
        processed_reports = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT company_or_sector) FROM reports WHERE company_or_sector != ''")
        total_sectors = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT broker) FROM reports WHERE broker != ''")
        total_brokers = cursor.fetchone()[0]
        
    surge_kws = get_surge_keywords(top_n=3)
    hot_themes = [k["keyword"] for k in surge_kws]
    
    return {
        "total_reports": total_reports,
        "processed_reports": processed_reports,
        "total_sectors": total_sectors,
        "total_brokers": total_brokers,
        "hot_themes": hot_themes
    }
