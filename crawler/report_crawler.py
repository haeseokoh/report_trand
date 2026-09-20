import requests
from bs4 import BeautifulSoup
import re
import urllib.parse
from typing import List, Dict, Any
import time
from db.database import save_report

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://consensus.hankyung.com/"
}

BASE_URL = "https://consensus.hankyung.com/analysis/list"

# 한경 컨센서스 카테고리 매핑
CATEGORY_SKINS = {
    "company": "business",   # 기업 분석 리포트
    "industry": "industry",  # 산업 분석 리포트
    "market": "market",      # 시장/시황 분석 리포트
}

def clean_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()

def extract_company_name_and_title(raw_title: str) -> tuple[str, str]:
    """제목에서 종목명/코드 분리 (예: '삼성전자(005930) 실적 개선 전망' -> ('삼성전자', '실적 개선 전망'))"""
    match = re.match(r'^([^(]+(?:\([0-9A-Za-z]+\))?)\s*(.*)$', raw_title)
    if match:
        target = match.group(1).strip()
        title = match.group(2).strip()
        
        # HTML 텍스트 중복 반복 현상 정제 (예: 제목이 2~3번 연속 붙어있는 경우)
        if len(title) > 20:
            half = len(title) // 2
            if title[:half] == title[half:]:
                title = title[:half]
        return target, title if title else raw_title
    return "", raw_title

def crawl_hk_research_page(category: str, page: int = 1) -> List[Dict[str, Any]]:
    """한경 컨센서스 특정 카테고리/페이지 크롤링"""
    skin_type = CATEGORY_SKINS.get(category, "business")
    url = f"{BASE_URL}?skinType={skin_type}&page={page}"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=12)
        response.encoding = "utf-8"
        
        if response.status_code != 200:
            print(f"Failed to fetch {url}, status: {response.status_code}")
            return []
            
        soup = BeautifulSoup(response.text, "lxml")
        table = soup.find("table")
        if not table:
            return []
            
        rows = table.find_all("tr")[1:] # 헤더 제외
        reports = []
        
        for tr in rows:
            tds = tr.find_all("td")
            if len(tds) < 5:
                continue
                
            report_date = clean_text(tds[0].text)
            raw_title = clean_text(tds[1].text)
            
            # PDF 링크 추출
            pdf_href = ""
            for a in tr.find_all("a"):
                href = a.get("href", "")
                if "downpdf" in href or ".pdf" in href:
                    pdf_href = href
                    break
                    
            if not pdf_href:
                continue
                
            if not pdf_href.startswith("http"):
                pdf_href = urllib.parse.urljoin("https://consensus.hankyung.com", pdf_href)
                
            company_or_sector = ""
            title = raw_title
            broker = ""
            author = ""
            
            if category == "company":
                company_or_sector, title = extract_company_name_and_title(raw_title)
                author = clean_text(tds[4].text) if len(tds) > 4 else ""
                broker = clean_text(tds[5].text) if len(tds) > 5 else ""
            elif category == "industry":
                # 산업 리포트: 제목 서두의 [산업분류] 추출
                sector_match = re.match(r'^\[([^\]]+)\]\s*(.*)$', raw_title)
                if sector_match:
                    company_or_sector = sector_match.group(1).strip()
                    title = sector_match.group(2).strip()
                else:
                    company_or_sector = "산업전반"
                author = clean_text(tds[3].text) if len(tds) > 3 else ""
                broker = clean_text(tds[4].text) if len(tds) > 4 else ""
            elif category == "market":
                company_or_sector = "시황/투자전략"
                author = clean_text(tds[2].text) if len(tds) > 2 else ""
                broker = clean_text(tds[3].text) if len(tds) > 3 else ""
                
            reports.append({
                "category": category,
                "title": title,
                "company_or_sector": company_or_sector,
                "broker": broker,
                "author": author,
                "report_date": report_date,
                "pdf_url": pdf_href
            })
            
        return reports
        
    except Exception as e:
        print(f"Error crawling {category} page {page}: {e}")
        return []

def crawl_recent_reports(max_pages_per_category: int = 2) -> Dict[str, int]:
    """최근 리포트 일괄 수집 및 DB 저장"""
    stats = {"company": 0, "industry": 0, "market": 0, "total_saved": 0}
    
    for category in CATEGORY_SKINS.keys():
        print(f"Crawling {category} reports (pages 1 to {max_pages_per_category})...")
        for page in range(1, max_pages_per_category + 1):
            reports = crawl_hk_research_page(category, page)
            for r in reports:
                row_id = save_report(r)
                if row_id:
                    stats[category] += 1
                    stats["total_saved"] += 1
            time.sleep(0.3)
            
    print(f"Crawling completed: {stats}")
    return stats
