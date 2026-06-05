# 나가자 (NaGaJa) 발표 슬라이드 구성안

> 총 21장 | 약 15~20분 발표 기준 | 청중: 교수/심사위원/동료 학생

---

## Slide 1 — 표지

**제목**: 나가자 (NaGaJa)  
**부제**: 스마트 기상 알람 + 물리 알람시계 연동 시스템  
**핵심 메시지**: 이름부터 직관적 — "지금 나가자!"

**들어갈 내용**:
- 프로젝트명 "나가자 (NaGaJa)" 큰 텍스트
- 팀원 이름 / 날짜
- 짧은 한 줄 설명: "수업에 늦지 않도록, 스스로 계산하는 알람시계"

**추천 시각 자료**:
- 라즈베리파이 + 7인치 디스플레이 실물 사진 (배경)
- 또는 timer_ui.html 스크린샷 (GREEN 상태)

---

## Slide 2 — 문제 제기

**제목**: 왜 스마트폰 알람은 아직도 불편할까?  
**핵심 메시지**: 기존 알람의 3가지 근본적 한계

**들어갈 내용**:
- 매일 아침 알람을 수동으로 바꾸는 번거로움
- 날씨가 나빠도, 교통이 막혀도 알람은 그대로
- 알람이 울려도 "얼마나 서두르면 되는지" 알 수 없음

**추천 시각 자료**:
- 스마트폰 알람 화면 스크린샷 (일반 알람, 정보 없음)
- 대비: "07:30 알람 ≠ 날씨·교통 반영"

---

## Slide 3 — 해결 아이디어

**제목**: 나가자의 접근: 알람이 스스로 계산한다  
**핵심 메시지**: 수업 시간표 + 날씨 + 교통 = 최적 기상 시각 자동 계산

**들어갈 내용**:
- 공식: `기상 시각 = 수업 시작 - 예측 이동 시간 - 준비 시간`
- 날씨(비/눈), 대중교통 혼잡도도 자동 반영
- 결과를 물리 알람시계(라즈베리파이)에 실시간 전송

**추천 시각 자료**:
- 수식을 시각화한 타임라인 화살표 (기상 → 준비 → 출발 → 도착)
- 또는 간단한 계산 예시 (10:30 수업, 35분 이동, 25분 준비 → 09:25 기상)

---

## Slide 4 — 시스템 전체 구조

**제목**: 3-Tier 아키텍처: 앱 ↔ Firebase ↔ 라즈베리파이  
**핵심 메시지**: 각 레이어가 역할을 분담하는 클라우드 연동 구조

**들어갈 내용**:
- Tier 1: Flutter 모바일 앱 (계산 + 등록)
- Tier 2: Firebase / Firestore (실시간 데이터 허브)
- Tier 3: Raspberry Pi (표시 + 알람 출력)
- Bluetooth로 앱 ↔ Pi 초기 연결

**추천 시각 자료**:
- 3-tier 아키텍처 다이어그램 (화살표 포함)
- 각 레이어 아이콘: 스마트폰 📱 / 클라우드 ☁️ / 라즈베리파이 🖥️

---

## Slide 5 — 모바일 앱 소개 (Flutter)

**제목**: 수업 시간표 등록부터 플랜 계산까지  
**핵심 메시지**: 사용자는 앱에서 수업만 등록하면 모든 것이 자동

**들어갈 내용**:
- 수업 등록: 과목명, 요일, 시각, 출발지/목적지, 이동 수단
- Cloud Functions가 날씨/교통 API를 조합해 `finalAlarmTime` 계산
- `displayColor`: GREEN / YELLOW / RED로 상태 전달
- Firebase Auth: Google 소셜 로그인

**추천 시각 자료**:
- Flutter 앱 UI 스크린샷 (수업 등록 화면, 홈 화면)
- Cloud Functions API 목록 (`/generateDailyPlan`, `/getWeatherData` 등)

---

## Slide 6 — Firebase / Firestore 데이터 구조

**제목**: 모든 데이터가 흐르는 곳 — Firestore 컬렉션 구조  
**핵심 메시지**: `dailyPlans` 컬렉션이 Pi와 앱을 연결하는 핵심

**들어갈 내용**:
- 컬렉션 트리: `users/{uid}` → `schedules/` + `dailyPlans/`
- `dailyPlans` 핵심 필드: `finalAlarmTime`, `finalDepartureTime`, `displayColor`
- `planDate`: KST 기준 "YYYY-MM-DD" 문자열
- 앱 ↔ Pi 연결고리: `dailyPlans` 문서 하나

