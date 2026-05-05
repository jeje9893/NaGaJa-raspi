"""
nagaja_bridge.py — Firestore <-> HTML UI 브리지 + 부저 알람
나가자 프로젝트 | Raspberry Pi 실행 스크립트

동작 방식:
  Firestore 문서를 실시간 구독하고, 변경이 발생하면
  WebSocket을 통해 timer_ui.html 로 데이터를 전송합니다.
  또한 기상 시각에 부저 알람을, 상태 전환 시점에 '삐 삐' 두 번을 울립니다.

사용법:
  cd ~/nagaja/ui
  source ~/nagaja/venv/bin/activate
  python3 nagaja_bridge.py

의존 패키지 (venv 내 설치):
  pip install firebase-admin websockets RPi.GPIO

Firestore 문서 경로:
  nagaja/{USER_ID}/schedule/today

Firestore 문서 필드 (Android 앱에서 설정):
  wakeUpTime       : "07:00"   기상 알람 시각 (없으면 null)
  classStartTime   : "09:00"
  className        : "전공필수"
  departureTime    : "08:20"
  prepStartTime    : "07:50"
  taxiDeadline     : "08:35"
  travelMinutes    : 25
  weatherCondition : "맑음"
  weatherDelay     : 0
  busNextMinutes   : null

GPIO 핀 (BCM 번호):
  BUZZER_PIN = 18  — 능동 부저 (+)
  BUTTON_PIN = 17  — 기상 알람 해제 버튼 (GND 쪽으로 누름)
"""

import asyncio
import json
import os
import threading
import logging
import time
from datetime import datetime

import websockets
import firebase_admin
from firebase_admin import credentials, firestore

# GPIO (라즈베리파이 전용; 없으면 자동 비활성화)
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    GPIO_AVAILABLE = False

# ─────────────────────────────────────
#  설정
# ─────────────────────────────────────

SERVICE_ACCOUNT_PATH = os.path.expanduser("~/nagaja/serviceAccountKey.json")
FIRESTORE_USER_ID    = "test_user"
FIRESTORE_DOC_PATH   = f"nagaja/{FIRESTORE_USER_ID}/schedule/today"

WS_HOST    = "localhost"
WS_PORT    = 8765
STATE_FILE = "/tmp/nagaja_state.json"

BUZZER_PIN         = 18   # BCM 핀 번호 — 부저
BUTTON_PIN         = 17   # BCM 핀 번호 — 기상 알람 해제 버튼
WAKE_ALARM_SECONDS = 120  # 기상 알람 최대 지속 시간 (초)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("nagaja")

# ─────────────────────────────────────
#  GPIO 초기화
# ─────────────────────────────────────

if GPIO_AVAILABLE:
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BUZZER_PIN, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    log.info(f"GPIO 초기화 완료 (부저={BUZZER_PIN}, 버튼={BUTTON_PIN})")
else:
    log.warning("RPi.GPIO 없음 — 부저 기능 비활성화 (시뮬레이션 모드)")

# ─────────────────────────────────────
#  부저 제어
# ─────────────────────────────────────

_alarm_active = False
_alarm_lock   = threading.Lock()


def _buzz(on: bool):
    if GPIO_AVAILABLE:
        GPIO.output(BUZZER_PIN, GPIO.HIGH if on else GPIO.LOW)


def double_beep():
    """상태 전환 시 '삐 삐' 두 번 울림."""
    log.info("부저: 삐삐")
    _buzz(True);  time.sleep(0.15)
    _buzz(False); time.sleep(0.20)
    _buzz(True);  time.sleep(0.15)
    _buzz(False)


def wake_up_alarm():
    """기상 알람: 최대 WAKE_ALARM_SECONDS 초 동안 울리거나 버튼으로 해제."""
    global _alarm_active
    with _alarm_lock:
        if _alarm_active:
            return
        _alarm_active = True

    log.info("기상 알람 시작")
    deadline = time.time() + WAKE_ALARM_SECONDS
    while _alarm_active and time.time() < deadline:
        _buzz(True);  time.sleep(0.5)
        _buzz(False); time.sleep(0.5)
    _buzz(False)
    _alarm_active = False
    log.info("기상 알람 종료")


def _stop_alarm(channel=None):
    global _alarm_active
    if _alarm_active:
        _alarm_active = False
        log.info("버튼으로 기상 알람 해제")


if GPIO_AVAILABLE:
    GPIO.add_event_detect(BUTTON_PIN, GPIO.FALLING, callback=_stop_alarm, bouncetime=300)

# ─────────────────────────────────────
#  Firestore 문서 -> UI 데이터 변환
# ─────────────────────────────────────


def doc_to_ui_data(doc_dict: dict) -> dict:
    return {
        "wakeUpTime":       doc_dict.get("wakeUpTime",       None),
        "classStartTime":   doc_dict.get("classStartTime",   "09:00"),
        "className":        doc_dict.get("className",        "수업"),
        "departureTime":    doc_dict.get("departureTime",    "08:20"),
        "prepStartTime":    doc_dict.get("prepStartTime",    "07:50"),
        "taxiDeadline":     doc_dict.get("taxiDeadline",     "08:35"),
        "travelMinutes":    doc_dict.get("travelMinutes",    25),
        "weatherCondition": doc_dict.get("weatherCondition", "맑음"),
        "weatherDelay":     doc_dict.get("weatherDelay",     0),
        "busNextMinutes":   doc_dict.get("busNextMinutes",   None),
    }

