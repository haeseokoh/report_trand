import os
import requests
import re
from typing import Optional, Tuple
import pymupdf as fitz
from db.database import PDF_DIR, update_report_text, get_unprocessed_reports

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def clean_pdf_text(text: str) -> str:
    """PDF에서 추출한 텍스트 클리닝 (불필요한 공백, 특수문자, 페이지 번호 제거)"""
    if not text:
        return ""
    
    # 이메일, 웹사이트 URL 제거
    text = re.sub(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', ' ', text)
    text = re.sub(r'https?://\S+|www\.\S+', ' ', text)
    
    # 연속된 줄바꿈 및 공백 정리
    text = re.sub(r'\n+', '\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    
    # 페이지 번호 단독 라인 제거 (예: - 1 -, [2])
    text = re.sub(r'\n\s*[-–—\[(]?\s*\d+\s*[-–—\])]?\s*\n', '\n', text)
    
    return text.strip()

def download_pdf(pdf_url: str, report_id: int) -> Optional[str]:
    """PDF 파일 다운로드 및 로컬 저장"""
    try:
        filename = f"report_{report_id}.pdf"
        filepath = os.path.join(PDF_DIR, filename)
        
        # 이미 다운로드되어 있으면 캐시 사용
        if os.path.exists(filepath) and os.path.getsize(filepath) > 1024:
            return filepath
            
        resp = requests.get(pdf_url, headers=HEADERS, timeout=20)
        if resp.status_code == 200 and len(resp.content) > 1024:
            with open(filepath, "wb") as f:
                f.write(resp.content)
            return filepath
        else:
            print(f"Failed to download PDF ({resp.status_code}): {pdf_url}")
            return None
    except Exception as e:
        print(f"Error downloading PDF {pdf_url}: {e}")
        return None

def extract_text_from_pdf(filepath: str, max_pages: int = 30) -> str:
    """PyMuPDF를 사용한 고속 PDF 텍스트 추출 (최대 30페이지)"""
    text_content = []
    try:
        with fitz.open(filepath) as doc:
            for page_num in range(min(len(doc), max_pages)):
                page = doc[page_num]
                page_text = page.get_text()
                if page_text:
                    text_content.append(page_text)
                    
        full_text = "\n".join(text_content)
        return clean_pdf_text(full_text)
    except Exception as e:
        print(f"Error extracting text from {filepath}: {e}")
        return ""

def process_single_report(report: dict) -> bool:
    """단일 리포트 다운로드 및 텍스트 추출 파이프라인"""
    report_id = report["id"]
    pdf_url = report["pdf_url"]
    
    local_path = download_pdf(pdf_url, report_id)
    if not local_path:
        # 다운로드 실패 시 처리 완료 표시(processed=-1)
        update_report_text(report_id, "", "", "")
        return False
        
    extracted_text = extract_text_from_pdf(local_path)
    if not extracted_text:
        update_report_text(report_id, local_path, "", "")
        return False
        
    # 요약문 생성 (본문 서두 약 200~300자)
    summary_lines = [line.strip() for line in extracted_text.split('\n') if len(line.strip()) > 20]
    summary_text = " ".join(summary_lines[:4])[:300]
    if len(summary_text) >= 300:
        summary_text += "..."
        
    update_report_text(report_id, local_path, extracted_text, summary_text)
    return True

def process_pending_reports(batch_size: int = 30) -> int:
    """미처리 리포트 일괄 PDF 다운로드 및 텍스트 파싱"""
    unprocessed = get_unprocessed_reports(limit=batch_size)
    if not unprocessed:
        print("No pending reports to process.")
        return 0
        
    print(f"Processing {len(unprocessed)} pending reports...")
    success_count = 0
    for report in unprocessed:
        if process_single_report(report):
            success_count += 1
            
    print(f"Successfully processed {success_count}/{len(unprocessed)} reports.")
    return success_count