**추천 시각 자료**:
- Firestore 컬렉션 트리 다이어그램
- 실제 Firebase Console 스크린샷 (dailyPlans 문서)

---

## Slide 7 — Cloud Functions API

**제목**: 날씨 + 교통 + 혼잡도를 하나로 — generateDailyPlan  
**핵심 메시지**: 서버리스 함수가 복잡한 계산을 담당

**들어갈 내용**:
- `POST /generateDailyPlan`: 핵심 함수, dailyPlans 문서 생성/갱신
- `POST /getTransitData`: 대중교통 경로 조회
- `POST /getCongestionData`: 버스 노선 혼잡도
- `POST /getWeatherData`: 날씨 조회
- 베이스 URL: `asia-northeast3-nagaja-a6a8b.cloudfunctions.net`

**추천 시각 자료**:
- API 호출 흐름 다이어그램 (앱 → Cloud Function → Firestore)
- 요청/응답 JSON 예시

---

## Slide 8 — 라즈베리파이 브리지 스크립트 개요

**제목**: nagaja_bridge.py — 4개 컴포넌트가 동시에 동작  
**핵심 메시지**: asyncio + 멀티스레드 하이브리드 설계

**들어갈 내용**:
- 메인 스레드: asyncio WebSocket 서버 (포트 8765)
- 데몬 스레드 1: Firestore on_snapshot 리스너
- 데몬 스레드 2: 알람 체커 (1초 루프)
- 데몬 스레드 3: Bluetooth RFCOMM 서버

**추천 시각 자료**:
- 4개 컴포넌트 동작 다이어그램 (스레드 구분 색상)
- `asyncio.run_coroutine_threadsafe()` 스레드 경계 표시

---

## Slide 9 — Firestore 실시간 리스너 상세

**제목**: 앱 설정이 바뀌면 Pi 화면이 1~2초 내 즉시 반영  
**핵심 메시지**: `on_snapshot`으로 polling 없이 실시간 동기화

**들어갈 내용**:
- `col_ref.on_snapshot(callback)`: DB 변경 감지 → 콜백 자동 호출
- `planDate == 오늘(KST)` 조건 쿼리
- 수업이 여러 개일 때 다음 수업 자동 선택 로직
- `run_coroutine_threadsafe()`: 스레드 → asyncio 경계 안전 통과

**추천 시각 자료**:
- 코드 블록: `on_snapshot` 콜백 핵심 로직
- 타임라인: Firebase 변경 → 콜백 → WebSocket 브로드캐스트 → 화면 갱신

---

## Slide 10 — 타이머 UI 화면 설명

**제목**: 7인치 디스플레이의 타이머 UI — timer_ui.html  
**핵심 메시지**: 한눈에 상황을 파악할 수 있는 시각적 인터페이스

**들어갈 내용**:
- 좌: 480×480 SVG 원형 링 (초록/노랑/빨강 3구간)
- 우: 현재 시각, 준비/이동/출발 3열 카드, 날씨, 혼잡도
- 중앙: 여유 시 수업 시각 | 긴박 시 출발까지 카운트다운
- 3가지 데이터 소스: websocket / file / demo

**추천 시각 자료**:
- timer_ui.html 실제 스크린샷 3장 (GREEN / YELLOW / RED 상태)
- 라즈베리파이 + 7인치 디스플레이 실물 사진

---

## Slide 11 — SVG 원형 링 계산 원리

**제목**: 수학으로 만든 타이머 링 — stroke-dasharray 활용  
**핵심 메시지**: 외부 라이브러리 없이 순수 SVG/JS로 구현

**들어갈 내용**:
- 원 둘레: `2π × 200 = 1256.64`
- `stroke-dasharray`: 그릴 길이 / 빈 공간 제어
- `stroke-dashoffset`: 시작 위치 제어
- 3구간 비율 계산: `r1 = (dep-10-ps)/total`, `r2 = (dep-ps)/total`

**추천 시각 자료**:
- SVG 링 분할 원리 다이어그램 (구간 표시)
- 핵심 JS 코드 블록 `segDash()` 함수

---

## Slide 12 — GPIO 부저 + 버튼 하드웨어 연동

**제목**: 물리 알람시계의 핵심 — 부저와 버튼  
**핵심 메시지**: 소프트웨어 폴링이 아닌 하드웨어 인터럽트로 즉각 응답

