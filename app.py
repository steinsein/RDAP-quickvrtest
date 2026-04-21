"""
RDAP 퀵버전 — Streamlit 웹 설문 앱 (수정판 v3)
종교 다양성 태도 프로파일 (Religious Diversity Attitude Profile)

수정 사항 (v3):
  - 퀵버전 A/B/C 10문항2 반영: 종교 명칭 일반화 + 괄호 예시 방식 적용
  - CR 시나리오 표현 통일 (PT/IS 구조적 대칭 강화)
  - VC 문항에 다종교 예시 추가
  - 선택지 포괄적 표현 적용

Google Cloud 프로젝트: ReligiousDiversityAttitudePro
"""

import streamlit as st
import random
from datetime import datetime, timezone, timedelta

import gspread
from google.oauth2.service_account import Credentials


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 페이지 설정
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
st.set_page_config(
    page_title="종교와 사회 — 나의 시선 돌아보기",
    page_icon="🔍",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    .block-container { max-width: 640px; padding: 1rem 1.5rem; }
    .stRadio > div { gap: 0.3rem; }
    .stRadio > div > label {
        background-color: #F0F4F8;
        padding: 0.6rem 1rem;
        border-radius: 8px;
        border: 1px solid #E0E0E0;
        cursor: pointer;
        transition: all 0.2s;
    }
    .stRadio > div > label:hover {
        background-color: #E3EBF5;
        border-color: #4A6FA5;
    }
    .question-card {
        background: #FAFBFC; border: 1px solid #E8ECF0;
        border-radius: 12px; padding: 1.2rem; margin-bottom: 1.5rem;
    }
    .question-number { color: #4A6FA5; font-weight: 700; font-size: 0.85rem; margin-bottom: 0.3rem; }
    .question-text { font-size: 1.0rem; line-height: 1.6; color: #1A1A2E; }
    .result-main {
        background: linear-gradient(135deg, #4A6FA5 0%, #6B8FC7 100%);
        color: white; border-radius: 16px; padding: 2rem;
        text-align: center; margin: 1.5rem 0;
    }
    .result-main h2 { color: white; margin-bottom: 0.5rem; }
    .result-detail {
        background: #F8F9FB; border-radius: 12px; padding: 1.2rem;
        margin: 0.8rem 0; border-left: 4px solid #4A6FA5;
    }
    .result-section {
        background: #FFFFFF; border: 1px solid #E8ECF0;
        border-radius: 12px; padding: 1.2rem; margin: 1rem 0;
    }
    .result-section h4 { color: #4A6FA5; margin-top: 0; }
    .progress-text { text-align: center; color: #888; font-size: 0.85rem; margin-bottom: 0.5rem; }
    .survey-header { text-align: center; padding: 1rem 0 0.5rem 0; }
    .survey-header h1 { font-size: 1.4rem; color: #1A1A2E; }
    [data-testid="stSidebar"] { display: none; }
    header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Google Sheets 연결
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SHEET_HEADERS = [
    "timestamp", "version", "reverse",
    "Q01_code", "Q01_score", "Q02_code", "Q02_score",
    "Q03_code", "Q03_score", "Q04_code", "Q04_score",
    "Q05_code", "Q05_score", "Q06_code", "Q06_score",
    "Q07_code", "Q07_score", "Q08_code", "Q08_score",
    "Q09_code", "Q09_score", "Q10_code", "Q10_score",
    "cr_dev_A", "cr_dev_B", "cr_dev_C",
    "cr_total", "cr_direction",
    "vc_total", "dq_score", "result_level",
]


@st.cache_resource
def get_gsheet_connection():
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        client = gspread.authorize(creds)
        return client
    except KeyError:
        return None  # secrets 미설정
    except Exception as e:
        return None


def get_worksheet():
    client = get_gsheet_connection()
    if client is None:
        return None
    try:
        spreadsheet_id = st.secrets["google_sheets"]["spreadsheet_id"]
        spreadsheet = client.open_by_key(spreadsheet_id)
        try:
            worksheet = spreadsheet.worksheet("responses")
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(
                title="responses", rows=1000, cols=len(SHEET_HEADERS)
            )
        first_row = worksheet.row_values(1)
        if not first_row or first_row[0] != SHEET_HEADERS[0]:
            worksheet.update(range_name="A1", values=[SHEET_HEADERS])
        return worksheet
    except Exception as e:
        return None


def save_response_to_sheet(answers, survey_data, scores, interp_level):
    worksheet = get_worksheet()
    if worksheet is None:
        return False
    try:
        kst = timezone(timedelta(hours=9))
        now_kst = datetime.now(kst).strftime("%Y-%m-%d %H:%M:%S")
        questions = survey_data["questions"]
        row = [now_kst, st.session_state.version, str(st.session_state.reverse)]
        for i in range(10):
            row.append(questions[i]["code"])
            row.append(str(answers.get(i, "")))
        for domain, dev, pt_s, is_s in scores["cr_deviations"]:
            row.append(str(dev))
        row.append(str(scores["cr_total"]))
        row.append(str(scores["cr_direction_sum"]))
        row.append(str(scores["vc_total"]))
        row.append(str(scores["dq_score"]))
        row.append(interp_level)
        worksheet.append_row(row, value_input_option="USER_ENTERED")
        return True
    except Exception as e:
        return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 설문 데이터 정의 (v3 — 10문항2 반영)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_survey_data():
    surveys = {
        # ════════════════════════════════════════
        # 버전 A: 공간·제도 중심
        # ════════════════════════════════════════
        "A": {
            "title": "퀵버전 A",
            "questions": [
                # Q1 (idx 0) — DQ-VL-XX-03: 내집단편향 / 인지
                {"code": "DQ-VL-XX-03", "type": "DQ",
                 "text": "\"신앙을 가진 사람은 그렇지 않은 사람보다 도덕적으로 더 나은 삶을 산다\"라는 의견에 대해 어떻게 생각하세요?",
                 "options": [
                     "전혀 동의하지 않는다 — 도덕성은 신앙과 관계없다",
                     "대체로 동의하지 않지만, 신앙이 도움이 될 수는 있다고 본다",
                     "어느 정도 동의한다 — 종교적 가르침이 도덕성에 영향을 준다",
                     "동의한다 — 종교적 신념이 도덕적 행동의 기반이다"]},

                # Q2 (idx 1) — CR-PB-PT-01: 현실적위협 / 행동 — 쌍A PT
                {"code": "CR-PB-PT-01", "type": "CR", "pair": "A", "religion": "PT",
                 "text": "내가 사는 동네에 **대규모 예배 시설** (예: 개신교 교회)이 새로 들어선다는 소식을 들었어요. 어떻게 반응할 것 같나요?",
                 "options": [
                     "동네가 다양해지는 것이니 나쁘지 않다",
                     "특별한 관심 없이 받아들인다",
                     "생활 환경에 영향이 있을까 걱정된다",
                     "가능하면 건축을 막고 싶다"]},

                # Q3 (idx 2) — VC-VL-XX-01: 상징적위협·통제적반응 / 인지
                {"code": "VC-VL-XX-01", "type": "VC",
                 "text": "공공장소(지하철, 광장 등)에서의 종교적 전도 행위 (예: 개신교 전도, 불교 포교, 이슬람 선교 등)에 대해 사회적으로 어떤 기준이 적용되어야 한다고 생각하세요?",
                 "options": [
                     "신앙의 자유이므로 아무 제한 없이 허용되어야 한다",
                     "타인에게 직접적 피해를 주지 않는 범위에서 허용되어야 한다",
                     "원하지 않는 사람에게 접근하는 것은 자제되어야 한다",
                     "공공질서를 위해 법적으로 규제해야 한다"]},

                # Q4 (idx 3) — CR-WK-PT-02: 집단간불안·자동적반응 / 정서 — 쌍B PT
                {"code": "CR-WK-PT-02", "type": "CR", "pair": "B", "religion": "PT",
                 "text": "새로 합류한 팀원이 자기소개에서 **특정 종교의 열성 신자** (예: 개신교 신자)라고 밝혔어요. 어떤 느낌이 들 것 같나요?",
                 "options": [
                     "개인의 정체성이니 자연스럽게 받아들인다",
                     "좀 뜬금없지만 크게 신경 쓰지 않는다",
                     "앞으로 종교 이야기가 많을까 봐 살짝 부담스럽다",
                     "그 사람에 대한 인상이 달라진다"]},

                # Q5 (idx 4) — CR-PB-IS-01: 현실적위협 / 행동 — 쌍A IS
                {"code": "CR-PB-IS-01", "type": "CR", "pair": "A", "religion": "IS",
                 "text": "내가 사는 동네에 **대규모 예배 시설** (예: 이슬람 모스크)이 새로 들어선다는 소식을 들었어요. 어떻게 반응할 것 같나요?",
                 "options": [
                     "동네가 다양해지는 것이니 나쁘지 않다",
                     "특별한 관심 없이 받아들인다",
                     "생활 환경에 영향이 있을까 걱정된다",
                     "가능하면 건축을 막고 싶다"]},

                # Q6 (idx 5) — VC-WK-XX-01: 현실적위협·부정적고정관념 / 인지
                {"code": "VC-WK-XX-01", "type": "VC",
                 "text": "면접 과정에서 지원자의 종교적 관행 (예: 무슬림의 하루 다섯 번 기도, 천주교 신자의 매주 미사 참석 등)이 채용 결정에 영향을 줄 수 있다고 생각하세요?",
                 "options": [
                     "종교적 관행이 채용에 영향을 주는 것은 어떤 경우에도 부당하다",
                     "부당하지만, 현실적으로 영향을 줄 수 있다고 생각한다",
                     "업무 특성에 따라 종교적 관행이 고려될 수 있는 경우도 있다고 본다",
                     "종교적 관행이 팀 분위기에 영향을 줄 수 있으니 참고할 수 있다"]},

                # Q7 (idx 6) — CR-PR-PT-01: 집단간불안·내집단편향 / 행동 — 쌍C PT
                {"code": "CR-PR-PT-01", "type": "CR", "pair": "C", "religion": "PT",
                 "text": "교제 중인 사람(또는 자녀의 교제 상대)이 **특정 종교의 열성 신자** (예: 개신교 신자)라는 것을 알게 되었어요. 이 사실이 관계에 대한 판단에 영향을 줄 것 같나요?",
                 "options": [
                     "종교와 관계없이 상대의 인격을 기준으로 판단한다",
                     "약간 신경 쓰이지만 큰 문제는 아니라고 본다",
                     "종교가 같거나 없는 사람이 더 편할 것 같다고 느낀다",
                     "해당 종교 신자와의 관계는 고민이 될 것 같다"]},

                # Q8 (idx 7) — CR-WK-IS-02: 집단간불안·자동적반응 / 정서 — 쌍B IS
                {"code": "CR-WK-IS-02", "type": "CR", "pair": "B", "religion": "IS",
                 "text": "새로 합류한 팀원이 자기소개에서 **특정 종교의 열성 신자** (예: 무슬림)라고 밝혔어요. 어떤 느낌이 들 것 같나요?",
                 "options": [
                     "개인의 정체성이니 자연스럽게 받아들인다",
                     "좀 뜬금없지만 크게 신경 쓰지 않는다",
                     "앞으로 종교 이야기가 많을까 봐 살짝 부담스럽다",
                     "그 사람에 대한 인상이 달라진다"]},

                # Q9 (idx 8) — VC-VL-XX-13: 통제적반응·당위실제불일치 / 인지
                {"code": "VC-VL-XX-13", "type": "VC",
                 "text": "\"모든 종교를 존중해야 한다\"는 원칙에 동의하시나요? 만약 동의한다면, 그 원칙이 적용되지 않아도 되는 경우 (예: 불교, 천주교, 이슬람, 개신교 등 어떤 종교든)가 있다고 생각하세요?",
                 "options": [
                     "모든 종교를 예외 없이 존중해야 한다",
                     "대부분의 종교를 존중하되, 반사회적 행위를 하는 종교는 예외이다",
                     "사회적 기준에 부합하는 종교만 존중의 대상이 된다",
                     "\"존중\"은 비판하지 않는 것이 아니라, 존재를 인정하는 것이다"]},

                # Q10 (idx 9) — CR-PR-IS-01: 집단간불안·내집단편향 / 행동 — 쌍C IS
                {"code": "CR-PR-IS-01", "type": "CR", "pair": "C", "religion": "IS",
                 "text": "교제 중인 사람(또는 자녀의 교제 상대)이 **특정 종교의 열성 신자** (예: 무슬림)라는 것을 알게 되었어요. 이 사실이 관계에 대한 판단에 영향을 줄 것 같나요?",
                 "options": [
                     "종교와 관계없이 상대의 인격을 기준으로 판단한다",
                     "약간 신경 쓰이지만 큰 문제는 아니라고 본다",
                     "종교가 같거나 없는 사람이 더 편할 것 같다고 느낀다",
                     "해당 종교 신자와의 관계는 고민이 될 것 같다"]},
            ],
            "cr_pairs": [(1, 4, "공적영역"), (3, 7, "직장"), (6, 9, "사적관계")],
            "vc_indices": [2, 5, 8], "dq_index": 0,
            "dq_label": "종교인 도덕적 우위 신념",
            "dq_interp": {
                1: "도덕성과 종교를 분리하여 바라보고 있으며, 종교 유무에 따른 도덕적 평가를 하지 않는 경향입니다.",
                2: "종교의 긍정적 역할을 인정하면서도, 도덕성을 종교에 귀속시키지는 않는 균형 잡힌 시선입니다.",
                3: "종교적 가르침이 도덕성에 기여한다고 보는 시선으로, 무종교인에 대해 다소 낮은 기대를 가질 수 있는 인식입니다.",
                4: "종교를 도덕성의 기반으로 보는 강한 신념으로, 무종교인을 도덕적으로 부족하게 볼 가능성이 있습니다. 이는 일상에서 비종교인에 대한 미묘한 차별로 이어질 수 있습니다.",
            },
        },

        # ════════════════════════════════════════
        # 버전 B: 행동·요청 중심
        # ════════════════════════════════════════
        "B": {
            "title": "퀵버전 B",
            "questions": [
                # Q1 (idx 0) — DQ-WK-XX-02: 부정적고정관념 / 인지
                {"code": "DQ-WK-XX-02", "type": "DQ",
                 "text": "새로 온 동료가 특정 종교의 열성 신자라는 것을 알게 되었어요. 그 동료에 대한 첫인상이 달라질 것 같나요?",
                 "options": [
                     "종교는 개인의 영역이라 인상에 영향을 주지 않는다",
                     "살짝 궁금하지만 업무 관계에는 영향이 없다",
                     "어떤 종교냐에 따라 인상이 좀 달라질 수 있다",
                     "열성 신자라는 점이 약간 부담스럽게 느껴진다"]},

                # Q2 (idx 1) — CR-PB-PT-02: 상징적위협·자동적반응 / 정서 — 쌍A PT
                {"code": "CR-PB-PT-02", "type": "CR", "pair": "A", "religion": "PT",
                 "text": "공원에서 **종교인 몇 명이 조용히 야외 기도** (예: 개신교 기도 모임)를 하고 있는 것을 봤어요. 어떤 느낌이 들 것 같나요?",
                 "options": [
                     "자유로운 종교 활동으로 자연스럽게 여긴다",
                     "좀 눈에 띄지만 신경 쓰지 않는다",
                     "왠지 불편하거나 어색하게 느껴진다",
                     "공공장소에서 그런 행동을 하면 안 된다고 생각한다"]},

                # Q3 (idx 2) — VC-VL-XX-02: 현실적위협·통제적반응 / 인지
                {"code": "VC-VL-XX-02", "type": "VC",
                 "text": "주거 밀집 지역에 대규모 종교 시설 (예: 불교 사찰, 천주교 성당, 이슬람 모스크 등)을 건축하려는 계획에 대해, 지자체는 어떤 기준을 적용해야 한다고 생각하세요?",
                 "options": [
                     "종교의 자유에 따라 건축을 허용해야 한다",
                     "교통·소음 등 객관적 기준만 적용하고, 어떤 종교인지는 고려하지 않아야 한다",
                     "지역 주민의 의견을 반영하여 허가 여부를 결정해야 한다",
                     "주거 지역에는 대규모 종교 시설 건축을 제한해야 한다"]},

                # Q4 (idx 3) — CR-WK-PT-01: 상징적위협·집단간불안 / 행동 — 쌍B PT
                {"code": "CR-WK-PT-01", "type": "CR", "pair": "B", "religion": "PT",
                 "text": "직장 동료가 **정기 종교 모임 참석** (예: 개신교 수요 예배)을 이유로 **매주 특정 요일에 일찍 퇴근**하겠다고 요청했어요. 어떻게 반응할 것 같나요?",
                 "options": [
                     "종교 활동도 중요하니 기꺼이 배려한다",
                     "업무에 지장이 없는 범위에서 괜찮다고 본다",
                     "개인 종교 때문에 업무 일정을 바꾸는 것은 좀 부담스럽다",
                     "직장에서 종교적 이유로 특별 대우를 받는 것은 적절하지 않다고 본다"]},

                # Q5 (idx 4) — CR-PB-IS-02: 상징적위협·자동적반응 / 정서 — 쌍A IS
                {"code": "CR-PB-IS-02", "type": "CR", "pair": "A", "religion": "IS",
                 "text": "공원에서 **종교인 몇 명이 조용히 야외 예배** (예: 이슬람 기도)를 하고 있는 것을 봤어요. 어떤 느낌이 들 것 같나요?",
                 "options": [
                     "자유로운 종교 활동으로 자연스럽게 여긴다",
                     "좀 눈에 띄지만 신경 쓰지 않는다",
                     "왠지 불편하거나 어색하게 느껴진다",
                     "공공장소에서 그런 행동을 하면 안 된다고 생각한다"]},

                # Q6 (idx 5) — VC-VL-XX-04: 상징적위협·통제적반응 / 인지
                {"code": "VC-VL-XX-04", "type": "VC",
                 "text": "특정 종교의 가르침이나 관행 (예: 이슬람의 라마단 금식, 불교의 채식 수행, 천주교의 사순절 절제 등)을 공개적으로 비판하는 것에 대해 어떻게 생각하세요?",
                 "options": [
                     "표현의 자유이므로 자유롭게 허용되어야 한다",
                     "종교 공동체 내에서는 자유이나, 공적 영역에서는 자제해야 한다",
                     "대상이 되는 집단에 대한 차별을 조장할 수 있으므로 자제되어야 한다",
                     "명확히 차별적 발언이므로 규제되어야 한다"]},

                # Q7 (idx 6) — CR-PR-PT-04: 현실적위협·자동적반응 / 행동 — 쌍C PT
                {"code": "CR-PR-PT-04", "type": "CR", "pair": "C", "religion": "PT",
                 "text": "이사할 집을 알아보는데, 마음에 드는 집 바로 옆에 **대규모 종교 시설** (예: 개신교 교회)이 있어요. 이 점이 결정에 영향을 줄 것 같나요?",
                 "options": [
                     "종교 시설과 관계없이 집 자체의 조건으로 결정한다",
                     "약간 고려하지만 결정적 요인은 아니다",
                     "이 점 때문에 고민이 좀 된다",
                     "다른 집을 찾아볼 것 같다"]},

                # Q8 (idx 7) — CR-WK-IS-01: 상징적위협·집단간불안 / 행동 — 쌍B IS
                {"code": "CR-WK-IS-01", "type": "CR", "pair": "B", "religion": "IS",
                 "text": "직장 동료가 **정기 종교 모임 참석** (예: 이슬람 금요 합동 예배)을 이유로 **매주 특정 요일에 일찍 퇴근**하겠다고 요청했어요. 어떻게 반응할 것 같나요?",
                 "options": [
                     "종교 활동도 중요하니 기꺼이 배려한다",
                     "업무에 지장이 없는 범위에서 괜찮다고 본다",
                     "개인 종교 때문에 업무 일정을 바꾸는 것은 좀 부담스럽다",
                     "직장에서 종교적 이유로 특별 대우를 받는 것은 적절하지 않다고 본다"]},

                # Q9 (idx 8) — VC-PB-XX-01: 상징적위협 / 인지
                {"code": "VC-PB-XX-01", "type": "VC",
                 "text": "공공 행사(졸업식, 개회식 등)에서 특정 종교의 기도나 축복 (예: 불교 독경, 개신교 기도, 천주교 축복 등)이 포함되는 것에 대해 어떻게 생각하세요?",
                 "options": [
                     "한국 문화의 일부이므로 자연스럽다",
                     "참석자의 동의가 있다면 괜찮다",
                     "특정 종교 행위 없이 중립적으로 진행하는 것이 바람직하다",
                     "공적 행사에 종교 행위를 포함하는 것은 부적절하다"]},

                # Q10 (idx 9) — CR-PR-IS-04: 현실적위협·자동적반응 / 행동 — 쌍C IS
                {"code": "CR-PR-IS-04", "type": "CR", "pair": "C", "religion": "IS",
                 "text": "이사할 집을 알아보는데, 마음에 드는 집 바로 옆에 **대규모 종교 시설** (예: 이슬람 모스크)이 있어요. 이 점이 결정에 영향을 줄 것 같나요?",
                 "options": [
                     "종교 시설과 관계없이 집 자체의 조건으로 결정한다",
                     "약간 고려하지만 결정적 요인은 아니다",
                     "이 점 때문에 고민이 좀 된다",
                     "다른 집을 찾아볼 것 같다"]},
            ],
            "cr_pairs": [(1, 4, "공적영역"), (3, 7, "직장"), (6, 9, "사적관계")],
            "vc_indices": [2, 5, 8], "dq_index": 0,
            "dq_label": "열성 종교인에 대한 고정관념",
            "dq_interp": {
                1: "종교를 개인의 영역으로 존중하며, 종교적 열성이 사람에 대한 판단에 영향을 주지 않는 태도입니다.",
                2: "호기심은 있지만 실질적 관계에는 영향을 주지 않는, 유연한 태도입니다.",
                3: "어떤 종교인지에 따라 인상이 달라질 수 있다는 반응은, 특정 종교에 대한 고정관념이 작동하고 있을 가능성을 시사합니다. 이는 직장에서 특정 종교인에 대한 무의식적 거리두기로 나타날 수 있습니다.",
                4: "열성 신자에 대한 부담감은 종교인 전반에 대한 부정적 고정관념을 반영할 수 있으며, 이는 채용·협업 등 실제 상황에서 종교인에 대한 차별적 판단으로 이어질 수 있습니다.",
            },
        },

        # ════════════════════════════════════════
        # 버전 C: 상징·정서 중심
        # ════════════════════════════════════════
        "C": {
            "title": "퀵버전 C",
            "questions": [
                # Q1 (idx 0) — DQ-VL-XX-01: 상징적위협 / 인지
                {"code": "DQ-VL-XX-01", "type": "DQ",
                 "text": "\"한국 사회에서 종교 간 갈등이 심각한 수준이다\"라는 의견에 대해 어떻게 생각하세요?",
                 "options": [
                     "갈등이라기보다 자연스러운 다양성이라고 본다",
                     "갈등이 있지만, 심각한 수준까지는 아니라고 본다",
                     "일부 종교 집단의 배타적 행동 때문에 갈등이 있다고 본다",
                     "한국의 종교 갈등은 심각한 편이라고 본다"]},

                # Q2 (idx 1) — CR-PB-PT-04: 자동적반응·집단간불안 / 정서 — 쌍A PT
                {"code": "CR-PB-PT-04", "type": "CR", "pair": "A", "religion": "PT",
                 "text": "대중교통에서 옆자리에 **눈에 띄는 종교적 상징물을 착용한 사람** (예: 큰 십자가 목걸이)이 앉았어요. 어떤 느낌이 들 것 같나요?",
                 "options": [
                     "전혀 신경 쓰이지 않는다",
                     "잠깐 눈이 가지만 불편하지는 않다",
                     "약간 어색하거나 불편하다",
                     "왠지 거리를 두고 싶다"]},

                # Q3 (idx 2) — VC-VL-XX-03: 상징적위협 / 인지
                {"code": "VC-VL-XX-03", "type": "VC",
                 "text": "종교 지도자 (예: 천주교 신부, 개신교 목사, 불교 승려 등)가 선거 시기에 특정 정당이나 후보를 지지하는 발언을 하는 것에 대해 어떻게 생각하세요?",
                 "options": [
                     "시민으로서의 정치적 표현이므로 자유롭게 할 수 있어야 한다",
                     "개인적 의견은 가능하지만, 교단 차원의 조직적 지지는 부적절하다",
                     "종교 지도자의 영향력을 고려하면 정치 발언을 자제해야 한다",
                     "종교와 정치의 완전한 분리가 필요하므로 법적으로 금지해야 한다"]},

                # Q4 (idx 3) — CR-WK-PT-05: 집단간불안·상징적위협 / 정서 — 쌍B PT
                {"code": "CR-WK-PT-05", "type": "CR", "pair": "B", "religion": "PT",
                 "text": "점심시간에 동료가 주말에 **종교 공동체 모임** (예: 교회 소그룹)에서 있었던 일을 즐겁게 이야기해요. 이 대화를 듣고 있을 때 어떤 감정이 드나요?",
                 "options": [
                     "동료의 일상을 듣는 것이라 자연스럽고 편안하다",
                     "별다른 감정 없이 듣는다",
                     "종교 이야기가 나오니 좀 어색하거나 불편하다",
                     "은근히 전도하려는 것 같아 경계심이 든다"]},

                # Q5 (idx 4) — CR-PB-IS-04: 자동적반응·집단간불안 / 정서 — 쌍A IS
                {"code": "CR-PB-IS-04", "type": "CR", "pair": "A", "religion": "IS",
                 "text": "대중교통에서 옆자리에 **눈에 띄는 종교적 상징물을 착용한 사람** (예: 히잡)이 앉았어요. 어떤 느낌이 들 것 같나요?",
                 "options": [
                     "전혀 신경 쓰이지 않는다",
                     "잠깐 눈이 가지만 불편하지는 않다",
                     "약간 어색하거나 불편하다",
                     "왠지 거리를 두고 싶다"]},

                # Q6 (idx 5) — VC-PR-XX-01: 집단간불안·내집단편향 / 인지
                {"code": "VC-PR-XX-01", "type": "VC",
                 "text": "\"서로 다른 종교를 가진 사람들의 결혼은 갈등의 원인이 될 수 있으므로, 같은 종교인끼리 결혼하는 것이 낫다\"라는 의견 (예: 개신교 신자와 불교 신자, 천주교 신자와 이슬람 신자 간 결혼 등을 떠올려 보세요)에 대해 어떻게 생각하세요?",
                 "options": [
                     "전혀 동의하지 않는다 — 종교가 결혼의 기준이 되어서는 안 된다",
                     "대체로 동의하지 않지만, 현실적 어려움이 있을 수는 있다",
                     "어느 정도 동의한다 — 종교가 다르면 갈등이 생기기 쉽다",
                     "동의한다 — 결혼 생활을 위해 같은 종교가 중요하다"]},

                # Q7 (idx 6) — CR-PR-PT-05: 자동적반응·내집단편향 / 정서 — 쌍C PT
                {"code": "CR-PR-PT-05", "type": "CR", "pair": "C", "religion": "PT",
                 "text": "오랜 친구가 갑자기 **특정 종교에 깊이 빠져서** (예: 개신교), 대화 중에 종교 이야기를 자주 해요. 어떤 느낌이 들 것 같나요?",
                 "options": [
                     "친구가 좋은 것을 찾았으니 기쁘게 생각한다",
                     "좀 뜬금없지만, 친구니까 들어줄 수 있다",
                     "전도하려는 건 아닌지 부담스럽다",
                     "사이가 멀어질 것 같아 걱정되거나 답답하다"]},

                # Q8 (idx 7) — CR-WK-IS-05: 집단간불안·상징적위협 / 정서 — 쌍B IS
                {"code": "CR-WK-IS-05", "type": "CR", "pair": "B", "religion": "IS",
                 "text": "점심시간에 동료가 주말에 **종교 공동체 모임** (예: 이슬람 모스크 모임)에서 있었던 일을 즐겁게 이야기해요. 이 대화를 듣고 있을 때 어떤 감정이 드나요?",
                 "options": [
                     "동료의 일상을 듣는 것이라 자연스럽고 편안하다",
                     "별다른 감정 없이 듣는다",
                     "종교 이야기가 나오니 좀 어색하거나 불편하다",
                     "은근히 전도하려는 것 같아 경계심이 든다"]},

                # Q9 (idx 8) — VC-VL-XX-12: 현실적위협 / 인지
                {"code": "VC-VL-XX-12", "type": "VC",
                 "text": "대형 종교 단체 (예: 불교 사찰, 개신교 대형교회, 천주교 수도원 등 어떤 종교든)가 도심의 넓은 부지를 차지하고 있지만 지역 사회에 개방하지 않는 것에 대해 어떻게 생각하세요?",
                 "options": [
                     "종교 단체의 재산이므로 사용 방법은 자유롭게 결정할 수 있다",
                     "자율에 맡기되, 지역 사회 공헌을 권장하는 것이 바람직하다",
                     "세금 면제 혜택을 받는 만큼 지역 사회에 공간을 개방해야 한다",
                     "공공 이익을 위해 법적으로 개방을 의무화해야 한다"]},

                # Q10 (idx 9) — CR-PR-IS-05: 자동적반응·내집단편향 / 정서 — 쌍C IS
                {"code": "CR-PR-IS-05", "type": "CR", "pair": "C", "religion": "IS",
                 "text": "오랜 친구가 갑자기 **특정 종교에 깊이 빠져서** (예: 이슬람), 대화 중에 종교 이야기를 자주 해요. 어떤 느낌이 들 것 같나요?",
                 "options": [
                     "친구가 좋은 것을 찾았으니 기쁘게 생각한다",
                     "좀 뜬금없지만, 친구니까 들어줄 수 있다",
                     "전도하려는 건 아닌지 부담스럽다",
                     "사이가 멀어질 것 같아 걱정되거나 답답하다"]},
            ],
            "cr_pairs": [(1, 4, "공적영역"), (3, 7, "직장"), (6, 9, "사적관계")],
            "vc_indices": [2, 5, 8], "dq_index": 0,
            "dq_label": "종교 갈등 심각성 인식",
            "dq_interp": {
                1: "종교적 다양성을 자연스러운 현상으로 인식하며, 갈등 프레임보다 공존 프레임으로 바라보는 시선입니다.",
                2: "갈등의 존재를 인정하면서도 과장하지 않는, 현실적이고 균형 잡힌 인식입니다.",
                3: "갈등의 원인을 '특정 종교의 배타성'에 귀인하고 있으며, 이는 해당 종교(주로 개신교)에 대한 부정적 프레이밍으로 이어질 수 있습니다. 이 시선은 해당 종교 신자와의 관계에서 선입견으로 작용할 수 있습니다.",
                4: "종교 갈등을 심각하게 인식하는 것 자체가 문제는 아니지만, 이러한 인식이 강할수록 종교인 전반에 대한 경계심이 높아지고, 일상에서 종교인을 '갈등의 원인'으로 바라보는 편향이 나타날 수 있습니다.",
            },
        },
    }
    return surveys


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 세션·점수 산출
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def init_session():
    if "initialized" not in st.session_state:
        st.session_state.initialized = True
        st.session_state.version = random.choice(["A", "B", "C"])
        st.session_state.reverse = random.choice([True, False])
        st.session_state.page = "intro"
        st.session_state.answers = {}
        st.session_state.saved = False


def compute_scores(answers, survey_data):
    cr_deviations = []
    pt_sum = 0
    is_sum = 0
    for pt_idx, is_idx, domain in survey_data["cr_pairs"]:
        pt_score = answers.get(pt_idx, 0)
        is_score = answers.get(is_idx, 0)
        deviation = abs(pt_score - is_score)
        cr_deviations.append((domain, deviation, pt_score, is_score))
        pt_sum += pt_score
        is_sum += is_score
    cr_total = sum(d[1] for d in cr_deviations)
    cr_direction_sum = pt_sum - is_sum
    pt_avg = pt_sum / 3
    is_avg = is_sum / 3
    vc_total = sum(answers.get(i, 0) for i in survey_data["vc_indices"])
    dq_score = answers.get(survey_data["dq_index"], 0)
    return {
        "cr_deviations": cr_deviations,
        "cr_total": cr_total,
        "cr_direction_sum": cr_direction_sum,
        "pt_avg": pt_avg,
        "is_avg": is_avg,
        "vc_total": vc_total,
        "dq_score": dq_score,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 해석 생성 (v2 — 대폭 강화)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def generate_interpretation(scores, survey_data):
    cr = scores["cr_total"]
    direction = scores["cr_direction_sum"]
    pt_avg = scores["pt_avg"]
    is_avg = scores["is_avg"]
    overall_avg = (pt_avg + is_avg) / 2
    vc = scores["vc_total"]
    dq = scores["dq_score"]

    result = {}

    # ── 1. 종교에 대한 전반적 태도 수준 ──
    if overall_avg <= 1.5:
        result["attitude_level"] = "매우 개방적"
        result["attitude_msg"] = (
            "종교와 관련된 상황 전반에서 매우 수용적이고 개방적인 태도를 보이고 있습니다. "
            "종교인이나 종교적 행위에 대해 자연스럽게 받아들이는 경향이 강합니다."
        )
    elif overall_avg <= 2.2:
        result["attitude_level"] = "비교적 개방적"
        result["attitude_msg"] = (
            "종교와 관련된 상황에서 대체로 수용적인 태도를 보이고 있습니다. "
            "약간의 낯설음을 느끼는 경우가 있지만, 그것이 행동에까지 영향을 주지는 않는 수준입니다."
        )
    elif overall_avg <= 3.0:
        result["attitude_msg"] = (
            "종교와 관련된 상황에서 일정 수준의 불편함이나 경계심이 나타나고 있습니다. "
            "이는 종교인이나 종교 활동에 대해 심리적 거리를 두는 경향으로, "
            "직장에서의 관계 형성이나 이웃 관계에서 미묘한 회피 행동으로 나타날 수 있습니다."
        )
        result["attitude_level"] = "다소 경계적"
    else:
        result["attitude_level"] = "뚜렷한 경계"
        result["attitude_msg"] = (
            "종교와 관련된 상황에서 뚜렷한 불편함이나 거부감이 나타나고 있습니다. "
            "종교인이나 종교 시설에 대한 부정적 반응이 강하며, 이는 실제 생활에서 "
            "종교인과의 교류를 피하거나, 종교 시설 근처를 기피하는 등의 "
            "행동으로 나타날 가능성이 있습니다."
        )

    # ── 2. CR 일관성 해석 ──
    if cr <= 1:
        result["consistency_level"] = "높은 일관성"
        result["consistency_msg"] = (
            "개신교와 이슬람이 등장하는 동일한 상황에서 거의 같은 반응을 선택했습니다. "
            "종교의 종류와 관계없이 상황 자체를 기준으로 판단하는 경향입니다."
        )
    elif cr <= 3:
        result["consistency_level"] = "대체로 일관"
        result["consistency_msg"] = (
            "대부분의 상황에서 비슷한 반응을 보였지만, 일부 상황에서 미세한 차이가 나타났습니다. "
            "특정 맥락에서 익숙함이나 낯설음이 반응에 약간 영향을 준 것으로 보입니다."
        )
    elif cr <= 6:
        result["consistency_level"] = "차등 반응"
        result["consistency_msg"] = (
            "같은 상황이라도 어떤 종교가 관련되느냐에 따라 다른 반응을 보이는 경향이 관찰됩니다. "
            "이러한 차등 반응은 의식하지 못하는 사이에 형성된 인식 차이에서 비롯되는 경우가 많습니다."
        )
    else:
        result["consistency_level"] = "뚜렷한 차등"
        result["consistency_msg"] = (
            "동일한 상황에서 종교에 따라 상당히 다른 반응을 보이고 있습니다. "
            "이는 특정 종교에 대한 고정관념이나 미디어를 통해 형성된 이미지가 "
            "판단에 강하게 영향을 주고 있음을 시사합니다."
        )

    # ── 3. 차별 경향 분석 (방향 + 구체적 영향) ──
    result["discrimination_msgs"] = []

    if cr >= 2:
        if direction < 0:
            result["discrimination_msgs"].append(
                "📌 **이슬람에 대한 더 강한 경계 반응**: 동일한 상황에서 이슬람이 관련될 때 "
                "개신교가 관련될 때보다 더 부정적이거나 조심스러운 반응을 보이고 있습니다. "
                "이러한 경향은 무슬림 동료와의 관계 형성, 이슬람 문화에 대한 이해, "
                "모스크 주변 거주 판단 등 실생활에서 미묘한 차별로 나타날 수 있습니다."
            )
        elif direction > 0:
            result["discrimination_msgs"].append(
                "📌 **개신교에 대한 더 강한 경계 반응**: 동일한 상황에서 개신교가 관련될 때 "
                "이슬람이 관련될 때보다 더 부정적이거나 조심스러운 반응을 보이고 있습니다. "
                "한국 사회에서 개신교에 대한 비판적 담론에 영향을 받았을 가능성이 있으며, "
                "이는 개신교 신자와의 관계에서 선입견으로 작용할 수 있습니다."
            )

    # 영역별 차별 경향
    for domain, dev, pt_s, is_s in scores["cr_deviations"]:
        if dev >= 2:
            higher = "이슬람" if is_s > pt_s else "개신교"
            if domain == "공적영역":
                result["discrimination_msgs"].append(
                    f"📌 **공적 영역에서의 차등 반응**: {higher} 관련 상황에서 더 부정적 반응을 보입니다. "
                    f"이는 {higher} 시설 건립이나 공공장소에서의 종교 활동에 대해 "
                    f"다른 종교에 비해 더 높은 기준을 적용하는 것으로, "
                    f"실제 지역 사회에서 특정 종교의 가시성에 대한 거부감으로 나타날 수 있습니다."
                )
            elif domain == "직장":
                result["discrimination_msgs"].append(
                    f"📌 **직장 내 차등 반응**: {higher} 신자인 동료에 대해 더 불편한 반응을 보입니다. "
                    f"이는 채용, 팀 배치, 일상적 교류에서 특정 종교인에 대한 "
                    f"무의식적 거리두기나 편견으로 이어질 수 있습니다."
                )
            elif domain == "사적관계":
                result["discrimination_msgs"].append(
                    f"📌 **사적 관계에서의 차등 반응**: {higher}와 관련된 사적 관계(교제, 우정 등)에서 "
                    f"더 부정적 반응을 보입니다. 이는 가장 개인적인 영역에서의 종교적 배타성으로, "
                    f"특정 종교인과의 깊은 관계 형성을 무의식적으로 회피하게 만들 수 있습니다."
                )

    # ── 4. VC 해석 (사회적 규범 태도) ──
    if vc <= 5:
        result["vc_msg"] = (
            "종교 활동의 자유를 폭넓게 인정하는 입장입니다. "
            "다양한 종교적 표현에 대해 사회가 관용적이어야 한다고 보는 시선으로, "
            "종교적 다양성을 지지하는 가치관을 반영합니다."
        )
    elif vc <= 8:
        result["vc_msg"] = (
            "종교의 자유를 존중하되, 공공 질서와의 균형을 중시하는 입장입니다. "
            "이는 한국 사회에서 가장 일반적인 시각으로, "
            "종교 활동이 타인의 권리를 침해하지 않는 범위에서 보장되어야 한다고 보는 균형 잡힌 관점입니다."
        )
    else:
        result["vc_msg"] = (
            "종교 활동에 대해 비교적 엄격한 사회적 규제를 지지하는 입장입니다. "
            "이러한 입장이 모든 종교에 동일하게 적용된다면 일관된 원칙이지만, "
            "만약 특정 종교에만 더 엄격한 기준을 적용하고 있다면 "
            "이는 차별적 태도로 이어질 수 있습니다."
        )

    # ── 5. DQ 해석 ──
    result["dq_msg"] = survey_data["dq_interp"].get(dq, "")
    result["dq_label"] = survey_data["dq_label"]

    # ── 6. 삼각측정 종합 ──
    result["triangulation"] = ""
    if cr <= 1 and (vc >= 9 or dq >= 3):
        result["triangulation"] = (
            "💡 **의식적 개방성과 규범적 엄격함의 공존**: "
            "구체적인 상황에서는 종교에 관계없이 일관된 반응을 보이면서도, "
            "가치 판단에서는 종교에 대해 엄격한 기준을 가지고 있습니다. "
            "이는 개인적 수용은 가능하지만 사회적 제도 차원에서는 "
            "종교의 영향력을 제한하고 싶은 이중적 태도일 수 있습니다."
        )
    elif cr >= 4 and vc <= 5 and dq <= 2:
        result["triangulation"] = (
            "💡 **가치와 반응의 간극**: "
            "가치 판단에서는 종교에 대해 개방적 태도를 표명하면서도, "
            "구체적 상황에서는 종교에 따라 다른 반응을 보이고 있습니다. "
            "이는 편견 연구에서 말하는 '의식적 가치와 자동적 반응 사이의 괴리'에 해당하며, "
            "실제 상황에서는 본인의 가치관과 다르게 행동할 가능성을 시사합니다. "
            "이러한 간극을 인식하는 것 자체가 변화의 시작점이 될 수 있습니다."
        )
    elif cr >= 2 and dq >= 3:
        result["triangulation"] = (
            "💡 **일관된 경계 패턴**: "
            "직접적인 태도 문항과 상황 기반 문항 모두에서 "
            "종교에 대한 경계적 반응이 나타나고 있습니다. "
            "이는 의식적·무의식적 수준 모두에서 종교에 대한 부정적 인식이 "
            "비교적 일관되게 자리잡고 있음을 보여줍니다."
        )

    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 화면 렌더링
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def render_intro():
    st.markdown('<div class="survey-header"><h1>종교와 사회 — 나의 시선 돌아보기</h1></div>', unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("이 설문은 종교와 관련된 다양한 일상 상황에 대한 여러분의 생각과 느낌을 묻는 **10문항**으로 구성되어 있습니다.\n\n⏱️ 소요 시간: 약 **3~4분**")
    st.info(
        "• 옳고 그른 답은 없습니다. **평소 가장 먼저 떠오르는 생각**에 가까운 답을 고르시면 됩니다.\n\n"
        "• 응답은 익명으로 수집되며, 결과는 개인을 평가하거나 낙인찍는 용도가 아닙니다.\n\n"
        "• 참여는 언제든 중단할 수 있습니다."
    )
    st.markdown("")
    if st.button("설문 시작하기 →", type="primary", use_container_width=True):
        st.session_state.page = "survey"
        st.rerun()


def render_survey():
    surveys = get_survey_data()
    survey = surveys[st.session_state.version]
    is_reverse = st.session_state.reverse
    questions = survey["questions"]

    st.markdown('<div class="survey-header"><h1>종교와 사회 — 나의 시선 돌아보기</h1></div>', unsafe_allow_html=True)
    answered = sum(1 for i in range(10) if f"q_{i}" in st.session_state)
    st.markdown(f'<div class="progress-text">응답 완료: {answered} / 10</div>', unsafe_allow_html=True)
    st.progress(answered / 10)
    st.markdown("---")

    all_answered = True
    for i, q in enumerate(questions):
        options = q["options"][:]
        scores_list = list(range(1, len(options) + 1))
        if is_reverse:
            options = options[::-1]
            scores_list = scores_list[::-1]
        st.markdown(
            f'<div class="question-card"><div class="question-number">Q{i+1}.</div>'
            f'<div class="question-text">{q["text"]}</div></div>', unsafe_allow_html=True)
        choice = st.radio(f"Q{i+1} 선택", options=options, index=None, key=f"q_{i}", label_visibility="collapsed")
        if choice is not None:
            selected_idx = options.index(choice)
            st.session_state.answers[i] = scores_list[selected_idx]
        else:
            all_answered = False
        st.markdown("---")

    st.markdown("")
    if st.button("결과 보기 →", type="primary", use_container_width=True, disabled=not all_answered):
        st.session_state.page = "result"
        st.rerun()
    if not all_answered:
        st.caption("⬆️ 모든 문항에 응답하면 결과를 확인할 수 있습니다.")


def render_result():
    surveys = get_survey_data()
    survey = surveys[st.session_state.version]
    answers = st.session_state.answers
    scores = compute_scores(answers, survey)
    interp = generate_interpretation(scores, survey)

    # Google Sheets 저장
    if not st.session_state.get("saved", False):
        save_ok = save_response_to_sheet(answers, survey, scores, interp["consistency_level"])
        st.session_state.saved = True
        if not save_ok:
            st.caption("⚠️ 응답 데이터 저장에 실패했습니다. secrets.toml 설정을 확인해 주세요.")

    # ── 1. 종합 결과 카드 ──
    st.markdown(f"""
    <div class="result-main">
        <p style="font-size: 0.9rem; opacity: 0.9; margin-bottom: 0.3rem;">
            종교 다양성 태도 프로파일 (RDAP) 퀵 진단 결과</p>
        <h2>당신의 종교 포용적 태도</h2>
        <p style="font-size: 1.1rem; margin: 0.8rem 0 0.3rem 0;">
            종교에 대한 전반적 태도: <strong>「{interp['attitude_level']}」</strong></p>
        <p style="font-size: 1.1rem; margin: 0.3rem 0;">
            종교 간 반응 일관성: <strong>「{interp['consistency_level']}」</strong></p>
    </div>
    """, unsafe_allow_html=True)

    # ── 2. 종교에 대한 나의 태도 ──
    st.markdown(f"""
    <div class="result-section">
        <h4>🔹 종교에 대한 나의 태도</h4>
        <p style="line-height: 1.8;">{interp['attitude_msg']}</p>
    </div>
    """, unsafe_allow_html=True)

    # ── 3. 종교 간 반응의 일관성 ──
    st.markdown(f"""
    <div class="result-section">
        <h4>🔹 종교 간 반응의 일관성</h4>
        <p style="line-height: 1.8;">{interp['consistency_msg']}</p>
    </div>
    """, unsafe_allow_html=True)

    # 영역별 시각화
    st.markdown("**영역별 반응 일관성**")
    for domain, dev, pt_s, is_s in scores["cr_deviations"]:
        if dev == 0: icon, label = "🟢", "일관됨"
        elif dev == 1: icon, label = "🟡", "미세한 차이"
        elif dev == 2: icon, label = "🟠", "차이 있음"
        else: icon, label = "🔴", "큰 차이"
        st.markdown(f"  {icon} **{domain}**: {label}")

    # ── 4. 차별 경향 분석 ──
    if interp["discrimination_msgs"]:
        disc_html = "".join(
            f'<p style="line-height: 1.8; margin-bottom: 0.8rem;">{msg}</p>'
            for msg in interp["discrimination_msgs"]
        )
        st.markdown(f"""
        <div class="result-section">
            <h4>🔹 차별적 경향 분석</h4>
            {disc_html}
        </div>
        """, unsafe_allow_html=True)

    # ── 5. 사회적 규범에 대한 태도 (VC) ──
    st.markdown(f"""
    <div class="result-section">
        <h4>🔹 사회 속 종교에 대한 나의 기준</h4>
        <p style="line-height: 1.8;">{interp['vc_msg']}</p>
    </div>
    """, unsafe_allow_html=True)

    # ── 6. DQ 기반 심층 해석 ──
    if interp["dq_msg"]:
        st.markdown(f"""
        <div class="result-section">
            <h4>🔹 {interp['dq_label']}</h4>
            <p style="line-height: 1.8;">{interp['dq_msg']}</p>
        </div>
        """, unsafe_allow_html=True)

    # ── 7. 삼각측정 종합 ──
    if interp["triangulation"]:
        st.markdown(f"""
        <div class="result-detail">
            <p style="margin: 0; line-height: 1.8;">{interp['triangulation']}</p>
        </div>
        """, unsafe_allow_html=True)

    # ── 마무리 ──
    st.markdown("---")
    st.markdown("""
    > **이 결과를 읽는 법**: 위의 분석은 '편견 있는 사람'을 낙인찍기 위한 것이 아닙니다.
    > 누구나 살아온 환경과 접해온 정보에 따라 특정 집단에 대한 인식 차이를 갖게 되며,
    > 그것을 **알아차리는 것** 자체가 더 공정한 시선을 갖는 첫걸음입니다.
    >
    > 만약 특정 종교에 대해 자신도 모르게 다른 기준을 적용하고 있었다면,
    > "왜 그런 반응이 나왔을까?"를 스스로 물어보는 것이 가장 좋은 성찰의 시작입니다.
    """)

    st.markdown("")
    if st.button("처음으로 돌아가기", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def main():
    init_session()
    if st.session_state.page == "intro": render_intro()
    elif st.session_state.page == "survey": render_survey()
    elif st.session_state.page == "result": render_result()

if __name__ == "__main__":
    main()
