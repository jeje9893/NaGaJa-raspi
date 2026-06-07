"""
demo_bridge.py — 구동화면 캡처(카메라 촬영)용 데모 브리지
나가자 프로젝트 | Raspberry Pi 시연/촬영용 (Firebase 불필요)

목적:
  라즈베리파이 7인치 화면에 timer_ui.html 을 띄워 두고, 상태별(여유·나가자·
  지각·악천후·폴백·기상알람) 화면을 안정적으로 보여 줘 카메라로 찍기 좋게 한다.
    - 수정하지 않은 원본 timer_ui.html 을 그대로 사용 (WebSocket 연결)
    - 각 장면의 시각을 '현재 시각 기준'으로 계산 → 타이머 링 포인터가 정확한 구간에 위치
    - 기상알람 장면에서는 실제 부저(GPIO)도 함께 울려 알람 동작을 촬영 가능

실행 (라즈베리파이):
  # 1) 데모 브리지 실행
  python3 demo_bridge.py                # 키보드로 장면 전환 (촬영에 가장 좋음)
  python3 demo_bridge.py --cycle 12     # 12초마다 자동 순환
  python3 demo_bridge.py --scene hurry  # 한 장면만 고정
  python3 demo_bridge.py --passive      # 수동형 부저(XCMT12D2001AP) 사용

  # 2) 다른 창/키오스크에서 화면 띄우기
  chromium --kiosk timer_ui.html

키보드 명령 (기본 모드에서 숫자/문자 입력 후 Enter):
  1 여유   2 나가자   3 지각위기   4 비오는날   5 폴백   6 기상알람(부저)
  a 부저 울리기   s 부저 정지   l 장면 목록   q 종료

필수 패키지:
  pip install websockets gpiozero lgpio
  (부저 없이 화면만 촬영하려면 gpiozero/lgpio 없어도 동작 — 시뮬레이션 모드)
"""

import asyncio
import json
import logging
import os
import sys
import threading
import time
from datetime import datetime

import websockets

# ── GPIO(부저) — 라즈베리파이 5: gpiozero + lgpio ──────────────
os.environ.setdefault("GPIOZERO_PIN_FACTORY", "lgpio")
try:
    from gpiozero import Buzzer, Button, PWMOutputDevice
    GPIOZERO_IMPORTED = True
except ImportError:
    GPIOZERO_IMPORTED = False

# ─────────────────────────────────────
#  설정
# ─────────────────────────────────────

WS_HOST = "localhost"
WS_PORT = 8765

BUZZER_PIN = 18
BUTTON_PIN = 17

# 부저 구동 모드 (hardware_test.py 와 동일 규칙)
PASSIVE_MODE = ("--passive" in sys.argv)
PASSIVE_FREQ = 2048   # XCMT12D2001AP 공진 주파수
PASSIVE_DUTY = 0.20   # 수동형 듀티(전류 제한)
DEMO_ALARM_SECONDS = 30  # 데모 알람 최대 지속(촬영용)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("demo")

# ─────────────────────────────────────
#  장면(Scene) 정의 — 현재 시각 기준 상대 계산
# ─────────────────────────────────────


def _ms(total_min: int) -> str:
    """분(하루 기준)을 'HH:MM' 으로."""
    total_min %= 1440
    return f"{total_min // 60:02d}:{total_min % 60:02d}"


def build_scene(name: str) -> dict:
    """현재 시각을 기준으로 장면 데이터를 생성. 링 포인터가 의도한 구간에 오도록."""
    now = datetime.now()
    base = now.hour * 60 + now.minute  # 현재 분

    if name == "relaxed":   # 여유 (GREEN)
        prep, dep, travel = base - 5, base + 20, 22
        return _scene(prep, dep, travel, "운영체제", "GREEN",
                      weather=("맑음", 0), congestion=0, margin=20)

    if name == "hurry":     # 나가자 (YELLOW)
        prep, dep, travel = base - 24, base + 6, 22
        return _scene(prep, dep, travel, "자료구조", "YELLOW",
                      weather=("맑음", 0), congestion=5, margin=5)

    if name == "late":      # 지각위기 (RED)
        prep, dep, travel = base - 35, base - 2, 22
        return _scene(prep, dep, travel, "알고리즘", "RED",
                      weather=("맑음", 0), congestion=8, margin=-3)

    if name == "rainy":     # 비오는날 + 혼잡 (GREEN, 보정 카드 강조)
        prep, dep, travel = base - 5, base + 18, 30
        return _scene(prep, dep, travel, "캡스톤디자인", "GREEN",
                      weather=("비", 10), congestion=7, margin=15)

    if name == "fallback":  # AI 예측 실패 → 기본값
        prep, dep, travel = base - 5, base + 20, 30
        s = _scene(prep, dep, travel, "데이터베이스", "GREEN",
                   weather=("맑음", 0), congestion=0, margin=18)
        s["planStatus"] = "FALLBACK"
        return s

    if name == "wake":      # 기상알람 (지금이 기상 시각) + 부저
        prep, dep, travel = base, base + 60, 22
        return _scene(prep, dep, travel, "1교시 강의", "GREEN",
                      weather=("맑음", 0), congestion=0, margin=38,
                      wake_at=base)

    # 알 수 없는 이름 → 여유
    return build_scene("relaxed")


