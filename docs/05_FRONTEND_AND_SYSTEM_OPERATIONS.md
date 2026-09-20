# 05. 프론트엔드 UI 시각화 및 시스템 운영 가이드

본 문서는 FastAPI 기반의 비동기 백엔드 API, Glassmorphism 다크 테마 프론트엔드 시각화 기법, 윈도우 환경 자동화 배치 및 시스템 운영 방법을 상세히 기술합니다.

---

## 1. FastAPI 백엔드 REST API 명세 (`app/main.py`)

FastAPI는 비동기 이벤트 루프(`asyncio`)와 고성능 ASGI 서버(`uvicorn`)를 통해 지연 시간(Latency) 10ms 이하의 빠른 응답성을 제공합니다.

| Method | Endpoint | 설명 | 파라미터 / 쿼리 |
| :--- | :--- | :--- | :--- |
| `GET` | `/` | 모던 웹 대시보드 HTML 반환 | - |
| `GET` | `/api/summary` | 상단 4대 핵심 KPI 및 핫 테마 조회 | - |
| `GET` | `/api/surge` | 급상승(Surge) 키워드 랭킹 목록 | `top_n` (기본 15) |
| `GET` | `/api/keywords/top` | 전체 빈출 키워드 (워드클라우드용) | `top_n` (기본 40) |
| `GET` | `/api/timeline` | 주요 테마 일자별 출현 빈도 시계열 | `keywords`, `top_n` |
| `GET` | `/api/sectors` | 섹터별 리포트 발행량 및 대표 키워드 | `top_n` (기본 8) |
| `GET` | `/api/reports` | 리포트 목록 검색 및 필터링 | `category`, `keyword`, `limit` |
| `GET` | `/api/llm/models` | 로컬 설치된 Ollama 모델 목록 | - |
| `GET` | `/api/reports/{id}/ai-summary` | 개별 리포트 3줄 AI 심층 요약 | `model`, `refresh` |
| `GET` | `/api/themes/{name}/ai-brief` | 급상승 테마 다중 리포트 종합 브리프 | `model`, `refresh` |
| `GET` | `/api/market/ai-brief` | 데일리 마켓 인텔리전스 AI 브리프 | `model`, `refresh` |
| `POST` | `/api/pipeline/run` | 백그라운드 크롤링 및 분석 트리거 | `pages`, `max_pdfs` |
| `GET` | `/api/pipeline/status` | 백그라운드 파이프라인 진행 상태 | - |

---

## 2. 프론트엔드 UI & 시각화 기술 스택 (`app/static/`)

### 2.1 Glassmorphism 다크 테마 디자인 시스템
- **배경 및 서체**: 딥 슬레이트 블랙(`--bg-primary: #0b0f19`) + Google Fonts **`Outfit`** & **`Inter`**
- **글래스모피즘 효과**: `background: rgba(17, 24, 39, 0.75); backdrop-filter: blur(16px);`를 적용하여 입체감 있는 반투명 카드 렌더링.
- **네온 엑센트 그라데이션**: 
  - Blue-Cyan (`#3b82f6` $\to$ `#06b6d4`)
  - AI Purple-Pink (`#6366f1` $\to$ `#a855f7` $\to$ `#ec4899`)

### 2.2 인터랙티브 차트 (Chart.js)
- 일자별 테마 언급 추이를 멀티 라인 차트로 렌더링.
- 부드러운 베지어 곡선(`tension: 0.35`)과 투명 채우기(`fill: true`) 적용.

### 2.3 캔버스 워드클라우드 (WordCloud2.js)
- 상위 50개 키워드를 빈도 비례 크기로 반응형 HTML5 `<canvas>`에 렌더링.
- **클릭 이벤트 연동**: 워드클라우드의 특정 단어를 클릭하면 해당 단어의 **AI 테마 종합 브리프 모달 팝업**이 즉시 호출되도록 바인딩.

### 2.4 실시간 디바운스 검색 (Debounce Search)
- 리포트 제목/종목 검색창에 300ms 디바운스 타이머를 적용하여 불필요한 과도한 API 호출을 방지하고 부드러운 실시간 검색 경험 제공.

---

## 3. 윈도우 환경 원클릭 실행 및 바로가기 구조

### 3.1 원클릭 배치 파일 (`run_dashboard.bat`)
```bat
@echo off
chcp 65001 > nul
cd /d "c:\project\angravity\report_trand"
start "" "http://localhost:8000"
python main.py --server-only --port 8000
pause
```
1. 한글 깨짐 방지를 위해 콘솔 인코딩을 `UTF-8 (65001)`로 자동 전환.
2. 기본 웹 브라우저를 열어 `http://localhost:8000` 대시보드에 즉시 접속.
3. 백그라운드 FastAPI 서버를 포트 8000으로 실행.

### 3.2 바탕화면 바로가기 (`리포트 트렌드 인텔리전스.lnk`)
- `WScript.Shell`을 통해 사용자의 실제 바탕화면(`OneDrive\Desktop` 또는 `Desktop`)에 자동 배포됨.

---

## 4. 일상 운영 및 유지보수

1. **최신 리포트 증분 업데이트**:
   - 웹 대시보드 우측 상단의 **`[⚡ 최신 리포트 수집 & 분석]`** 버튼을 누르면 서버가 백그라운드에서 신규 리포트만 다운로드하여 파싱 및 분석을 자동 갱신합니다.
2. **CLI를 통한 대량 과거 데이터 일괄 수집**:
   ```bash
   # 각 카테고리당 5페이지(총 300건), 최대 100건 PDF 텍스트 파싱
   python main.py --crawl-only --pages 5 --max-pdfs 100
   ```
3. **AI 모델 변경**:
   - 대시보드 상단 셀렉트박스에서 **`qwen2.5:7b` (1~2초 고속)** ↔ **`qwen2.5:14b` (심층 분석)** 간 자유롭게 변경 가능.
