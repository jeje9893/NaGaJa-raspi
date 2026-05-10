"""
db_read_write_test.py — Firestore 읽기/쓰기 연동 테스트
NaGaJa 프로젝트 | dbtest 브랜치

실제 Firestore 컬렉션 구조 (Android 앱 기준):
  users/{uid}
  users/{uid}/schedules/{scheduleId}
  users/{uid}/dailyPlans/{planId}          ← schedules 하위가 아님

테스트 항목:
  [users]      전체 읽기 / 단건 읽기 / prepMinutes 수정 + 롤백
  [schedules]  해당 유저의 스케줄 전체 읽기 / 단건 읽기 / isActive 수정 + 롤백
  [dailyPlans] 해당 유저의 플랜 전체 읽기 / 단건 읽기 / displayColor 수정 + 롤백

실행:
  source ~/nagaja/venv/bin/activate
  python3 db_read_write_test.py
  python3 db_read_write_test.py --uid <userId>
"""

import os
import sys
import argparse
from datetime import datetime, timezone

import firebase_admin
from firebase_admin import credentials, firestore

SERVICE_ACCOUNT_PATH = os.path.expanduser("~/nagaja/serviceAccountKey.json")

# dailyPlans + schedules 서브컬렉션이 모두 존재하는 확인된 유저
DEFAULT_UID = "NTzZVeFvS7PbmChKhQgL"

PASS = "✅ PASS"
FAIL = "❌ FAIL"
SKIP = "⏭️  SKIP"

results: dict[str, bool] = {}


def record(label: str, ok: bool):
    results[label] = ok
    return PASS if ok else FAIL


def init_firebase():
    if not firebase_admin._apps:
        if not os.path.exists(SERVICE_ACCOUNT_PATH):
            print(f"{FAIL} 서비스 계정 파일 없음: {SERVICE_ACCOUNT_PATH}")
            sys.exit(1)
        cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
        firebase_admin.initialize_app(cred)


# ══════════════════════════════════════════
#  USERS
# ══════════════════════════════════════════

def test_users_read_all(db) -> list[dict]:
    print("\n[USERS 1] users 컬렉션 전체 읽기")
    docs = list(db.collection("users").stream())
    ok = len(docs) > 0
    print(f"  {record('users_read_all', ok)} 총 {len(docs)}개 문서")
    for doc in docs:
        d = doc.to_dict()
        print(f"    - {doc.id} | name={d.get('name')} | email={d.get('email')}")
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]


def test_users_read_single(db, uid: str) -> dict | None:
    print(f"\n[USERS 2] 단건 읽기 — uid={uid}")
    doc = db.collection("users").document(uid).get()
    ok = doc.exists
    print(f"  {record('users_read_single', ok)}")
    if not ok:
        return None
    d = doc.to_dict()
    print(f"    name             : {d.get('name')}")
    print(f"    email            : {d.get('email')}")
    print(f"    prepMinutes      : {d.get('prepMinutes')}")
    print(f"    defaultTravel    : {d.get('defaultTravelMinutes')}")
    print(f"    homeWifiSsids    : {d.get('homeWifiSsids')}")
    print(f"    schoolWifiSsids  : {d.get('schoolWifiSsids')}")
    return d


def test_users_update(db, uid: str, original: dict) -> int:
    print(f"\n[USERS 3] prepMinutes 수정 테스트")
    ref = db.collection("users").document(uid)
    orig_val = original.get("prepMinutes", 0)
    test_val = orig_val + 999
    ref.update({"prepMinutes": test_val, "updatedAt": datetime.now(timezone.utc)})
    updated = ref.get().to_dict().get("prepMinutes")
    ok = updated == test_val
    print(f"  {record('users_update', ok)} {orig_val} → {test_val} (DB={updated})")
    return orig_val


def rollback_users(db, uid: str, original: dict):
    ref = db.collection("users").document(uid)
    ref.update({"prepMinutes": original.get("prepMinutes"),
                "updatedAt": original.get("updatedAt")})
    restored = ref.get().to_dict().get("prepMinutes")
    ok = restored == original.get("prepMinutes")
    print(f"  {PASS if ok else FAIL} users rollback (prepMinutes={restored})")


# ══════════════════════════════════════════
#  SCHEDULES
# ══════════════════════════════════════════