**들어갈 내용**:
- GPIO 18: 능동 부저 (별도 PWM 불필요)
- GPIO 17: 알람 해제 버튼 (FALLING edge 인터럽트)
- 기상 알람: 최대 120초, 0.5초 간격
- 상태 전환 알림: "삐 삐" 두 번
- 내부 풀업 저항 사용 → 외부 회로 불필요

**추천 시각 자료**:
- GPIO 핀 배선 다이어그램 (BCM 번호 포함)
- 능동 부저 + 버튼 실물 사진 또는 회로도

---

## Slide 13 — Bluetooth 모바일 연동

**제목**: 앱 → Pi: Bluetooth RFCOMM으로 사용자 ID 전달  
**핵심 메시지**: 한 번 연결하면 재부팅 후에도 자동으로 동작

**들어갈 내용**:
- Classic Bluetooth RFCOMM (SPP UUID)
- JSON 1회 전송: `{"userId": "...", "action": "identify"}`
- Pi 응답: `{"status": "ok"}`
- `user_config.json`에 userId 영속 저장
- Android: `flutter_bluetooth_serial`, iOS: BLE GATT 방식 필요

**추천 시각 자료**:
- 블루투스 연결 흐름 시퀀스 다이어그램
- Flutter 앱 설정 화면의 "기기 연결" UI

---

## Slide 14 — 실제 사용 시나리오 (아침 루틴)

**제목**: 나가자를 쓰면 아침이 이렇게 달라진다  
**핵심 메시지**: 계산은 앱이, 알람은 Pi가, 사용자는 버튼만 누른다

**들어갈 내용**:
- 전날 밤: Cloud Functions가 내일 날씨·교통 반영해 플랜 생성
- 기상 알람 울림 → 버튼 눌러 해제
- 화면: GREEN → YELLOW (나가자!) → RED (지각 위기)
- 각 상태 전환마다 "삐삐" 청각 알림

**추천 시각 자료**:
- 단계별 타임라인 (06:00~10:30)
- 각 상태별 UI 스크린샷 나열

---

## Slide 15 — displayColor 판단 기준

**제목**: GREEN / YELLOW / RED — 서버가 판단, Pi는 표시만  
**핵심 메시지**: 상태 계산은 클라우드, 표시는 Pi — 역할 분리

**들어갈 내용**:
- GREEN: 여유 시간 > 이동 + 10분
- YELLOW: 여유 시간 > 이동 + 5분
- RED: 그 외 (지각 위험)
- Pi는 `displayColor` 값을 그대로 사용 → 로직 중복 없음

**추천 시각 자료**:
- 3가지 상태 UI 스크린샷 나란히
- 판단 기준 표

---

## Slide 16 — 데이터베이스 구조 상세

**제목**: Firestore 컬렉션 구조 — 개발자 관점  
**핵심 메시지**: schedules(고정 일정) + dailyPlans(오늘의 계산 결과) 분리

**들어갈 내용**:
- `schedules`: 요일별 반복 수업 (변하지 않음)
- `dailyPlans`: 날씨/교통 반영한 오늘의 계산 결과 (매일 갱신)
- `finalAlarmTime` = `targetArrivalTime` - `predictedTravelMinutes` - `prepMinutes`
- 컬렉션 간 관계: `dailyPlans.scheduleId` → `schedules` 참조

**추천 시각 자료**:
- DB_STRUCTURE.md 기반 컬렉션 다이어그램
- 실제 Firebase Console dailyPlans 문서 필드 목록 스크린샷

---

## Slide 17 — 개발 과정 및 기술적 도전

**제목**: 개발하면서 부딪힌 3가지 도전  
**핵심 메시지**: 실제 구현에서 만난 문제와 해결 방법

**들어갈 내용**:

**도전 1: Firestore DatetimeWithNanoseconds 오류**  
- SDK 버전에 따라 Timestamp 타입이 달라짐 → `_ts_to_utc()` 방어 코드

**도전 2: asyncio + 멀티스레드 스레드 안전성**  
- Firestore 콜백 스레드 → asyncio 이벤트 루프 경계  
- `run_coroutine_threadsafe()`로 해결

**도전 3: Pi 없는 환경에서 UI 개발**  
- `demo` / `file` 모드로 하드웨어 없이도 개발·테스트 가능

**추천 시각 자료**:
- 각 도전별 before/after 코드 스니펫
- Git 커밋 메시지: `fix: Firestore DatetimeWithNanoseconds 오류 수정`

---

## Slide 18 — 테스트 전략 (db_read_write_test.py)

**제목**: 실제 DB를 건드리되 흔적을 남기지 않는 테스트  
**핵심 메시지**: 자동 롤백 설계로 운영 데이터 안전하게 보호

