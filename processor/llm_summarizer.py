import requests
import json
import re
from typing import Dict, Any, Optional, List
from db.database import (
    get_report_by_id,
    save_report_ai_summary,
    get_report_ai_summary,
    get_trend_cache,
    set_trend_cache,
    DB_PATH
)
import sqlite3

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:7b"

def get_available_models() -> List[str]:
    """설치된 Ollama 모델 목록 조회"""
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
        if resp.status_code == 200:
            models = [m["name"] for m in resp.json().get("models", [])]
            return models
        return [DEFAULT_MODEL]
    except Exception:
        return [DEFAULT_MODEL]

def call_ollama(
    prompt: str,
    system_prompt: str = "",
    model: str = DEFAULT_MODEL,
    json_mode: bool = True
) -> str:
    """Ollama API 호출 (스트리밍 없이 한 번에 반환)"""
    url = f"{OLLAMA_BASE_URL}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "system": system_prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "top_p": 0.9,
            "num_ctx": 8192
        }
    }
    if json_mode:
        payload["format"] = "json"
        
    try:
        response = requests.post(url, json=payload, timeout=60)
        if response.status_code == 200:
            result = response.json()
            return result.get("response", "").strip()
        else:
            raise RuntimeError(f"Ollama API Error ({response.status_code}): {response.text}")
    except Exception as e:
        raise RuntimeError(f"Failed to communicate with Ollama at {OLLAMA_BASE_URL}: {e}")

def parse_json_safely(raw_text: str) -> Dict[str, Any]:
    """LLM 반환 텍스트에서 안전하게 JSON 파싱"""
    try:
        return json.loads(raw_text)
    except Exception:
        # Markdown 코드 블록 제거 후 재시도
        match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
        return {"raw_content": raw_text}

def summarize_single_report(
    report_id: int,
    model: str = DEFAULT_MODEL,
    force_refresh: bool = False
) -> Dict[str, Any]:
    """개별 리포트 3줄 핵심 요약 및 투자포인트 추출"""
    if not force_refresh:
        cached = get_report_ai_summary(report_id)
        if cached:
            return cached
            
    report = get_report_by_id(report_id)
    if not report:
        raise ValueError(f"Report ID {report_id} not found.")
        
    title = report.get("title", "")
    target = report.get("company_or_sector", "")
    broker = report.get("broker", "")
    date = report.get("report_date", "")
    full_text = report.get("full_text", "")
    
    # 텍스트가 없을 경우 요약 불가
    if not full_text or len(full_text) < 50:
        return {
            "one_line_summary": "본문 텍스트가 부족하여 AI 요약을 생성할 수 없습니다.",
            "investment_points": [],
            "financial_outlook": "-",
            "risk_factors": [],
            "sentiment": "중립"
        }
        
    # 최대 4000자만 프롬프트에 포함
    trimmed_text = full_text[:4000]
    
    system_prompt = """당신은 증권사 및 자산운용사의 수석 퀀트/애널리스트입니다. 
제공된 증권사 리포트 본문을 분석하여, 투자자가 30초 내에 핵심을 파악할 수 있도록 구조화된 JSON 형태로 요약하십시오.
한국어로 명확하고 전문적인 어조로 작성하십시오.

반드시 다음 JSON 스키마를 엄격히 준수하여 응답하십시오:
{
  "one_line_summary": "핵심을 꿰뚫는 한 줄 결론 (100자 이내)",
  "sentiment": "긍정(Bullish) 또는 중립(Neutral) 또는 신중(Bearish)",
  "investment_points": [
    "핵심 투자 포인트 1",
    "핵심 투자 포인트 2",
    "핵심 투자 포인트 3"
  ],
  "financial_outlook": "실적 및 밸류에이션/목표주가 전망 요약",
  "risk_factors": [
    "투자 시 주의해야 할 주요 리스크 1",
    "주요 리스크 2"
  ]
}"""

    user_prompt = f"""[리포트 정보]
- 작성일: {date}
- 대상: {target}
- 증권사: {broker}
- 제목: {title}

[리포트 본문]
{trimmed_text}
"""

    raw_response = call_ollama(user_prompt, system_prompt, model=model, json_mode=True)
    summary_data = parse_json_safely(raw_response)
    
    # 기본 필드 누락 방지
    summary_data.setdefault("one_line_summary", title)
    summary_data.setdefault("sentiment", "중립")
    summary_data.setdefault("investment_points", [])
    summary_data.setdefault("financial_outlook", "")
    summary_data.setdefault("risk_factors", [])
    
    # DB 저장
    save_report_ai_summary(report_id, model, summary_data)
    
    summary_data["_model"] = model
    return summary_data

