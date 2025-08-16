import requests
import schedule
import time
import os
import json
from datetime import datetime, timezone, timedelta

# 환경변수
DART_API_KEY = os.getenv('DART_API_KEY')
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# 한국 시간대 설정
KST = timezone(timedelta(hours=9))

# 이미 본 공시를 저장할 파일
SEEN_DISCLOSURES_FILE = 'seen_disclosures.json'

def get_korean_time():
    """현재 한국 시간 반환"""
    return datetime.now(KST)

def is_business_day():
    """평일인지 확인 (월-금)"""
    korean_time = get_korean_time()
    weekday = korean_time.weekday()  # 0=월요일, 6=일요일
    return weekday < 5  # 0,1,2,3,4 (월~금)

def is_business_hours():
    """공시 활성 시간대인지 확인 (평일 오전 8시 ~ 오후 9시)"""
    if not is_business_day():
        return False
    
    korean_time = get_korean_time()
    hour = korean_time.hour
    return 8 <= hour <= 21  # 오전 8시 ~ 오후 9시

def should_check_disclosures():
    """공시를 확인해야 하는 시간인지 판단"""
    if not is_business_day():
        print("📅 주말이므로 공시 확인을 건너뜁니다.")
        return False
    
    if not is_business_hours():
        korean_time = get_korean_time()
        print(f"🕐 업무시간 외({korean_time.hour:02d}시)이므로 공시 확인을 건너뜁니다.")
        return False
    
    return True

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
        'page_count': 100,  # 최신 100개
        'page_no': 1
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        if response.status_code == 200:
            data = response.json()
            print(f"📊 API 응답: {data.get('status')} - {data.get('message')}")
            
            if data['status'] == '000':  # 정상
                print(f"📋 공시 개수: {len(data['list'])}개")
                return data['list']
            elif data['status'] == '013':  # 조회된 데이터 없음
                print("✅ 현재 새로운 공시가 없습니다.")
                return []
            else:
                print(f"⚠️ DART API 응답: {data.get('message')}")
                return []
        else:
            print(f"❌ HTTP 오류: {response.status_code}")
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
        response = requests.post(url, data=data, timeout=30)
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
    
    korean_time = get_korean_time()
    
    message = f"""🔔 <b>새로운 공시 발표!</b>

📈 <b>{company}</b>
📋 {title}
📅 {formatted_date}
🔗 <a href="{dart_link}">공시 내용 보기</a>

⏰ {korean_time.strftime('%Y-%m-%d %H:%M:%S')} (KST)"""
    
    return message

def check_new_disclosures():
    """새로운 공시 체크 및 알림"""
    korean_time = get_korean_time()
    
    # 시간 확인
    if not should_check_disclosures():
        return
    
    print(f"🔍 공시 체크 중... {korean_time.strftime('%H:%M:%S')} (KST)")
    
    # 현재 공시 목록 가져오기
    current_disclosures = get_dart_disclosures()
    
    if not current_disclosures:
        print("✅ 조회된 공시가 없거나 오류가 발생했습니다.")
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

def send_startup_message():
    """봇 시작 알림 메시지"""
    korean_time = get_korean_time()
    weekday_name = ['월', '화', '수', '목', '금', '토', '일'][korean_time.weekday()]
    
    status_msg = ""
    if is_business_day() and is_business_hours():
        status_msg = "🟢 공시 모니터링 활성 (30분마다 확인)"
    elif is_business_day() and not is_business_hours():
        status_msg = "🟡 업무시간 외 (오전 8시~오후 9시에 활성화)"
    else:
        status_msg = "🔴 주말 (평일에 활성화)"
    
    startup_message = f"""🤖 <b>DART 공시 알림 봇 시작!</b>

📅 {korean_time.strftime('%Y-%m-%d')} ({weekday_name}요일)
⏰ {korean_time.strftime('%H:%M:%S')} (KST)

{status_msg}

<b>⚙️ 운영 시간:</b>
- 평일 오전 8시 ~ 오후 9시
- 30분마다 새 공시 확인
- 주말 및 야간 시간 자동 휴면"""

    send_telegram_message(startup_message)

# 스케줄 설정: 30분마다 체크 (정각, 30분)
schedule.every().hour.at(":00").do(check_new_disclosures)
schedule.every().hour.at(":30").do(check_new_disclosures)

print("🤖 DART 공시 알림 봇이 시작되었습니다!")
print(f"📱 DART_API_KEY: {'✅ 설정됨' if DART_API_KEY else '❌ 미설정'}")
print(f"📱 BOT_TOKEN: {'✅ 설정됨' if BOT_TOKEN else '❌ 미설정'}")
print(f"💬 CHAT_ID: {'✅ 설정됨' if CHAT_ID else '❌ 미설정'}")

korean_time = get_korean_time()
print(f"🕐 현재 한국 시간: {korean_time.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"📅 평일 여부: {'✅ 평일' if is_business_day() else '❌ 주말'}")
print(f"🕐 업무시간 여부: {'✅ 업무시간' if is_business_hours() else '❌ 업무시간 외'}")

# 봇 시작 알림
if DART_API_KEY and BOT_TOKEN and CHAT_ID:
    send_startup_message()
    
    # 현재 업무시간이면 즉시 한 번 체크
    if should_check_disclosures():
        print("🚀 초기 공시 체크를 시작합니다...")
        check_new_disclosures()
    
    print("⏰ 스케줄러를 시작합니다... (30분마다 :00, :30분에 실행)")
else:
    print("⚠️ 환경변수가 설정되지 않았습니다!")

# 스케줄러 실행
while True:
    schedule.run_pending()
    time.sleep(60)  # 1분마다 스케줄 확인