def test_schedules_read_all(db, uid: str) -> list[dict]:
    print(f"\n[SCHEDULES 1] schedules 전체 읽기 — uid={uid}")
    docs = list(db.collection("users").document(uid).collection("schedules").stream())
    ok = len(docs) > 0
    print(f"  {record('schedules_read_all', ok)} 총 {len(docs)}개 스케줄")
    for doc in docs:
        d = doc.to_dict()
        print(f"    - {doc.id} | title={d.get('title')} | classTime={d.get('classTime')}"
              f" | isActive={d.get('isActive')}")
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]


def test_schedules_read_single(db, uid: str, sid: str) -> dict | None:
    print(f"\n[SCHEDULES 2] 단건 읽기 — sid={sid}")
    doc = (db.collection("users").document(uid)
             .collection("schedules").document(sid).get())
    ok = doc.exists
    print(f"  {record('schedules_read_single', ok)}")
    if not ok:
        return None
    d = doc.to_dict()
    print(f"    title            : {d.get('title')}")
    print(f"    classTime        : {d.get('classTime')}")
    print(f"    dayOfWeek        : {d.get('dayOfWeek')}")
    print(f"    transportMode    : {d.get('transportMode')}")
    print(f"    startPlaceName   : {d.get('startPlaceName')}")
    print(f"    destinationName  : {d.get('destinationName')}")
    print(f"    targetArrival    : {d.get('targetArrivalTime')}")
    print(f"    isActive         : {d.get('isActive')}")
    return d


def test_schedules_update(db, uid: str, sid: str, original: dict) -> bool:
    print(f"\n[SCHEDULES 3] isActive 수정 테스트")
    ref = (db.collection("users").document(uid)
             .collection("schedules").document(sid))
    orig_val = original.get("isActive", True)
    test_val = not orig_val
    ref.update({"isActive": test_val, "updatedAt": datetime.now(timezone.utc)})
    updated = ref.get().to_dict().get("isActive")
    ok = updated == test_val
    print(f"  {record('schedules_update', ok)} {orig_val} → {test_val} (DB={updated})")
    return orig_val


def rollback_schedules(db, uid: str, sid: str, original: dict):
    ref = (db.collection("users").document(uid)
             .collection("schedules").document(sid))
    ref.update({"isActive": original.get("isActive"),
                "updatedAt": original.get("updatedAt")})
    restored = ref.get().to_dict().get("isActive")
    ok = restored == original.get("isActive")
    print(f"  {PASS if ok else FAIL} schedules rollback (isActive={restored})")


# ══════════════════════════════════════════
#  DAILY PLANS  (users/{uid}/dailyPlans)
# ══════════════════════════════════════════

def test_daily_plans_read_all(db, uid: str) -> list[dict]:
    print(f"\n[DAILY_PLANS 1] dailyPlans 전체 읽기 — uid={uid}")
    docs = list(db.collection("users").document(uid).collection("dailyPlans").stream())
    ok = len(docs) > 0
    print(f"  {record('daily_plans_read_all', ok)} 총 {len(docs)}개 플랜")
    for doc in docs:
        d = doc.to_dict()
        print(f"    - {doc.id} | planDate={d.get('planDate')} | title={d.get('title')}"
              f" | status={d.get('planStatus')} | color={d.get('displayColor')}")
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]


def test_daily_plans_read_single(db, uid: str, pid: str) -> dict | None:
    print(f"\n[DAILY_PLANS 2] 단건 읽기 — pid={pid}")
    doc = (db.collection("users").document(uid)
             .collection("dailyPlans").document(pid).get())
    ok = doc.exists
    print(f"  {record('daily_plans_read_single', ok)}")
    if not ok:
        return None
    d = doc.to_dict()
    print(f"    title                 : {d.get('title')}")
    print(f"    planDate              : {d.get('planDate')}")
    print(f"    planStatus            : {d.get('planStatus')}")
    print(f"    displayColor          : {d.get('displayColor')}")
    print(f"    classTime             : {d.get('classTime')}")
    print(f"    transportMode         : {d.get('transportMode')}")
    print(f"    predictedTravelMin    : {d.get('predictedTravelMinutes')}")
    print(f"    remainingMarginMin    : {d.get('remainingMarginMinutes')}")
    print(f"    baseDepartureTime     : {d.get('baseDepartureTime')}")
    print(f"    finalDepartureTime    : {d.get('finalDepartureTime')}")
    print(f"    finalAlarmTime        : {d.get('finalAlarmTime')}")
    print(f"    weatherType           : {d.get('weatherType')}")
    print(f"    weatherApplied        : {d.get('weatherApplied')}")
    print(f"    scheduleId            : {d.get('scheduleId')}")
    return d


