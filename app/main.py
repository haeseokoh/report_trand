from fastapi import FastAPI, BackgroundTasks, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os
from typing import Optional, List

from db.database import (
    init_db,
    get_all_reports,
    get_processed_reports_for_analysis
)
from analyzer.trend_analyzer import (
    get_summary_insights,
    get_surge_keywords,
    get_overall_keyword_trends,
    get_keyword_timeline,
    get_sector_keyword_analysis
)
from processor.llm_summarizer import (
    summarize_single_report,
    generate_theme_brief,
    generate_market_intelligence,
    get_available_models,
    DEFAULT_MODEL
)
from pipeline import run_pipeline

app = FastAPI(title="증권/산업 리포트 트렌드 분석 시스템", version="1.0.0")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정적 파일 경로
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(CURRENT_DIR, "static")

# 정적 파일 마운트
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.on_event("startup")
def startup_event():
    init_db()

@app.get("/")
def read_root():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.get("/api/summary")
def api_summary():
    """상단 통계 및 핫 테마 요약"""
    return get_summary_insights()

@app.get("/api/surge")
def api_surge(top_n: int = Query(15, ge=5, le=50)):
    """급상승 키워드 목록"""
    return get_surge_keywords(top_n=top_n)

@app.get("/api/keywords/top")
def api_top_keywords(top_n: int = Query(40, ge=10, le=100)):
    """상위 빈출 키워드 (워드클라우드 및 차트용)"""
    return get_overall_keyword_trends(top_n=top_n)

@app.get("/api/timeline")
def api_timeline(keywords: Optional[str] = None, top_n: int = 5):
    """키워드 일자별 언급 추이"""
    kw_list = [k.strip() for k in keywords.split(",")] if keywords else None
    return get_keyword_timeline(keywords=kw_list, top_n_keywords=top_n)

@app.get("/api/sectors")
def api_sectors(top_n: int = Query(8, ge=3, le=20)):
    """섹터별 리포트 수 및 대표 키워드"""
    return get_sector_keyword_analysis(top_sectors=top_n)

@app.get("/api/reports")
def api_reports(
    limit: int = Query(50, ge=1, le=200),
    category: Optional[str] = None,
    keyword: Optional[str] = None
):
    """리포트 목록 조회"""
    return get_all_reports(limit=limit, category=category, keyword=keyword)

# === [NEW] LLM AI 요약 및 인텔리전스 엔드포인트 ===

@app.get("/api/llm/models")
def api_llm_models():
    """사용 가능한 Ollama 모델 목록 및 기본 모델"""
    return {"models": get_available_models(), "default_model": DEFAULT_MODEL}

@app.get("/api/reports/{report_id}/ai-summary")
def api_report_ai_summary(
    report_id: int,
    model: str = Query(DEFAULT_MODEL),
    refresh: bool = Query(False)
):
    """단일 리포트 3줄 AI 심층 요약"""
    try:
        res = summarize_single_report(report_id, model=model, force_refresh=refresh)
        return res
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/themes/{theme_name}/ai-brief")
def api_theme_ai_brief(
    theme_name: str,
    model: str = Query(DEFAULT_MODEL),
    refresh: bool = Query(False)
):
    """급상승 테마 다중 리포트 종합 브리프"""
    try:
        res = generate_theme_brief(theme_name, model=model, force_refresh=refresh)
        return res
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/market/ai-brief")
def api_market_ai_brief(
    model: str = Query(DEFAULT_MODEL),
    refresh: bool = Query(False)
):
    """데일리 마켓 인텔리전스 AI 브리프"""
    try:
        res = generate_market_intelligence(model=model, force_refresh=refresh)
        return res
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# 파이프라인 백그라운드 실행 상태
is_running_pipeline = False

def background_run_pipeline(pages: int, max_pdfs: int):
    global is_running_pipeline
    try:
        run_pipeline(crawl_pages=pages, max_process_pdf=max_pdfs)
    except Exception as e:
        print(f"❌ 파이프라인 백그라운드 실행 오류: {e}")
    finally:
        is_running_pipeline = False

@app.post("/api/pipeline/run")
def api_run_pipeline(
    background_tasks: BackgroundTasks,
    pages: int = Query(2, ge=1, le=5),
    max_pdfs: int = Query(30, ge=5, le=100)
):
    """크롤링 및 트렌드 분석 백그라운드 실행 트리거"""
    global is_running_pipeline
    if is_running_pipeline:
        return JSONResponse(status_code=400, content={"message": "현재 이미 수집 및 분석 작업이 진행 중입니다."})
        
    is_running_pipeline = True
    background_tasks.add_task(background_run_pipeline, pages, max_pdfs)
    return {"message": f"수집(카테고리당 {pages}p) 및 분석({max_pdfs}건) 작업을 시작했습니다.", "status": "started"}

@app.get("/api/pipeline/status")
def api_pipeline_status():
    """파이프라인 실행 상태 확인"""
    global is_running_pipeline
    return {"is_running": is_running_pipeline}
