# 02. 리포트 크롤링 및 PDF 텍스트 파싱 기술서

본 문서는 한경 컨센서스(Hankyung Consensus)로부터 증권사 리포트 메타데이터를 수집하고, 첨부 PDF 파일을 다운로드하여 텍스트를 고속 추출·정제하는 기술적 구현 방식을 상세히 기술합니다.

---

## 1. 크롤링 전략 및 메타데이터 파싱 (`crawler/report_crawler.py`)

### 1.1 타겟 소스 및 URL 엔드포인트
- **베이스 URL**: `https://consensus.hankyung.com/analysis/list`
- **카테고리별 매핑**:
  - `company` (기업 분석): `?skinType=business&page={N}`
  - `industry` (산업 분석): `?skinType=industry&page={N}`
  - `market` (시장/시황 분석): `?skinType=market&page={N}`

### 1.2 안티 블로킹 및 HTTP 헤더 최적화
한경 컨센서스는 User-Agent가 누락되거나 부적절할 경우 빈 응답(18 bytes)을 반환하므로, 브라우저 표준 헤더를 구성하여 요청합니다.

```python
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://consensus.hankyung.com/"
}
```

### 1.3 비정형 제목 문자열 정제 알고리즘
HTML 파싱 시 종목명과 제목이 결합되어 있거나 동일 문자열이 반복되는 현상을 다음 정규식 및 슬라이싱 알고리즘으로 해결합니다:

```python
def extract_company_name_and_title(raw_title: str) -> tuple[str, str]:
    # 예: '삼성전자(005930) 실적 개선 전망' -> ('삼성전자(005930)', '실적 개선 전망')
    match = re.match(r'^([^(]+(?:\([0-9A-Za-z]+\))?)\s*(.*)$', raw_title)
    if match:
        target = match.group(1).strip()
        title = match.group(2).strip()
        
        # HTML 텍스트 중복 반복 현상 정제 (예: "A문장A문장" 형태로 붙어있는 경우)
        if len(title) > 20:
            half = len(title) // 2
            if title[:half] == title[half:]:
                title = title[:half]
        return target, title if title else raw_title
    return "", raw_title
```

---

## 2. PDF 다운로드 및 무결성 검증 (`processor/pdf_parser.py`)

### 2.1 PDF 다운로드 파이프라인
1. **로컬 캐시 확인**: 이미 다운로드된 `report_{id}.pdf` 파일이 존재하고 크기가 1KB 초과인 경우 네트워크 요청 생략.
2. **스트림 다운로드**: 타임아웃(20초) 설정 및 응답 바이트 크기 검증 (오류 페이지 다운로드 방지).
3. **저장 경로**: `data/pdfs/report_{id}.pdf`

---

## 3. PyMuPDF 기반 고속 텍스트 추출 및 정제

### 3.1 PyMuPDF (`fitz`)를 선택한 이유
- `PyPDF2`/`pypdf` 대비 C++ 네이티브 바인딩을 통해 **약 5~10배 빠른 텍스트 렌더링 속도** 제공.
- 한국어 CID/폰트 인코딩 매핑 정확도가 높아 금융 표(Table) 및 다단 레이아웃 본문에서도 깨짐 없이 텍스트 추출 가능.

### 3.2 텍스트 정제 정규식 파이프라인
PDF에서 추출된 원시 문자열은 페이지 번호, 이메일 주소, 연속 줄바꿈 등 노이즈가 많으므로 순차 정제합니다:

```python
def clean_pdf_text(text: str) -> str:
    if not text:
        return ""
    
    # 1. 애널리스트 이메일 주소 제거
    text = re.sub(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', ' ', text)
    
    # 2. 웹사이트 URL 링크 제거
    text = re.sub(r'https?://\S+|www\.\S+', ' ', text)
    
    # 3. 연속 줄바꿈 및 다중 공백 정규화
    text = re.sub(r'\n+', '\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    
    # 4. 페이지 번호 단독 라인 제거 (예: - 1 -, [2])
    text = re.sub(r'\n\s*[-–—\[(]?\s*\d+\s*[-–—\])]?\s*\n', '\n', text)
    
    return text.strip()
```

### 3.3 본문 요약문(Snippet) 추출
전체 본문 중 유의미한 길이(20자 이상)를 가진 첫 4개 문장을 결합하여 **상위 300자의 요약문(Snippet)**을 생성하고 DB `reports.summary_text` 컬럼에 인덱싱합니다.
