# 나가자 — 라즈베리파이 세팅 가이드

## 파일 구성

```
/home/jeje9893/nagaja/
├── venv/                      # Python 가상환경
├── timer_ui.html              # 터치스크린 UI (7인치, 800×480)
├── nagaja_bridge.py           # Firestore ↔ WebSocket 브리지 + 부저 알람 (gpiozero)
├── demo_bridge.py             # 구동화면 촬영/시연용 데모 브리지 (Firebase 불필요)
├── hardware_test.py           # 부저/버튼 하드웨어 점검 서버
├── hardware_test.html         # 하드웨어 점검 UI
├── init_firestore.py          # Firestore 초기 데이터 생성 (1회성)
├── firebase_test.py           # Firebase 연결 테스트 (쓰기/읽기)
├── db_read_write_test.py      # Firestore 읽기·수정 연동 테스트
├── requirements.txt           # Python 의존 패키지 목록
├── README.md                  # (이 문서) 세팅 가이드
├── PROJECT_DESCRIPTION.md     # 앱/Firestore 데이터 명세
├── DB_STRUCTURE.md            # Firestore 컬렉션 구조 개발자 참조
├── DEMO_CAPTURE.md            # 구동화면 촬영 가이드
├── HARDWARE_TEST.md           # 부저/버튼 하드웨어 점검 가이드
├── analysis.md                # 코드 전체 분석 문서
├── slide_outline.md           # 발표 슬라이드 개요
├── mobileEdit.md              # 모바일 앱 수정 사항 (블루투스 연동)
├── serviceAccountKey.json     # Firebase 서비스 계정 키 (git 제외)
└── user_config.json           # 수신된 사용자 UID 저장 파일 (git 제외)
```

---

## 최초 설치

### 1. GitHub에서 클론
```bash
cd ~
git clone https://github.com/<repo> nagaja
cd nagaja
```

> 이미 클론된 경우 업데이트만:
> ```bash
> cd ~/nagaja && git pull
> ```

### 2. 가상환경 생성 및 패키지 설치
```bash
python3 -m venv ~/nagaja/venv
source ~/nagaja/venv/bin/activate
pip install -r requirements.txt
pip install gpiozero lgpio        # 라즈베리파이 GPIO (Pi 5: RPi.GPIO 대신 gpiozero+lgpio)
sudo apt install -y python3-bluez # 블루투스 (PyBluez) — pip PyBluez 0.23 은 설치 불가
```

> **블루투스(PyBluez) 주의**: PyPI 의 `PyBluez 0.23`(2020, 마지막 릴리스)은
> `use_2to3` 오류로 최신 setuptools/Python 에서 **설치되지 않습니다.**
> 아래 중 하나를 사용하세요(모두 `import bluetooth` 동일, 코드 수정 불필요):
> ```bash
> # (권장) 시스템 미리빌드 패키지 — 아래 system-site-packages 설정 필요
> sudo apt install -y python3-bluez
> # 또는 유지보수 포크
> sudo apt install -y libbluetooth-dev && pip install pybluez2
> ```
> 블루투스는 앱에서 UID를 수신하는 용도일 뿐이라, 없으면 `user_config.json`에
> UID를 직접 넣어도 됩니다(브리지는 BT 없이도 `BT_AVAILABLE=False`로 동작).
>
> **라즈베리파이 5 참고**: 구형 `RPi.GPIO`는 Pi 5(RP1 칩)에서
> `Cannot determine SOC peripheral base address` 오류로 동작하지 않습니다.
> 본 프로젝트는 `gpiozero` + `lgpio`를 사용합니다.
> `lgpio` 빌드가 실패하면(Python 3.13 등) 미리 빌드된 패키지를 쓰세요:
> ```bash
> sudo apt install -y python3-lgpio python3-gpiozero
> ```
>
> **system-site-packages 설정**: `python3-bluez`·`python3-lgpio` 등 apt 미리빌드
> 패키지를 venv 에서 쓰려면 한 번만 아래를 실행하세요:
> ```bash
> sed -i 's/include-system-site-packages = false/include-system-site-packages = true/' ~/nagaja/venv/pyvenv.cfg
> ```

