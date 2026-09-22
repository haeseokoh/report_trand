import argparse
import uvicorn
import os
import sys

# Windows 콘솔 인코딩 대응
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass
from pipeline import run_pipeline

def main():
    parser = argparse.ArgumentParser(description="주식/산업 리포트 트렌드 분석 시스템")
    parser.add_argument("--crawl-only", action="store_true", help="수집 및 분석 파이프라인만 실행")
    parser.add_argument("--server-only", action="store_true", help="웹 대시보드 서버만 구동")
    parser.add_argument("--port", type=int, default=8000, help="웹 서버 포트 (기본값: 8000)")
    parser.add_argument("--pages", type=int, default=2, help="수집할 페이지 수 (카테고리당)")
    parser.add_argument("--max-pdfs", type=int, default=30, help="PDF 텍스트 분석 대상 리포트 수")
    
    parser.add_argument("--no-browser", action="store_true", help="브라우저 자동 열기 비활성화")
    
    args = parser.parse_args()
    
    if args.crawl_only:
        print("🚀 리포트 수집 및 트렌드 분석 파이프라인을 실행합니다...")
        run_pipeline(crawl_pages=args.pages, max_process_pdf=args.max_pdfs)
        return
        
    if not args.server_only:
        # 최초 실행 시 샘플 데이터가 없으면 기본 1회 파이프라인 실행
        from db.database import DB_PATH
        if not os.path.exists(DB_PATH):
            print("📦 최초 실행: 기본 데이터 수집 및 분석을 진행합니다...")
            run_pipeline(crawl_pages=args.pages, max_process_pdf=args.max_pdfs)
            
    print(f"\n🌐 웹 대시보드 서버를 시작합니다: http://localhost:{args.port}")
    
    if not args.no_browser:
        import threading
        import webbrowser
        def _open_browser():
            import time
            time.sleep(1.2)
            try:
                webbrowser.open(f"http://localhost:{args.port}")
            except Exception:
                pass
        threading.Thread(target=_open_browser, daemon=True).start()

    uvicorn.run("app.main:app", host="0.0.0.0", port=args.port, reload=False)

if __name__ == "__main__":
    main()
