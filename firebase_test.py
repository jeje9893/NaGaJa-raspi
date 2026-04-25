import firebase_admin
from firebase_admin import credentials, firestore

# 초기화
cred = credentials.Certificate("testKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# 쓰기 테스트
db.collection("test").document("hello").set({
    "message": "라즈베리파이에서 연결 성공",
    "timestamp": firestore.SERVER_TIMESTAMP
})
print("쓰기 완료")

# 읽기 테스트
doc = db.collection("test").document("hello").get()
if doc.exists:
    print("읽기 완료:", doc.to_dict())
else:
    print("문서 없음")
