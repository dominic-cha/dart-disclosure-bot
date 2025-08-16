import requests
import schedule
import time
import os
import json
from datetime import datetime

# 환경변수
DART_API_KEY = os.getenv('DART_API_KEY')
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# 이미 본 공시를 저장할 파일
SEEN_DISCLOSURES_FILE = 'seen_disclosures.json'

def load_seen_disclosures():
    """이미 본 공시 목록 로드"""
    try:
        with open(SEEN_DISCLOSURES_FILE, 'r', encoding='utf-8') as f:
            return set(json.load(f))
    except FileNotFoundError:
        return set()

def save_seen_disclosures(seen_set):
    """본 공시 목록 저장"""
    with open(SEEN_DISCLOSURES_FILE, 'w', encoding='utf-8') as f:
        json.dump(list(seen_set), f, ensure_ascii=False, indent=2)

def get_dart_disclosures():
    """DART API에서 최신 공시 가져오기"""
    url = "https://opendart.fss.or.kr/api/list.json"
    params = {
        'crtfc_key': DART_API_KEY,
        'corp_cls': 'Y',  # 상장회사만
        'page_count': 50,  # 최신 50개
        'page_no': 1
    }
    
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            if data['status'] == '000':  # 정상
                return data['list']
        return []
    except Exception as e:
        print(f"🚨 DART API 오류: {e}")
        return []

def send_telegram_message(message):
    """텔레그램으로 메시지 전송"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    
    try:
        response = requests.post(url, data=data)
        if response.status_code == 200:
            print("✅ 텔레그램 전송 성공")
        else:
            print(f"❌ 텔레그램 전송 실패: {response.text}")
    except Exception as e:
        print(f"🚨 텔레그램 오류: {e}")

def format_disclosure_message(disclosure):
    """공시 정보를 예쁘게 포맷"""
    company = disclosure['corp_name']
    title = disclosure['report_nm']
    date = disclosure['rcept_dt']
    receipt_no = disclosure['rcept_no']
    
    # DART 링크 생성
    dart_link = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt_no}"
    
    # 날짜 포맷팅 (20240815 -> 2024-08-15)
    formatted_date = f"{date[:4]}-{date[4:6]}-{date[6:8]}"
    
    message = f"""🔔 <b>새로운 공시 발표!</b>

📈 <b>{company}</b>
📋 {title}
📅 {formatted_date}
🔗 <a href="{dart_link}">공시 내용 보기</a>

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
    
    return message

def check_new_disclosures():
    """새로운 공시 체크 및 알림"""
    print(f"🔍 공시 체크 중... {datetime.now().strftime('%H:%M:%S')}")
    
    # 현재 공시 목록 가져오기
    current_disclosures = get_dart_disclosures()
    
    if not current_disclosures:
        print("❌ 공시 데이터를 가져올 수 없습니다")
        return
    
    # 이미 본 공시 목록 로드
    seen_disclosures = load_seen_disclosures()
    
    # 새로운 공시 찾기
    new_count = 0
    for disclosure in current_disclosures:
        receipt_no = disclosure['rcept_no']
        
        if receipt_no not in seen_disclosures:
            # 새로운 공시 발견!
            print(f"🆕 새 공시: {disclosure['corp_name']} - {disclosure['report_nm']}")
            
            # 텔레그램으로 전송
            message = format_disclosure_message(disclosure)
            send_telegram_message(message)
            
            # 본 공시로 추가
            seen_disclosures.add(receipt_no)
            new_count += 1
    
    # 업데이트된 목록 저장
    save_seen_disclosures(seen_disclosures)
    
    if new_count == 0:
        print("✅ 새로운 공시 없음")
    else:
        print(f"📤 {new_count}개의 새 공시 전송 완료")

# 스케줄 설정: 5분마다 체크
schedule.every(5).minutes.do(check_new_disclosures)

print("🤖 DART 공시 알림 봇이 시작되었습니다!")
print(f"📱 DART_API_KEY: {'✅ 설정됨' if DART_API_KEY else '❌ 미설정'}")
print(f"📱 BOT_TOKEN: {'✅ 설정됨' if BOT_TOKEN else '❌ 미설정'}")
print(f"💬 CHAT_ID: {'✅ 설정됨' if CHAT_ID else '❌ 미설정'}")

# 시작 시 즉시 한 번 체크
if DART_API_KEY and BOT_TOKEN and CHAT_ID:
    print("🚀 초기 공시 체크를 시작합니다...")
    check_new_disclosures()
    print("⏰ 5분마다 새 공시를 확인합니다...")
else:
    print("⚠️ 환경변수가 설정되지 않았습니다!")

# 스케줄러 실행
while True:
    schedule.run_pending()
    time.sleep(60)