def _scene(prep, dep, travel, title, color, weather, congestion, margin, wake_at=None):
    wcond, wdelay = weather
    return {
        "wakeUpTime":             _ms(wake_at if wake_at is not None else prep),
        "departureTime":          _ms(dep),
        "prepStartTime":          _ms(prep),
        "classStartTime":         _ms(dep + travel),
        "className":              title,
        "travelMinutes":          travel,
        "prepMinutes":            dep - prep if dep - prep > 0 else 25,
        "weatherCondition":       wcond,
        "weatherDelay":           wdelay,
        "congestionDelay":        congestion,
        "displayColor":           color,
        "remainingMarginMinutes": margin,
        "planStatus":             "CALCULATED",
        "taxiDeadline":           None,
        "busNextMinutes":         None,
    }


SCENES = {
    "1": ("relaxed",  "여유 (GREEN)"),
    "2": ("hurry",    "나가자 (YELLOW)"),
    "3": ("late",     "지각위기 (RED)"),
    "4": ("rainy",    "비오는날 + 혼잡"),
    "5": ("fallback", "폴백 (AI 예측 실패)"),
    "6": ("wake",     "기상알람 (부저 울림)"),
}
SCENE_ORDER = ["1", "2", "3", "4", "5", "6"]

# ─────────────────────────────────────
#  WebSocket
# ─────────────────────────────────────

connected_clients: set = set()
current_data: dict = build_scene("relaxed")
current_label: str = "여유 (GREEN)"
MAIN_LOOP: asyncio.AbstractEventLoop | None = None


async def _broadcast(data: dict):
    if not connected_clients:
        return
    msg = json.dumps(data, ensure_ascii=False)
    await asyncio.gather(
        *[c.send(msg) for c in list(connected_clients)],
        return_exceptions=True,
    )


def show_scene(key: str):
    """장면 전환 → 모든 화면에 송출. (key 는 '1'~'6')"""
    global current_data, current_label
    if key not in SCENES:
        return
    name, label = SCENES[key]
    current_data = build_scene(name)
    current_label = label
    log.info(f"▶ 장면: {label}")
    if MAIN_LOOP:
        asyncio.run_coroutine_threadsafe(_broadcast(current_data), MAIN_LOOP)
    if name == "wake":
        start_alarm()  # 기상알람 장면은 부저도 울림


async def ws_handler(websocket, path=None):
    connected_clients.add(websocket)
    log.info(f"화면 연결됨: {websocket.remote_address}")
    try:
        await websocket.send(json.dumps(current_data, ensure_ascii=False))
        await websocket.wait_closed()
    finally:
        connected_clients.discard(websocket)
        log.info("화면 연결 해제")

# ─────────────────────────────────────
#  부저 (gpiozero, active/passive)
# ─────────────────────────────────────

GPIO_AVAILABLE = False
buzzer = None
_alarm_active = False
_alarm_lock = threading.Lock()


def init_gpio():
    global GPIO_AVAILABLE, buzzer
    if not GPIOZERO_IMPORTED:
        log.warning("gpiozero 없음 — 부저 없이 화면만 시연 (pip install gpiozero lgpio)")
        return
    try:
        if PASSIVE_MODE:
            buzzer = PWMOutputDevice(BUZZER_PIN, frequency=PASSIVE_FREQ, initial_value=0.0)
            mode = f"수동형/PWM {PASSIVE_FREQ}Hz duty{int(PASSIVE_DUTY*100)}%"
        else:
            buzzer = Buzzer(BUZZER_PIN)
            mode = "능동형/ON·OFF"
        # 해제 버튼: 누르면 알람 정지
        try:
            btn = Button(BUTTON_PIN, pull_up=True, bounce_time=0.05)
            btn.when_pressed = lambda *_: stop_alarm("버튼")
            globals()["_button"] = btn  # GC 방지
        except Exception as e:
            log.warning(f"버튼 초기화 생략: {e}")
        GPIO_AVAILABLE = True
        log.info(f"GPIO 초기화 완료 (부저={BUZZER_PIN}[{mode}], 버튼={BUTTON_PIN})")
    except Exception as e:
        GPIO_AVAILABLE = False
        log.warning(f"GPIO 초기화 실패 — 부저 없이 진행: {e}")