def test_daily_plans_update(db, uid: str, pid: str, original: dict):
    print(f"\n[DAILY_PLANS 3] displayColor 수정 테스트")
    ref = (db.collection("users").document(uid)
             .collection("dailyPlans").document(pid))
    orig_val = original.get("displayColor", "GREEN")
    test_val = "TEST_COLOR"
    ref.update({"displayColor": test_val, "updatedAt": datetime.now(timezone.utc)})
    updated = ref.get().to_dict().get("displayColor")
    ok = updated == test_val
    print(f"  {record('daily_plans_update', ok)} {orig_val} → {test_val} (DB={updated})")


def rollback_daily_plans(db, uid: str, pid: str, original: dict):
    ref = (db.collection("users").document(uid)
             .collection("dailyPlans").document(pid))
    ref.update({"displayColor": original.get("displayColor"),
                "updatedAt": original.get("updatedAt")})
    restored = ref.get().to_dict().get("displayColor")
    ok = restored == original.get("displayColor")
    print(f"  {PASS if ok else FAIL} dailyPlans rollback (displayColor={restored})")


# ══════════════════════════════════════════
#  메인
# ══════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="NaGaJa Firestore 읽기/쓰기 테스트")
    parser.add_argument("--uid", default=None, help="테스트할 유저의 userId")
    args = parser.parse_args()

    print("=" * 60)
    print("NaGaJa Firestore 읽기/쓰기 연동 테스트")
    print("컬렉션: users / schedules / dailyPlans")
    print("=" * 60)

    init_firebase()
    db = firestore.client()

    # ── users ──
    users = test_users_read_all(db)
    if not users:
        print("\n중단: 테스트할 유저 없음"); sys.exit(1)

    uid = args.uid or DEFAULT_UID
    print(f"\n  테스트 대상 uid: {uid}")

    user_data = test_users_read_single(db, uid)
    if not user_data:
        sys.exit(1)
    test_users_update(db, uid, user_data)

    # ── schedules ──
    schedules = test_schedules_read_all(db, uid)
    sched_data = None
    if schedules:
        sid = schedules[0]["id"]
        sched_data = test_schedules_read_single(db, uid, sid)
        if sched_data:
            test_schedules_update(db, uid, sid, sched_data)
    else:
        print(f"\n  {SKIP} schedules — 문서 없음")

    # ── dailyPlans ──
    plans = test_daily_plans_read_all(db, uid)
    plan_data = None
    if plans:
        pid = plans[0]["id"]
        plan_data = test_daily_plans_read_single(db, uid, pid)
        if plan_data:
            test_daily_plans_update(db, uid, pid, plan_data)
    else:
        print(f"\n  {SKIP} dailyPlans — 문서 없음")

    # ── 롤백 ──
    print("\n" + "─" * 60)
    print("[ROLLBACK] 모든 수정값 원복")
    rollback_users(db, uid, user_data)
    if sched_data:
        rollback_schedules(db, uid, sid, sched_data)
    if plan_data:
        rollback_daily_plans(db, uid, pid, plan_data)

    # ── 결과 요약 ──
    print("\n" + "=" * 60)
    print("테스트 결과 요약")
    print("=" * 60)
    labels = {
        "users_read_all":            "users  전체 읽기",
        "users_read_single":         "users  단건 읽기",
        "users_update":              "users  수정 (prepMinutes)",
        "schedules_read_all":        "sched  전체 읽기",
        "schedules_read_single":     "sched  단건 읽기",
        "schedules_update":          "sched  수정 (isActive)",
        "daily_plans_read_all":      "plans  전체 읽기",
        "daily_plans_read_single":   "plans  단건 읽기",
        "daily_plans_update":        "plans  수정 (displayColor)",
    }
    all_pass = True
    for key, label in labels.items():
        if key in results:
            ok = results[key]
            all_pass = all_pass and ok
            print(f"  {PASS if ok else FAIL}  {label}")
        else:
            print(f"  {SKIP}  {label}")

    print("─" * 60)
    print(f"  {'✅ 전체 통과' if all_pass else '❌ 일부 실패 — 위 로그 확인'}")
    if not all_pass:
        sys.exit(1)


if __name__ == "__main__":
    main()
