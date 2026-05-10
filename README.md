# 나가자 — 라즈베리파이 세팅 가이드

## 파일 구성

```
/home/jeje9893/nagaja/
├── venv/                      # Python 가상환경
├── timer_ui.html              # 터치스크린 UI (7인치, 800×480)
├── nagaja_bridge.py           # Firestore ↔ WebSocket 브리지 + 부저 알람
├── init_firestore.py          # Firestore 초기 데이터 생성 (1회성)
├── firebase_test.py           # Firebase 연결 테스트 (쓰기/읽기)
├── db_read_write_test.py      # Firestore 읽기·수정 연동 테스트
├── DB_STRUCTURE.md            # Firestore 컬렉션 구조 개발자 참조 문서
├── requirements.txt           # Python 의존 패키지 목록
├── serviceAccountKey.json     # Firebase 서비스 계정 키 (git 제외)
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

### 0단계 — Firestore DB 읽기·수정 연동 테스트 (dbtest 브랜치)

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

## GitHub에 포함되지 않은 보안 파일

보안상 민감한 파일은 `.gitignore`에 등록되어 **GitHub에 올라가지 않습니다.**  
`git clone` 또는 `git pull` 후 **수동으로** 라즈베리파이에 배치해야 합니다.

| 파일 | 역할 | 취득 방법 |
|---|---|---|
| `serviceAccountKey.json` | Firebase 서비스 계정 비밀키 (운영용) | Firebase Console → 프로젝트 설정 → 서비스 계정 탭 → **새 비공개 키 생성** |
| `testKey.json` | Firebase 비밀키 (테스트 프로젝트용) | 동일 (테스트용 Firebase 프로젝트에서 발급) |
| `github token.txt` | GitHub Personal Access Token | GitHub → Settings → Developer Settings → Personal Access Tokens → Tokens (classic) |

### 라즈베리파이로 파일 전송

**방법 1: scp (같은 네트워크 내)**
```bash
# Windows PowerShell 또는 Git Bash 에서 실행
scp serviceAccountKey.json jeje9893@<라즈베리파이_IP>:~/nagaja/
scp testKey.json            jeje9893@<라즈베리파이_IP>:~/nagaja/
```

**방법 2: USB 드라이브**
```
1. USB에 파일 복사
2. 라즈베리파이에 USB 꽂기
3. 파일 관리자에서 ~/nagaja/ 로 복사
```

> **주의:** 이 파일들을 절대 git add 하거나 타인과 공유하지 마세요.

---

## Firebase 연결 방식

프로젝트는 **Firebase Admin SDK + 서비스 계정 키 파일** 방식으로 Firestore에 연결합니다.

```
serviceAccountKey.json
        ↓  (credentials.Certificate)
Firebase Admin SDK
        ↓  (firestore.client)
Firestore DB
```

**어떤 Firebase 프로젝트에 연결되는지는 키 파일 내용으로 결정됩니다.**  
코드 안에 프로젝트 ID나 DB URL이 하드코딩되어 있지 않습니다.

키 파일을 참조하는 파일과 경로:

| 파일 | 상수명 | 경로 |
|---|---|---|
| `nagaja_bridge.py` | `SERVICE_ACCOUNT_PATH` | `~/nagaja/serviceAccountKey.json` |
| `init_firestore.py` | `SERVICE_ACCOUNT_PATH` | `~/nagaja/serviceAccountKey.json` |
| `firebase_test.py` | `SERVICE_ACCOUNT_PATH` | `~/nagaja/serviceAccountKey.json` |

### 다른 Firebase 프로젝트로 전환하는 방법

**코드 변경 없이** 키 파일만 교체하면 됩니다.

#### 1. 새 프로젝트의 서비스 계정 키 발급
```
Firebase Console (console.firebase.google.com)
  → 전환할 프로젝트 선택
  → 프로젝트 설정 (⚙️)
  → 서비스 계정 탭
  → [새 비공개 키 생성] 버튼 클릭
  → JSON 파일 다운로드
```

#### 2. 기존 키 백업 (선택)
```bash
# 라즈베리파이에서
cp ~/nagaja/serviceAccountKey.json ~/nagaja/serviceAccountKey.json.bak
```

#### 3. 새 키 파일 교체
```bash
# Windows에서 scp로 전송
scp 새로운키파일.json jeje9893@<라즈베리파이_IP>:~/nagaja/serviceAccountKey.json
```

#### 4. 연결 확인
```bash
source ~/nagaja/venv/bin/activate
python3 ~/nagaja/firebase_test.py
# → 쓰기 완료 / 읽기 완료 출력되면 성공
```

#### 5. 브리지 재시작
```bash
sudo systemctl restart nagaja-bridge
```

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
