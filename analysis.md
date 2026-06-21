# 나가자 (NaGaJa) 라즈베리파이 프로젝트 — 상세 분석

> 작성일: 2026-06-05  
> 분석 대상: `C:\Users\JG\Desktop\git\NaGaJa-raspi` (브랜치: `ui`)

---

## 1. 프로젝트 개요

### 이름의 의미

**나가자(NaGaJa)**는 한국어 "나가자!"에서 유래한 이름으로, 지각하지 않도록 제때 집을 나서라는 의미를 담고 있습니다. 대학생이 수업에 늦지 않기 위해 알람이 울리면 바로 "나가자!"를 외치는 장면을 제품 이름에 녹여냈습니다.

### 목적

나가자는 **대학생을 위한 스마트 알람·출발 관리 시스템**입니다. 단순히 시각을 알려주는 알람에서 벗어나, 수업 시간표·이동 경로·날씨·대중교통 혼잡도를 종합적으로 고려해 **최적 기상/출발 시각을 자동 계산**합니다.

### 문제 정의

기존 스마트폰 알람의 한계:
- 매일 수동으로 알람 시각을 조정해야 함
- 날씨나 교통 상황을 반영하지 못함
- 시끄럽기만 하고 정보 전달이 없음

### 해결 방식

나가자는 3개의 레이어로 문제를 해결합니다.

1. **모바일 앱 (Flutter)**: 수업 시간표를 등록하고, Google Maps API + 날씨 API + 혼잡도 데이터를 종합해 최적 알람 시각을 계산합니다.
2. **클라우드 (Firebase)**: 계산된 플랜을 Firestore에 저장하고 Cloud Functions를 통해 실시간으로 갱신합니다.
3. **라즈베리파이 물리 기기**: 침대맡에 놓인 7인치 터치스크린에 시각적 타이머를 표시하고, 부저로 알람을 울립니다.

### 프로젝트 배경

- Firebase 프로젝트 ID: `nagaja-a6a8b`
- Firebase 리전: `asia-northeast3` (서울)
- 플랫폼: Flutter (Android/iOS) + Python (Raspberry Pi)
- Git 브랜치: `main`, `ui`, `dbtest`, `dev`

---

## 2. 시스템 아키텍처

### 전체 구조도 (ASCII 다이어그램)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         사용자 (대학생)                                   │
└────────────────┬────────────────────────────────┬────────────────────────┘
                 │ 앱 설정                          │ 물리 버튼 (알람 해제)
                 ▼                                 ▼
┌───────────────────────────┐      ┌──────────────────────────────────────┐
│    모바일 앱 (Flutter)     │      │        Raspberry Pi 기기              │
│  Android / iOS            │      │  ┌────────────────────────────────┐  │
│                           │      │  │   nagaja_bridge.py             │  │
│  ① 수업 시간표 등록        │      │  │   (Python 3, asyncio)          │  │
│  ② 출발지/목적지 설정      │      │  │                                │  │
│  ③ 이동 수단 선택          │      │  │  ┌─────────┐  ┌─────────────┐ │  │
│  ④ displayColor 계산       │      │  │  │Firestore│  │  WebSocket  │ │  │
│                           │      │  │  │Listener │  │  서버:8765  │ │  │
│  [설정 화면]               │      │  │  └────┬────┘  └──────┬──────┘ │  │
│  "기기 연결 > 물리 알람시계"│      │  │       │              │        │  │
└──────────┬────────────────┘      │  │  ┌────▼────┐  ┌──────▼──────┐ │  │
           │ Bluetooth RFCOMM      │  │  │ 알람 체커│  │timer_ui.html│ │  │
           │ JSON: userId+action   │  │  │(1초 루프)│  │ (Chromium)  │ │  │
           ▼                       │  │  └────┬────┘  └─────────────┘ │  │
┌─────────────────────────────┐    │  │       │ GPIO                   │  │
│    Firebase Cloud           │    │  │  ┌────▼────────────────────┐  │  │
│                             │    │  │  │  GPIO 제어               │  │  │
│  ┌───────────────────────┐  │    │  │  │  BUZZER_PIN=18 (부저)   │  │  │
│  │ Firebase Auth         │  │    │  │  │  BUTTON_PIN=17 (버튼)   │  │  │
│  └───────────────────────┘  │    │  │  └─────────────────────────┘  │  │
│                             │    │  └────────────────────────────────┘  │
│  ┌───────────────────────┐  │    │                                      │
│  │ Firestore DB          │◄─┼────┘    7인치 터치스크린 (800×480px)       │
│  │                       │  │         능동 부저 + 해제 버튼               │
│  │ users/{uid}           │  │                                            │
│  │  ├─ schedules/        │  │                                            │
│  │  └─ dailyPlans/       │  │                                            │
│  └───────────────────────┘  │                                            │
│                             │                                            │
│  ┌───────────────────────┐  │                                            │
│  │ Cloud Functions       │  │                                            │
│  │ /generateDailyPlan    │  │                                            │
│  │ /getTransitData       │  │                                            │
│  │ /getCongestionData    │  │                                            │
│  │ /getWeatherData       │  │                                            │
│  └───────────────────────┘  │                                            │
└─────────────────────────────┘                                            │
                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

