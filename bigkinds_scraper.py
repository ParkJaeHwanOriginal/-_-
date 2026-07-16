import asyncio
import re
import sys
from datetime import datetime
from playwright.async_api import async_playwright

# 설정 파일 로드
try:
    import config
except ImportError:
    # config.py가 같은 경로에 없을 경우 예외 처리
    print("[오류] config.py 파일을 찾을 수 없습니다. 설정 파일을 먼저 확인해 주세요.")
    sys.exit(1)

async def scrape_keyword(page, keyword: str) -> list:
    """
    지정된 단일 키워드로 빅카인즈에서 당일 기사를 검색하여 반환합니다.
    """
    print(f"\n[KEYWORD] '{keyword}' 키워드로 검색을 시작합니다...")
    
    # 1. 빅카인즈 메인 페이지로 이동
    await page.goto(config.MEDIA_SITES["bigkinds"]["url"], timeout=60000)
    await page.wait_for_timeout(2000)
    
    # 2. 검색창에 키워드 입력 후 엔터
    search_input = "#total-search-key"
    await page.wait_for_selector(search_input, timeout=10000)
    await page.fill(search_input, keyword)
    await page.press(search_input, "Enter")
    
    # 검색 결과 페이지 로딩 대기
    await page.wait_for_timeout(4000)
    
    # 3. '최신순' 정렬 선택 (드롭다운 select 박스 제어)
    try:
        selects = await page.query_selector_all("select")
        sort_applied = False
        for sel in selects:
            options = await sel.query_selector_all("option")
            for opt in options:
                val = await opt.get_attribute("value")
                text = await opt.inner_text()
                if val == "date" or "최신순" in text:
                    await sel.select_option(value="date")
                    print("-> 정렬 방식을 '최신순'으로 변경했습니다.")
                    await page.wait_for_timeout(2000)
                    sort_applied = True
                    break
            if sort_applied:
                break
    except Exception as e:
        print(f"-> [경고] 최신순 정렬 적용 중 오류 발생: {e} (기본 검색 정렬로 계속 진행)")

    # 4. 뉴스 데이터 파싱 및 오늘 날짜 필터링
    today_str = datetime.now().strftime("%Y/%m/%d")
    articles = []
    
    # 뉴스 아이템 목록 대기
    try:
        await page.wait_for_selector(".news-item", timeout=10000)
    except Exception:
        # 뉴스 아이템이 아예 존재하지 않는 경우
        print("-> 검색 결과가 없습니다.")
        return articles

    news_items = await page.query_selector_all(".news-item")
    
    for item in news_items:
        # 제목 파싱
        title_el = await item.query_selector(".title-elipsis")
        title = await title_el.inner_text() if title_el else "제목 없음"
        title = title.strip()
        
        # 언론사 파싱
        provider_el = await item.query_selector("a.provider")
        provider = await provider_el.inner_text() if provider_el else "언론사 없음"
        provider = provider.strip()
        
        # 날짜 파싱 (info 영역 안의 p.name 중 YYYY/MM/DD 형식 찾기)
        name_elements = await item.query_selector_all(".info p.name")
        date_str = ""
        for ne in name_elements:
            txt = (await ne.inner_text()).strip()
            if re.match(r"^\d{4}/\d{2}/\d{2}$", txt):
                date_str = txt
                break
                
        # 오늘 날짜와 일치하는 기사만 리스트에 추가
        if date_str == today_str:
            # 원본 기사 링크 추출 (a.provider의 href 속성 활용)
            link_el = await item.query_selector("a.provider")
            link = await link_el.get_attribute("href") if link_el else ""
            
            articles.append({
                "date": date_str,
                "provider": provider,
                "title": title,
                "url": link if link and link.startswith("http") else config.MEDIA_SITES["bigkinds"]["url"]
            })
            
    return articles

async def run_scraper():
    """
    config.py에 등록된 모든 키워드에 대해 스크래핑을 실행하고
    CMD 창에 결과를 포맷팅하여 출력합니다.
    """
    today_date = datetime.now().strftime("%Y/%m/%d")
    
    print("============================================================")
    print(f"[NEWS] 빅카인즈 뉴스 스크래퍼 기동 (로컬 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
    print("============================================================")
    
    results_summary = {}
    
    async with async_playwright() as p:
        # config.py의 HEADLESS 설정을 따름
        browser = await p.chromium.launch(headless=config.HEADLESS)
        page = await browser.new_page()
        
        for keyword in config.SEARCH_KEYWORDS:
            try:
                articles = await scrape_keyword(page, keyword)
                results_summary[keyword] = articles
            except Exception as e:
                print(f"-> [에러] '{keyword}' 키워드 검색 중 오류 발생: {e}")
                results_summary[keyword] = []
                
        await browser.close()
        
    # CMD 화면에 결과 리포트 출력
    print("\n============================================================")
    print(f"[RESULT] 빅카인즈 당일 뉴스 모니터링 결과 ({today_date})")
    print("============================================================")
    
    for keyword, articles in results_summary.items():
        print(f"[KEYWORD] 검색 키워드: '{keyword}'")
        if not articles:
            print("  -> 오늘 기사 결과: 기사 없음")
        else:
            for idx, art in enumerate(articles):
                print(f"  - [{art['provider']}] {art['title']}")
            print(f"  -> 오늘 기사 결과: 총 {len(articles)}건 있음")
        print("------------------------------------------------------------")
    print("============================================================")

if __name__ == "__main__":
    # 스크립트 단독 실행 시 작동하는 엔트리 포인트
    asyncio.run(run_scraper())
