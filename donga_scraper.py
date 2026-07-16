import asyncio
import re
import sys
from datetime import datetime
from playwright.async_api import async_playwright

# 설정 파일 로드
try:
    import config
except ImportError:
    print("[오류] config.py 파일을 찾을 수 없습니다. 설정 파일을 먼저 확인해 주세요.")
    sys.exit(1)

def is_today_article(date_txt: str) -> bool:
    """
    동아일보 날짜 텍스트를 분석하여 오늘 작성된 기사인지 판별합니다.
    - 상대적 시간 표시(예: 5시간 전, 30분 전, 오늘 등)는 오늘 기사로 인정 (단, '일 전'은 제외)
    - 절대적 날짜 표시(예: 2026-07-02 또는 2026.07.02)는 오늘 날짜와 대조
    """
    date_txt = date_txt.strip()
    if not date_txt:
        return False
        
    # 1. 상대적 시간 표시 처리
    if "전" in date_txt:
        if "일 전" in date_txt:
            return False  # 1일 전, 2일 전 등은 오늘이 아님
        return True       # 분 전, 시간 전, 초 전 등은 오늘 기사임
        
    if "오늘" in date_txt:
        return True
        
    # 2. 절대적 날짜 표시 처리
    today = datetime.now()
    today_dash = today.strftime("%Y-%m-%d")
    today_dot = today.strftime("%Y.%m.%d")
    
    if today_dash in date_txt or today_dot in date_txt:
        return True
        
    # YYYYMMDD 형태가 텍스트에 포함되어 있는지 체크 (예: URL 등에서 흔히 보임)
    today_compact = today.strftime("%Y%m%d")
    if today_compact in date_txt:
        return True
        
    return False

async def scrape_keyword(page, keyword: str) -> list:
    """
    지정된 단일 키워드로 동아일보에서 당일 기사를 검색하여 반환합니다.
    """
    print(f"\n[KEYWORD] '{keyword}' 키워드로 검색을 시작합니다...")
    
    # 1. 동아일보 뉴스 검색 페이지 직접 접근
    url = f"{config.MEDIA_SITES['donga']['url']}/news/search?query={keyword}"
    await page.goto(url, timeout=60000)
    await page.wait_for_timeout(2000)
    
    # 2. '최신순' 정렬 클릭 시도
    try:
        latest_btn = page.locator("text=최신순")
        if await latest_btn.count() > 0:
            await latest_btn.first.click()
            print("-> 정렬 방식을 '최신순'으로 변경했습니다.")
            await page.wait_for_timeout(2000)
    except Exception as e:
        print(f"-> [경고] 최신순 정렬 적용 중 오류 발생: {e} (기본 검색 정렬로 계속 진행)")
        
    # 3. 뉴스 데이터 파싱 및 오늘 날짜 필터링
    articles = []
    
    # 뉴스 아이템 목록 대기
    try:
        await page.wait_for_selector(".news_card", timeout=10000)
    except Exception:
        # 뉴스 결과가 없는 경우
        print("-> 검색 결과가 없습니다.")
        return articles
        
    news_cards = await page.query_selector_all(".news_card")
    
    for card in news_cards:
        # 제목 및 링크 파싱
        title_el = await card.query_selector("h4.tit a")
        if not title_el:
            title_el = await card.query_selector(".tit a")
            
        title = await title_el.inner_text() if title_el else "제목 없음"
        title = title.strip()
        
        link = await title_el.get_attribute("href") if title_el else ""
        
        # 날짜 파싱
        date_el = await card.query_selector("span.date")
        date_txt = await date_el.inner_text() if date_el else ""
        date_txt = date_txt.strip()
        
        # 오늘 날짜와 부합하는 기사인지 판별
        if is_today_article(date_txt):
            # 언론사 판별 (도메인 기반)
            provider = "동아일보"
            if link and "sports.donga.com" in link:
                provider = "스포츠동아"
            elif link and "weekly.donga.com" in link:
                provider = "주간동아"
                
            articles.append({
                "date": datetime.now().strftime("%Y/%m/%d"),  # 오늘 날짜로 기록
                "provider": provider,
                "title": title,
                "url": link
            })
            
    return articles

async def run_scraper():
    """
    config.py에 등록된 모든 키워드에 대해 스크래핑을 실행하고
    CMD 창에 결과를 포맷팅하여 출력합니다.
    """
    today_date = datetime.now().strftime("%Y/%m/%d")
    
    print("============================================================")
    print(f"[NEWS] 동아일보 뉴스 스크래퍼 기동 (로컬 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
    print("============================================================")
    
    results_summary = {}
    
    async with async_playwright() as p:
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
    print(f"[RESULT] 동아일보 당일 뉴스 모니터링 결과 ({today_date})")
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
    asyncio.run(run_scraper())
