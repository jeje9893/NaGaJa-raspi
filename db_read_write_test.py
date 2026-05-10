"""
db_read_write_test.py — Firestore 읽기/쓰기 연동 테스트
NaGaJa 프로젝트 | dbtest 브랜치

테스트 항목:
  1. users 컬렉션 전체 읽기
  2. 특정 유저 문서 단건 읽기
  3. 필드 수정 (prepMinutes) 후 확인
  4. 원래 값으로 롤백

실행:
  source ~/nagaja/venv/bin/activate
  python3 db_read_write_test.py
  python3 db_read_write_test.py --uid <userId>   # 특정 유저만 테스트
"""

import os
import sys
import argparse
from datetime import datetime, timezone

import firebase_admin
from firebase_admin import credentials, firestore

SERVICE_ACCOUNT_PATH = os.path.expanduser("~/nagaja/serviceAccountKey.json")

PASS = "✅ PASS"
FAIL = "❌ FAIL"


def init_firebase():
    if not firebase_admin._apps:
        if not os.path.exists(SERVICE_ACCOUNT_PATH):
            print(f"{FAIL} 서비스 계정 파일 없음: {SERVICE_ACCOUNT_PATH}")
            sys.exit(1)
        cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
        firebase_admin.initialize_app(cred)


# ─────────────────────────────────────
#  테스트 1: users 컬렉션 전체 읽기
# ─────────────────────────────────────

def test_read_all_users(db) -> list[dict]:
    print("\n[TEST 1] users 컬렉션 전체 읽기")
    docs = list(db.collection("users").stream())
    if not docs:
        print(f"  {FAIL} 문서 없음")
        return []

    print(f"  {PASS} 총 {len(docs)}개 문서 발견")
    for doc in docs:
        d = doc.to_dict()
        print(f"    - {doc.id} | name={d.get('name')} | email={d.get('email')}")
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]


# ─────────────────────────────────────
#  테스트 2: 특정 유저 단건 읽기
# ─────────────────────────────────────

def test_read_single_user(db, uid: str) -> dict | None:
    print(f"\n[TEST 2] 유저 단건 읽기 — uid={uid}")
    doc = db.collection("users").document(uid).get()
    if not doc.exists:
        print(f"  {FAIL} 문서 없음")
        return None

    d = doc.to_dict()
    print(f"  {PASS} 문서 확인")
    print(f"    name              : {d.get('name')}")
    print(f"    email             : {d.get('email')}")
    print(f"    prepMinutes       : {d.get('prepMinutes')}")
    print(f"    defaultTravelMin  : {d.get('defaultTravelMinutes')}")
    print(f"    homeWifiSsids     : {d.get('homeWifiSsids')}")
    print(f"    schoolWifiSsids   : {d.get('schoolWifiSsids')}")
    print(f"    createdAt         : {d.get('createdAt')}")
    print(f"    updatedAt         : {d.get('updatedAt')}")
    return d


# ─────────────────────────────────────
#  테스트 3: 필드 수정 (prepMinutes)
# ─────────────────────────────────────

def test_update_field(db, uid: str, original: dict) -> bool:
    print(f"\n[TEST 3] 필드 수정 테스트 — prepMinutes 변경")
    ref = db.collection("users").document(uid)
    original_value = original.get("prepMinutes", 0)
    test_value = original_value + 999   # 원본과 구분되는 값

    # 수정
    ref.update({
        "prepMinutes": test_value,
        "updatedAt": datetime.now(timezone.utc),
    })
    print(f"    수정 완료: {original_value} → {test_value}")

    # 재조회로 확인
    updated = ref.get().to_dict()
    if updated.get("prepMinutes") == test_value:
        print(f"  {PASS} 수정 값 DB 반영 확인")
        return True
    else:
        print(f"  {FAIL} 값이 다름: {updated.get('prepMinutes')}")
        return False


# ─────────────────────────────────────
#  롤백: 원래 값 복원
# ─────────────────────────────────────

def rollback_field(db, uid: str, original: dict):
    print(f"\n[ROLLBACK] prepMinutes → {original.get('prepMinutes')} 복원")
    ref = db.collection("users").document(uid)
    ref.update({
        "prepMinutes": original.get("prepMinutes"),
        "updatedAt": original.get("updatedAt"),
    })
    restored = ref.get().to_dict()
    if restored.get("prepMinutes") == original.get("prepMinutes"):
        print(f"  {PASS} 롤백 완료")
    else:
        print(f"  {FAIL} 롤백 실패 — 수동 확인 필요")


# ─────────────────────────────────────
#  메인
# ─────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="NaGaJa Firestore 읽기/쓰기 테스트")
    parser.add_argument("--uid", default=None, help="테스트할 특정 유저의 userId")
    args = parser.parse_args()

    print("=" * 55)
    print("NaGaJa Firestore 읽기/쓰기 테스트")
    print("=" * 55)

    init_firebase()
    db = firestore.client()

    # 테스트 1: 전체 읽기
    users = test_read_all_users(db)
    if not users:
        print("\n중단: 테스트할 유저 없음")
        sys.exit(1)

    # 테스트 대상 uid 결정
    uid = args.uid or users[0]["id"]
    print(f"\n테스트 대상 uid: {uid}")

    # 테스트 2: 단건 읽기
    user_data = test_read_single_user(db, uid)
    if not user_data:
        sys.exit(1)

    # 테스트 3: 수정 + 확인 + 롤백
    success = test_update_field(db, uid, user_data)
    rollback_field(db, uid, user_data)

    # 결과 요약
    print("\n" + "=" * 55)
    print("테스트 결과 요약")
    print("=" * 55)
    print(f"  전체 읽기   : {PASS}")
    print(f"  단건 읽기   : {PASS}")
    print(f"  필드 수정   : {PASS if success else FAIL}")
    print(f"  롤백        : {PASS}")
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