### 데이터 흐름

```
[모바일 앱]
  → Cloud Functions /generateDailyPlan 호출
  → (날씨 API + 교통 API + 혼잡도 API 조합)
  → Firestore users/{uid}/dailyPlans/{planId} 생성/갱신

[Raspberry Pi]
  ← Firestore on_snapshot 실시간 수신 (Firestore Listener)
  → WebSocket broadcast → timer_ui.html 화면 갱신
  → 알람 체커: finalAlarmTime 도달 시 GPIO 부저 ON
  → 버튼 누름 → GPIO Interrupt → 부저 OFF

[모바일 앱 → Pi 블루투스 연동]
  앱 "연결" 버튼 → Bluetooth RFCOMM
  → JSON {"userId": "...", "action": "identify"}
  → Pi: userId 저장 → Firestore 구독 대상 변경
```

---

## 3. 기술 스택 상세

### Python (Raspberry Pi)

- **버전**: Python 3.10+ (asyncio, typing `str | None` 구문 사용)
- **주요 라이브러리**:

| 라이브러리 | 버전 | 역할 |
|---|---|---|
| `firebase_admin` | 7.4.0 | Firebase Admin SDK — Firestore 읽기/쓰기 |
| `google-cloud-firestore` | 2.27.0 | Firestore 클라이언트 (on_snapshot 리스너) |
| `websockets` | (requirements에 포함) | WebSocket 서버 (브라우저 UI와 통신) |
| `gpiozero` + `lgpio` | (Pi 전용, 별도 설치) | GPIO 핀 제어 (부저, 버튼) — Pi 5(RP1) 호환 |
| `PyBluez` | 0.23 | Bluetooth RFCOMM 서버 |
| `asyncio` | 표준 라이브러리 | 비동기 이벤트 루프 (WebSocket 서버) |
| `grpcio` | 1.80.0 | Firestore gRPC 통신 기반 |
| `cryptography` | 47.0.0 | Firebase 서비스 계정 인증 |

### Firebase / Firestore

**왜 Firebase를 선택했는가?**

- **실시간 동기화**: `on_snapshot` 리스너를 이용하면 Firestore 문서가 변경될 때 Pi가 즉시 알림을 받음 — polling이 불필요하고 지연이 최소화됨
- **Admin SDK**: 라즈베리파이에서 서비스 계정 키(`serviceAccountKey.json`)만 있으면 ID Token 없이 Firestore에 직접 접근 가능 → 인증 복잡도 절감
- **Cloud Functions 연계**: 날씨·교통·혼잡도 계산 로직을 서버리스 함수로 분리, Pi는 결과만 소비
- **서버리스 스케일**: 사용량 기반 과금, 학생 프로젝트에 적합한 무료 티어

**활용 방식**:
- 모바일 앱이 `dailyPlans` 문서를 매일 생성/갱신
- Pi는 `users/{uid}/dailyPlans` 컬렉션을 `planDate == 오늘` 조건으로 실시간 구독
- 리전: `asia-northeast3` (서울) — 한국 사용자 지연시간 최소화

### HTML/JS (timer_ui.html)

- **역할**: 라즈베리파이의 7인치 디스플레이(800×480px)에 Chromium 키오스크 모드로 표시되는 터치스크린 UI
- **특징**:
  - 순수 Vanilla JS — 외부 프레임워크 미사용
  - SVG 기반 원형 타이머 링 (반지름 200px, stroke-width 20)
  - CSS 변수로 테마 일관성 유지
  - 3가지 데이터 소스 지원: `websocket` | `file` | `demo`
  - Google Fonts `Noto Sans KR` (오프라인 시 Arial 폴백)

### requirements.txt 분석

```
firebase_admin==7.4.0          ← Firebase Admin SDK 핵심
google-cloud-firestore==2.27.0 ← Firestore 클라이언트
grpcio==1.80.0                 ← gRPC 통신 (Firestore 내부)
websockets                     ← WebSocket 서버
PyBluez==0.23                  ← Bluetooth RFCOMM
cryptography==47.0.0           ← 서비스 계정 JWT 서명
httpx==0.28.1                  ← HTTP 클라이언트 (Cloud Functions 호출)
protobuf==6.33.6               ← Firestore 직렬화
```

GPIO 제어는 `gpiozero` + `lgpio`를 사용하며, Pi 전용이라 requirements.txt에서 분리해 별도 설치합니다 (일반 환경 설치 시 오류 방지). 구형 `RPi.GPIO`는 Pi 5(RP1 칩)에서 동작하지 않아 사용하지 않습니다.

---

## 4. 핵심 기능 상세 설명

### 4-1. nagaja_bridge.py 동작 원리

`nagaja_bridge.py`는 프로젝트의 **심장부**입니다. 4개의 비동기/멀티스레드 컴포넌트가 동시에 동작합니다.

#### 전체 실행 흐름

