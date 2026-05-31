# 모바일 앱 수정/추가 사항 (NaGaJa 라즈베리파이 연동)

라즈베리파이 측 변경에 따라 모바일 앱에서 추가 또는 수정이 필요한 사항을 정리한다.

---

## 1. 블루투스 연결 시 사용자 정보 전송

### 배경
설정 화면의 "기기 연결 > 물리 알람시계" 연결 버튼이 이미 존재한다.  
라즈베리파이는 이 연결을 통해 **현재 로그인된 사용자의 Firebase UID**를 받아야 한다.  
Pi는 Firebase Admin SDK(서비스 계정)를 사용하므로 idToken 없이 UID만 있으면 Firestore 접근이 가능하다.

### 구현 사항

#### 1-1. 블루투스 방식: Classic Bluetooth RFCOMM (권장)
- Pi가 RFCOMM 서버로 동작 (채널 1, UUID `00001101-0000-1000-8000-00805F9B34FB`)
- 앱이 클라이언트로 연결 후 JSON 1회 전송

**전송 데이터 형식:**
```json
{
  "userId": "NTzZVeFvS7PbmChKhQgL",
  "action": "identify"
}
```

#### 1-2. 연결 흐름
1. 사용자가 설정 화면에서 "연결" 버튼 탭
2. 앱이 블루투스 기기 목록에서 "NaGaJa-Pi" 기기 검색 (기기명으로 필터)
3. RFCOMM 소켓 연결
4. 현재 로그인 사용자의 Firebase UID를 JSON으로 전송
5. Pi로부터 응답 수신: `{"status": "ok", "userId": "..."}`
6. 연결 상태를 설정 화면에 표시: "연결됨 ✓"

#### 1-3. 앱에서 사용할 Flutter 패키지
```yaml
# pubspec.yaml
flutter_bluetooth_serial: ^0.4.0   # Classic BT (Android)
```

#### 1-4. 연결 끊김 처리
- 앱이 포그라운드로 돌아올 때 재연결 시도
- Pi 전원 꺼짐 감지 시 "연결되지 않음"으로 상태 변경
- 기존 연결 정보(기기 MAC 주소)를 SharedPreferences에 저장해 자동 재연결

#### 1-5. 설정 화면 UI 수정
현재: "연결되지 않음" + "연결" 버튼  
추가: 연결 성공 시 → "연결됨 · NaGaJa-Pi" + "연결 해제" 버튼으로 변경

---

## 2. (선택) BLE GATT 방식 대안

Classic BT 대신 BLE를 사용할 경우:

**Pi 측 서비스 정의:**
- Service UUID: `12345678-1234-1234-1234-123456789abc`
- Characteristic UUID: `12345678-1234-1234-1234-123456789abd` (Write, Notify)

**앱 Flutter 패키지:**
```yaml
flutter_blue_plus: ^1.0.0
```

*구현 복잡도가 높으므로 Classic RFCOMM 방식을 권장한다.*

---

## 3. 주의 사항

- Android 12 이상: 블루투스 권한 선언 필요
  ```xml
  <!-- AndroidManifest.xml -->
  <uses-permission android:name="android.permission.BLUETOOTH_CONNECT"/>
  <uses-permission android:name="android.permission.BLUETOOTH_SCAN"/>
  ```
- iOS는 Classic Bluetooth RFCOMM 미지원 → BLE GATT 방식으로만 가능
- Pi의 블루투스 기기명은 `sudo hostnamectl set-hostname NaGaJa-Pi` 로 설정
