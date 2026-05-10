# NaGaJa — Firestore 컬렉션 구조

> 실제 Firebase Console 스크린샷 기준으로 작성된 개발자 참조 문서.  
> 코드에서 Firestore 읽기·쓰기 시 필드명·타입을 이 파일에서 확인하세요.

---

## 컬렉션 경로 트리

```
users/
└── {uid}                          ← Firebase Auth UID
    ├── schedules/
    │   └── {scheduleId}           ← 자동 생성 ID
    └── dailyPlans/
        └── {planId}               ← 자동 생성 ID
```

> **주의:** `dailyPlans`는 `schedules` 하위가 아닌 `users/{uid}` 바로 아래에 위치합니다.  
> `dailyPlans` 문서 안의 `scheduleId` 필드가 연결고리 역할을 합니다.

---

## users/{uid}

유저 기본 정보. Firebase Auth UID가 문서 ID.

| 필드 | 타입 | 예시값 | 설명 |
|---|---|---|---|
| `userId` | string | `"NTzZVeFvS7PbmChKhQgL"` | 문서 ID와 동일 |
| `name` | string | `"홍길동"` | 유저 이름 |
| `email` | string | `"hong@test.com"` | 이메일 |
| `prepMinutes` | integer | `20` | 기본 준비 시간(분) |
| `defaultTravelMinutes` | integer | `30` | 기본 이동 시간(분) |
| `homeWifiSsids` | array\<string\> | `["HOME_WIFI"]` | 집 Wi-Fi SSID 목록 |
| `schoolWifiSsids` | array\<string\> | `["SCHOOL_WIFI"]` | 학교 Wi-Fi SSID 목록 |
| `createdAt` | timestamp | — | 생성 시각 |
| `updatedAt` | timestamp | — | 최종 수정 시각 |

---

## users/{uid}/schedules/{scheduleId}

수업 스케줄. 요일별로 반복되는 고정 일정.

| 필드 | 타입 | 예시값 | 설명 |
|---|---|---|---|
| `scheduleId` | string | `"5pOTwxZRtmKB0I6j4PPD"` | 문서 ID와 동일 |
| `userId` | string | `"NTzZVeFvS7PbmChKhQgL"` | 부모 유저 UID |
| `title` | string | `"운영체제"` | 수업명 |
| `dayOfWeek` | integer | `3` | 요일 (1=월 … 7=일) |
| `classTime` | string | `"10:30"` | 수업 시작 시각 (HH:MM) |
| `targetArrivalTime` | string | `"10:25"` | 목표 도착 시각 (HH:MM) |
| `startPlaceName` | string | `"집"` | 출발지 이름 |
| `startAddress` | string | `"부산광역시 부산진구 시민공원로 73"` | 출발지 주소 |
| `destinationName` | string | `"정보관"` | 목적지 이름 |
| `destinationAddress` | string | `"부산대학교 정보관"` | 목적지 주소 |
| `transportMode` | string | `"SUBWAY"` | 이동 수단 (`SUBWAY` \| `BUS` \| `WALK` \| `TAXI`) |
| `isActive` | boolean | `true` | 활성 여부 |
| `createdAt` | timestamp | — | 생성 시각 |
| `updatedAt` | timestamp | — | 최종 수정 시각 |

---

## users/{uid}/dailyPlans/{planId}

날짜별 계산된 출발 플랜. 앱이 매일 자동 생성·갱신.

### 기본 식별 정보

| 필드 | 타입 | 예시값 | 설명 |
|---|---|---|---|
| `dailyPlanId` | string | `"vX6d9EVCoXYdXCrohPIA"` | 문서 ID와 동일 |
| `scheduleId` | string | `"mockScheduleId2"` | 연결된 schedules 문서 ID |
| `planDate` | string | `"2026-04-25"` | 플랜 날짜 (YYYY-MM-DD) |
| `title` | string | `"운영체제"` | 수업명 (schedules에서 복사) |
| `dayOfWeek` | integer | `3` | 요일 |
| `classTime` | string | `"10:30"` | 수업 시작 시각 |
| `targetArrivalTime` | string | `"10:25"` | 목표 도착 시각 |
| `startPlaceName` | string | `"집"` | 출발지 이름 |
| `destinationName` | string | `"정보관"` | 목적지 이름 |
| `transportMode` | string | `"SUBWAY"` | 이동 수단 |

