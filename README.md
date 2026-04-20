# RDAP 퀵버전 Streamlit 설문 앱 — 설치 및 설정 안내

## 📁 파일 목록

```
RDAP-quickvrtest/
├── app.py                    ← 메인 앱 코드
├── requirements.txt          ← 패키지 목록
├── generate_qr.py            ← QR 코드 생성 (배포 후 1회 실행)
├── .gitignore                ← Git 제외 대상 목록
├── README.md                 ← 이 파일
└── .streamlit/
    ├── config.toml           ← UI 테마 설정
    └── secrets.toml          ← 🔒 Google 인증 정보 (직접 입력 필요)
```

## 🚀 설정 순서

### 1단계: 파일 배치

다운로드한 파일들을 아래 경로에 풀어놓습니다.
```
F:\Users\Dropbox\00_2026년\[프로젝트] 종교 편향 테스트\RDAP-quickvrtest\
```

### 2단계: Google Cloud 서비스 계정 설정

1. https://console.cloud.google.com 접속
2. 프로젝트 `ReligiousDiversityAttitudePro` 선택 (또는 새로 생성)
3. **API 및 서비스 → 라이브러리**에서 활성화:
   - ✅ Google Sheets API
   - ✅ Google Drive API
4. **사용자 인증 정보 → 서비스 계정 만들기** → JSON 키 다운로드
5. 서비스 계정 이메일 복사 (예: `xxx@ReligiousDiversityAttitudePro.iam.gserviceaccount.com`)

### 3단계: Google Sheets 준비

1. Google Drive에서 새 스프레드시트 생성: `RDAP_퀵버전_응답데이터`
2. 시트 탭 이름을 `responses`로 변경
3. 서비스 계정 이메일을 **편집자**로 공유
4. URL에서 스프레드시트 ID 복사:
   ```
   https://docs.google.com/spreadsheets/d/[이 부분]/edit
   ```

### 4단계: secrets.toml 입력

`.streamlit/secrets.toml`을 열고, 다운로드한 JSON 파일의 값으로 교체합니다.

⚠️ 반드시 교체해야 할 항목:
- `private_key_id`
- `private_key` (전체 키 문자열)
- `client_email`
- `client_id`
- `client_x509_cert_url`
- `[google_sheets]` 섹션의 `spreadsheet_id`

### 5단계: 로컬 테스트

터미널(CMD/PowerShell)에서:
```cmd
cd "F:\Users\Dropbox\00_2026년\[프로젝트] 종교 편향 테스트\RDAP-quickvrtest"
pip install -r requirements.txt
streamlit run app.py
```

브라우저에서 `http://localhost:8501`이 열리면 테스트 응답 1회 진행 후
Google Sheets에 데이터가 기록되는지 확인합니다.

### 6단계: 배포

1. GitHub 리포지토리 생성 후 push (secrets.toml 제외 확인!)
2. https://share.streamlit.io 에서 배포
3. Settings → Secrets에 secrets.toml 내용 붙여넣기
4. 배포 URL 확정 후 `generate_qr.py`의 URL 수정 → 실행

## ⚠️ 보안 주의사항

- `.streamlit/secrets.toml`은 절대 GitHub에 올리지 마세요
- `.gitignore`가 이미 설정되어 있으나, push 전 반드시 재확인하세요
- 서비스 계정 JSON 파일은 secrets.toml 작성 후 안전한 곳에 별도 보관하세요
