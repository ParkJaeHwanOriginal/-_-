import asyncio
import os
import sys
import time
from datetime import datetime
from playwright.async_api import async_playwright

# 윈도우 터미널 인코딩 오류 방지
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

# 설정 파일 로드
try:
    import config
except ImportError:
    print("[오류] config.py 설정을 읽을 수 없습니다.")
    sys.exit(1)

# 개별 스크래퍼 모듈 임포트
try:
    import bigkinds_scraper
    import donga_scraper
    import kjdaily_scraper
    import namdo_scraper
    import excel_writer
    import email_sender
except ImportError as e:
    print(f"[오류] 스크래퍼 핵심 모듈 임포트 실패: {e}")
    sys.exit(1)

async def main():
    start_time = time.time()
    print("============================================================")
    print("🚀 [START] 광주상생일자리재단 뉴스 모니터링 수집 시스템 가동")
    print(f"-> 로컬 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"-> 수집 대상 키워드 목록: {config.SEARCH_KEYWORDS}")
    print(f"-> 수집 대상 매체 목록: {[v['name'] for v in config.MEDIA_SITES.values()]}")
    print("============================================================")
    
    # 키워드별 수집 결과 통합용 딕셔너리
    total_results = {kw: [] for kw in config.SEARCH_KEYWORDS}
    
    # Playwright 컨텍스트 기동 (동적 크롤링 매체용)
    async with async_playwright() as p:
        print("\n🤖 Playwright 브라우저 기동 중...")
        browser = await p.chromium.launch(headless=config.HEADLESS)
        page = await browser.new_page()
        
        # 키워드별 수집 수행
        for keyword in config.SEARCH_KEYWORDS:
            print(f"\n🔍 [검색] 키워드: '{keyword}' 분석 및 수집 중...")
            
            # 1. 빅카인즈 검색
            try:
                print("   -> 빅카인즈 수집 가동...")
                arts = await bigkinds_scraper.scrape_keyword(page, keyword)
                for a in arts:
                    a["origin_site"] = "bigkinds"
                total_results[keyword].extend(arts)
                print(f"      [빅카인즈] 완료 (오늘자 기사: {len(arts)}건)")
            except Exception as e:
                print(f"   -> [빅카인즈 에러] 수집 실패: {e}")
                
            # 2. 동아일보 검색
            try:
                print("   -> 동아일보 수집 가동...")
                arts = await donga_scraper.scrape_keyword(page, keyword)
                for a in arts:
                    a["origin_site"] = "donga"
                total_results[keyword].extend(arts)
                print(f"      [동아일보] 완료 (오늘자 기사: {len(arts)}건)")
            except Exception as e:
                print(f"   -> [동아일보 에러] 수집 실패: {e}")
                
            # 3. 광주매일신문 검색
            try:
                print("   -> 광주매일신문 e-Book 수집 가동...")
                arts = await kjdaily_scraper.scrape_keyword(page, keyword)
                for a in arts:
                    a["origin_site"] = "kjdaily"
                total_results[keyword].extend(arts)
                print(f"      [광주매일신문] 완료 (오늘자 기사: {len(arts)}건)")
            except Exception as e:
                print(f"   -> [광주매일신문 에러] 수집 실패: {e}")
                
            # 4. 남도일보 검색 (requests 기반이라 page는 dummy로 넘어감)
            try:
                print("   -> 남도일보 지면 PDF 수집 가동...")
                arts = await namdo_scraper.scrape_keyword(page, keyword)
                for a in arts:
                    a["origin_site"] = "namdonews"
                total_results[keyword].extend(arts)
                print(f"      [남도일보] 완료 (오늘자 기사: {len(arts)}건)")
            except Exception as e:
                print(f"   -> [남도일보 에러] 수집 실패: {e}")
                
        await browser.close()
        print("\n🤖 Playwright 브라우저 정상 종료.")
        
    # 엑셀 보고서 갱신
    print("\n📊 엑셀 보고서 데이터 적재 및 서식 갱신 시작...")
    try:
        excel_writer.save_to_excel(total_results)
    except Exception as e:
        print(f"[에러] 엑셀 결과 저장 중 오류 발생: {e}")
        
    # 이메일 자동 보고 전송
    if config.SEND_EMAIL:
        print("\n✉️ 엑셀 보고서 이메일 자동 발송 시작...")
        try:
            email_sender.send_report_email(total_results)
        except Exception as e:
            print(f"[에러] 이메일 보고서 발송 중 오류 발생: {e}")
            
    duration = time.time() - start_time
    print("\n============================================================")
    print(f"🎉 [SUCCESS] 뉴스 모니터링 시스템 전체 수집 주기 완료 (총 소요시간: {duration:.2f}초)")
    print("============================================================")

if __name__ == "__main__":
    asyncio.run(main())