# ─────────────────────────────────────
#  상태 결정 (timer_ui.html 로직 미러)
# ─────────────────────────────────────


def _time_to_mins(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def _determine_state(now_mins: float, data: dict) -> str:
    dep    = _time_to_mins(data.get("departureTime", "08:20"))
    taxi   = _time_to_mins(data.get("taxiDeadline",  "08:35"))
    travel = int(data.get("travelMinutes", 25))
    if now_mins >= taxi + travel: return "give_up"
    if now_mins >= dep:           return "late"
    if now_mins >= dep - 10:      return "hurry"
    return "relaxed"

# ─────────────────────────────────────
#  WebSocket 서버
# ─────────────────────────────────────

connected_clients: set = set()
latest_data: dict = {}


async def ws_handler(websocket, path=None):
    connected_clients.add(websocket)
    log.info(f"클라이언트 연결: {websocket.remote_address}")
    try:
        if latest_data:
            await websocket.send(json.dumps(latest_data, ensure_ascii=False))
        await websocket.wait_closed()
    finally:
        connected_clients.discard(websocket)


async def broadcast(data: dict):
    if not connected_clients:
        return
    msg = json.dumps(data, ensure_ascii=False)
    await asyncio.gather(
        *[c.send(msg) for c in list(connected_clients)],
        return_exceptions=True,
    )

# ─────────────────────────────────────
#  Firestore 리스너
# ─────────────────────────────────────


def start_firestore_listener(loop: asyncio.AbstractEventLoop):
    db = firestore.client()
    doc_ref = db.document(FIRESTORE_DOC_PATH)

    def on_snapshot(doc_snapshot, changes, read_time):
        for doc in doc_snapshot:
            if doc.exists:
                ui_data = doc_to_ui_data(doc.to_dict())
                log.info(
                    f"Firestore 갱신: 기상={ui_data['wakeUpTime']}, "
                    f"출발={ui_data['departureTime']}, 이동={ui_data['travelMinutes']}분"
                )
                global latest_data
                latest_data = ui_data
                try:
                    with open(STATE_FILE, "w", encoding="utf-8") as f:
                        json.dump(ui_data, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    log.warning(f"상태 파일 기록 실패: {e}")
                asyncio.run_coroutine_threadsafe(broadcast(ui_data), loop)

    doc_ref.on_snapshot(on_snapshot)
    log.info(f"Firestore 구독 시작: {FIRESTORE_DOC_PATH}")

# ─────────────────────────────────────
#  알람 체커 스레드 (1초 간격)
# ─────────────────────────────────────


def start_alarm_checker():
    """
    매 초마다:
    - 현재 시각 == wakeUpTime → 기상 알람 시작
    - 상태가 바뀌었을 때 → '삐 삐' 두 번
    """
    prev_state: str | None = None
    wake_done_keys: set    = set()   # 당일 알람 중복 방지
    last_beep_min: int     = -1      # 같은 분에 두 번 울리지 않도록

    while True:
        try:
            now      = datetime.now()
            now_mins = now.hour * 60 + now.minute

            if latest_data:
                # ── 기상 알람 ──
                wake_time = latest_data.get("wakeUpTime")
                if wake_time and now.second < 5:
                    wake_key = f"{now.strftime('%Y-%m-%d')}_{wake_time}"
                    if (now_mins == _time_to_mins(wake_time) and
                            wake_key not in wake_done_keys):
                        wake_done_keys.add(wake_key)
                        threading.Thread(target=wake_up_alarm, daemon=True).start()

                # ── 상태 전환 감지 ──
                current_state = _determine_state(now_mins, latest_data)
                if (prev_state is not None
                        and prev_state != current_state
                        and current_state != "give_up"
                        and now_mins != last_beep_min):
                    last_beep_min = now_mins
                    log.info(f"상태 전환: {prev_state} → {current_state}")
                    threading.Thread(target=double_beep, daemon=True).start()
                prev_state = current_state

        except Exception as e:
            log.warning(f"알람 체커 오류: {e}")

        time.sleep(1)

# ─────────────────────────────────────
#  메인
# ─────────────────────────────────────


def init_firebase():
    if not firebase_admin._apps:
        cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
        firebase_admin.initialize_app(cred)
        log.info("Firebase 초기화 완료")


async def main():
    init_firebase()
    loop = asyncio.get_event_loop()
    threading.Thread(target=start_firestore_listener, args=(loop,), daemon=True).start()
    threading.Thread(target=start_alarm_checker, daemon=True).start()
    log.info(f"WebSocket 서버 시작: ws://{WS_HOST}:{WS_PORT}")
    async with websockets.serve(ws_handler, WS_HOST, WS_PORT):
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        if GPIO_AVAILABLE:
            GPIO.cleanup()