```python
async def main():
    init_gpio()                              # 1. GPIO(부저/버튼) 초기화 (gpiozero)
    init_firebase()                          # 2. Firebase Admin SDK 초기화
    _current_user_id = load_user_id()        # 3. 저장된 userId 로드

    loop = asyncio.get_event_loop()
    # 3개 스레드 동시 시작
    threading.Thread(target=start_firestore_listener, args=(loop,)).start()
    threading.Thread(target=start_alarm_checker).start()
    threading.Thread(target=start_bluetooth_server).start()

    # 메인 스레드: WebSocket 서버 (asyncio)
    async with websockets.serve(ws_handler, "localhost", 8765):
        await asyncio.Future()   # 영구 대기
```

4개의 컴포넌트가 역할을 분담합니다:

| 컴포넌트 | 스레드 | 역할 |
|---|---|---|
| WebSocket 서버 | 메인 (asyncio) | 브라우저 UI와 실시간 통신 |
| Firestore 리스너 | 데몬 스레드 | DB 변경 감지 → 브로드캐스트 |
| 알람 체커 | 데몬 스레드 | 1초 간격으로 시각 비교 → 부저 제어 |
| 블루투스 서버 | 데몬 스레드 | 모바일 앱에서 userId 수신 |

#### Firestore 리스너 — 핵심 코드

```python
def subscribe_today(uid: str):
    today = today_kst_str()   # "2026-06-05" (KST 기준)
    col_ref = (db.collection("users")
                 .document(uid)
                 .collection("dailyPlans")
                 .where("planDate", "==", today))

    def on_snapshot(query_snapshot, changes, read_time):
        # 오늘 플랜 중 가장 빠른 미래 알람 시각 선택
        candidates = []
        for d in query_snapshot:
            alarm_utc = _ts_to_utc(d.to_dict().get("finalAlarmTime"))
            candidates.append((alarm_utc, d.to_dict()))
        candidates.sort(key=lambda x: x[0])

        now_utc = datetime.now(timezone.utc)
        chosen = next((dd for t, dd in candidates if t >= now_utc), None)
        if chosen is None and candidates:
            chosen = candidates[-1][1]   # 마지막 수업 표시

        ui_data = doc_to_ui_data(chosen)
        asyncio.run_coroutine_threadsafe(broadcast(ui_data), loop)

    _watch_handle[0] = col_ref.on_snapshot(on_snapshot)
```

**핵심 설계 포인트**: Firestore 리스너는 별도 스레드에서 동작하지만, WebSocket 브로드캐스트는 asyncio 이벤트 루프에서 실행되어야 합니다. `asyncio.run_coroutine_threadsafe()`가 이 스레드 경계를 안전하게 넘어줍니다.

#### Firestore 문서 → UI 데이터 변환

```python
def doc_to_ui_data(doc_dict: dict) -> dict:
    alarm_ts  = doc_dict.get("finalAlarmTime")
    depart_ts = doc_dict.get("finalDepartureTime")
    alarm_str = timestamp_to_kst_str(alarm_ts)   # UTC Timestamp → KST "HH:MM"
    return {
        "wakeUpTime":    alarm_str,               # "07:30"
        "departureTime": timestamp_to_kst_str(depart_ts),
        "travelMinutes": int(doc_dict.get("predictedTravelMinutes",
                             doc_dict.get("defaultTravelMinutes", 30))),
        "weatherCondition": WEATHER_TYPE_KR.get(
                             doc_dict.get("weatherType", "CLEAR"), "맑음"),
        "displayColor": doc_dict.get("displayColor", "GREEN"),
        ...
    }
```

Firestore의 Timestamp는 UTC로 저장되므로 KST(+9시간) 변환이 필수입니다.

#### 알람 체커 — 1초 루프

```python
def start_alarm_checker():
    prev_state: str | None = None

    while True:
        now_kst  = datetime.now(KST)
        now_mins = now_kst.hour * 60 + now_kst.minute

        if latest_data:
            wake_time = latest_data.get("wakeUpTime")   # "07:30"
            wake_key  = f"{now_kst.strftime('%Y-%m-%d')}_{wake_time}"

            # 기상 알람: 분 단위 일치 + 당일 중복 방지
            if now_mins == _time_to_mins(wake_time) and now_kst.second < 5:
                if wake_key not in wake_done_keys:
                    wake_done_keys.add(wake_key)
                    threading.Thread(target=wake_up_alarm, daemon=True).start()

            # 상태 전환 감지 → 삐삐
            current_state = _determine_state(latest_data)
            if prev_state is not None and prev_state != current_state:
                threading.Thread(target=double_beep, daemon=True).start()
            prev_state = current_state

        time.sleep(1)
```

**중복 방지 설계**: `wake_done_keys` 집합에 `"날짜_시각"` 형태의 키를 저장해 같은 알람이 두 번 울리는 것을 방지합니다. `second < 5` 조건으로 1분 내 재트리거도 방지합니다.

#### 부저 제어

