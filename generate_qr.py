"""
generate_qr.py — RDAP 퀵버전 설문 QR 코드 생성
Streamlit Community Cloud 배포 완료 후, 실제 URL로 수정하여 1회 실행한다.

사용법:
    python generate_qr.py
"""
import qrcode

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⬇️ 배포 후 실제 URL로 교체하세요
SURVEY_URL = "https://rdap-quickvrtest.streamlit.app"
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

qr = qrcode.QRCode(
    version=1,
    error_correction=qrcode.constants.ERROR_CORRECT_H,
    box_size=10,
    border=4,
)
qr.add_data(SURVEY_URL)
qr.make(fit=True)

img = qr.make_image(fill_color="#1A1A2E", back_color="white")
img.save("rdap_survey_qr.png")

print("=" * 50)
print("  QR 코드 생성 완료!")
print(f"  파일: rdap_survey_qr.png")
print(f"  대상 URL: {SURVEY_URL}")
print("=" * 50)
