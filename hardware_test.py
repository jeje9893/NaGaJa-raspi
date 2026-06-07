"""
hardware_test.py — 라즈베리파이 부저/버튼 하드웨어 테스트 서버
나가자 프로젝트 | Raspberry Pi 하드웨어 점검용 (Firebase 불필요)

목적:
  실기기(라즈베리파이)에서 부저(GPIO18)와 버튼(GPIO17)이 실제로
  동작하는지 화면의 테스트 버튼만으로 확인한다.
    - 화면 버튼 → 부저를 즉시 울림(삐삐 / 기상알람 / 수동 ON·OFF)
    - 실제 물리 버튼(GPIO17)을 누르면 → 화면에 즉시 표시 + 알람 해제

  nagaja_bridge.py 의 부저/버튼 코드를 그대로 재사용하므로,
  이 테스트가 통과하면 실제 브리지의 알람도 동일하게 동작한다.

실행:
  cd ~/nagaja/ui
  source ~/nagaja/venv/bin/activate
  python3 hardware_test.py
  # 다른 창(또는 키오스크 브라우저)에서 hardware_test.html 열기
  #   chromium-browser --kiosk hardware_test.html

필수 패키지:
  pip install websockets RPi.GPIO
  (RPi.GPIO 가 없으면 시뮬레이션 모드로 UI만 점검 가능 — 데스크탑에서도 실행됨)

GPIO 핀 (BCM, nagaja_bridge.py 와 동일):
  BUZZER_PIN = 18  — 능동 부저 (+)
  BUTTON_PIN = 17  — 기상 알람 해제 버튼 (GND 쪽으로 누름, 내부 풀업)
"""

import asyncio
import json
import logging
import threading
import time

import websockets

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    GPIO_AVAILABLE = False

# ─────────────────────────────────────
#  설정 (nagaja_bridge.py 와 동일)
# ─────────────────────────────────────

WS_HOST = "localhost"
WS_PORT = 8765

BUZZER_PIN         = 18
BUTTON_PIN         = 17
WAKE_ALARM_SECONDS = 120   # 기상 알람 최대 지속 시간

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("hwtest")

# ─────────────────────────────────────
#  WebSocket (양방향) — UI 명령 수신 + 이벤트 송신
# ─────────────────────────────────────

connected_clients: set = set()
MAIN_LOOP: asyncio.AbstractEventLoop | None = None


def _emit(obj: dict):
    """다른 스레드(GPIO 콜백·알람 스레드)에서도 안전하게 UI로 이벤트 전송."""
    if MAIN_LOOP is None or MAIN_LOOP.is_closed():
        return
    asyncio.run_coroutine_threadsafe(_broadcast(obj), MAIN_LOOP)


async def _broadcast(obj: dict):
    if not connected_clients:
        return
    msg = json.dumps(obj, ensure_ascii=False)
    await asyncio.gather(
        *[c.send(msg) for c in list(connected_clients)],
        return_exceptions=True,
    )


def emit_log(msg: str):
    log.info(msg)
    _emit({"event": "log", "msg": msg})

# ─────────────────────────────────────
#  부저 제어 (nagaja_bridge.py 와 동일 + 화면 표시용 이벤트 추가)
# ─────────────────────────────────────

_alarm_active = False
_alarm_lock   = threading.Lock()
_buzzer_on    = False


def _buzz(on: bool):
    """부저 ON/OFF + 화면 표시를 위한 상태 브로드캐스트."""
    global _buzzer_on
    _buzzer_on = bool(on)
    if GPIO_AVAILABLE:
        GPIO.output(BUZZER_PIN, GPIO.HIGH if on else GPIO.LOW)
    _emit({"event": "buzzer", "on": _buzzer_on})


def double_beep():
    """상태 전환 시 '삐 삐' 두 번 (실제 브리지의 double_beep 과 동일)."""
    emit_log("부저: 삐삐 (double_beep)")
    _buzz(True);  time.sleep(0.15)
    _buzz(False); time.sleep(0.20)
    _buzz(True);  time.sleep(0.15)
    _buzz(False)