```python
BUZZER_PIN = 18   # BCM 번호
BUTTON_PIN = 17

# gpiozero + lgpio (Pi 5 호환). 핀 팩토리는 lgpio 로 고정
buzzer = Buzzer(BUZZER_PIN)                        # 능동 부저
button = Button(BUTTON_PIN, pull_up=True,
                bounce_time=0.05)                  # 50ms 디바운스
button.when_pressed = _stop_alarm                  # 버튼 → 알람 해제

def wake_up_alarm():
    """기상 알람: 최대 120초 동안 0.5초 간격으로 울림"""
    deadline = time.time() + WAKE_ALARM_SECONDS    # 120초
    while _alarm_active and time.time() < deadline:
        buzzer.on();  time.sleep(0.5)
        buzzer.off(); time.sleep(0.5)

def double_beep():
    """상태 전환 시 삐-삐 두 번"""
    buzzer.on();  time.sleep(0.15)
    buzzer.off(); time.sleep(0.20)
    buzzer.on();  time.sleep(0.15)
    buzzer.off()
```

**능동 부저 + gpiozero**: `Button.when_pressed`(lgpio 엣지 이벤트) 콜백을 사용해 버튼 응답이 즉각적이며 CPU 폴링이 없습니다.

#### 블루투스 RFCOMM 서버

```python
def start_bluetooth_server():
    server_sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
    server_sock.bind(("", bluetooth.PORT_ANY))
    server_sock.listen(1)
    bluetooth.advertise_service(server_sock, "NaGaJa", BT_UUID)

    while True:
        client_sock, addr = server_sock.accept()
        data = client_sock.recv(1024)
        msg = json.loads(data.decode())
        if msg.get("action") == "identify" and "userId" in msg:
            _current_user_id = msg["userId"]
            save_user_id(new_uid)       # user_config.json 에 영속 저장
            client_sock.send(json.dumps({"status": "ok"}).encode())
```

**UUID**: `00001101-0000-1000-8000-00805F9B34FB` (Serial Port Profile — SPP)

모바일 앱에서 한 번 연결하면 userId가 `user_config.json`에 저장되어 Pi 재부팅 후에도 자동으로 로드됩니다.

---

### 4-2. DB 읽기/쓰기 로직 (db_read_write_test.py)

이 스크립트는 Firebase 서비스 계정 연결이 실제로 작동하는지, Firestore의 3가지 컬렉션을 모두 읽고 쓸 수 있는지 검증하는 **연동 테스트 도구**입니다.

#### 테스트 항목 (10단계)

| 단계 | 컬렉션 | 테스트 내용 |
|---|---|---|
| USERS 1 | `users` | 전체 문서 목록 조회 |
| USERS 2 | `users` | 특정 UID 단건 조회 |
| USERS 3 | `users` | `prepMinutes += 999` 수정 후 재확인 |
| SCHED 1 | `schedules` | 해당 유저의 스케줄 목록 조회 |
| SCHED 2 | `schedules` | 첫 번째 스케줄 단건 조회 |
| SCHED 3 | `schedules` | `isActive` 반전 수정 후 재확인 |
| PLANS 1 | `dailyPlans` | 플랜 목록 조회 |
| PLANS 2 | `dailyPlans` | 첫 번째 플랜 단건 조회 |
| PLANS 3 | `dailyPlans` | `displayColor = "TEST_COLOR"` 수정 |
| ROLLBACK | 전체 | 모든 수정값 원래대로 복원 |

#### 안전한 테스트 설계

```python
def test_users_update(db, uid, original):
    orig_val = original.get("prepMinutes", 0)
    test_val = orig_val + 999    # 명백히 구별되는 값으로 수정
    ref.update({"prepMinutes": test_val})
    updated = ref.get().to_dict().get("prepMinutes")
    assert updated == test_val   # 실제 DB에 반영됐는지 확인
    return orig_val

def rollback_users(db, uid, original):
    ref.update({"prepMinutes": original.get("prepMinutes"),
                "updatedAt": original.get("updatedAt")})
    # 원래 updatedAt까지 복원해 흔적을 남기지 않음
```

---

### 4-3. Firebase 초기화 (init_firestore.py)

개발 초기 단계에서 Firestore에 샘플 데이터를 생성하기 위한 **1회성 초기화 스크립트**입니다.

```python
def ensure_user(db, uid):
    ref = db.collection("users").document(uid)
    if ref.get().exists:
        print("[SKIP] 이미 존재")
        return False
    ref.set({ "prep_minutes": 30, "default_travel_minutes": 30, ... })
```

**주의**: 이 스크립트는 초기 개발용 ERD 기반 구조(`schedules/{sid}/daily_plans/`)를 사용하며, 실제 Android 앱 기준 구조(`users/{uid}/dailyPlans/`)와 다릅니다. DB_STRUCTURE.md에 이 차이가 명시되어 있습니다.

---

### 4-4. 타이머 UI (timer_ui.html)

#### UI 레이아웃 구조

화면은 좌우 2개의 섹션으로 구성됩니다 (800×480px 고정):