### 3. Firebase 서비스 계정 키 배치
```
serviceAccountKey.json 파일을 ~/nagaja/ 에 복사
(git에 포함되지 않으므로 수동 배치 필요)
```

---

## 실행 순서

### 0단계 — Firestore DB 읽기·수정 연동 테스트

실제 Firestore에 저장된 `users` 컬렉션을 읽고 수정할 수 있는지 확인합니다.  
테스트 후 변경된 값은 자동으로 원래 값으로 롤백됩니다.

```bash
source ~/nagaja/venv/bin/activate

# 전체 유저 대상 (첫 번째 유저로 자동 선택)
python3 ~/nagaja/db_read_write_test.py

# 특정 유저 지정
python3 ~/nagaja/db_read_write_test.py --uid <userId>
```

**실제 Firestore 컬렉션 구조 (Android 앱 기준):**
```
users/{uid}
users/{uid}/schedules/{scheduleId}
users/{uid}/dailyPlans/{planId}     ← schedules 하위가 아님
```

**테스트 항목:**

| 단계 | 컬렉션 | 내용 | 확인 기준 |
|---|---|---|---|
| USERS 1 | `users` | 전체 읽기 | 문서 목록 출력 |
| USERS 2 | `users` | 단건 읽기 | 모든 필드 출력 |
| USERS 3 | `users` | `prepMinutes` 수정 후 재조회 | 수정 값 DB 반영 |
| SCHED 1 | `schedules` | 해당 유저 스케줄 전체 읽기 | 문서 목록 출력 |
| SCHED 2 | `schedules` | 단건 읽기 | 모든 필드 출력 |
| SCHED 3 | `schedules` | `isActive` 수정 후 재조회 | 수정 값 DB 반영 |
| PLANS 1 | `dailyPlans` | 해당 유저 플랜 전체 읽기 | 문서 목록 출력 |
| PLANS 2 | `dailyPlans` | 단건 읽기 | 모든 필드 출력 |
| PLANS 3 | `dailyPlans` | `displayColor` 수정 후 재조회 | 수정 값 DB 반영 |
| ROLLBACK | 전체 | 모든 수정값 원복 | 원래 값 일치 확인 |

모든 단계에서 `✅ PASS` 가 출력되면 정상입니다.  
해당 유저에 `schedules` 또는 `dailyPlans` 문서가 없으면 `⏭️ SKIP` 으로 건너뜁니다.

---

### 1단계 — Firebase 연결 확인 (최초 1회)
```bash
source ~/nagaja/venv/bin/activate
python3 ~/nagaja/firebase_test.py
```
`성공` 메시지가 출력되면 다음 단계로 진행합니다.

### 2단계 — 사용자 ID 설정

브리지는 블루투스로 모바일 앱에서 사용자 UID를 수신합니다.  
테스트 시에는 파일에 직접 입력해도 됩니다.

```bash
echo '{"userId": "여기에_실제_UID_입력"}' > ~/nagaja/user_config.json
```

앱 블루투스 연결 시에는 이 파일이 자동으로 갱신됩니다.

### 3단계 — 브리지 실행
```bash
source ~/nagaja/venv/bin/activate
python3 ~/nagaja/nagaja_bridge.py
```

정상 시작 시 로그:
```
[HH:MM:SS] INFO Firebase 초기화 완료
[HH:MM:SS] INFO 저장된 사용자 ID 로드: <uid>
[HH:MM:SS] INFO 블루투스 서버 대기 중 (채널 1)
[HH:MM:SS] INFO WebSocket 서버 시작: ws://localhost:8765
[HH:MM:SS] INFO Firestore 구독: users/<uid>/dailyPlans planDate=YYYY-MM-DD
```

### 4단계 — 브라우저로 UI 열기

**창모드 (테스트용):**
```bash
chromium --app=file:///home/jeje9893/nagaja/timer_ui.html \
  --window-size=800,480 --window-position=0,0
```

**키오스크 모드 (운영용):**
```bash
chromium --kiosk --noerrdialogs --disable-infobars \
  --app=file:///home/jeje9893/nagaja/timer_ui.html &
```

