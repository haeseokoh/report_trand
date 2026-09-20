# 04. 로컬 LLM 심층 합성 및 프롬프트 엔지니어링 기술서

본 문서는 로컬 GPU(RTX 3060 12GB) 및 Ollama 기반의 **Qwen 2.5 (7B / 14B)** 모델을 활용하여 증권사 리포트 본문을 구조화된 투자 인텔리전스로 합성하는 메커니즘과 프롬프트 엔지니어링을 상세히 기술합니다.

---

## 1. LLM 연동 아키텍처 (`processor/llm_summarizer.py`)

### 1.1 로컬 Ollama API 통신
- **엔드포인트**: `POST http://localhost:11434/api/generate`
- **구조화된 출력 모드**: `"format": "json"` 옵션을 활성화하여 모델이 100% 파싱 가능한 JSON 문자열을 생성하도록 강제.
- **하이퍼파라미터 최적화**:
  - `temperature`: `0.2` (할루시네이션을 최소화하고 리포트 사실 기반의 일관된 요약 보장)
  - `top_p`: `0.9`
  - `num_ctx`: `8192` (긴 리포트 본문과 다중 리포트 동시 입력을 위한 넉넉한 컨텍스트 윈도우 확보)

### 1.2 모델별 특성 및 스위칭
1. **`qwen2.5:7b` (기본 추천)**:
   - VRAM 점유 약 5.0GB
   - 추론 속도: 초당 약 40~50 토큰 (요약 생성 1~2초 완료)
2. **`qwen2.5:14b` (심층 분석용)**:
   - VRAM 점유 약 9.5GB
   - 다중 리포트 간의 미묘한 의견 차이 및 심층 컨센서스 도출에 최적화

---

## 2. 3대 프롬프트 엔지니어링 설계 (Prompt Engineering)

### 2.1 [기능 1] 개별 리포트 3줄 핵심 요약 (`summarize_single_report`)
- **목적**: 애널리스트가 작성한 10~30페이지 분량의 본문에서 30초 내에 파악 가능한 3대 핵심 투자 포인트와 리스크 추출.
- **시스템 프롬프트 (System Prompt)**:
  ```
  당신은 증권사 및 자산운용사의 수석 퀀트/애널리스트입니다. 
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
  }
  ```

---

### 2.2 [기능 2] 급상승 테마 다중 리포트 종합 브리프 (`generate_theme_brief`)
- **목적**: 특정 테마(예: `삼성전기`, `자동`, `장비`)를 다룬 **서로 다른 4개 증권사 리포트 본문을 교차 비교(Cross-Analysis)**하여 증권가 공통 시각과 수혜주 도출.
- **입력 데이터 구조화**:
  ```
  [리포트 1] (2026-09-18 | 메리츠증권 | 두산)
  제목: 화룡점정
  발췌: ...
  ---
  [리포트 2] (2026-09-18 | 한국IR협의회 | 링크제니시스)
  제목: 반도체 업황 개선 수혜...
  발췌: ...
  ```
- **출력 스키마**: `market_driver`, `consensus`, `top_beneficiaries`, `catalysts`, `risk_points`

---

### 2.3 [기능 3] 데일리 마켓 인텔리전스 (`generate_market_intelligence`)
- **목적**: 오늘 발간된 시황/기업/산업 리포트 전체를 조망하여 **오늘의 시장 핵심 드라이버 3가지**와 집중 관심 섹터 합성.
- **출력 스키마**:
  - `headline`: 시장을 관통하는 한 줄 헤드라인
  - `market_summary`: 거시적 증시 환경 요약
  - `key_drivers`: `[{"driver": "...", "detail": "..."}, ...]`
  - `hot_sectors`: `["섹터1", "섹터2", ...]`
  - `actionable_insight`: 투자자를 위한 실행 조언

---

## 3. 원본 근거 데이터(`source_reports`) 추적 및 투명성 보장

AI 요약의 신뢰성을 확보하기 위해, LLM 합성 시 참조된 실제 리포트들의 메타데이터를 결과 객체에 자동으로 첨부합니다:

```python
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
```

---

## 4. 캐싱 및 영구 보존 전략

- **단일 리포트 요약**: `report_ai_summaries` 테이블에 `(report_id, model_name)` 복합키로 영구 보관.
- **테마 및 마켓 브리프**: `trend_cache` 테이블에 `(cache_key)` 형태로 직렬화 저장.
- **온디맨드 강제 갱신**: 사용자가 대시보드에서 `[🔄 다시 생성]`을 누르면 `refresh=true` 파라미터가 전달되어 기존 캐시를 무효화하고 최신 관점으로 재합성.
