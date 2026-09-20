# 📈 주식/산업 리포트 트렌드 인텔리전스 (Report Trend Intelligence)

증권사 및 산업 리포트를 크롤링하여 PDF 본문을 파싱하고, 한국어 형태소 분석(`Kiwi`)과 시계열 급상승 알고리즘을 통해 **시장의 핵심 키워드, 섹터별 관심도, 신규 급상승 테마**를 실시간으로 발굴하고 시각화하는 인텔리전스 플랫폼입니다.

---

## 🚀 주요 기능

- 📡 **자동 리포트 수집**: 기업, 산업, 시황 분석 리포트 메타데이터 및 PDF 다운로드
- 📄 **고속 PDF 텍스트 파싱**: `PyMuPDF`를 활용한 텍스트 추출 및 본문 요약문 생성
- 🧠 **한국어 NLP 형태소 분석**: `Kiwi` 기반 전문 금융 용어/명사 추출 및 불용어 필터링
- 🚀 **급상승(Surge) 테마 발굴**: 전주/이전 기간 대비 언급 빈도가 급증한 테마 TOP 랭킹 산출
- 📊 **인터랙티브 웹 대시보드**:
  - 실시간 급상승 키워드 랭킹
  - 핵심 키워드 인터랙티브 워드클라우드
  - 일자별 테마 언급 추이 타임라인 차트
  - 섹터별 관심도 및 대표 키워드 매핑
  - 리포트 원문 탐색기 및 PDF 바로보기
  - 원클릭 최신 리포트 수집 트리거 버튼

---

## 📂 프로젝트 구조

```
report_trand/
├── crawler/
│   └── report_crawler.py      # 리포트 메타데이터 및 PDF 링크 크롤러
├── processor/
│   ├── pdf_parser.py          # PDF 다운로드 및 텍스트 추출
│   └── nlp_engine.py          # Kiwi 형태소 분석 및 금융 불용어 처리
├── analyzer/
│   └── trend_analyzer.py      # TF-IDF, 급상승 지수, 시계열 타임라인 분석 엔진
├── db/
│   └── database.py            # SQLite 데이터베이스 관리 (리포트, 키워드, 캐시)
├── app/
│   ├── main.py                # FastAPI 백엔드 REST API
│   └── static/
│       ├── index.html         # Glassmorphism 모던 웹 대시보드
│       ├── css/style.css      # 다크 테마 스타일링
│       └── js/dashboard.js    # 차트/워드클라우드 및 인터랙션 로직
├── pipeline.py                # 전체 수집 -> 분석 일괄 파이프라인
├── main.py                    # 실행 엔트리포인트 (CLI / 서버 구동)
├── requirements.txt           # 의존성 패키지 목록
└── IMPLEMENTATION_PLAN.md     # 상세 구현 계획서
```

---

## 🛠️ 설치 및 실행 방법

### 1. 패키지 설치
```bash
pip install -r requirements.txt
```

### 2. 대시보드 서버 실행
```bash
python main.py --server-only --port 8000
```
브라우저에서 `http://localhost:8000` 접속

### 3. CLI를 통한 수집/분석 일괄 실행
```bash
python main.py --crawl-only --pages 3 --max-pdfs 50
```
