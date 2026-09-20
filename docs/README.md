# 📚 주식/산업 리포트 트렌드 인텔리전스 기술 문서 모음

본 디렉터리(`docs/`)는 **주식/산업 리포트 트렌드 인텔리전스 시스템**의 모든 기술적 접근 방법, 알고리즘 수식, LLM 프롬프트 엔지니어링, 데이터베이스 설계 및 운영 가이드를 주제별로 정리한 상세 기술 문서 세트입니다.

---

## 📑 문서 목차 및 색인

| 문서 번호 | 문서 제목 | 주요 내용 요약 | 바로가기 |
| :---: | :--- | :--- | :---: |
| **01** | **전체 시스템 아키텍처 및 데이터 흐름** | 5단계 파이프라인 아키텍처, ERD 스키마 설계, 다계층 캐싱 및 멱등성 원칙 | [01_ARCHITECTURE_OVERVIEW.md](./01_ARCHITECTURE_OVERVIEW.md) |
| **02** | **리포트 크롤링 및 PDF 텍스트 파싱** | 한경컨센서스 크롤링 전략, 비정형 제목 문자열 정제 알고리즘, PyMuPDF 고속 텍스트 추출 | [02_CRAWLING_AND_PDF_PARSING.md](./02_CRAWLING_AND_PDF_PARSING.md) |
| **03** | **한국어 형태소 분석 및 트렌드/급상승 알고리즘** | Kiwi 형태소 분석기, 금융 불용어/사용자 사전, **급상승 지수(Surge Index)** 수학적 수식 및 원리 | [03_NLP_AND_TREND_ALGORITHMS.md](./03_NLP_AND_TREND_ALGORITHMS.md) |
| **04** | **로컬 LLM 심층 합성 및 프롬프트 엔지니어링** | Ollama Qwen 2.5 (7B/14B) 연동, 3대 구조화 JSON 프롬프트 설계, 출처 리포트 메타데이터 추적 | [04_LLM_SYNTHESIS_AND_PROMPT_ENGINEERING.md](./04_LLM_SYNTHESIS_AND_PROMPT_ENGINEERING.md) |
| **05** | **프론트엔드 UI 시각화 및 시스템 운영 가이드** | FastAPI REST API 명세, Glassmorphism 디자인 시스템, 인터랙티브 차트/워드클라우드, 윈도우 바로가기 자동화 | [05_FRONTEND_AND_SYSTEM_OPERATIONS.md](./05_FRONTEND_AND_SYSTEM_OPERATIONS.md) |

---

## 🎯 핵심 기술 요약

1. **데이터 수집**: 중복 없는 증분(Incremental) 크롤링 및 `PyMuPDF` C++ 네이티브 고속 텍스트 파싱
2. **정량 트렌드**: $\text{Surge Score} = \frac{C_{\text{recent}} + 1}{C_{\text{past}} + 1} \times \log_2(C_{\text{recent}} + 2)$ 공식을 통한 핫 테마 자동 포착
3. **생성형 AI**: RTX 3060 12GB VRAM 100% 활용 로컬 Ollama Qwen 2.5를 통한 30초 내 초고속 투자 인텔리전스 합성
4. **시각화**: FastAPI 비동기 백엔드 + Chart.js / WordCloud2.js + 반응형 다크 테마 대시보드