def _buzz(on: bool):
    if GPIO_AVAILABLE and buzzer is not None:
        if PASSIVE_MODE:
            buzzer.value = PASSIVE_DUTY if on else 0.0
        else:
            if on:
                buzzer.on()
            else:
                buzzer.off()


def _alarm_loop():
    global _alarm_active
    log.info("🔔 데모 알람 시작 (s=정지, 버튼=정지)")
    deadline = time.time() + DEMO_ALARM_SECONDS
    while _alarm_active and time.time() < deadline:
        _buzz(True);  time.sleep(0.5)
        _buzz(False); time.sleep(0.5)
    _buzz(False)
    _alarm_active = False
    log.info("🔕 데모 알람 종료")


def start_alarm():
    global _alarm_active
    with _alarm_lock:
        if _alarm_active:
            return
        _alarm_active = True
    threading.Thread(target=_alarm_loop, daemon=True).start()


def stop_alarm(src: str = "명령"):
    global _alarm_active
    if _alarm_active:
        _alarm_active = False
        log.info(f"{src}(으)로 알람 정지")

# ─────────────────────────────────────
#  키보드 / 자동순환 컨트롤러
# ─────────────────────────────────────

MENU = (
    "\n──────── 촬영용 장면 메뉴 ────────\n"
    " 1 여유    2 나가자   3 지각위기\n"
    " 4 비오는날 5 폴백     6 기상알람(부저)\n"
    " a 부저울림  s 부저정지  l 메뉴  q 종료\n"
    " (입력 후 Enter)\n"
    "──────────────────────────────────"
)


def keyboard_loop():
    print(MENU, flush=True)
    for raw in sys.stdin:
        cmd = raw.strip().lower()
        if not cmd:
            continue
        if cmd in SCENES:
            show_scene(cmd)
        elif cmd == "a":
            start_alarm()
        elif cmd == "s":
            stop_alarm("화면 명령")
        elif cmd == "l":
            print(MENU, flush=True)
        elif cmd == "q":
            log.info("종료합니다")
            os._exit(0)
        else:
            print("  ? 1~6 / a / s / l / q 중 입력", flush=True)


def cycle_loop(seconds: float):
    log.info(f"자동 순환 모드: {seconds}초 간격 (Ctrl+C 종료)")
    i = 0
    while True:
        key = SCENE_ORDER[i % len(SCENE_ORDER)]
        show_scene(key)
        i += 1
        time.sleep(seconds)

# ─────────────────────────────────────
#  메인
# ─────────────────────────────────────


def _parse_opt(flag: str, default=None):
    if flag in sys.argv:
        idx = sys.argv.index(flag)
        if idx + 1 < len(sys.argv):
            return sys.argv[idx + 1]
    return default


async def main():
    global MAIN_LOOP, current_data, current_label
    MAIN_LOOP = asyncio.get_event_loop()
    init_gpio()

    # 시작 장면 결정
    scene_opt = _parse_opt("--scene")
    if scene_opt:
        # 이름으로 시작 장면 지정 (relaxed/hurry/late/rainy/fallback/wake)
        key = next((k for k, (n, _) in SCENES.items() if n == scene_opt), "1")
        name, current_label = SCENES[key]
        current_data = build_scene(name)

    mode = "수동형 부저" if PASSIVE_MODE else "능동형 부저"
    log.info(f"[{mode}] 데모 브리지 시작: ws://{WS_HOST}:{WS_PORT}")
    log.info("화면: chromium --kiosk timer_ui.html  (timer_ui.html 은 수정 불필요)")

    # 컨트롤러 스레드
    cycle_opt = _parse_opt("--cycle")
    if cycle_opt:
        threading.Thread(target=cycle_loop, args=(float(cycle_opt),), daemon=True).start()
    elif scene_opt:
        log.info(f"고정 장면: {current_label}")
    else:
        threading.Thread(target=keyboard_loop, daemon=True).start()

    async with websockets.serve(ws_handler, WS_HOST, WS_PORT):
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        if GPIO_AVAILABLE and buzzer is not None:
            try:
                buzzer.off()
                buzzer.close()
            except Exception:
                pass
