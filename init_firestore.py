"""
init_firestore.py — Firestore 초기 데이터 생성 스크립트 (1회성)
NaGaJa 프로젝트

ERD 기반 컬렉션 구조 (서브컬렉션):
  users/{uid}
  users/{uid}/schedules/{scheduleId}
  users/{uid}/schedules/{scheduleId}/daily_plans/{planId}

이미 문서가 존재하면 건너뜁니다. 안전하게 여러 번 실행해도 됩니다.

실행:
  python3 init_firestore.py
  python3 init_firestore.py --uid <firebase_uid>

의존 패키지:
  pip install firebase-admin
"""

import os
import sys
import argparse
from datetime import datetime, timezone, date

import firebase_admin
from firebase_admin import credentials, firestore

# ─────────────────────────────────────
#  설정
# ─────────────────────────────────────

SERVICE_ACCOUNT_PATH = os.path.expanduser("~/nagaja/serviceAccountKey.json")
DEFAULT_UID = "test_user"


def _now():
    return datetime.now(timezone.utc)


def _today():
    return date.today().isoformat()


# ─────────────────────────────────────
#  Firebase 초기화
# ─────────────────────────────────────

def init_firebase():
    if not firebase_admin._apps:
        if not os.path.exists(SERVICE_ACCOUNT_PATH):
            print(f"[ERROR] 서비스 계정 파일 없음: {SERVICE_ACCOUNT_PATH}")
            sys.exit(1)
        cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
        firebase_admin.initialize_app(cred)
        print(f"[OK] Firebase 초기화: {SERVICE_ACCOUNT_PATH}")


# ─────────────────────────────────────
#  users
# ─────────────────────────────────────

def ensure_user(db, uid: str) -> bool:
    """
    users/{uid} 문서가 없으면 생성.
    반환: True=생성됨, False=이미 존재
    """
    ref = db.collection("users").document(uid)
    if ref.get().exists:
        print(f"[SKIP] users/{uid} — 이미 존재")
        return False

    ref.set({
        "id":                     uid,
        "name":                   "",
        "email":                  "",
        "prep_minutes":           30,
        "default_travel_minutes": 30,
        "home_wifi_ssids":        [],
        "school_wifi_ssids":      [],
        "created_at":             _now(),
        "updated_at":             _now(),
    })
    print(f"[CREATE] users/{uid}")
    return True


# ─────────────────────────────────────
#  schedules
# ─────────────────────────────────────

def ensure_schedule(db, uid: str) -> str:
    """
    users/{uid}/schedules 에 문서가 없으면 샘플 스케줄 생성.
    반환: schedule_id (기존 or 새로 생성)
    """
    coll = db.collection("users").document(uid).collection("schedules")
    existing = list(coll.limit(1).stream())
    if existing:
        sid = existing[0].id
        print(f"[SKIP] users/{uid}/schedules/{sid} — 이미 존재")
        return sid

    ref = coll.document()
    sid = ref.id
    ref.set({
        "id":                   sid,
        "user_id":              uid,
        "title":                "샘플 수업",
        "day_of_week":          1,          # 1=월요일 (앱과 동일 규칙 사용)
        "class_time":           "09:00",
        "target_arrival_time":  "08:50",
        "start_place_name":     "집",
        "start_address":        "",
        "destination_name":     "학교",
        "destination_address":  "",
        "transport_mode":       "bus",      # bus | walk | taxi | subway
        "is_active":            True,
        "created_at":           _now(),
        "updated_at":           _now(),
    })
    print(f"[CREATE] users/{uid}/schedules/{sid}")
    return sid


# ─────────────────────────────────────
#  daily_plans
# ─────────────────────────────────────

def ensure_daily_plan(db, uid: str, schedule_id: str):
    """
    .../schedules/{schedule_id}/daily_plans 에 문서가 없으면 오늘 날짜 샘플 플랜 생성.
    """
    coll = (
        db.collection("users").document(uid)
          .collection("schedules").document(schedule_id)
          .collection("daily_plans")
    )
    existing = list(coll.limit(1).stream())
    if existing:
        pid = existing[0].id
        print(f"[SKIP] .../daily_plans/{pid} — 이미 존재")
        return

    ref = coll.document()
    pid = ref.id
    ref.set({
        # ── 기본 식별 정보 ──
        "id":                       pid,
        "schedule_id":              schedule_id,
        "plan_date":                _today(),       # "YYYY-MM-DD"
        "title":                    "샘플 플랜",
        "day_of_week":              1,
        "class_time":               "09:00",
        "target_arrival_time":      "08:50",
        "start_place_name":         "집",
        "destination_name":         "학교",
        "transport_mode":           "bus",

        # ── 사용자 기본값 복사 ──
        "default_travel_minutes":   30,
        "prep_minutes":             30,

        # ── 기본 계산 결과 (앱이 채움) ──
        "base_departure_time":      None,   # timestamp
        "base_alarm_time":          None,   # timestamp
        "calculation_time":         None,   # timestamp

        # ── 날씨 보정 ──
        "weather_type":             None,   # "맑음" | "비" | "눈" | ...
        "weather_adjust_minutes":   0,
        "weather_checked_at":       None,
        "weather_applied":          False,

        # ── 교통 혼잡 보정 ──
        "map_base_travel_minutes":  None,
        "congestion_adjust_minutes": 0,
        "predicted_travel_minutes": None,
        "congestion_applied":       False,

        # ── 최종 출발·알람 시각 ──
        "final_departure_time":     None,   # timestamp
        "final_alarm_time":         None,   # timestamp

        # ── 폴백 여부 ──
        "fallback_used":            False,

        # ── 표시 상태 ──
        "plan_status":              "pending",  # pending | active | completed | missed
        "remaining_margin_minutes": None,
        "display_color":            None,       # "green" | "yellow" | "red"
        "display_checked_at":       None,

        # ── 실행 추적 ──
        "alarm_dismissed_at":       None,   # timestamp
        "departed_at":              None,   # timestamp
        "arrived_at":               None,   # timestamp
        "actual_travel_minutes":    None,
        "result_status":            None,   # "on_time" | "late" | "very_late" | ...

        # ── 메타 ──
        "created_at":               _now(),
        "updated_at":               _now(),
    })
    print(f"[CREATE] .../daily_plans/{pid}")


# ─────────────────────────────────────
#  메인
# ─────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="NaGaJa Firestore 초기 데이터 생성 (없는 경우에만)"
    )
    parser.add_argument(
        "--uid",
        default=DEFAULT_UID,
        help=f"Firebase UID (기본값: {DEFAULT_UID})",
    )
    args = parser.parse_args()
    uid = args.uid

    print("=" * 50)
    print(f"NaGaJa Firestore 초기화")
    print(f"UID : {uid}")
    print(f"날짜: {_today()}")
    print("=" * 50)

    init_firebase()
    db = firestore.client()

    ensure_user(db, uid)
    sid = ensure_schedule(db, uid)
    ensure_daily_plan(db, uid, sid)

    print("\n[DONE] 초기화 완료.")
    print(f"\nFirestore 경로:")
    print(f"  users/{uid}")
    print(f"  users/{uid}/schedules/{sid}")
    print(f"  users/{uid}/schedules/{sid}/daily_plans/...")


if __name__ == "__main__":
    main()