def generate_theme_brief(
    theme_name: str,
    model: str = DEFAULT_MODEL,
    force_refresh: bool = False
) -> Dict[str, Any]:
    """급상승 테마/키워드 관련 다중 리포트 종합 브리프 생성"""
    cache_key = f"theme_brief_{theme_name}_{model}"
    if not force_refresh:
        cached = get_trend_cache(cache_key)
        if cached:
            return cached
            
    # 해당 키워드를 포함하는 최근 리포트 상위 4개 조회
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.id, r.title, r.company_or_sector, r.broker, r.report_date, r.summary_text, r.full_text
            FROM report_keywords rk
            JOIN reports r ON rk.report_id = r.id
            WHERE rk.keyword = ? AND r.processed = 1
            ORDER BY r.report_date DESC, rk.count DESC
            LIMIT 4
        """, (theme_name,))
        matched_reports = [dict(row) for row in cursor.fetchall()]
        
    if not matched_reports:
        return {
            "theme": theme_name,
            "market_driver": "관련 리포트 정보가 충분하지 않습니다.",
            "consensus": "데이터 수집 후 다시 시도해 주세요.",
            "top_beneficiaries": [],
            "risk_points": []
        }
        
    docs_context = ""
    for idx, r in enumerate(matched_reports, 1):
        snippet = (r.get("full_text") or r.get("summary_text") or "")[:1200]
        docs_context += f"\n[리포트 {idx}] ({r['report_date']} | {r['broker']} | {r['company_or_sector']})\n제목: {r['title']}\n발췌:\n{snippet}\n---"
        
    system_prompt = """당신은 시장 테마를 분석하는 탑티어 매크로 전략가입니다.
주어진 테마/키워드에 관련된 복수의 애널리스트 리포트들을 종합하여, 시장의 흐름과 투자 시사점을 JSON 포맷으로 작성하십시오.

JSON 스키마:
{
  "theme": "테마명",
  "market_driver": "해당 테마가 현재 시장에서 주목받는 핵심 배경 및 이유 (2~3문장)",
  "consensus": "증권사 애널리스트들의 공통 시각 및 의견 종합 (2~3문장)",
  "top_beneficiaries": ["수혜 기업/종목 1", "수혜 기업/종목 2", "수혜 기업/종목 3"],
  "catalysts": ["주가 상승을 이끌 향후 이벤트 및 촉매 1", "촉매 2"],
  "risk_points": ["유의해야 할 리스크 및 변수 1", "변수 2"]
}"""

    user_prompt = f"""[분석 대상 테마]: {theme_name}

[참고 리포트 데이터]
{docs_context}
"""

    raw_response = call_ollama(user_prompt, system_prompt, model=model, json_mode=True)
    brief_data = parse_json_safely(raw_response)
    brief_data.setdefault("theme", theme_name)
    brief_data.setdefault("related_reports_count", len(matched_reports))
    
    # 근거 리포트 목록
    brief_data["source_reports"] = [{
        "id": r["id"],
        "title": r["title"],
        "company_or_sector": r["company_or_sector"],
        "broker": r["broker"],
        "report_date": r["report_date"],
        "pdf_url": r.get("pdf_url", "")
    } for r in matched_reports]
    
    set_trend_cache(cache_key, brief_data)
    return brief_data

def generate_market_intelligence(
    model: str = DEFAULT_MODEL,
    force_refresh: bool = False
) -> Dict[str, Any]:
    """시장 전체 데일리 마켓 인텔리전스 종합 브리프 생성"""
    cache_key = f"market_intelligence_{model}"
    if not force_refresh:
        cached = get_trend_cache(cache_key)
        if cached:
            return cached
            
    # 최근 리포트 8건의 요약문 및 메타데이터 수집
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, category, title, company_or_sector, broker, report_date, pdf_url, summary_text
            FROM reports
            WHERE processed = 1
            ORDER BY report_date DESC, id DESC
            LIMIT 8
        """)
        reports = [dict(row) for row in cursor.fetchall()]
        
    if not reports:
        return {
            "headline": "리포트 분석 대기 중",
            "market_summary": "수집된 리포트가 없습니다.",
            "key_drivers": [],
            "hot_sectors": [],
            "source_reports": []
        }
        
    reports_text = ""
    for r in reports:
        reports_text += f"- [{r['category'].upper()}] {r['company_or_sector']} ({r['broker']}): {r['title']}\n  요약: {r['summary_text'][:150]}\n"
        
    system_prompt = """당신은 모닝 투자 전략 브리핑을 작성하는 수석 전략가입니다.
최근 증권사 리포트 요약 데이터를 바탕으로, 오늘의 주식 시장을 관통하는 핵심 트렌드 브리프를 작성하십시오.

JSON 스키마:
{
  "headline": "오늘의 시장을 정의하는 강렬한 한 줄 헤드라인",
  "market_summary": "전반적인 증시 환경 및 애널리스트 톤앤매너 요약 (2문장)",
  "key_drivers": [
    {"driver": "핵심 테마 1", "detail": "상세 설명"},
    {"driver": "핵심 테마 2", "detail": "상세 설명"},
    {"driver": "핵심 테마 3", "detail": "상세 설명"}
  ],
  "hot_sectors": ["관심 집중 섹터 1", "섹터 2", "섹터 3"],
  "actionable_insight": "투자자를 위한 최종 액션 인사이트 (1~2문장)"
}"""

    user_prompt = f"""[최근 발간 리포트 목록]
{reports_text}
"""

    raw_response = call_ollama(user_prompt, system_prompt, model=model, json_mode=True)
    intel_data = parse_json_safely(raw_response)
    intel_data.setdefault("headline", "시장 인텔리전스 요약")
    
    # 근거가 된 원본 리포트 목록 첨부
    source_reports_list = []
    for r in reports:
        source_reports_list.append({
            "id": r["id"],
            "category": r["category"],
            "title": r["title"],
            "company_or_sector": r["company_or_sector"],
            "broker": r["broker"],
            "report_date": r["report_date"],
            "pdf_url": r["pdf_url"]
        })
    intel_data["source_reports"] = source_reports_list
    
    set_trend_cache(cache_key, intel_data)
    return intel_data
