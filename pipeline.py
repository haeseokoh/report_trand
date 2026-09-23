import os
import sys
import time

# Windows 콘솔 인코딩 대응
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass
from db.database import (
    init_db,
    get_unprocessed_reports,
    get_processed_reports_for_analysis
)
from crawler.report_crawler import crawl_recent_reports
from processor.pdf_parser import download_pdf, extract_text_from_pdf
from processor.nlp_engine import update_keywords_for_report
from analyzer.trend_analyzer import (
    get_summary_insights,
    get_surge_keywords,
    get_overall_keyword_trends
)
from db.database import update_report_text

def run_pipeline(crawl_pages: int = 2, max_process_pdf: int = 40):
    """전체 데이터 수집 -> PDF 파싱 -> 키워드 분석 파이프라인 실행"""
    print("=" * 60)
    print("🚀 [Step 1] 데이터베이스 초기화")
    print("=" * 60)
    init_db()
    
    print("\n" + "=" * 60)
    print(f"📡 [Step 2] 증권사 리포트 메타데이터 수집 (카테고리당 {crawl_pages}페이지)")
    print("=" * 60)
    crawl_stats = crawl_recent_reports(max_pages_per_category=crawl_pages)
    print(f"✅ 수집 완료: 기업 {crawl_stats['company']}건, 산업 {crawl_stats['industry']}건, 시황 {crawl_stats['market']}건")
    
    print("\n" + "=" * 60)
    print("📄 [Step 3] PDF 다운로드, 텍스트 추출 및 형태소 키워드 분석")
    print("=" * 60)
    pending_reports = get_unprocessed_reports(limit=max_process_pdf)
    print(f"⏳ 분석 대상 리포트: {len(pending_reports)}건")
    
    success_count = 0
    for idx, report in enumerate(pending_reports, 1):
        report_id = report["id"]
        title = report["title"]
        pdf_url = report["pdf_url"]
        
        print(f"[{idx}/{len(pending_reports)}] 처리 중: [{report['category']}] {title[:35]}...")
        
        # 1. PDF 다운로드
        pdf_path = download_pdf(pdf_url, report_id)
        if not pdf_path:
            update_report_text(report_id, "", "", "")
            continue
            
        # 2. 텍스트 추출
        full_text = extract_text_from_pdf(pdf_path)
        if not full_text or len(full_text) < 50:
            update_report_text(report_id, pdf_path, "", "")
            continue
            
        # 3. 요약문 추출
        summary_lines = [line.strip() for line in full_text.split('\n') if len(line.strip()) > 20]
        summary_text = " ".join(summary_lines[:4])[:300]
        if len(summary_text) >= 300:
            summary_text += "..."
            
        update_report_text(report_id, pdf_path, full_text, summary_text)
        
        # 4. Kiwi 형태소 분석 및 키워드 추출/저장
        update_keywords_for_report(report_id, full_text)
        success_count += 1
        
    print(f"\n✅ 텍스트 & 키워드 분석 완료: {success_count}/{len(pending_reports)}건 성공")
    
    try:
        from processor.llm_summarizer import DEFAULT_MODEL, summarize_single_report, get_available_models
        from db.database import get_report_ai_summary
        
        models = get_available_models()
        chosen_model = DEFAULT_MODEL if DEFAULT_MODEL in models else (models[0] if models else DEFAULT_MODEL)
        
        print("\n" + "=" * 60)
        print(f"🤖 [Step 3.5] Ollama ({chosen_model}) AI 심층 3단 요약 사전 생성")
        print("=" * 60)
        
        ai_target_count = 0
        for report in pending_reports[:10]:
            r_id = report["id"]
            if not get_report_ai_summary(r_id):
                try:
                    print(f"  ⚡ AI 요약 진행 중: [{report.get('category', '기업')}] {report.get('title', '')[:30]}...")
                    summarize_single_report(r_id, model=chosen_model)
                    ai_target_count += 1
                except Exception as ex:
                    print(f"  ⚠️ AI 요약 건너뜀 (ID {r_id}): {ex}")
                    break
        print(f"✅ AI 심층 요약 완료: {ai_target_count}건 생성 (대시보드 클릭 시 0초 즉시 표시, 미생성 리포트는 클릭 시 온디맨드 생성)")
    except Exception as e:
        print(f"ℹ️ Ollama 서비스 상태 확인 ({e}) - 대시보드 온디맨드 요약 모드로 동작합니다.")

    print("\n" + "=" * 60)
    print("📊 [Step 4] 트렌드 분석 요약 결과")
    print("=" * 60)
    summary = get_summary_insights()
    print(f"• 총 수집 리포트: {summary['total_reports']}건")
    print(f"• 분석 완료 리포트: {summary['processed_reports']}건")
    print(f"• 대상 종목/섹터 수: {summary['total_sectors']}개")
    print(f"• 참여 증권사 수: {summary['total_brokers']}개")
    
    surge = get_surge_keywords(top_n=5)
    print("\n🔥 [급상승 키워드 TOP 5]")
    for item in surge:
        print(f"  - {item['keyword']}: 최근 {item['recent_count']}회 (성장배수 {item['growth_ratio']}x, 급상승점수 {item['surge_score']})")
        
    top_overall = get_overall_keyword_trends(top_n=10)
    print("\n🏆 [전체 빈출 키워드 TOP 10]")
    for item in top_overall:
        print(f"  - {item['text']}: 총 {item['value']}회 출현 ({item['doc_count']}개 리포트)")
        
    print("\n🎉 파이프라인 실행이 성공적으로 완료되었습니다!")

if __name__ == "__main__":
    run_pipeline()