**들어갈 내용**:
- 10단계 테스트: users / schedules / dailyPlans 읽기·쓰기 검증
- 쓰기 후 원래 값 + 원래 `updatedAt`까지 완전 복원
- `✅ PASS / ❌ FAIL / ⏭️ SKIP` 출력 형식
- 실제 Firebase DB(`NTzZVeFvS7PbmChKhQgL`)로 검증 완료

**추천 시각 자료**:
- 테스트 실행 터미널 출력 스크린샷 (✅ 전체 통과)
- 10단계 테스트 항목 표

---

## Slide 19 — 기술 스택 요약

**제목**: 사용한 기술 스택 한눈에 보기  
**핵심 메시지**: 실무에서도 쓰이는 기술들의 조합

**들어갈 내용**:
- **Raspberry Pi**: Python 3.10+, asyncio, RPi.GPIO, PyBluez
- **Cloud**: Firebase Admin SDK 7.4, Firestore, Cloud Functions, Auth
- **Frontend**: HTML/CSS/SVG/Vanilla JS, Chromium 키오스크
- **Mobile**: Flutter (Android/iOS), firebase_flutter
- **인프라**: systemd, autostart, git 5개 브랜치 운영

**추천 시각 자료**:
- 기술 스택 로고 아이콘 그리드
- 또는 레이어별 기술 다이어그램

---

## Slide 20 — 차별점 및 완성도

**제목**: 나가자가 다른 알람 앱과 다른 점  
**핵심 메시지**: 스마트폰 + 물리 기기의 결합, 실시간 연동, 하드웨어 인터럽트

**들어갈 내용**:
- 물리 알람시계: 스마트폰을 봐야 하는 번거로움 제거
- 실시간 3-tier 연동: 앱 변경 → 1~2초 내 Pi 화면 반영
- 하드웨어 인터럽트 버튼: CPU 부하 없는 즉각 응답
- 3-mode 개발 환경: Pi 없이도 개발/테스트 가능
- 자동 롤백 테스트: 운영 데이터 안전 보호
- systemd + autostart: 전원 켜면 자동 시작

**추천 시각 자료**:
- 경쟁 제품 비교표 (일반 알람 / 스마트폰 앱 / 나가자)
- 완성된 실물 사진 (Pi + 디스플레이 + 부저 + 버튼)

---

## Slide 21 — 마무리 및 Q&A

**제목**: 나가자 — 오늘부터 지각 걱정 없이  
**핵심 메시지**: 기술이 일상의 불편함을 해결한다

**들어갈 내용**:
- 핵심 기능 3줄 요약:
  1. 수업·날씨·교통을 반영한 최적 기상 시각 자동 계산
  2. 물리 알람시계(라즈베리파이)에 실시간 전송
  3. 시각·청각으로 "지금 나가야 할 때"를 알려줌
- 향후 개선 방향: BLE iOS 지원, 머신러닝 이동 시간 예측
- Q&A

**추천 시각 자료**:
- 프로젝트 전체 사진 (실제 동작 중인 Pi 디스플레이)
- QR 코드 (GitHub 링크)

---

## 발표 시간 배분 가이드 (15분 기준)

| 슬라이드 | 제목 | 시간 |
|---|---|---|
| 1~3 | 소개 + 문제 + 해결 아이디어 | 2분 |
| 4~7 | 시스템 구조 + Firebase + Cloud Functions | 3분 |
| 8~13 | 핵심 구현 상세 (브리지, UI, GPIO, BT) | 5분 |
| 14~15 | 사용 시나리오 + 상태 전환 | 2분 |
| 16~18 | DB 구조 + 기술 도전 + 테스트 | 2분 |
| 19~21 | 기술 스택 + 차별점 + 마무리 | 1분 |

---

## 데모 시연 포인트 (선택)

발표 중 라이브 데모가 가능하다면 아래 순서를 권장합니다:

1. **Firebase Console 실시간 변경**  
   `dailyPlans/{planId}` → `displayColor` 필드를 `GREEN` → `YELLOW` → `RED`로 변경  
   → Pi 화면이 1~2초 내 바뀌는 모습 시연

2. **demo 모드 UI 확인**  
   `timer_ui.html` `dataSource: 'demo'`로 열어 3가지 상태 자동 전환 시연

3. **터미널 로그**  
   `nagaja_bridge.py` 실행 중인 터미널 화면 — Firestore 구독 및 갱신 로그 표시

4. **버튼으로 알람 해제**  
   부저를 직접 울리고 버튼으로 해제하는 모습 시연
