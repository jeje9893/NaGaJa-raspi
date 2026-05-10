# 나가자 — 라즈베리파이 세팅 가이드

## 파일 구성

```
/home/jeje9893/nagaja/
├── venv/                   # Python 가상환경
├── timer_ui.html           # 터치스크린 UI (7인치, 800×480)
├── nagaja_bridge.py        # Firestore ↔ WebSocket 브리지 + 부저 알람
├── init_firestore.py       # Firestore 초기 데이터 생성 (1회성)
├── firebase_test.py        # Firebase 연결 테스트
├── requirements.txt        # Python 의존 패키지 목록
├── serviceAccountKey.json  # Firebase 서비스 계정 키 (git 제외)
└── README.md
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
pip install RPi.GPIO          # 라즈베리파이 GPIO (requirements에 없는 경우)
```

### 3. Firebase 서비스 계정 키 배치
```
serviceAccountKey.json 파일을 ~/nagaja/ 에 복사
(git에 포함되지 않으므로 수동 배치 필요)
```

---

## 실행 순서

### 1단계 — Firebase 연결 확인 (최초 1회)
```bash
source ~/nagaja/venv/bin/activate
python3 ~/nagaja/firebase_test.py
```
`성공` 메시지가 출력되면 다음 단계로 진행합니다.

### 2단계 — Firestore 초기 데이터 생성 (최초 1회)
```bash
source ~/nagaja/venv/bin/activate
python3 ~/nagaja/init_firestore.py
```
이미 데이터가 있으면 `[SKIP]`으로 건너뛰므로 여러 번 실행해도 안전합니다.

생성되는 Firestore 경로:
```
users/{uid}
users/{uid}/schedules/{scheduleId}
users/{uid}/schedules/{scheduleId}/daily_plans/{planId}
```

다른 UID로 초기화하려면:
```bash
python3 ~/nagaja/init_firestore.py --uid <firebase_uid>
```

### 3단계 — 브리지 실행
```bash
source ~/nagaja/venv/bin/activate
python3 ~/nagaja/nagaja_bridge.py
```

### 4단계 — 브라우저로 UI 열기 (터치스크린)
```bash
chromium-browser --kiosk --noerrdialogs --disable-infobars \
  --app=file:///home/jeje9893/nagaja/timer_ui.html
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
After=network.target

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
Exec=chromium-browser --kiosk --noerrdialogs --disable-infobars --app=file:///home/jeje9893/nagaja/timer_ui.html
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

**부저 동작:**
- 기상 알람 시각 도달 → 0.5초 간격으로 최대 2분 울림, 버튼으로 즉시 해제
- 여유→나가자, 나가자→지각위기 전환 시점 → '삐 삐' 두 번

---

## 데이터 연동 방식

`timer_ui.html` 상단 `NAGAJA_CONFIG.dataSource` 값으로 전환합니다:

| 값 | 설명 |
|---|---|
| `'websocket'` | `nagaja_bridge.py` WebSocket 연결 **(권장)** |
| `'file'` | `/tmp/nagaja_state.json` 폴링 (브리지 없이 동작 가능) |
| `'demo'` | 현재 시각 기준 가상 데이터 (UI 확인용) |

---

## 화면 상태 전환 로직

| 상태 | 조건 | 색상 |
|---|---|---|
| 여유 | 현재 < 출발−10분 | 초록 |
| 나가자 | 출발−10분 ≤ 현재 < 출발 | 노랑 |
| 지각위기 | 출발 ≤ 현재 < 택시마지노선 | 빨강 (깜빡임) |
| 포기 | 현재 ≥ 택시마지노선 + 이동시간 | 회색 오버레이 |

---

## Claude Code 작업 시 참고

- UI 레이아웃: 800×480px 고정 (7인치 공식 디스플레이)
- 폰트: 시스템 monospace (네트워크 없는 환경 대응)
- 상태 로직: `timer_ui.html` → `determineState()` 함수
- 새 정보 카드: `#info-section` 내 `.info-card` 블록 복사 후 id 부여
- GPIO 핀 변경: `nagaja_bridge.py` 상단 `BUZZER_PIN` / `BUTTON_PIN`
