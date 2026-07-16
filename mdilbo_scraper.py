import asyncio
import os
import re
import sys
import time
import requests
import io
from PIL import Image
import fitz  # PyMuPDF
import easyocr
from datetime import datetime
from playwright.async_api import async_playwright

# 윈도우 터미널 인코딩 오류 방지
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

# 설정 파일 로드
try:
    import config
except ImportError:
    print("[오류] config.py 파일을 찾을 수 없습니다. 설정 파일을 먼저 확인해 주세요.")
    sys.exit(1)

# PDF 파싱 데이터 캐시 및 OCR 리더 전역 선언
_pdf_cache_loaded = False
_pdf_cache_results = {}  # {keyword: [articles]}
_easyocr_reader = None

async def _load_pdf_and_ocr_all(page):
    """
    무등일보 지면 PDF를 다운로드하고, easyocr을 이용하여 각 지면을 판독하여 키워드 매칭을 수행합니다.
    """
    global _pdf_cache_loaded, _pdf_cache_results, _easyocr_reader
    
    # 1. 지면보기 페이지 접속 및 PDF URL 파싱
    url = config.MEDIA_SITES["mdilbo"]["url"]
    await page.goto(url, timeout=60000)
    await page.wait_for_timeout(3000)
    
    pdf_url = None
    links = await page.query_selector_all("a")
    for link in links:
        href = await link.get_attribute("href") or ""
        if ".pdf" in href.lower():
            if href.startswith("//"):
                pdf_url = "https:" + href
            elif href.startswith("/"):
                pdf_url = "https://www.mdilbo.com" + href
            else:
                pdf_url = href
            break
            
    if not pdf_url:
        print("-> [경고] 오늘자 무등일보 지면 PDF 링크를 찾지 못했습니다.")
        _pdf_cache_loaded = True
        return
        
    # 2. PDF 다운로드
    temp_pdf = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp_mdilbo_ocr.pdf")
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        print(f"-> 무등일보 지면 PDF 다운로드 중: {pdf_url}")
        response = requests.get(pdf_url, headers=headers, timeout=60)
        if response.status_code == 200:
            with open(temp_pdf, "wb") as f:
                f.write(response.content)
            print("-> PDF 다운로드 완료. OCR 분석 준비를 시작합니다.")
        else:
            print(f"-> [경고] PDF 다운로드 실패 (상태코드: {response.status_code})")
            _pdf_cache_loaded = True
            return
    except Exception as e:
        print(f"-> [경고] PDF 다운로드 중 오류 발생: {e}")
        _pdf_cache_loaded = True
        return

    # 3. EasyOCR 엔진 및 결과 딕셔너리 초기화
    try:
        for kw in config.SEARCH_KEYWORDS:
            _pdf_cache_results[kw] = []
            
        if not _easyocr_reader:
            print("-> OCR 한글 판독 모델 로딩 중...")
            t_loader = time.time()
            _easyocr_reader = easyocr.Reader(['ko'], gpu=False)
            print(f"-> 모델 로딩 완료 (소요시간: {time.time() - t_loader:.2f}초)")
            
        # PyMuPDF로 PDF 로드
        doc = fitz.open(temp_pdf)
        total_pages = len(doc)
        print(f"-> 무등일보 총 {total_pages}개 지면 OCR 문자 판독 시작...")
        
        for page_idx in range(total_pages):
            t_page_start = time.time()
            pdf_page = doc[page_idx]
            
            # DPI 70으로 이미지 렌더링
            pix = pdf_page.get_pixmap(dpi=70)
            img_bytes_raw = pix.tobytes("png")
            
            # PIL 이미지 리사이즈 (가로 500으로 고정하여 연산량 4배 감소)
            img = Image.open(io.BytesIO(img_bytes_raw))
            resized_img = img.resize((500, 725), Image.Resampling.LANCZOS)
            
            # 리사이즈 이미지 바이트 변환
            buf = io.BytesIO()
            resized_img.save(buf, format="PNG")
            img_bytes = buf.getvalue()
            
            # OCR 판독 (detail=0 으로 텍스트 목록만 획득)
            segments = _easyocr_reader.readtext(img_bytes, detail=0)
            full_text = " ".join(segments)
            
            # 키워드 대조
            match_found_in_page = False
            for kw in config.SEARCH_KEYWORDS:
                if kw in full_text:
                    match_found_in_page = True
                    # 키워드가 포함된 구절 추출
                    matching_line = ""
                    for seg in segments:
                        if kw in seg:
                            matching_line = seg.strip()
                            break
                            
                    title = f"[지면 {page_idx + 1}면] {matching_line}"
                    if len(title) > 85:
                        title = title[:85] + "..."
                        
                    _pdf_cache_results[kw].append({
                        "date": datetime.now().strftime("%Y/%m/%d"),
                        "provider": config.MEDIA_SITES["mdilbo"]["name"],
                        "title": title,
                        "url": pdf_url
                    })
            
            duration = time.time() - t_page_start
            match_status = "키워드 발견" if match_found_in_page else "매칭 없음"
            print(f"   [무등일보 OCR] {page_idx + 1}/{total_pages}면 분석 완료 ({duration:.2f}초 소요, 결과: {match_status})")
            
        doc.close()
        print("-> 무등일보 전체 지면 OCR 분석이 성공적으로 완료되었습니다.")
        
    except Exception as e:
        print(f"-> [경고] PDF OCR 파싱 중 오류 발생: {e}")
    finally:
        # 임시 다운로드한 PDF 삭제
        if os.path.exists(temp_pdf):
            os.remove(temp_pdf)
            
    _pdf_cache_loaded = True

async def scrape_keyword(page, keyword: str) -> list:
    """
    지정된 단일 키워드로 무등일보 지면에서 당일 기사를 검색하여 반환합니다.
    """
    global _pdf_cache_loaded, _pdf_cache_results
    
    if not _pdf_cache_loaded:
        await _load_pdf_and_ocr_all(page)
        
    return _pdf_cache_results.get(keyword, [])

async def run_scraper():
    """
    config.py에 등록된 모든 키워드에 대해 스크래핑을 실행하고
    CMD 창에 결과를 포맷팅하여 출력합니다.
    """
    today_date = datetime.now().strftime("%Y/%m/%d")
    
    print("============================================================")
    print(f"[NEWS] 무등일보 지면 OCR 스크래퍼 기동 (로컬 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
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
        
    print("\n============================================================")
    print(f"[RESULT] 무등일보 지면 OCR 당일 뉴스 모니터링 결과 ({today_date})")
    print("============================================================")
    
    for keyword, articles in results_summary.items():
        print(f"[KEYWORD] 검색 키워드: '{keyword}'")
        if not articles:
            print("  -> 오늘 지면 결과: 기사 없음")
        else:
            for idx, art in enumerate(articles):
                print(f"  - {art['title']}")
            print(f"  -> 오늘 기사 결과: 총 {len(articles)}건 있음")
        print("------------------------------------------------------------")
    print("============================================================")

if __name__ == "__main__":
    asyncio.run(run_scraper())