```
┌─────────────────────────────┬──────────────────────┐
│   타이머 섹션 (480×480)      │  정보 패널 (320px)    │
│                             │                      │
│   ┌─── 원형 링 ──────────┐  │  현재 시각 28px      │
│   │  초록 (여유 구간)     │  │  수업명 부제         │
│   │  노랑 (나가자 구간)   │  │  ──────────────────  │
│   │  빨강 (지각 구간)     │  │  준비 | 이동 | 출발  │
│   │                      │  │  (3열 카드)          │
│   │   중앙: 수업시각     │  │  ──────────────────  │
│   │   or 카운트다운      │  │  🔔 기상 알람 시각   │
│   │                      │  │  ──────────────────  │
│   └──────────────────────┘  │  🌤 날씨 | 🚦 혼잡도 │
│   ● 현재 위치 포인터         │  ──────────────────  │
│                             │  AI 예측 이용함      │
└─────────────────────────────┴──────────────────────┘
```

#### SVG 원형 링 계산 원리

```javascript
const R = 200, CIRC = 2 * Math.PI * R;  // 1256.64

function segDash(from, to) {
    const len = (to - from) * CIRC;     // 구간 길이 (픽셀)
    return {
        da:   `${len} ${CIRC - len}`,   // stroke-dasharray
        doff: -from * CIRC              // stroke-dashoffset (시작 위치)
    };
}

// 준비-여유 경계 r1, 출발-지각 경계 r2 계산
const r1 = Math.max(0, Math.min(1, (dep - 10 - ps) / total));
const r2 = Math.max(r1, Math.min(1, (dep - ps) / total));

setS('seg-relaxed', 0,  r1);   // 초록 구간
setS('seg-hurry',   r1, r2);   // 노랑 구간
setS('seg-late',    r2, 1);    // 빨강 구간
```

#### 상태 결정 로직

```javascript
function determineState(d) {
    const c = d.displayColor || 'GREEN';
    if (c === 'RED')    return STATE.LATE;    // 지각 위기
    if (c === 'YELLOW') return STATE.HURRY;   // 나가자!
    return STATE.RELAXED;                      // 여유
}
```

상태 판단은 클라이언트가 아닌 **서버(모바일 앱/Cloud Functions)가 계산한 `displayColor`** 값을 그대로 사용합니다.

#### 3가지 데이터 소스 모드

| 모드 | 사용 시점 | 동작 |
|---|---|---|
| `websocket` | 실제 운영 | nagaja_bridge.py의 WebSocket 서버에 연결, 실시간 갱신 |
| `file` | 상태 주입 테스트 | `/tmp/nagaja_state.json` 2초 폴링 |
| `demo` | UI 스타일 확인 | 현재 시각 기준 가상 데이터 자동 생성 |

---

## 5. 데이터베이스 구조

### 컬렉션 구조 다이어그램

```
Firestore (nagaja-a6a8b)
│
└── users/
    └── {uid}  (Firebase Auth UID)
        │
        ├── [문서 필드]
        │   userId, name, email
        │   prepMinutes: int (기본 30분)
        │   defaultTravelMinutes: int (기본 30분)
        │   homeWifiSsids: string[]
        │   schoolWifiSsids: string[]
        │   createdAt, updatedAt: Timestamp
        │
        ├── schedules/          ← 요일별 반복 수업 일정
        │   └── {scheduleId}
        │       scheduleId, userId, title
        │       dayOfWeek: int (1=월 ~ 7=일)
        │       classTime: "HH:MM"
        │       targetArrivalTime: "HH:MM"
        │       startPlaceName, startAddress
        │       destinationName, destinationAddress
        │       transportMode: "SUBWAY"|"BUS"|"WALK"|"TAXI"
        │       isActive: bool
        │
        └── dailyPlans/         ← ★ Pi가 구독하는 핵심 컬렉션
            └── {planId}
                ├── [식별]
                │   planDate: "YYYY-MM-DD" (KST)
                │   scheduleId (→ schedules 참조)
                │   title, classTime
                │
                ├── [시간 계산 결과]
                │   prepMinutes, defaultTravelMinutes
                │   predictedTravelMinutes  ← 날씨/혼잡도 반영 최종값
                │   congestionAdjustMinutes, weatherAdjustMinutes
                │   remainingMarginMinutes
                │
                ├── [핵심 시각 - UTC Timestamp]
                │   finalAlarmTime    ★ 부저가 울릴 시각
                │   finalDepartureTime ★ 출발해야 할 시각
                │   baseAlarmTime, baseDepartureTime
                │
                └── [상태]
                    planStatus: "PENDING"|"CALCULATED"|"DEPARTED"|"ARRIVED"
                    displayColor: "GREEN"|"YELLOW"|"RED"
                    weatherType: "CLEAR"|"RAIN"|"SNOW"|"CLOUDY"
```

### 알람 시각 계산 공식