### 키오스크 종료 방법

**방법 1: 단축키로 터미널 열기**
```
Ctrl + Alt + T
```
터미널이 열리면: `pkill chromium`

**방법 2: 가상 터미널 전환 (가장 빠름)**
```
Ctrl + Alt + F2
```
로그인 후:
```bash
pkill chromium
```
GUI 화면으로 복귀:
```
Ctrl + Alt + F1
```

**방법 3: SSH 원격 접속 (다른 기기에서)**
```bash
ssh jeje9893@<라즈베리파이_IP>
pkill chromium
```

---

## 창모드 테스트

### 상태 전환 테스트 (시스템 시계 변경 없이)

시스템 시계를 바꾸면 Firebase 인증 토큰이 꼬일 수 있습니다.  
대신 아래 방법으로 상태를 직접 주입해 확인합니다.

---

#### 방법 A: demo 모드 (가장 빠름 — 파일·Firebase 불필요)

**1단계:** `timer_ui.html` 상단 `NAGAJA_CONFIG` 블록에서 `dataSource` 변경:

```javascript
const NAGAJA_CONFIG = {
  dataSource: 'demo',   // ← 'websocket' 에서 변경
  ...
};
```

**2단계:** 창모드로 열기:

```bash
chromium --app=file:///home/jeje9893/nagaja/timer_ui.html \
  --window-size=800,480 --window-position=0,0
```

현재 시각 기준으로 약 15분 후 HURRY(노랑), 25분 후 LATE(빨강)로 자동 전환됩니다.

> 테스트 후 `dataSource: 'websocket'` 으로 되돌려야 합니다.

---

#### 방법 B: 파일 모드 (상태를 직접 지정하여 테스트)

**1단계:** `timer_ui.html` 상단 `NAGAJA_CONFIG` 블록에서 `dataSource` 변경:

```javascript
const NAGAJA_CONFIG = {
  dataSource: 'file',   // ← 'websocket' 에서 변경
  stateFilePath: '/tmp/nagaja_state.json',
  ...
};
```

**2단계:** Chromium 실행 시 `--allow-file-access-from-files` 플래그 추가:

```bash
chromium --app=file:///home/jeje9893/nagaja/timer_ui.html \
  --window-size=800,480 --window-position=0,0 \
  --allow-file-access-from-files
```

> 이 플래그 없이는 Chromium이 보안 정책으로 로컬 파일 읽기를 차단합니다.

**3단계:** 상태 JSON 파일 생성:

```bash
cat > /tmp/nagaja_state.json << 'EOF'
{
  "wakeUpTime": "07:30",
  "departureTime": "09:00",
  "prepStartTime": "07:30",
  "classStartTime": "10:00",
  "className": "캡스톤디자인",
  "travelMinutes": 30,
  "prepMinutes": 25,
  "weatherCondition": "맑음",
  "weatherDelay": 0,
  "congestionDelay": 5,
  "displayColor": "GREEN",
  "remainingMarginMinutes": 60,
  "planStatus": "CALCULATED"
}
EOF
```

**4단계:** `displayColor` 값만 바꿔가며 상태별 UI를 확인합니다:

| `displayColor` 값 | 화면 상태 | 링 중앙 표시 | 링 색상 |
|---|---|---|---|
| `"GREEN"` | 여유 | 수업 시각 (회색) | 초록 |
| `"YELLOW"` | 나가자! | 출발까지 카운트다운 | 노랑 |
| `"RED"` | 지각 위기 | 카운트다운 빨강 깜빡임 | 빨강 |

JSON 파일을 저장하면 2초 내로 UI에 반영됩니다.

> 테스트 후 `dataSource: 'websocket'` 으로 되돌려야 합니다.

**파일 모드가 동작하지 않을 때:**

Chromium에서 F12 → Console 탭 확인:
```
[NaGaJa] 상태 파일 읽기 실패: ...
```
위 메시지가 보이면 플래그 누락 또는 파일 경로 문제입니다.

---

#### 방법 C: Firebase Console에서 실시간 변경 (브리지 실행 중일 때)

브리지(`nagaja_bridge.py`)가 실행 중인 상태에서:

