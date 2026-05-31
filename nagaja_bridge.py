"""
nagaja_bridge.py — Firestore <-> HTML UI 브리지 + 부저 알람
나가자 프로젝트 | Raspberry Pi 실행 스크립트

동작 방식:
  블루투스(RFCOMM)로 모바일 앱에서 사용자 ID를 수신한 뒤,
  Firestore users/{userId}/dailyPlans 컬렉션을 실시간 구독합니다.
  WebSocket으로 timer_ui.html에 데이터를 전송하며,
  기상 시각에 부저 알람을, 상태 전환 시점에 '삐 삐' 두 번을 울립니다.

사용법:
  cd ~/nagaja/ui
  source ~/nagaja/venv/bin/activate
  python3 nagaja_bridge.py

필수 패키지:
  pip install firebase-admin websockets RPi.GPIO PyBluez

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
from datetime import datetime, timezone, timedelta

import websockets
import firebase_admin
from firebase_admin import credentials, firestore

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    GPIO_AVAILABLE = False

try:
    import bluetooth
    BT_AVAILABLE = True
except ImportError:
    BT_AVAILABLE = False

# ─────────────────────────────────────
#  설정
# ─────────────────────────────────────

SERVICE_ACCOUNT_PATH = os.path.expanduser("~/nagaja/serviceAccountKey.json")
USER_CONFIG_PATH     = os.path.expanduser("~/nagaja/user_config.json")
BT_UUID              = "00001101-0000-1000-8000-00805F9B34FB"  # SPP UUID

WS_HOST    = "localhost"
WS_PORT    = 8765
STATE_FILE = "/tmp/nagaja_state.json"

BUZZER_PIN         = 18
BUTTON_PIN         = 17
WAKE_ALARM_SECONDS = 120

KST = timezone(timedelta(hours=9))

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("nagaja")

# ─────────────────────────────────────
#  사용자 ID 관리
# ─────────────────────────────────────

_current_user_id: str | None = None


def load_user_id() -> str | None:
    try:
        with open(USER_CONFIG_PATH) as f:
            return json.load(f).get("userId")
    except Exception:
        return None


def save_user_id(uid: str):
    try:
        os.makedirs(os.path.dirname(USER_CONFIG_PATH), exist_ok=True)
        with open(USER_CONFIG_PATH, "w") as f:
            json.dump({"userId": uid}, f)
    except Exception as e:
        log.warning(f"사용자 설정 저장 실패: {e}")

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
#  시간 유틸
# ─────────────────────────────────────


def today_kst_str() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d")


def _ts_to_utc(ts) -> datetime | None:
    """Firestore DatetimeWithNanoseconds 또는 구형 Timestamp → UTC datetime."""
    if ts is None:
        return None
    if isinstance(ts, datetime):
        return ts.astimezone(timezone.utc) if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromtimestamp(ts.seconds, tz=timezone.utc)
    except Exception:
        return None


def timestamp_to_kst_str(ts) -> str | None:
    """Firestore Timestamp → KST 'HH:MM' 문자열."""
    dt_utc = _ts_to_utc(ts)
    if dt_utc is None:
        return None
    return dt_utc.astimezone(KST).strftime("%H:%M")


def _time_to_mins(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)

# ─────────────────────────────────────
#  Firestore 문서 → UI 데이터 변환
# ─────────────────────────────────────

WEATHER_TYPE_KR = {
    "CLEAR": "맑음", "RAIN": "비", "SNOW": "눈", "CLOUDY": "흐림",
}


def doc_to_ui_data(doc_dict: dict) -> dict:
    alarm_ts  = doc_dict.get("finalAlarmTime")
    depart_ts = doc_dict.get("finalDepartureTime")
    alarm_str = timestamp_to_kst_str(alarm_ts)
    return {
        "wakeUpTime":             alarm_str,
        "departureTime":          timestamp_to_kst_str(depart_ts),
        "prepStartTime":          alarm_str,
        "classStartTime":         doc_dict.get("classTime", "--:--"),
        "className":              doc_dict.get("title", "수업"),
        "travelMinutes":          int(doc_dict.get("predictedTravelMinutes",
                                      doc_dict.get("defaultTravelMinutes", 30))),
        "prepMinutes":            int(doc_dict.get("prepMinutes", 30)),
        "weatherCondition":       WEATHER_TYPE_KR.get(
                                      doc_dict.get("weatherType", "CLEAR"), "맑음"),
        "weatherDelay":           int(doc_dict.get("weatherAdjustMinutes", 0)),
        "congestionDelay":        int(doc_dict.get("congestionAdjustMinutes", 0)),
        "displayColor":           doc_dict.get("displayColor", "GREEN"),
        "remainingMarginMinutes": int(doc_dict.get("remainingMarginMinutes", 0)),
        "planStatus":             doc_dict.get("planStatus", "CALCULATED"),
        "taxiDeadline":           None,
        "busNextMinutes":         None,
    }

# ─────────────────────────────────────
#  상태 결정
# ─────────────────────────────────────


def _determine_state(data: dict) -> str:
    color = data.get("displayColor", "GREEN")
    if color == "RED":    return "late"
    if color == "YELLOW": return "hurry"
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

_watch_handle = [None]


def start_firestore_listener(loop: asyncio.AbstractEventLoop):
    db = firestore.client()

    def subscribe_today(uid: str):
        if _watch_handle[0]:
            try:
                _watch_handle[0].unsubscribe()
            except Exception:
                pass

        today = today_kst_str()
        col_ref = (db.collection("users")
                     .document(uid)
                     .collection("dailyPlans")
                     .where("planDate", "==", today))

        def on_snapshot(query_snapshot, changes, read_time):
            global latest_data
            docs = [d for d in query_snapshot if d.exists]
            if not docs:
                log.warning(f"오늘({today}) 플랜 없음")
                return

            # 여러 플랜 중 다음 수업 선택
            now_utc = datetime.now(timezone.utc)
            candidates = []
            for d in docs:
                dd = d.to_dict()
                alarm_ts = dd.get("finalAlarmTime")
                if alarm_ts:
                    alarm_utc = _ts_to_utc(alarm_ts)
                    if alarm_utc is None:
                        continue
                    candidates.append((alarm_utc, dd))
            candidates.sort(key=lambda x: x[0])

            chosen = next((dd for t, dd in candidates if t >= now_utc), None)
            if chosen is None and candidates:
                chosen = candidates[-1][1]
            if chosen is None:
                log.warning("finalAlarmTime이 없는 플랜만 존재")
                return

            ui_data = doc_to_ui_data(chosen)
            log.info(
                f"Firestore 갱신: 알람={ui_data['wakeUpTime']}, "
                f"출발={ui_data['departureTime']}, "
                f"상태={ui_data['displayColor']}, "
                f"이동={ui_data['travelMinutes']}분"
            )
            latest_data = ui_data
            try:
                with open(STATE_FILE, "w", encoding="utf-8") as f:
                    json.dump(ui_data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                log.warning(f"상태 파일 기록 실패: {e}")
            asyncio.run_coroutine_threadsafe(broadcast(ui_data), loop)

        _watch_handle[0] = col_ref.on_snapshot(on_snapshot)
        log.info(f"Firestore 구독: users/{uid}/dailyPlans planDate={today}")

    def listener_thread():
        last_uid  = None
        last_date = None
        while True:
            uid = _current_user_id
            if uid:
                cur_date = today_kst_str()
                if uid != last_uid or cur_date != last_date:
                    subscribe_today(uid)
                    last_uid  = uid
                    last_date = cur_date
                time.sleep(60)
            else:
                log.info("사용자 ID 대기 중... (블루투스로 앱에서 연결하세요)")
                time.sleep(5)

    threading.Thread(target=listener_thread, daemon=True).start()

# ─────────────────────────────────────
#  알람 체커 스레드 (1초 간격)
# ─────────────────────────────────────


def start_alarm_checker():
    prev_state: str | None = None
    wake_done_keys: set    = set()
    last_beep_min: int     = -1

    while True:
        try:
            now_kst  = datetime.now(KST)
            now_mins = now_kst.hour * 60 + now_kst.minute

            if latest_data:
                # ── 기상 알람 ──
                wake_time = latest_data.get("wakeUpTime")
                if wake_time and now_kst.second < 5:
                    wake_key = f"{now_kst.strftime('%Y-%m-%d')}_{wake_time}"
                    if (now_mins == _time_to_mins(wake_time)
                            and wake_key not in wake_done_keys):
                        wake_done_keys.add(wake_key)
                        threading.Thread(target=wake_up_alarm, daemon=True).start()

                # ── 상태 전환 감지 ──
                current_state = _determine_state(latest_data)
                if (prev_state is not None
                        and prev_state != current_state
                        and now_mins != last_beep_min):
                    last_beep_min = now_mins
                    log.info(f"상태 전환: {prev_state} → {current_state}")
                    threading.Thread(target=double_beep, daemon=True).start()
                prev_state = current_state

        except Exception as e:
            log.warning(f"알람 체커 오류: {e}")

        time.sleep(1)

# ─────────────────────────────────────
#  블루투스 RFCOMM 서버
# ─────────────────────────────────────


def start_bluetooth_server():
    global _current_user_id
    if not BT_AVAILABLE:
        log.warning("PyBluez 없음 — 블루투스 기능 비활성화 (pip install PyBluez)")
        return

    try:
        server_sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
        server_sock.bind(("", bluetooth.PORT_ANY))
        server_sock.listen(1)
        bluetooth.advertise_service(server_sock, "NaGaJa", BT_UUID)
        log.info(f"블루투스 서버 대기 중 (채널 {server_sock.getsockname()[1]})")
    except Exception as e:
        log.warning(f"블루투스 서버 시작 실패: {e}")
        return

    while True:
        try:
            client_sock, addr = server_sock.accept()
            log.info(f"블루투스 연결: {addr}")
            data = b""
            while True:
                chunk = client_sock.recv(1024)
                if not chunk:
                    break
                data += chunk
                if b"}" in data:
                    break
            msg = json.loads(data.decode())
            if msg.get("action") == "identify" and "userId" in msg:
                new_uid = msg["userId"]
                log.info(f"사용자 ID 수신: {new_uid}")
                _current_user_id = new_uid
                save_user_id(new_uid)
                client_sock.send(
                    json.dumps({"status": "ok", "userId": new_uid}).encode()
                )
            client_sock.close()
        except Exception as e:
            log.warning(f"블루투스 처리 오류: {e}")

# ─────────────────────────────────────
#  메인
# ─────────────────────────────────────


def init_firebase():
    if not firebase_admin._apps:
        cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
        firebase_admin.initialize_app(cred)
        log.info("Firebase 초기화 완료")


async def main():
    global _current_user_id
    init_firebase()

    _current_user_id = load_user_id()
    if _current_user_id:
        log.info(f"저장된 사용자 ID 로드: {_current_user_id}")
    else:
        log.info("사용자 ID 없음 — 블루투스로 앱에서 연결하세요")

    loop = asyncio.get_event_loop()
    threading.Thread(target=start_firestore_listener, args=(loop,), daemon=True).start()
    threading.Thread(target=start_alarm_checker, daemon=True).start()
    threading.Thread(target=start_bluetooth_server, daemon=True).start()

    log.info(f"WebSocket 서버 시작: ws://{WS_HOST}:{WS_PORT}")
    async with websockets.serve(ws_handler, WS_HOST, WS_PORT):
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        if GPIO_AVAILABLE:
            GPIO.cleanup()
