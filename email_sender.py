import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
import config

def send_report_email(results_summary):
    """
    results_summary: { keyword: [ ...articles... ] }
    수집 결과 엑셀 파일을 이메일 수신자 목록(EMAIL_RECIPIENTS)에게 전송합니다.
    """
    # 1. 전송 사전 조건 검증
    if not config.SEND_EMAIL:
        print("-> [이메일] SEND_EMAIL 설정이 False이므로 이메일 전송 단계를 생략합니다.")
        return
        
    if not config.EMAIL_RECIPIENTS:
        print("-> [이메일] 등록된 수신 이메일 주소(EMAIL_RECIPIENTS)가 없어 메일 발송을 취소합니다.")
        return
        
    if not config.SMTP_USER or not config.SMTP_PASSWORD:
        print("-> [이메일] 발신 SMTP 계정 설정(SMTP_USER / SMTP_PASSWORD)이 누락되어 메일을 전송하지 못했습니다.")
        return
        
    if not os.path.exists(config.OUTPUT_FILE_PATH):
        print(f"-> [이메일] 첨부할 결과 엑셀 파일이 디스크에 존재하지 않습니다: {config.OUTPUT_FILE_PATH}")
        return
        
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # 2. 이메일 기본 메타 정보 구성
    msg = MIMEMultipart()
    msg["From"] = config.SMTP_USER
    msg["To"] = ", ".join(config.EMAIL_RECIPIENTS)
    msg["Subject"] = f"[일일보고] {today_str} 광주상생일자리재단 뉴스 모니터링 수집 결과"
    
    # 3. 메일 본문 요약 리포트 동적 텍스트 생성 (가독성 향상)
    body_text = f"안녕하세요.\n\n{today_str}자 뉴스 모니터링 집계 결과를 다음과 같이 보고드립니다.\n"
    body_text += "상세 보도 정보는 첨부된 엑셀 보고서 파일(news_report.xlsx)을 확인해 주시기 바랍니다.\n\n"
    body_text += "========================================\n"
    body_text += f"📊 뉴스 모니터링 집계 요약 ({today_str})\n"
    body_text += "========================================\n"
    
    total_all_kw = 0
    # 매체 이름 매핑용 헬퍼
    provider_map = {
        "bigkinds": config.MEDIA_SITES["bigkinds"]["name"],
        "donga": config.MEDIA_SITES["donga"]["name"],
        "kjdaily": config.MEDIA_SITES["kjdaily"]["name"],
        "namdonews": config.MEDIA_SITES["namdonews"]["name"]
    }
    
    for kw, articles in results_summary.items():
        # 각 매체별 카운트 세분화
        counts = {p_name: 0 for p_name in provider_map.values()}
        for art in articles:
            origin = art.get("origin_site")
            p_name = provider_map.get(origin, art["provider"])
            if p_name in counts:
                counts[p_name] += 1
                
        kw_total = len(articles)
        total_all_kw += kw_total
        body_text += f"🔍 검색 키워드: '{kw}'\n"
        for p_name, count in counts.items():
            body_text += f"  - {p_name}: {count}건\n"
        body_text += f"  -> 당일 소계: 총 {kw_total}건\n"
        body_text += "----------------------------------------\n"
        
    body_text += f"🔥 전체 당일 수집 총계: 총 {total_all_kw}건\n"
    body_text += "========================================\n\n"
    body_text += "본 메일은 시스템 자동 생성 및 발신 전용 메일입니다.\n감사합니다."
    
    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    
    # 4. 결과 엑셀 파일 바이너리 첨부
    try:
        with open(config.OUTPUT_FILE_PATH, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())
            
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename={os.path.basename(config.OUTPUT_FILE_PATH)}"
        )
        msg.attach(part)
    except Exception as e:
        print(f"-> [이메일] 엑셀 파일 첨부 중 오류 발생: {e}")
        return
        
    # 5. SMTP 메일 발송 실행
    try:
        print(f"-> [이메일] SMTP 서버 연결 시도 중 ({config.SMTP_SERVER}:{config.SMTP_PORT})...")
        if config.SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(config.SMTP_SERVER, config.SMTP_PORT)
        else:
            server = smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT)
            server.starttls()
            
        server.login(config.SMTP_USER, config.SMTP_PASSWORD)
        print("-> [이메일] SMTP 서버 로그인 성공. 메일을 발송합니다...")
        
        # 전체 수신자 리스트로 전송
        server.sendmail(config.SMTP_USER, config.EMAIL_RECIPIENTS, msg.as_string())
        server.quit()
        print(f"-> [성공] 수신자 리스트 {config.EMAIL_RECIPIENTS} 에게 보고서 메일 전송이 완료되었습니다.")
        
    except Exception as e:
        print(f"-> [에러] 이메일 발송 중 오류 발생: {e}")
