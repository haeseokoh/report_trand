import requests
from bs4 import BeautifulSoup
import re
from typing import List, Dict, Any
import time
import urllib.parse
from db.database import save_report

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

BASE_URL = "https://finance.naver.com/research/"

CATEGORY_URLS = {
    "company": "company_list.naver",     # 기업 분석 리포트
    "industry": "industry_list.naver",   # 산업 분석 리포트
    "market": "market_info_list.naver",  # 시황 정보 리포트
}

def clean_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()

def crawl_naver_research_page(category: str, page: int = 1) -> List[Dict[str, Any]]:
    """네이버 증권 리서치 특정 카테고리/페이지 크롤링"""
    if category not in CATEGORY_URLS:
        raise ValueError(f"Unknown category: {category}")
        
    url = f"{BASE_URL}{CATEGORY_URLS[category]}?page={page}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.encoding = "euc-kr" # 네이버 증권 인코딩
        
        if response.status_code != 200:
            print(f"Failed to fetch {url}, status code: {response.status_code}")
            return []
            
        soup = BeautifulSoup(response.text, "lxml")
        table = soup.find("table", class_="type_1")
        if not table:
            return []
            
        rows = table.find_all("tr")
        reports = []
        
        for tr in rows:
            tds = tr.find_all("td")
            if len(tds) < 5:
                continue
                
            # 카테고리별 컬럼 위치 차이 처리
            # company: [0: 종목명, 1: 리포트제목, 2: 증권사, 3: 첨부파일(PDF), 4: 작성일, 5: 조회수]
            # industry/market: [0: 분류/제목, 1: 리포트제목, 2: 증권사, 3: 첨부파일, 4: 작성일, 5: 조회수]
            
            company_or_sector = ""
            title = ""
            broker = ""
            pdf_url = ""
            report_date = ""
            author = ""
            
            if category == "company":
                # 종목명
                company_tag = tds[0].find("a")
                company_or_sector = clean_text(company_tag.text) if company_tag else clean_text(tds[0].text)
                
                # 제목
                title_tag = tds[1].find("a")
                title = clean_text(title_tag.text) if title_tag else clean_text(tds[1].text)
                
                # 증권사
                broker = clean_text(tds[2].text)
                
                # PDF 링크
                pdf_tag = tds[3].find("a")
                if pdf_tag and pdf_tag.get("href"):
                    pdf_url = pdf_tag.get("href")
                    
                # 작성일
                report_date = clean_text(tds[4].text)
                
            elif category == "industry":
                # 산업 분류
                sector_tag = tds[0].find("a")
                company_or_sector = clean_text(sector_tag.text) if sector_tag else clean_text(tds[0].text)
                
                # 제목
                title_tag = tds[1].find("a")
                title = clean_text(title_tag.text) if title_tag else clean_text(tds[1].text)
                
                # 증권사
                broker = clean_text(tds[2].text)
                
                # PDF 링크
                pdf_tag = tds[3].find("a")
                if pdf_tag and pdf_tag.get("href"):
                    pdf_url = pdf_tag.get("href")
                    
                # 작성일
                report_date = clean_text(tds[4].text)
                
            elif category == "market":
                # 제목
                title_tag = tds[0].find("a")
                title = clean_text(title_tag.text) if title_tag else clean_text(tds[0].text)
                company_or_sector = "시황/투자전략"
                
                # 증권사
                broker = clean_text(tds[1].text)
                
                # PDF 링크
                pdf_tag = tds[2].find("a")
                if pdf_tag and pdf_tag.get("href"):
                    pdf_url = pdf_tag.get("href")
                    
                # 작성일
                report_date = clean_text(tds[3].text)
            
            # 날짜 정규화: YY.MM.DD -> 20YY-MM-DD
            if report_date:
                parts = report_date.split(".")
                if len(parts) == 3:
                    year = parts[0]
                    if len(year) == 2:
                        year = "20" + year
                    report_date = f"{year}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
            
            # PDF 링크가 있는 유효한 리포트만 수집
            if pdf_url and title:
                # PDF url 절대경로 보정
                if not pdf_url.startswith("http"):
                    pdf_url = urllib.parse.urljoin("https://ssl.pstatic.net/imgstock/upload/research/", pdf_url)
                    
                report_item = {
                    "category": category,
                    "title": title,
                    "company_or_sector": company_or_sector,
                    "broker": broker,
                    "author": author,
                    "report_date": report_date,
                    "pdf_url": pdf_url
                }
                reports.append(report_item)
                
        return reports
        
    except Exception as e:
        print(f"Error crawling {category} page {page}: {e}")
        return []

def crawl_recent_reports(max_pages_per_category: int = 3) -> Dict[str, int]:
    """최근 리포트 일괄 수집 및 DB 저장"""
    stats = {"company": 0, "industry": 0, "market": 0, "total_saved": 0}
    
    for category in CATEGORY_URLS.keys():
        print(f"Crawling {category} reports (pages 1 to {max_pages_per_category})...")
        for page in range(1, max_pages_per_category + 1):
            reports = crawl_naver_research_page(category, page)
            for r in reports:
                row_id = save_report(r)
                if row_id:
                    stats[category] += 1
                    stats["total_saved"] += 1
            time.sleep(0.3) # 서버 부하 방지 딜레이
            
    print(f"Crawling completed: {stats}")
    return stats
