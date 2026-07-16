import os
from datetime import datetime

# 외부 라이브러리(python-dotenv) 의존성 없이 순수 파이썬으로 .env 파일을 파싱하여 환경변수에 직접 주입합니다.
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(env_path):
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # 주석이거나 빈 줄이 아니고, 등호(=)가 포함된 설정 행만 파싱
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ[key.strip()] = val.strip()
    except Exception as e:
        print(f"[경고] .env 설정 로딩 중 오류 발생: {e}")

# ==========================================
# 1. 검색 키워드 설정
# ==========================================
# 기본 고정 키워드 (광주경제진흥상생일자리재단)
DEFAULT_KEYWORDS = ["광주경제진흥상생일자리재단"]

# 환경변수 'SEARCH_KEYWORDS'가 있으면 쉼표(,) 구분하여 리스트로 파싱, 없으면 기본 고정값 사용
env_keywords = os.environ.get("SEARCH_KEYWORDS")
if env_keywords:
    SEARCH_KEYWORDS = [k.strip() for k in env_keywords.split(",") if k.strip()]
else:
    SEARCH_KEYWORDS = DEFAULT_KEYWORDS

# ==========================================
# 2. 이메일 전송 수신자 설정
# ==========================================
# 이메일 전송 여부 (True인 경우 실행 완료 후 최종 엑셀 결과 파일을 메일로 발송함)
SEND_EMAIL = os.environ.get("SEND_EMAIL", "False").lower() in ("true", "1", "yes")

# 수신 이메일 주소 리스트 (쉼표로 구분하여 여러 개 등록 가능)
env_recipients = os.environ.get("EMAIL_RECIPIENTS")
if env_recipients:
    EMAIL_RECIPIENTS = [e.strip() for e in env_recipients.split(",") if e.strip()]
else:
    EMAIL_RECIPIENTS = []

# ==========================================
# 3. SMTP 메일 발신 서버 설정
# ==========================================
# 깃헙액션 시크릿(Secret)이나 로컬 .env 에 등록하여 사용합니다.
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")          # 발신인 Gmail/Naver 등 이메일 계정
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")  # 발신인 이메일의 2차 앱 비밀번호

# ==========================================
# 4. 결과 파일 설정
# ==========================================
# 결과가 누적 저장될 엑셀 파일 경로입니다.
OUTPUT_FILE_NAME = "news_report.xlsx"
OUTPUT_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), OUTPUT_FILE_NAME)

# ==========================================
# 5. 크롤링 모니터링 옵션
# ==========================================
IS_LOCAL = os.environ.get("GITHUB_ACTIONS") is None
HEADLESS = False if IS_LOCAL else True
PLAYWRIGHT_TIMEOUT = 30000

# ==========================================
# 6. 대상 매체 정보 정의 (무등일보 제외)
# ==========================================
MEDIA_SITES = {
    "bigkinds": {
        "name": "빅카인즈 (BigKinds)",
        "url": "https://www.bigkinds.or.kr/",
        "method": "Playwright 동적 크롤링"
    },
    "donga": {
        "name": "동아일보",
        "url": "https://www.donga.com",
        "method": "Playwright 통합검색"
    },
    "kjdaily": {
        "name": "광주매일신문",
        "url": "https://kjdaily.wigoview.com/",
        "method": "Playwright e-Book HTML 분석"
    },
    "namdonews": {
        "name": "남도일보",
        "url": "https://www.namdonews.com/pdf/list.html",
        "method": "requests & pdfplumber PDF 분석"
    }
}
