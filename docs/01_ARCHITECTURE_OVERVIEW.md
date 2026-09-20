# 01. 전체 시스템 아키텍처 및 데이터 흐름 설계서

본 문서는 **주식/산업 리포트 트렌드 인텔리전스 시스템**의 전반적인 구조, 데이터 라이프사이클, 모듈 간 상호작용 및 데이터베이스 설계를 상세히 기술합니다.

---

## 1. 시스템 전체 아키텍처 (System Architecture)

본 시스템은 **데이터 수집(Data Ingestion) ➔ 전처리 및 NLP(Text & NLP Processing) ➔ 정량적 트렌드 분석(Trend Analytics) ➔ 생성형 AI 심층 합성(LLM Synthesis) ➔ 시각화 대시보드(Presentation)**의 5단계 파이프라인으로 구성됩니다.

```mermaid
flowchart TD
    subgraph Layer1 [1. 데이터 수집 계층 Data Collection]
        CR[한경컨센서스 리서치 크롤러]
        CR -->|HTTP GET / UTF-8 파싱| META[메타데이터 추출]
        CR -->|PDF 바이트 스트림 다운로드| PDF_STORE[data/pdfs/ 저장소]
    end

    subgraph Layer2 [2. 전처리 & 형태소 분석 계층 Processing & NLP]
        PDF_STORE -->|PyMuPDF fitz 파싱| TXT[본문 텍스트 추출]
        TXT --> REG[정규표현식 노이즈 정제]
        REG --> KIWI[Kiwi 한국어 형태소 분석 엔진]
        KIWI --> STOP[금융 노이즈 & 불용어 필터]
        STOP --> KW_DB[(단어 빈도 DB 매핑)]
    end

    subgraph Layer3 [3. 정량 트렌드 알고리즘 계층 Quantitative Analytics]
        KW_DB --> SURGE[시계열 급상승 Surge Index 산출 엔진]
        KW_DB --> TIMELINE[일자별 키워드 타임라인 집계]
        KW_DB --> SECTOR[섹터별 핵심어 클러스터링]
    end

    subgraph Layer4 [4. 생성형 AI 심층 합성 계층 Local LLM Engine]
        META & TXT --> OLLAMA[로컬 Ollama Qwen 2.5 엔진]
        OLLAMA --> BRIEF1[개별 리포트 3줄 핵심 요약]
        OLLAMA --> BRIEF2[급상승 테마 종합 브리프]
        OLLAMA --> BRIEF3[데일리 마켓 인텔리전스]
        BRIEF1 & BRIEF2 & BRIEF3 --> CACHE[(SQLite AI 캐시 테이블)]
    end

    subgraph Layer5 [5. 사용자 대시보드 계층 Presentation UI]
        SURGE & TIMELINE & SECTOR & CACHE --> API[FastAPI 비동기 REST API]
        API --> DASHBOARD[모던 다크 Glassmorphism 웹 대시보드]
    end
```

---

## 2. 데이터베이스 스키마 설계 (SQLite Database Design)

데이터 저장은 영구성, 단일 파일 배포 용이성, 고속 인덱싱 성능을 고려하여 **SQLite (`data/reports.db`)**를 사용합니다.

```mermaid
erDiagram
    REPORTS ||--o{ REPORT_KEYWORDS : "has"
    REPORTS ||--o| REPORT_AI_SUMMARIES : "summarized_as"

    REPORTS {
        INTEGER id PK "자동증가 고유식별자"
        TEXT category "리포트 분류 (company, industry, market)"
        TEXT title "리포트 원문 제목"
        TEXT company_or_sector "대상 종목명 또는 산업 섹터명"
        TEXT broker "발행 증권사"
        TEXT author "작성 애널리스트"
        TEXT report_date "발행일자 (YYYY-MM-DD)"
        TEXT pdf_url UK "원문 다운로드 고유 URL (중복 방지)"
        TEXT local_pdf_path "로컬 PDF 파일 경로"
        TEXT summary_text "본문 서두 요약문 (300자 내외)"
        TEXT full_text "PDF 전체 본문 텍스트"
        INTEGER processed "처리 상태 (0:미처리, 1:완료, -1:실패)"
        TIMESTAMP created_at "수집 일시"
    }

    REPORT_KEYWORDS {
        INTEGER id PK "자동증가 고유키"
        INTEGER report_id FK "reports.id 참조"
        TEXT keyword "추출된 명사/전문용어"
        INTEGER count "해당 리포트 내 출현 횟수"
    }

    REPORT_AI_SUMMARIES {
        INTEGER report_id PK "reports.id 참조"
        TEXT model_name "사용된 LLM 모델 (qwen2.5:7b 등)"
        TEXT summary_json "구조화된 AI 요약 JSON (투자포인트, 리스크 등)"
        TIMESTAMP created_at "요약 생성 일시"
    }

    TREND_CACHE {
        TEXT cache_key PK "캐시 식별 키 (예: market_intelligence_qwen2.5:7b)"
        TEXT data_json "직렬화된 분석 결과 JSON"
        TIMESTAMP updated_at "캐시 갱신 일시"
    }
```

---

## 3. 핵심 설계 원칙 (Design Principles)

1. **멱등성(Idempotency) 및 증분 수집(Incremental Ingestion)**
   - `reports.pdf_url`을 유니크 키로 지정하여, 크롤러를 여러 번 실행해도 이미 존재하는 리포트는 건너뛰고 새롭게 발행된 리포트만 다운로드/분석합니다.
2. **다계층 캐싱 전략 (Multi-Layer Caching)**
   - **PDF 텍스트 캐싱**: 한 번 다운로드 및 추출된 텍스트는 DB와 로컬 파일에 캐싱되어 재파싱 비용 제로화.
   - **키워드 사전 집계 캐싱**: `report_keywords` 테이블에 단어 출현 빈도를 사전에 인덱싱하여 트렌드 계산 속도를 $O(1) \sim O(\log N)$으로 단축.
   - **LLM 추론 결과 캐싱**: LLM 요약 결과를 `report_ai_summaries` 및 `trend_cache`에 영구 보관하여 중복 요청 시 0초 즉시 반환.
3. **완전 로컬/프라이빗 운영 (Zero External Dependency)**
   - 외부 유료 API나 클라우드 의존성 없이, 사용자 로컬 GPU(RTX 3060 12GB)와 Ollama를 통해 모든 AI 기능이 오프라인 상태에서도 100% 동작합니다.