def wake_up_alarm():
    """기상 알람: 최대 WAKE_ALARM_SECONDS 초 또는 버튼 해제까지 (실제 브리지와 동일)."""
    global _alarm_active
    with _alarm_lock:
        if _alarm_active:
            return
        _alarm_active = True

    emit_log("기상 알람 시작 — 부저가 울립니다 (버튼을 누르거나 '정지'로 해제)")
    _emit({"event": "alarm", "active": True})
    deadline = time.time() + WAKE_ALARM_SECONDS
    while _alarm_active and time.time() < deadline:
        _buzz(True);  time.sleep(0.5)
        _buzz(False); time.sleep(0.5)
    _buzz(False)
    _alarm_active = False
    _emit({"event": "alarm", "active": False})
    emit_log("기상 알람 종료")


def stop_alarm(source: str = "버튼"):
    """알람 해제 (물리 버튼 GPIO17 또는 화면 '정지' 버튼)."""
    global _alarm_active
    if _alarm_active:
        _alarm_active = False
        emit_log(f"{source}(으)로 기상 알람 해제")
    else:
        emit_log(f"{source} 입력 (해제할 알람 없음)")

# ─────────────────────────────────────
#  물리 버튼 (GPIO17) 콜백
# ─────────────────────────────────────


def _on_button(channel=None):
    """실제 버튼 누름 → 화면에 즉시 표시 + 알람 해제."""
    emit_log("✅ 물리 버튼(GPIO17) 눌림 감지")
    _emit({"event": "button", "ts": time.strftime("%H:%M:%S")})
    stop_alarm(source="물리 버튼")

# ─────────────────────────────────────
#  GPIO 초기화
# ─────────────────────────────────────


def init_gpio():
    if not GPIO_AVAILABLE:
        log.warning("RPi.GPIO 없음 — 시뮬레이션 모드 (UI/통신만 점검, 실제 부저는 안 울림)")
        return
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BUZZER_PIN, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.add_event_detect(BUTTON_PIN, GPIO.FALLING, callback=_on_button, bouncetime=300)
    log.info(f"GPIO 초기화 완료 (부저={BUZZER_PIN}, 버튼={BUTTON_PIN})")

# ─────────────────────────────────────
#  UI 명령 처리
# ─────────────────────────────────────


def handle_command(cmd: str):
    if cmd == "double_beep":
        threading.Thread(target=double_beep, daemon=True).start()
    elif cmd == "wake_alarm":
        threading.Thread(target=wake_up_alarm, daemon=True).start()
    elif cmd == "stop_alarm":
        stop_alarm(source="화면 정지 버튼")
    elif cmd == "buzz_on":
        emit_log("수동 부저 ON")
        _buzz(True)
    elif cmd == "buzz_off":
        emit_log("수동 부저 OFF")
        _buzz(False)
    elif cmd == "ping":
        pass
    else:
        emit_log(f"알 수 없는 명령: {cmd}")


async def ws_handler(websocket, path=None):
    connected_clients.add(websocket)
    log.info(f"화면 연결됨: {websocket.remote_address}")
    # 접속 즉시 현재 상태/환경 안내
    await websocket.send(json.dumps({
        "event": "hello",
        "gpio": GPIO_AVAILABLE,
        "buzzerPin": BUZZER_PIN,
        "buttonPin": BUTTON_PIN,
        "buzzerOn": _buzzer_on,
        "alarmActive": _alarm_active,
    }, ensure_ascii=False))
    try:
        async for raw in websocket:
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            cmd = msg.get("cmd")
            if cmd:
                handle_command(cmd)
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        connected_clients.discard(websocket)
        log.info("화면 연결 해제")

# ─────────────────────────────────────
#  메인
# ─────────────────────────────────────


async def main():
    global MAIN_LOOP
    MAIN_LOOP = asyncio.get_event_loop()
    init_gpio()
    mode = "실기기(GPIO)" if GPIO_AVAILABLE else "시뮬레이션"
    log.info(f"[{mode}] 하드웨어 테스트 서버 시작: ws://{WS_HOST}:{WS_PORT}")
    log.info("브라우저에서 hardware_test.html 을 열어 테스트하세요")
    async with websockets.serve(ws_handler, WS_HOST, WS_PORT):
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    finally:
        if GPIO_AVAILABLE:
            GPIO.output(BUZZER_PIN, GPIO.LOW)
            GPIO.cleanup()
            log.info("GPIO 정리 완료")