```
finalAlarmTime = targetArrivalTime
               - predictedTravelMinutes  (날씨/혼잡도 반영)
               - prepMinutes             (준비 시간)

예시:
  수업: 10:30, 목표 도착: 10:25
  예측 이동: 35분, 준비: 25분

  finalDepartureTime = 10:25 - 35분 = 09:50
  finalAlarmTime     = 09:50 - 25분 = 09:25
```

### displayColor 판단 기준

| 조건 | displayColor |
|---|---|
| 여유 시간 > 이동시간 + 10분 | GREEN |
| 여유 시간 > 이동시간 + 5분 | YELLOW |
| 그 외 (지각 위험) | RED |

---

## 6. 모바일 연동

### 블루투스 연결 흐름

```
[모바일 앱]                          [Raspberry Pi]
     │                                      │
     │  1. "연결" 버튼 탭                    │
     │  2. BT 기기 목록에서 "NaGaJa-Pi" 탐색 │
     │  3. RFCOMM 소켓 연결                  │
     │ ──────── JSON 전송 ─────────────────► │
     │  {"userId": "UID", "action": "identify"} │
     │                                      │  4. userId 저장
     │ ◄───── 응답 수신 ──────────────────── │  5. Firestore 재구독
     │  {"status": "ok", "userId": "..."}   │
     │  6. 설정 화면: "연결됨 · NaGaJa-Pi"  │
```

### Flutter 패키지

```yaml
flutter_bluetooth_serial: ^0.4.0   # Classic BT (Android 권장)
# iOS 지원 시:
flutter_blue_plus: ^1.0.0          # BLE GATT 방식 필요
```

### iOS 제약 사항

iOS는 Classic Bluetooth RFCOMM을 지원하지 않습니다. iOS 지원을 위해서는 BLE GATT 방식으로 전환이 필요합니다.

### 연결 끊김 처리

기기 MAC 주소를 `SharedPreferences`에 저장해 다음 연결 시 자동 탐색합니다. Pi 재부팅 시에도 `user_config.json`에 userId가 저장되어 있어 블루투스 재연결 없이도 동작합니다.

---

## 7. 하드웨어 연동

### Raspberry Pi의 역할

| 역할 | 구체 내용 |
|---|---|
| **화면 표시** | 7인치 공식 디스플레이(800×480)에 Chromium 키오스크 모드 실행 |
| **알람 출력** | GPIO 18번 능동 부저 — 기상 알람(최대 120초), 상태 전환 삐삐 |
| **입력 처리** | GPIO 17번 버튼 — 알람 해제 (하드웨어 인터럽트) |
| **Firebase 연결** | 유선/무선 인터넷 → Firebase Admin SDK → Firestore 실시간 구독 |
| **블루투스 서버** | RFCOMM SPP 서버 — 모바일 앱으로부터 사용자 ID 수신 |

### GPIO 배선

| 역할 | BCM 핀 | 물리 핀 |
|---|---|---|
| 부저 (+) | GPIO 18 | 핀 12 |
| 부저 (–) | GND | 핀 6 |
| 알람 해제 버튼 | GPIO 17 | 핀 11 |
| 버튼 반대쪽 | GND | 핀 9 |

**능동 부저**: 전압만 공급하면 스스로 소리를 내는 타입. 별도 PWM 제어 불필요.  
**PULL_UP 저항**: gpiozero `Button(pull_up=True)` 내부 풀업 사용 → 외부 저항 불필요.

---

## 8. 사용 시나리오

### 최초 설정 (1회)

```
1. 모바일 앱 설치 → Firebase 로그인 (Google 계정)
2. 앱에서 수업 시간표 등록
   - 과목명, 요일, 수업 시각, 출발지/목적지, 이동 수단 선택
3. Raspberry Pi 설정:
   - serviceAccountKey.json 복사 (scp 또는 USB)
   - python3 nagaja_bridge.py 실행 (또는 systemd 등록)
4. 앱 설정 → "기기 연결 > 물리 알람시계 → 연결"
   → 블루투스로 Pi에 userId 전송 완료
5. Chromium 키오스크 모드로 timer_ui.html 열기
```

### 매일 아침 사용 흐름

```
[전날 밤 또는 당일 새벽]
① 모바일 앱 → /generateDailyPlan 호출
   → 날씨 + 교통 + 혼잡도 조합
   → finalAlarmTime 계산 → Firestore 저장

[아침]
② Raspberry Pi
   → Firestore on_snapshot 수신 → timer_ui.html 갱신
   → 7인치 화면: 원형 링 타이머 표시 (GREEN 상태)

③ finalAlarmTime 도달
   → 능동 부저 0.5초 간격으로 울림 (최대 120초)
   → 사용자: 버튼 누름 → 즉시 알람 해제

④ 시간 경과에 따른 화면 상태 변화:
   GREEN → YELLOW (나가자!): 삐삐 + 출발 카운트다운
   YELLOW → RED (지각 위기): 삐삐 + 빨간 깜빡임 카운트다운

⑤ 사용자: 화면 보고 출발 시각 확인 → 집 출발
```

### 상태별 화면 동작