```
Firebase Console
→ Firestore Database
→ users/{uid}/dailyPlans/{planId}
→ displayColor 필드 클릭 → GREEN / YELLOW / RED 로 수정
```

`on_snapshot`이 감지해 1~2초 내 UI가 자동 업데이트됩니다.

---

### 알람 울림 테스트

Firebase Console에서 `finalAlarmTime`을 **현재 UTC 기준 +2분**으로 설정합니다.

```
Firebase Console → dailyPlans/{planId}
→ finalAlarmTime → Timestamp 타입, 현재 UTC + 2분으로 수정
```

브리지 터미널에서 아래 로그가 출력되면 정상:
```
[HH:MM:SS] INFO 기상 알람 시작
[HH:MM:SS] INFO 기상 알람 종료
```

---

### 자주 쓰는 확인 명령

```bash
# 현재 상태 파일 확인
cat /tmp/nagaja_state.json | python3 -m json.tool

# 브리지 핵심 로그만 보기
python3 ~/nagaja/nagaja_bridge.py 2>&1 | grep -E "갱신|알람|상태|오류|구독"

# 사용자 ID 확인
cat ~/nagaja/user_config.json
```

---

## 자동 시작 설정

부팅 시 브리지와 UI가 자동으로 실행되도록 설정합니다.

### 브리지 자동 시작 (systemd)
```bash
sudo nano /etc/systemd/system/nagaja-bridge.service
```
```ini
[Unit]
Description=NaGaJa Bridge
After=network.target bluetooth.target

[Service]
User=jeje9893
WorkingDirectory=/home/jeje9893/nagaja
ExecStart=/home/jeje9893/nagaja/venv/bin/python3 /home/jeje9893/nagaja/nagaja_bridge.py
Restart=always

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl enable nagaja-bridge
sudo systemctl start nagaja-bridge
```

### UI 자동 시작 (autostart)
```bash
sudo nano /etc/xdg/autostart/nagaja-ui.desktop
```
```ini
[Desktop Entry]
Type=Application
Name=NaGaJa UI
Exec=chromium --kiosk --noerrdialogs --disable-infobars --app=file:///home/jeje9893/nagaja/timer_ui.html
```

---

## 부저 / 버튼 GPIO 배선

| 역할 | BCM 핀 | 물리 핀 |
|---|---|---|
| 부저 (+) | GPIO 18 | 핀 12 |
| 부저 (–) | GND | 핀 6 |
| 알람 해제 버튼 | GPIO 17 | 핀 11 |
| 버튼 반대쪽 | GND | 핀 9 |

> 핀 번호는 `nagaja_bridge.py` 상단 `BUZZER_PIN`, `BUTTON_PIN` 에서 변경 가능합니다.

**GPIO 제어:** `gpiozero` + `lgpio` 사용 (Pi 5 호환). 능동 부저는 `Buzzer`, 버튼은
`Button(pull_up=True, bounce_time=0.05)`. 핀 팩토리는 `lgpio`로 고정됩니다.

> SM-1205C 같은 **마그네틱 부저는 GPIO 전류(~16mA)를 초과**해 3.3V 직결로는
> 소리가 약할 수 있습니다. 트랜지스터(NPN)로 5V 구동하거나, 수동형 부저는
> PWM 구동이 필요합니다. 자세한 점검·배선은 `HARDWARE_TEST.md` 참고.

**부저 동작:**
- 기상 알람 시각 도달 → 0.5초 간격으로 최대 2분 울림, 버튼으로 즉시 해제
- 여유→나가자, 나가자→지각위기 전환 시점 → '삐 삐' 두 번

---

## 테스트 / 시연 도구

| 도구 | 용도 | 가이드 |
|---|---|---|
| `hardware_test.py` + `hardware_test.html` | 부저/버튼 하드웨어 단독 점검 (Firebase 불필요) | `HARDWARE_TEST.md` |
| `demo_bridge.py` + `timer_ui.html` | 상태별 구동화면 시연·촬영 (전환음·배경 깜빡임) | `DEMO_CAPTURE.md` |

> 두 도구와 `nagaja_bridge.py`는 모두 8765 포트를 쓰므로 **한 번에 하나만** 실행하세요.

