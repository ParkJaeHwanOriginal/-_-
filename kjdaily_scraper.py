import asyncio
import re
import sys
from datetime import datetime
from playwright.async_api import async_playwright

# 윈도우 터미널 인코딩 오류 방지 설정
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

# 설정 파일 로드
try:
    import config
except ImportError:
    print("[오류] config.py 파일을 찾을 수 없습니다. 설정 파일을 먼저 확인해 주세요.")
    sys.exit(1)

async def scrape_keyword(page, keyword: str) -> list:
    """
    지정된 단일 키워드로 광주매일신문 e-Book 지면에서 기사를 검색하여 반환합니다.
    """
    print(f"\n[KEYWORD] '{keyword}' 키워드로 검색을 시작합니다...")
    
    # 1. 광주매일신문 e-Book 지면 뷰어 메인 페이지 접속
    url = config.MEDIA_SITES["kjdaily"]["url"]
    await page.goto(url, timeout=60000)
    await page.wait_for_timeout(5000)  # 지면 뷰어 및 렌더링을 위해 충분히 대기
    
    # 2. 오늘 날짜 지면인지 교차 검증 (body 텍스트 내 오늘 날짜 문자열 확인)
    today_str = datetime.now().strftime("%Y-%m-%d")  # 예: 2026-07-02
    body_text = await page.locator("body").inner_text()
    
    if today_str not in body_text:
        print(f"-> [안내] 오늘 날짜({today_str})의 지면이 아직 발행되지 않았거나 열리지 않았습니다.")
        return []
        
    # 3. 좌측 메뉴바의 2번째 돋보기(검색) 탭 버튼 클릭
    try:
        tabs_locator = page.locator(".MuiTabs-flexContainerVertical button")
        if await tabs_locator.count() >= 2:
            # 2번째 탭 클릭 (인덱스 1)
            await tabs_locator.nth(1).click()
            await page.wait_for_timeout(2000)
        else:
            print("-> [경고] 검색 탭 버튼을 찾지 못했습니다. (검색을 건너뜁니다)")
            return []
    except Exception as e:
        print(f"-> [경고] 검색 탭 버튼 클릭 중 오류 발생: {e}")
        return []
        
    # 4. 검색창 입력 및 검색 수행
    articles = []
    try:
        # UUID id 대응 접두어 속성 선택자 사용
        search_input = page.locator("input[id^='search-cw-']")
        if await search_input.count() > 0:
            await search_input.first.fill(keyword)
            await search_input.first.press("Enter")
            await page.wait_for_timeout(4000)  # 검색 결과 렌더링 대기
        else:
            print("-> [경고] 검색 입력창을 찾지 못했습니다.")
            return []
    except Exception as e:
        print(f"-> [경고] 검색 수행 중 오류 발생: {e}")
        return []
        
    # 5. 검색 결과 파싱
    try:
        news_items = await page.query_selector_all(".MuiListItem-root")
        for item in news_items:
            text = (await item.inner_text()).strip()
            if not text:
                continue
                
            # 줄바꿈으로 나누어 첫 줄(면번호), 둘째 줄(기사내용)을 분리합니다.
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            if not lines:
                continue
                
            # 첫 번째 라인에서 면번호(숫자) 추출
            page_num_match = re.match(r"^(\d+)", lines[0])
            page_num = page_num_match.group(1) if page_num_match else "01"
            
            # 기사 내용 요약
            content_desc = lines[1] if len(lines) > 1 else lines[0]
            if len(content_desc) > 80:
                content_desc = content_desc[:80] + "..."
                
            title = f"[지면 {int(page_num)}면] {content_desc}"
            
            articles.append({
                "date": datetime.now().strftime("%Y/%m/%d"),
                "provider": config.MEDIA_SITES["kjdaily"]["name"],
                "title": title,
                "url": url  # 지면 뷰어 메인 URL로 연결
            })
    except Exception as e:
        print(f"-> [경고] 결과 파싱 중 오류 발생: {e}")
        
    return articles

async def run_scraper():
    """
    config.py에 등록된 모든 키워드에 대해 스크래핑을 실행하고
    CMD 창에 결과를 포맷팅하여 출력합니다.
    """
    today_date = datetime.now().strftime("%Y/%m/%d")
    
    print("============================================================")
    print(f"[NEWS] 광주매일신문 e-Book 스크래퍼 기동 (로컬 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
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
    print(f"[RESULT] 광주매일신문 e-Book 당일 뉴스 모니터링 결과 ({today_date})")
    print("============================================================")
    
    for keyword, articles in results_summary.items():
        print(f"[KEYWORD] 검색 키워드: '{keyword}'")
        if not articles:
            print("  -> 오늘 기사 결과: 기사 없음")
        else:
            for idx, art in enumerate(articles):
                print(f"  - {art['title']}")
            print(f"  -> 오늘 기사 결과: 총 {len(articles)}건 있음")
        print("------------------------------------------------------------")
    print("============================================================")

if __name__ == "__main__":
    asyncio.run(run_scraper())