| displayColor | 화면 상태 | 링 중앙 | 링 색상 | 부저 |
|---|---|---|---|---|
| GREEN | 여유 | 수업 시각 (회색) | 초록 | 알람 시각에만 |
| YELLOW | 나가자! | 출발까지 카운트다운 (노랑) | 노랑 | 삐삐 1회 |
| RED | 지각 위기 | 카운트다운 깜빡임 (빨강) | 빨강 | 삐삐 1회 |

---

## 9. 발표 강조 포인트

### 기술적 차별점

**1. 실시간 양방향 데이터 파이프라인**
단방향 알람이 아닌, 모바일 앱 ↔ Firebase ↔ Raspberry Pi의 실시간 3-tier 연동. Firestore `on_snapshot`을 통해 앱에서 설정을 바꾸면 Pi 화면이 1~2초 내 즉시 반영됩니다.

**2. 멀티스레드 + asyncio 하이브리드 설계**
Firestore SDK는 별도 스레드에서 동작하고, WebSocket 서버는 asyncio 이벤트 루프에서 동작합니다. `asyncio.run_coroutine_threadsafe()`로 스레드 경계를 안전하게 넘어가는 설계는 실무 수준의 동시성 처리입니다.

**3. 하드웨어 인터럽트 기반 버튼**
gpiozero `Button.when_pressed`(lgpio 엣지 이벤트) 콜백을 사용해 버튼 응답이 즉각적이며 CPU 폴링이 없습니다.

**4. 3-mode 데이터 소스 설계**
`websocket` / `file` / `demo` 세 가지 모드를 지원해 Pi 없이도 웹 브라우저에서 UI를 개발/테스트할 수 있습니다. 하드웨어 독립적인 개발 환경입니다.

**5. 안전한 DB 테스트 — 자동 롤백**
쓰기 테스트 후 반드시 원래 값으로 복원하는 자동 롤백 설계로, 실제 운영 데이터를 보호하면서도 연동 검증이 가능합니다.

### 기술적 도전과 해결

| 도전 | 해결 방법 |
|---|---|
| Firestore Timestamp UTC/KST 변환 | `_ts_to_utc()`, `timestamp_to_kst_str()` 유틸 함수로 일관 처리 |
| Pi 5(RP1)에서 RPi.GPIO 미동작 | `gpiozero` + `lgpio` 로 전환 (핀 팩토리 lgpio 고정) |
| gpiozero/lgpio 없는 환경에서 테스트 | import·장치 생성 실패 감지 → 시뮬레이션 모드 자동 전환 |
| PyBluez 없는 환경 | 동일하게 BT_AVAILABLE 플래그로 graceful degradation |
| 당일 중복 알람 방지 | `wake_done_keys` set + second < 5 조건 |
| init_firestore.py와 실제 DB 구조 불일치 | DB_STRUCTURE.md에 차이점을 명문화 |
| Chromium 로컬 파일 접근 보안 정책 | `--allow-file-access-from-files` 플래그로 해결 |

---

## 10. 코드 하이라이트

### 코드 1: Firestore 실시간 리스너 + asyncio 브리지

```python
def on_snapshot(query_snapshot, changes, read_time):
    # 이 콜백은 Firestore SDK의 별도 스레드에서 실행됨
    ui_data = doc_to_ui_data(chosen)
    # 스레드 경계를 안전하게 넘어 asyncio 코루틴 스케줄링
    asyncio.run_coroutine_threadsafe(broadcast(ui_data), loop)

_watch_handle[0] = col_ref.on_snapshot(on_snapshot)
```

**설명**: Firestore SDK 콜백은 내부 스레드에서 실행되지만, WebSocket 브로드캐스트는 asyncio 이벤트 루프에서만 실행 가능합니다. `run_coroutine_threadsafe()`가 이 경계를 안전하게 넘어줍니다.

---

### 코드 2: 오늘 플랜 중 다음 수업 자동 선택

```python
now_utc = datetime.now(timezone.utc)
candidates = [(alarm_utc, dd) for ... if alarm_utc]
candidates.sort(key=lambda x: x[0])

# 현재 시각 이후의 첫 번째 → 없으면 마지막 수업 표시
chosen = next((dd for t, dd in candidates if t >= now_utc), None)
if chosen is None and candidates:
    chosen = candidates[-1][1]
```

**설명**: 하루에 수업이 여러 개일 때 현재 시각 이후의 가장 가까운 수업을 자동으로 선택합니다.

---

### 코드 3: GPIO 알람 — 버튼 콜백으로 즉각 해제 (gpiozero)

```python
button = Button(BUTTON_PIN, pull_up=True, bounce_time=0.05)
button.when_pressed = _stop_alarm

def _stop_alarm(*_args):
    global _alarm_active
    _alarm_active = False   # 알람 루프 즉시 종료

def wake_up_alarm():
    deadline = time.time() + 120  # 120초 타임아웃
    while _alarm_active and time.time() < deadline:
        buzzer.on();  time.sleep(0.5)
        buzzer.off(); time.sleep(0.5)
```

