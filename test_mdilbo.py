import asyncio
import os
import sys
import time
import requests
import fitz  # PyMuPDF
import easyocr

# 윈도우 터미널 인코딩 오류 방지
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

async def main():
    pdf_url = "https://file.sarangbang.com/moodeungilbo//ebook/pdf/202607/20260706.pdf"
    print(f"[1] 무등일보 PDF 다운로드 시작: {pdf_url}", flush=True)
    
    temp_pdf = "temp_debug_mdilbo.pdf"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(pdf_url, headers=headers, timeout=60)
        if response.status_code == 200:
            with open(temp_pdf, "wb") as f:
                f.write(response.content)
            print("-> 다운로드 성공. 고정밀 OCR 엔진을 초기화합니다.", flush=True)
        else:
            print(f"[에러] 다운로드 실패 (상태코드: {response.status_code})", flush=True)
            return
    except Exception as e:
        print(f"[에러] 다운로드 중 오류 발생: {e}", flush=True)
        return

    # OCR 리더 로드
    try:
        reader = easyocr.Reader(['ko'], gpu=False)
    except Exception as e:
        print(f"[에러] easyocr 초기화 실패: {e}", flush=True)
        if os.path.exists(temp_pdf):
            os.remove(temp_pdf)
        return

    # 오직 1면(1페이지)만 950px 고해상도 OCR 수행
    try:
        doc = fitz.open(temp_pdf)
        print("\n[2] 1면 지면 고정밀 OCR 문자 판독 구동...", flush=True)
        
        page = doc[0]
        rect = page.rect
        scale = 950.0 / rect.width
        matrix = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=matrix)
        img_bytes = pix.tobytes("png")
        
        # OCR 수행
        segments = reader.readtext(img_bytes, detail=0)
        full_text = " ".join(segments)
        
        # 1면 키워드 검출 여부 즉시 출력
        print("\n========================================", flush=True)
        print("📊 무등일보 1면 고정밀 OCR 검출 결과", flush=True)
        print("========================================", flush=True)
        
        for kw in ["정근식", "김대중"]:
            count = full_text.count(kw)
            print(f"🔍 검색 키워드 '{kw}': {count}회 검출 (발견 여부: {kw in full_text})", flush=True)
            # 키워드가 포함된 문맥 출력
            if count > 0:
                for seg in segments:
                    if kw in seg:
                        print(f"   -> 검출 문맥: ...{seg.strip()}...", flush=True)
                        break
        print("========================================", flush=True)
        
        doc.close()
    except Exception as e:
        print(f"[에러] OCR 판독 중 오류 발생: {e}", flush=True)
    finally:
        if os.path.exists(temp_pdf):
            os.remove(temp_pdf)
            print("\n[3] 임시 PDF 파일 삭제 완료.", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
