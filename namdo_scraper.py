import asyncio
import os
import sys
import time
import requests
import fitz  # PyMuPDF
from datetime import datetime

# 윈도우 터미널 인코딩 오류 방지
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

# 설정 파일 로드
try:
    import config
except ImportError:
    print("[오류] config.py 파일을 찾을 수 없습니다. 설정 파일을 먼저 확인해 주세요.")
    sys.exit(1)

# PDF 파싱 데이터 캐시 전역 선언
_namdo_cache_loaded = False
_namdo_cache_results = {}  # {keyword: [articles]}

async def _load_pdf_and_parse_all(page):
    """
    남도일보 오늘 자 지면 PDF들을 동적으로 순회하며 메모리 상에서 다운로드 및 파싱하여 캐싱합니다.
    """
    global _namdo_cache_loaded, _namdo_cache_results
    
    # 캐시 결과 구조 초기화
    for kw in config.SEARCH_KEYWORDS:
        _namdo_cache_results[kw] = []
        
    today = datetime.now()
    yyyy = today.strftime("%Y")
    mm = today.strftime("%m")
    dd = today.strftime("%d")
    
    print(f"-> 남도일보 지면 분석 시작 (기준 날짜: {yyyy}/{mm}/{dd})")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    page_num = 1
    max_pages = 40  # 안전을 위한 최대 탐색 면수
    
    while page_num <= max_pages:
        pdf_url = f"https://www.namdonews.com/pdf/php/check.php?category=&y={yyyy}&m={mm}&d={dd}&page={page_num}&hosu=0"
        
        try:
            t_start = time.time()
            response = requests.get(pdf_url, headers=headers, timeout=30)
            
            # 남도일보는 없는 페이지를 호출하면 PDF 포맷이 아닌 오류 메시지(HTML 등)를 리턴합니다.
            if response.status_code == 200 and response.content.startswith(b"%PDF"):
                # 메모리 상에서 스트림 형태로 PDF 바로 로딩 (디스크 쓰기 생략)
                doc = fitz.open(stream=response.content, filetype="pdf")
                text = doc[0].get_text()
                
                # 키워드 검색
                for kw in config.SEARCH_KEYWORDS:
                    if kw in text:
                        # 키워드가 포함된 라인 구절 파싱
                        lines = text.split("\n")
                        matching_line = ""
                        for line in lines:
                            if kw in line:
                                matching_line = line.strip()
                                break
                                
                        title = f"[지면 {page_num}면] {matching_line}"
                        if len(title) > 85:
                            title = title[:85] + "..."
                            
                        _namdo_cache_results[kw].append({
                            "date": f"{yyyy}/{mm}/{dd}",
                            "provider": config.MEDIA_SITES["namdonews"]["name"],
                            "title": title,
                            "url": pdf_url
                        })
                        
                doc.close()
                duration = time.time() - t_start
                print(f"   [남도일보] {page_num}면 분석 완료 ({duration:.2f}초 소요, 크기: {len(response.content)} bytes)")
                page_num += 1
            else:
                # 더 이상 지면이 없으면 break로 종료
                print(f"-> 남도일보 지면 탐색 완료 (마지막 면수: {page_num - 1}면)")
                break
        except Exception as e:
            print(f"-> [경고] {page_num}면 파싱 중 오류 발생: {e}")
            # 에러 발생 시 일단 중단 처리
            break
            
    _namdo_cache_loaded = True

async def scrape_keyword(page, keyword: str) -> list:
    """
    지정된 단일 키워드로 남도일보 지면에서 당일 기사를 검색하여 반환합니다.
    """
    global _namdo_cache_loaded, _namdo_cache_results
    
    if not _namdo_cache_loaded:
        await _load_pdf_and_parse_all(page)
        
    return _namdo_cache_results.get(keyword, [])

async def run_scraper():
    """
    config.py에 등록된 모든 키워드에 대해 남도일보 지면 검색을 수행하고
    결과를 출력합니다.
    """
    today_date = datetime.now().strftime("%Y/%m/%d")
    
    print("============================================================")
    print(f"[NEWS] 남도일보 지면 PDF 스크래퍼 기동 (로컬 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
    print("============================================================")
    
    results_summary = {}
    
    # 호환성 규격을 위해 dummy page 인스턴스를 넘김 (실제 브라우저 기동 없음)
    dummy_page = None
    
    for keyword in config.SEARCH_KEYWORDS:
        try:
            articles = await scrape_keyword(dummy_page, keyword)
            results_summary[keyword] = articles
        except Exception as e:
            print(f"-> [에러] '{keyword}' 키워드 검색 중 오류 발생: {e}")
            results_summary[keyword] = []
            
    print("\n============================================================")
    print(f"[RESULT] 남도일보 지면 PDF 당일 뉴스 모니터링 결과 ({today_date})")
    print("============================================================")
    
    for keyword, articles in results_summary.items():
        print(f"[KEYWORD] 검색 키워드: '{keyword}'")
        if not articles:
            print("  -> 오늘 지면 결과: 기사 없음")
        else:
            for idx, art in enumerate(articles):
                print(f"  - {art['title']}")
            print(f"  -> 오늘 기사 결과: total {len(articles)}건 있음")
        print("------------------------------------------------------------")
    print("============================================================")

if __name__ == "__main__":
    asyncio.run(run_scraper())
