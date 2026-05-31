# 나가자 (NaGaJa) — 프로젝트 설명서

물리 알람시계 등 외부 기기 연동을 위한 프로젝트 구조 및 데이터 명세입니다.

---

## 개요

**나가자**는 대학생을 위한 스마트 알람 · 출결 관리 앱입니다.  
수업 시간표, 이동 경로, 날씨, 대중교통 혼잡도를 종합해 **최적 기상/출발 시각을 자동 계산**합니다.

- 플랫폼: Flutter (Android / iOS)
- 백엔드: Firebase (Firestore, Authentication, Cloud Functions)
- 리전: `asia-northeast3` (서울)
- Firebase 프로젝트 ID: `nagaja-a6a8b`

---

## 핵심 개념

| 용어 | 설명 |
|------|------|
| `prepMinutes` | 알람 울린 후 실제 출발까지 걸리는 준비 시간 (기본 30분) |
| `defaultTravelMinutes` | 기본 이동 시간 (기본 20분) |
| `finalAlarmTime` | **알람시계가 울려야 할 시각** = 목표 도착 시각 − 예측 이동 시간 − 준비 시간 |
| `finalDepartureTime` | 출발해야 할 시각 = 목표 도착 시각 − 예측 이동 시간 |
| `displayColor` | 시간 여유 상태: `GREEN` (여유) / `YELLOW` (주의) / `RED` (위험) |
| `planStatus` | `CALCULATED` (정상 계산) / `FALLBACK` (로컬 폴백) |

---

## Firestore 데이터 구조

### 1. 사용자 문서 — `users/{userId}`

```
users/
  {userId}/
    userId          : String   — Firebase Auth UID
    name            : String   — 사용자 이름
    email           : String   — 이메일
    prepMinutes     : int      — 준비 시간 (분)
    defaultTravelMinutes : int — 기본 이동 시간 (분)
    homeWifiSsids   : String[] — 집 Wi-Fi SSID 목록
    schoolWifiSsids : String[] — 학교 Wi-Fi SSID 목록
    createdAt       : Timestamp
    updatedAt       : Timestamp
```

### 2. 수업 일정 — `users/{userId}/schedules/{scheduleId}`

```
schedules/
  {scheduleId}/
    scheduleId          : String   — 문서 ID와 동일
    userId              : String
    title               : String   — 과목명 (예: "자료구조")
    dayOfWeek           : int      — 1=월 ~ 7=일
    classTime           : String   — "HH:MM" 수업 시작 시각
    targetArrivalTime   : String   — "HH:MM" 목표 도착 시각
    startPlaceName      : String   — 출발지 이름 (예: "집")
    startAddress        : String   — 출발지 주소
    startLat            : double?  — 출발지 위도 (백엔드 계산)
    startLng            : double?  — 출발지 경도 (백엔드 계산)
    destinationName     : String   — 목적지 이름 (예: "공학관")
    destinationAddress  : String   — 목적지 주소
    endLat              : double?  — 목적지 위도
    endLng              : double?  — 목적지 경도
    transportMode       : String   — "BUS" | "SUBWAY" | "WALK"
    isActive            : bool     — 비활성화된 일정은 false
    createdAt           : Timestamp
    updatedAt           : Timestamp
```

### 3. 오늘의 플랜 — `users/{userId}/dailyPlans/{planId}`

**알람시계가 주로 참조해야 할 컬렉션입니다.**

```
dailyPlans/
  {planId}/
    dailyPlanId             : String
    scheduleId              : String   — schedules 문서 ID 참조
    planDate                : String   — "YYYY-MM-DD" (KST 기준)
    title                   : String   — 과목명
    dayOfWeek               : int
    classTime               : String   — "HH:MM"
    targetArrivalTime       : String   — "HH:MM"

    finalAlarmTime          : Timestamp  ★ 알람 시각 (알람시계 핵심 값)
    finalDepartureTime      : Timestamp  ★ 출발 시각
    baseAlarmTime           : Timestamp  — 혼잡/날씨 보정 전 원래 알람 시각
    baseDepartureTime       : Timestamp

    prepMinutes             : int      — 준비 시간
    defaultTravelMinutes    : int      — 기본 이동 시간
    predictedTravelMinutes  : int      — 예측 이동 시간 (날씨/혼잡도 반영)
    congestionAdjustMinutes : int      — 혼잡도 보정 시간 (+이면 늦어짐)
    weatherAdjustMinutes    : int      — 날씨 보정 시간
    weatherType             : String   — "CLEAR" | "RAIN" | "SNOW" 등
    remainingMarginMinutes  : int      — 현재 시각 기준 여유 시간

    displayColor            : String   — "GREEN" | "YELLOW" | "RED"
    planStatus              : String   — "CALCULATED" | "FALLBACK"
    fallbackUsed            : bool     — Cloud Function 실패 시 로컬 계산 여부

    calculationTime         : Timestamp
    createdAt               : Timestamp
    updatedAt               : Timestamp
```