### 시간 계산 결과

| 필드 | 타입 | 예시값 | 설명 |
|---|---|---|---|
| `prepMinutes` | integer | `20` | 준비 시간(분) |
| `defaultTravelMinutes` | integer | `35` | 기본 이동 시간(분) |
| `mapBaseTravelMinutes` | integer | `35` | 지도 API 기반 이동 시간(분) |
| `congestionAdjustMinutes` | integer | `0` | 혼잡도 보정(분) |
| `weatherAdjustMinutes` | integer | `0` | 날씨 보정(분) |
| `predictedTravelMinutes` | integer | `35` | 최종 예측 이동 시간(분) |
| `remainingMarginMinutes` | integer | `30` | 여유 시간(분) |
| `calculationTime` | timestamp | — | 계산 수행 시각 |
| `baseDepartureTime` | timestamp | — | 기본 출발 시각 |
| `finalDepartureTime` | timestamp | — | 최종 출발 시각 |
| `baseAlarmTime` | timestamp | — | 기본 알람 시각 |
| `finalAlarmTime` | timestamp | — | 최종 알람 시각 |

### 날씨·혼잡도 적용 여부

| 필드 | 타입 | 예시값 | 설명 |
|---|---|---|---|
| `weatherType` | string | `"CLEAR"` | 날씨 (`CLEAR` \| `RAIN` \| `SNOW` 등) |
| `weatherApplied` | boolean | `false` | 날씨 보정 적용 여부 |
| `weatherCheckedAt` | timestamp | — | 날씨 조회 시각 |
| `congestionApplied` | boolean | `false` | 혼잡도 보정 적용 여부 |
| `fallbackUsed` | boolean | `false` | 폴백 데이터 사용 여부 |

### 상태·표시

| 필드 | 타입 | 예시값 | 설명 |
|---|---|---|---|
| `planStatus` | string | `"CALCULATED"` | 플랜 상태 (`PENDING` \| `CALCULATED` \| `DEPARTED` \| `ARRIVED`) |
| `displayColor` | string | `"GREEN"` | UI 표시 색상 (`GREEN` \| `YELLOW` \| `RED`) |
| `displayCheckedAt` | timestamp | — | 표시 상태 갱신 시각 |

### 메타

| 필드 | 타입 | 설명 |
|---|---|---|
| `createdAt` | timestamp | 생성 시각 |
| `updatedAt` | timestamp | 최종 수정 시각 |

---

## 컬렉션 간 관계

```
users/{uid}
    │
    ├── schedules/{scheduleId}
    │       ↑
    │       │ dailyPlans.scheduleId 로 참조 (외래키 역할)
    │
    └── dailyPlans/{planId}
            └── scheduleId: "5pOTwxZRtmKB0I6j4PPD"
```

Firestore는 JOIN이 없으므로, `dailyPlans` 문서를 읽은 후 `scheduleId` 값으로  
`users/{uid}/schedules/{scheduleId}` 문서를 별도 조회해야 합니다.

---

## 주의사항

### 필드명 규칙
모든 필드는 **camelCase** 를 사용합니다. (`homeWifiSsids`, `scheduleId`, `planStatus` 등)

### `init_firestore.py` 와의 구조 차이
`init_firestore.py`는 초기 개발 시 ERD 기반으로 작성되어 구조가 다릅니다.

| 항목 | `init_firestore.py` | 실제 Android 앱 |
|---|---|---|
| dailyPlans 위치 | `schedules/{sid}/daily_plans/` | `users/{uid}/dailyPlans/` |
| 필드명 일부 | snake_case 혼용 | 완전 camelCase |

실제 운영 DB는 Android 앱 기준 구조를 따릅니다. `init_firestore.py`는 추후 실제 구조에 맞게 수정 필요.

### 테스트 기준 유저
`db_read_write_test.py`의 기본 테스트 대상:
```
uid: NTzZVeFvS7PbmChKhQgL
```
이 유저에 `schedules`와 `dailyPlans` 서브컬렉션이 모두 존재하는 것이 확인됨.
