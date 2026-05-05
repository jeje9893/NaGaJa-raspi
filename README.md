# 나가자 — 라즈베리파이 UI 세팅 가이드

## 파일 구성

```
nagaja_ui/
├── timer_ui.html       # 터치스크린 UI (7인치, 800x480)
├── nagaja_bridge.py    # Firestore <-> WebSocket 브리지
└── README.md
```

## 설치 및 실행 (라즈베리파이)

### 1. 파일 복사
```bash
mkdir -p ~/nagaja/ui
cp timer_ui.html nagaja_bridge.py ~/nagaja/ui/
```

### 2. 의존 패키지 설치 (기존 venv 사용)
```bash
source ~/nagaja/venv/bin/activate
pip install websockets
# firebase-admin은 이미 설치되어 있어야 함
```

### 3. 브리지 실행
```bash
cd ~/nagaja/ui
source ~/nagaja/venv/bin/activate
python3 nagaja_bridge.py
```

### 4. 브라우저로 UI 열기 (터치스크린)
```bash
# Chromium 키오스크 모드
chromium-browser --kiosk --noerrdialogs --disable-infobars \
  --app=file:///home/pi/nagaja/ui/timer_ui.html
```

자동 시작 (autostart 파일):
```ini
# /etc/xdg/autostart/nagaja.desktop
[Desktop Entry]
Type=Application
Name=NagaJa
Exec=chromium-browser --kiosk --app=file:///home/pi/nagaja/ui/timer_ui.html
```

---

## 데이터 연동 방식 선택

timer_ui.html 상단 NAGAJA_CONFIG.dataSource 값을 변경하세요:

  'demo'      - 현재 시각 기준 가상 데이터 (개발 테스트용)
  'websocket' - nagaja_bridge.py WebSocket 연결 (권장)
  'file'      - /tmp/nagaja_state.json 폴링 (대안)

---

## Firestore 문서 구조

경로: nagaja/{userId}/schedule/today

{
  "classStartTime":   "09:00",
  "className":        "캡스톤디자인",
  "departureTime":    "08:20",
  "prepStartTime":    "07:50",
  "taxiDeadline":     "08:35",
  "travelMinutes":    25,
  "weatherCondition": "비",
  "weatherDelay":     10,
  "busNextMinutes":   8
}

busNextMinutes가 null이면 버스 카드가 자동으로 숨겨집니다.

---

## 화면 상태 전환 로직

  여유      현재 < 출발-10분              초록
  나가자    출발-10분 <= 현재 < 출발      노랑
  지각위기  출발 <= 현재 < 택시마지노선   빨강 (깜빡임)
  포기      현재 >= 택시마지노선+이동시간 회색 오버레이

---

## 확장 예정 기능

- busNextMinutes 필드 활성화 -> 다음 버스 카드 자동 표시
- 버튼 이벤트(준비완료/출발) 터치 입력 -> Firestore 기록
- 다중 수업 스케줄 지원

---

## Claude Code 작업 시 참고

- UI 레이아웃: 800x480px 고정 (7인치 공식 디스플레이)
- 폰트: 시스템 monospace (네트워크 없는 환경 대응)
- 상태 로직: determineState() 함수 수정
- 새 정보 카드 추가: #info-section 내 .info-card 블록 복사 후 id 부여