### 4. 기타 서브컬렉션

```
users/{userId}/arrivalLogs/{logId}
  arrivedAt   : Timestamp
  scheduleId  : String?
  createdAt   : Timestamp

users/{userId}/prepLogs/{logId}
  startedAt     : Timestamp
  departedAt    : Timestamp
  scheduleId    : String?
  actualMinutes : int
  createdAt     : Timestamp
```

---

## Cloud Functions API

베이스 URL: `https://asia-northeast3-nagaja-a6a8b.cloudfunctions.net`

모든 요청은 `Content-Type: application/json`, POST 방식.  
인증이 필요한 엔드포인트는 `Authorization: Bearer {Firebase ID Token}` 헤더 포함.

### `POST /generateDailyPlan` ★ 핵심 함수

날씨 + 대중교통 혼잡도를 반영해 `dailyPlans` 문서를 생성/갱신합니다.  
알람시계에서 알람 시각을 갱신하고 싶을 때 호출하면 됩니다.

**Request Body**
```json
{
  "userId": "Firebase UID",
  "scheduleId": "선택 — 특정 수업만 계산할 때"
}
```

**Response** `200 OK`  
성공 시 Firestore `dailyPlans`에 문서가 생성/갱신됩니다.

---

### `POST /getTransitData`

특정 유저의 첫 번째 활성 스케줄로 대중교통 경로를 조회합니다.

```json
{ "userId": "Firebase UID", "routeNo": "버스 노선번호(선택)" }
```

---

### `POST /getCongestionData`

버스 노선 혼잡도를 계산합니다.

```json
{ "routeNo": "버스 노선번호", "departureAt": "2025-01-01T08:00:00" }
```

---

### `POST /getWeatherData`

출발지 기준 날씨를 조회합니다.

```json
{ "userId": "Firebase UID" }
```

---

## 알람시계 연동 흐름

```
1. Firebase Auth 로그인 → ID Token 획득
2. POST /generateDailyPlan  →  dailyPlans 문서 생성/갱신
3. Firestore 읽기:
     users/{uid}/dailyPlans
       where planDate == "오늘 날짜(YYYY-MM-DD, KST)"
4. finalAlarmTime (Timestamp) → 알람 시각으로 설정
5. displayColor 으로 LED 색상 표시 (GREEN/YELLOW/RED)
```

> **주의**: 날짜는 **KST(UTC+9)** 기준입니다.  
> `planDate` 필드는 `"YYYY-MM-DD"` 문자열이며, UTC 자정이 아닌 KST 자정 기준으로 생성됩니다.

---

## displayColor 판단 기준

앱 내 상태(HomeScreen) 기준으로 남은 시간을 계산합니다.

| 조건 | displayColor |
|------|-------------|
| 여유 시간 > 이동시간 + 10분 | `GREEN` |
| 여유 시간 > 이동시간 + 5분  | `YELLOW` |
| 그 외 (지각 위험)           | `RED` |

---

## 인증 방식

Firebase Authentication (Google 소셜 로그인 기반).  
Cloud Functions 호출 시 `Authorization: Bearer <idToken>` 헤더 필요.  
ID Token은 1시간마다 갱신됩니다.

---

## 타임존

- 앱 및 Cloud Functions 모두 **KST (UTC+9)** 기준으로 날짜를 계산합니다.
- Firestore Timestamp는 UTC로 저장되므로, 읽을 때 +9시간 변환이 필요합니다.
- `planDate` 문자열(`"YYYY-MM-DD"`)은 KST 기준입니다.