---

## 블루투스 연결 (모바일 앱 → Pi)

앱 설정 화면의 "기기 연결 > 물리 알람시계 > 연결" 버튼을 누르면  
Pi의 RFCOMM 서버에 연결되고 사용자 UID가 자동 전송됩니다.

Pi 블루투스 기기명 설정 (최초 1회):
```bash
sudo hostnamectl set-hostname NaGaJa-Pi
```

연결 성공 시 브리지 로그:
```
[HH:MM:SS] INFO 블루투스 연결: ('XX:XX:XX:XX:XX:XX', 1)
[HH:MM:SS] INFO 사용자 ID 수신: <uid>
[HH:MM:SS] INFO Firestore 재구독 (날짜=YYYY-MM-DD, uid=<uid>)
```

---

## GitHub에 포함되지 않은 보안 파일

| 파일 | 역할 | 취득 방법 |
|---|---|---|
| `serviceAccountKey.json` | Firebase 서비스 계정 비밀키 | Firebase Console → 프로젝트 설정 → 서비스 계정 → 새 비공개 키 생성 |
| `user_config.json` | 수신된 사용자 UID | 앱 블루투스 연결 시 자동 생성, 또는 수동 작성 |
| `github token.txt` | GitHub Personal Access Token | GitHub → Settings → Developer Settings → Personal Access Tokens |

### 라즈베리파이로 파일 전송

```bash
# Windows PowerShell 또는 Git Bash 에서 실행
scp serviceAccountKey.json jeje9893@<라즈베리파이_IP>:~/nagaja/
```

---

## Firebase 연결 방식

```
serviceAccountKey.json
        ↓  (credentials.Certificate)
Firebase Admin SDK
        ↓  (firestore.client)
Firestore DB (users/{uid}/dailyPlans)
```

키 파일을 참조하는 파일과 경로:

| 파일 | 상수명 | 경로 |
|---|---|---|
| `nagaja_bridge.py` | `SERVICE_ACCOUNT_PATH` | `~/nagaja/serviceAccountKey.json` |
| `init_firestore.py` | `SERVICE_ACCOUNT_PATH` | `~/nagaja/serviceAccountKey.json` |
| `firebase_test.py` | `SERVICE_ACCOUNT_PATH` | `~/nagaja/serviceAccountKey.json` |

---

## 데이터 연동 방식

`timer_ui.html` 상단 `NAGAJA_CONFIG.dataSource` 값으로 전환합니다:

| 값 | 설명 |
|---|---|
| `'websocket'` | `nagaja_bridge.py` WebSocket 연결 **(기본값, 운영용)** |
| `'file'` | `/tmp/nagaja_state.json` 폴링 (상태 직접 주입 테스트용) |
| `'demo'` | 현재 시각 기준 가상 데이터 (UI 스타일 확인용) |

---

## 화면 상태 전환 로직

상태는 서버(앱)가 계산한 `displayColor` 값을 사용합니다.

| `displayColor` | 화면 상태 | 링 중앙 표시 | 링 색상 |
|---|---|---|---|
| `GREEN` | 여유 | 수업 시각 (회색) | 초록 |
| `YELLOW` | 나가자! | 출발까지 카운트다운 (노랑) | 노랑 |
| `RED` | 지각 위기 | 카운트다운 깜빡임 (빨강) | 빨강 |

---

## Claude Code 작업 시 참고

- UI 레이아웃: 800×480px 고정 (7인치 공식 디스플레이)
- 폰트: Noto Sans KR (Google Fonts, 오프라인 환경에서는 Arial 폴백)
- 상태 로직: `timer_ui.html` → `determineState()` — `displayColor` 서버값 기반
- 정보 카드: `#info-row-card` 내 `.info-col` 구조
- GPIO 핀 변경: `nagaja_bridge.py` 상단 `BUZZER_PIN` / `BUTTON_PIN`
- Firestore 경로: `users/{userId}/dailyPlans` — `planDate == today_kst_str()`
- 사용자 ID: 블루투스 수신 → `_current_user_id` 전역 변수 + `user_config.json` 영속