**설명**: `_alarm_active` 플래그를 공유하는 간단하지만 안전한 설계입니다. 버튼 콜백(`when_pressed`)이 플래그를 False로 바꾸면 알람 루프가 다음 0.5초 내에 자연스럽게 종료됩니다.

---

### 코드 4: SVG 원형 링 세그먼트 계산

```javascript
const R = 200, CIRC = 2 * Math.PI * R;  // 원 둘레 1256.64

function segDash(from, to) {
    const len = (to - from) * CIRC;
    return {
        da:   `${len} ${CIRC - len}`,  // stroke-dasharray
        doff: -from * CIRC             // stroke-dashoffset
    };
}

// 3개 구간 배치
setS('seg-relaxed', 0,  r1);   // 초록
setS('seg-hurry',   r1, r2);   // 노랑
setS('seg-late',    r2, 1);    // 빨강
```

**설명**: SVG circle의 `stroke-dasharray`와 `stroke-dashoffset`을 수학적으로 제어해 하나의 원을 3개의 색깔 구간으로 분할합니다. 원 둘레를 1로 정규화한 비율 값으로 계산합니다.

---

### 코드 5: Firestore Timestamp → KST 변환 (버그 수정 포함)

```python
KST = timezone(timedelta(hours=9))

def _ts_to_utc(ts) -> datetime | None:
    """DatetimeWithNanoseconds 또는 구형 Timestamp 모두 처리"""
    if isinstance(ts, datetime):
        return ts.astimezone(timezone.utc) if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromtimestamp(ts.seconds, tz=timezone.utc)
    except Exception:
        return None

def timestamp_to_kst_str(ts) -> str | None:
    dt_utc = _ts_to_utc(ts)
    if dt_utc is None: return None
    return dt_utc.astimezone(KST).strftime("%H:%M")
```

**설명**: Firestore SDK 버전에 따라 Timestamp가 두 가지 형태로 반환될 수 있습니다. 두 경우를 모두 처리하는 방어적 코드로, `fix: Firestore DatetimeWithNanoseconds 오류 수정` 커밋으로 해결된 실제 버그입니다.

---

### 코드 6: WebSocket 멀티클라이언트 브로드캐스트

```python
async def broadcast(data: dict):
    if not connected_clients: return
    msg = json.dumps(data, ensure_ascii=False)
    await asyncio.gather(
        *[c.send(msg) for c in list(connected_clients)],
        return_exceptions=True,   # 한 클라이언트 실패해도 나머지 계속
    )
```

**설명**: `return_exceptions=True`로 특정 클라이언트 연결이 끊겨도 다른 클라이언트 전송에 영향을 주지 않습니다.

---

### 코드 7: 상태 전환 감지 → 청각 알림

```python
current_state = _determine_state(latest_data)
if (prev_state is not None
        and prev_state != current_state
        and now_mins != last_beep_min):  # 같은 분 중복 방지
    last_beep_min = now_mins
    threading.Thread(target=double_beep, daemon=True).start()
prev_state = current_state
```

**설명**: 1초 루프에서 상태 변화를 감지하면 즉시 청각 알림을 발생시킵니다. `last_beep_min` 비교로 같은 분 내 중복 알림을 방지합니다.

---

### 코드 8: 사용자 ID 영속 저장 (재부팅 복원)

```python
# 블루투스 수신 시
save_user_id(new_uid)   # → user_config.json에 저장

# 재부팅 후 자동 복원
async def main():
    _current_user_id = load_user_id()  # 파일에서 로드
    if _current_user_id:
        log.info(f"저장된 사용자 ID 로드: {_current_user_id}")
```

**설명**: 블루투스로 한 번 연결된 사용자 ID를 파일로 영속화해, Pi 재부팅 후에도 앱 재연결 없이 즉시 동작합니다.

---

### 코드 9: UI 상태별 카운트다운 표시

```javascript
if (state === STATE.HURRY) {
    const rem = dep - nm;               // 출발까지 남은 분
    countdown.textContent = mmss(rem);  // "MM:SS"
    countdown.style.color = 'var(--state-yellow)';
    stateLabel.textContent = '나가자!';

} else if (state === STATE.LATE) {
    countdown.classList.add('urgent');  // 깜빡임 CSS 클래스
    countdown.textContent = mmss(dep - nm);
    countdown.style.color = 'var(--state-red)';
    stateLabel.textContent = '지각 위기';
}
```

**설명**: 서버의 `displayColor` 하나로 화면의 색상, 텍스트, 애니메이션이 모두 전환됩니다.

---

### 코드 10: 안전한 DB 테스트 — updatedAt까지 완전 복원

```python
def rollback_daily_plans(db, uid, pid, original):
    ref.update({
        "displayColor": original.get("displayColor"),
        "updatedAt":    original.get("updatedAt")  # 타임스탬프까지 복원
    })
    restored = ref.get().to_dict().get("displayColor")
    print(f"  {'✅ PASS' if restored == original.get('displayColor') else '❌ FAIL'} rollback")
```

**설명**: `updatedAt` 타임스탬프까지 원래 값으로 복원해 테스트 흔적이 전혀 남지 않도록 합니다.
