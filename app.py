"""
RDAP 퀵버전 — Streamlit 웹 설문 앱 (v3)
종교 다양성 태도 프로파일 (Religious Diversity Attitude Profile)

v3 변경 사항 (2026-05-03, 파일럿 응답 분석 반영):
  ★ 개선 1: CR 쌍별 독립 PT/IS 순서 무작위화 (기존 일괄 reverse 대체)
  ★ 개선 2: 인구통계 수집 (종교적 배경, 연령대) — demographics 페이지 추가
  ★ 개선 3: 비교 의도 인식 피드백 문항 — feedback 페이지 추가
  ★ 개선 4: 응답 소요 시간 자동 기록
  ★ 개선 5: 삼각측정 프로파일 5유형 판별 + 성찰적 결과 화면
  ★ 개선 6: Google Sheets 열 구조 확장

페이지 흐름: intro → demographics → survey → feedback → result

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
    .profile-card {
        background: linear-gradient(135deg, #F0F4FF 0%, #E8F0FE 100%);
        border: 1px solid #C5D5EA; border-radius: 14px;
        padding: 1.5rem; margin: 1rem 0;
    }
    .profile-card h3 { color: #2C3E6B; margin-top: 0; }
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

# ★ 개선 6: 확장된 헤더
SHEET_HEADERS = [
    "timestamp", "version", "pair_order",               # 기본 (reverse → pair_order)
    "dm_religion", "dm_age_group",                       # ★ 인구통계
    "Q01_code", "Q01_score", "Q02_code", "Q02_score",
    "Q03_code", "Q03_score", "Q04_code", "Q04_score",
    "Q05_code", "Q05_score", "Q06_code", "Q06_score",
    "Q07_code", "Q07_score", "Q08_code", "Q08_score",
    "Q09_code", "Q09_score", "Q10_code", "Q10_score",
    "cr_dev_A", "cr_dev_B", "cr_dev_C",
    "cr_total", "cr_direction",
    "vc_total", "dq_score",
    "result_level", "profile_type",                      # ★ 프로파일 유형
    "fb_noticed", "fb_noticed_when", "fb_length",        # ★ 피드백
    "duration_seconds",                                  # ★ 소요 시간
]


@st.cache_resource
def get_gsheet_connection():
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        client = gspread.authorize(creds)
        return client
    except KeyError:
        return None
    except Exception:
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
    except Exception:
        return None


def save_response_to_sheet(answers, survey_data, scores, interp):
    """★ 개선 6: 확장된 열 구조로 저장"""
    worksheet = get_worksheet()
    if worksheet is None:
        return False
    try:
        kst = timezone(timedelta(hours=9))
        now_kst = datetime.now(kst).strftime("%Y-%m-%d %H:%M:%S")
        questions = survey_data["questions"]

        row = [
            now_kst,
            st.session_state.version,
            st.session_state.pair_order_str,                  # ★ pair_order
            st.session_state.get("dm_religion", ""),          # ★ 인구통계
            st.session_state.get("dm_age_group", ""),
        ]

        for i in range(10):
            row.append(questions[i]["code"])
            row.append(str(answers.get(i, "")))

        for domain, dev, pt_s, is_s in scores["cr_deviations"]:
            row.append(str(dev))

        row.append(str(scores["cr_total"]))
        row.append(str(scores["cr_direction_sum"]))
        row.append(str(scores["vc_total"]))
        row.append(str(scores["dq_score"]))

        row.append(interp["consistency_level"])               # result_level
        row.append(interp.get("profile_type", ""))            # ★ profile_type

        row.append(st.session_state.get("fb_noticed", ""))    # ★ 피드백
        row.append(st.session_state.get("fb_noticed_when", ""))
        row.append(st.session_state.get("fb_length", ""))

        duration = calculate_duration()                        # ★ 소요 시간
        row.append(str(duration) if duration else "")

        worksheet.append_row(row, value_input_option="USER_ENTERED")
        return True
    except Exception:
        return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ★ 개선 1: CR 쌍별 독립 무작위화 로직
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def generate_pair_orders():
    """
    CR 3개 쌍(A, B, C) 각각에 대해 독립적으로 PT/IS 순서를 무작위 결정.
    제약: 3개 쌍이 모두 같은 순서가 되지 않도록 한다.
    """
    while True:
        orders = {
            pid: random.choice(["PT_first", "IS_first"])
            for pid in ["A", "B", "C"]
        }
        if len(set(orders.values())) > 1:
            return orders


def encode_pair_orders(pair_orders):
    """dict → 기록용 문자열. 예: 'A:PT|B:IS|C:PT'"""
    parts = []
    for pid in ["A", "B", "C"]:
        short = "PT" if pair_orders[pid] == "PT_first" else "IS"
        parts.append(f"{pid}:{short}")
    return "|".join(parts)


def apply_pair_swap(questions, pair_orders, cr_pairs_meta):
    """
    IS_first인 쌍은 PT 문항과 IS 문항의 위치를 교체한다.
    cr_pairs_meta: [(pt_idx, is_idx, domain_label), …] — 0-indexed
    pair_id 순서: 첫 번째 쌍=A, 두 번째=B, 세 번째=C
    """
    result = list(questions)
    pair_ids = ["A", "B", "C"]
    for i, (pt_idx, is_idx, _domain) in enumerate(cr_pairs_meta):
        pid = pair_ids[i]
        if pair_orders[pid] == "IS_first":
            result[pt_idx], result[is_idx] = result[is_idx], result[pt_idx]
    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ★ 개선 4: 소요 시간 산출
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def calculate_duration():
    s = st.session_state.get("start_time")
    e = st.session_state.get("end_time")
    if s and e:
        try:
            return int((datetime.fromisoformat(e) - datetime.fromisoformat(s)).total_seconds())
        except Exception:
            return None
    return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 설문 데이터 정의 (문항 변경 없음)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_survey_data():
    surveys = {
        "A": {
            "title": "퀵버전 A",
            "questions": [
                {"code": "DQ-VL-XX-03", "type": "DQ",
                 "text": "\"종교인은 무종교인보다 도덕적으로 더 나은 삶을 산다\"라는 의견에 대해 어떻게 생각하세요?",
                 "options": ["전혀 동의하지 않는다 — 도덕성은 종교와 관계없다",
                             "대체로 동의하지 않지만, 종교가 도움이 될 수는 있다고 본다",
                             "어느 정도 동의한다 — 종교적 가르침이 도덕성에 영향을 준다",
                             "동의한다 — 종교적 신념이 도덕적 행동의 기반이다"]},
                {"code": "CR-PB-PT-01", "type": "CR", "pair": "A", "religion": "PT",
                 "text": "내가 사는 동네에 **대형 교회**가 새로 들어선다는 소식을 들었어요. 어떻게 반응할 것 같나요?",
                 "options": ["동네가 다양해지는 것이니 나쁘지 않다", "특별한 관심 없이 받아들인다",
                             "소음이나 교통 문제가 걱정된다", "가능하면 건축을 막고 싶다"]},
                {"code": "VC-VL-XX-01", "type": "VC",
                 "text": "공공장소(지하철, 광장 등)에서 종교적 전도 행위에 대해 사회적으로 어떤 기준이 적용되어야 한다고 생각하세요?",
                 "options": ["신앙의 자유이므로 아무 제한 없이 허용되어야 한다",
                             "타인에게 직접적 피해를 주지 않는 범위에서 허용되어야 한다",
                             "원하지 않는 사람에게 접근하는 것은 자제되어야 한다",
                             "공공질서를 위해 법적으로 규제해야 한다"]},
                {"code": "CR-WK-PT-02", "type": "CR", "pair": "B", "religion": "PT",
                 "text": "새로 합류한 팀원이 자기소개에서 \"저는 **열심히 교회에 다니는 개신교 신자**입니다\"라고 밝혔어요. 어떤 느낌이 들 것 같나요?",
                 "options": ["개인의 정체성이니 자연스럽게 받아들인다", "좀 뜬금없지만 크게 신경 쓰지 않는다",
                             "앞으로 종교 이야기가 많을까 봐 살짝 부담스럽다", "그 사람에 대한 인상이 달라진다"]},
                {"code": "CR-PB-IS-01", "type": "CR", "pair": "A", "religion": "IS",
                 "text": "내가 사는 동네에 **이슬람 사원(모스크)**이 새로 들어선다는 소식을 들었어요. 어떻게 반응할 것 같나요?",
                 "options": ["동네가 다양해지는 것이니 나쁘지 않다", "특별한 관심 없이 받아들인다",
                             "소음이나 교통 문제가 걱정된다", "가능하면 건축을 막고 싶다"]},
                {"code": "VC-WK-XX-01", "type": "VC",
                 "text": "면접 과정에서 지원자의 종교가 채용 결정에 영향을 줄 수 있다고 생각하세요?",
                 "options": ["종교가 채용에 영향을 주는 것은 어떤 경우에도 부당하다",
                             "부당하지만, 현실적으로 영향을 줄 수 있다고 생각한다",
                             "업무 특성에 따라 종교가 고려될 수 있는 경우도 있다고 본다",
                             "종교적 성향이 팀 분위기에 영향을 줄 수 있으니 참고할 수 있다"]},
                {"code": "CR-PR-PT-01", "type": "CR", "pair": "C", "religion": "PT",
                 "text": "교제 중인 사람(또는 자녀의 교제 상대)이 **열심히 교회에 다니는 개신교 신자**라는 것을 알게 되었어요. 이 사실이 관계에 대한 판단에 영향을 줄 것 같나요?",
                 "options": ["종교와 관계없이 상대의 인격을 기준으로 판단한다", "약간 신경 쓰이지만 큰 문제는 아니라고 본다",
                             "종교가 같거나 없는 사람이 더 편할 것 같다고 느낀다", "해당 종교 신자와의 관계는 고민이 될 것 같다"]},
                {"code": "CR-WK-IS-02", "type": "CR", "pair": "B", "religion": "IS",
                 "text": "새로 합류한 팀원이 자기소개에서 \"저는 **이슬람을 믿는 무슬림**입니다\"라고 밝혔어요. 어떤 느낌이 들 것 같나요?",
                 "options": ["개인의 정체성이니 자연스럽게 받아들인다", "좀 뜬금없지만 크게 신경 쓰지 않는다",
                             "앞으로 종교 이야기가 많을까 봐 살짝 부담스럽다", "그 사람에 대한 인상이 달라진다"]},
                {"code": "VC-VL-XX-13", "type": "VC",
                 "text": "\"모든 종교를 존중해야 한다\"는 원칙에 동의하시나요? 만약 동의한다면, 그 원칙이 적용되지 않아도 되는 경우가 있다고 생각하세요?",
                 "options": ["모든 종교를 예외 없이 존중해야 한다",
                             "대부분의 종교를 존중하되, 반사회적 행위를 하는 종교는 예외이다",
                             "사회적 기준에 부합하는 종교만 존중의 대상이 된다",
                             "\"존중\"은 비판하지 않는 것이 아니라, 존재를 인정하는 것이다"]},
                {"code": "CR-PR-IS-01", "type": "CR", "pair": "C", "religion": "IS",
                 "text": "교제 중인 사람(또는 자녀의 교제 상대)이 **독실한 무슬림**이라는 것을 알게 되었어요. 이 사실이 관계에 대한 판단에 영향을 줄 것 같나요?",
                 "options": ["종교와 관계없이 상대의 인격을 기준으로 판단한다", "약간 신경 쓰이지만 큰 문제는 아니라고 본다",
                             "종교가 같거나 없는 사람이 더 편할 것 같다고 느낀다", "해당 종교 신자와의 관계는 고민이 될 것 같다"]},
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
        "B": {
            "title": "퀵버전 B",
            "questions": [
                {"code": "DQ-WK-XX-02", "type": "DQ",
                 "text": "새로 온 동료가 특정 종교의 열성 신자라는 것을 알게 되었어요. 그 동료에 대한 첫인상이 달라질 것 같나요?",
                 "options": ["종교는 개인의 영역이라 인상에 영향을 주지 않는다", "살짝 궁금하지만 업무 관계에는 영향이 없다",
                             "어떤 종교냐에 따라 인상이 좀 달라질 수 있다", "열성 신자라는 점이 약간 부담스럽게 느껴진다"]},
                {"code": "CR-PB-PT-02", "type": "CR", "pair": "A", "religion": "PT",
                 "text": "공원에서 **교인 몇 명이 조용히 야외 기도**를 하고 있는 것을 봤어요. 어떤 느낌이 들 것 같나요?",
                 "options": ["자유로운 종교 활동으로 자연스럽게 여긴다", "좀 눈에 띄지만 신경 쓰지 않는다",
                             "왠지 불편하거나 어색하게 느껴진다", "공공장소에서 그런 행동을 하면 안 된다고 생각한다"]},
                {"code": "VC-VL-XX-02", "type": "VC",
                 "text": "주거 밀집 지역에 대규모 종교 시설을 건축하려는 계획에 대해, 지자체는 어떤 기준을 적용해야 한다고 생각하세요?",
                 "options": ["종교의 자유에 따라 건축을 허용해야 한다",
                             "교통·소음 등 객관적 기준만 적용하고, 어떤 종교인지는 고려하지 않아야 한다",
                             "지역 주민의 의견을 반영하여 허가 여부를 결정해야 한다",
                             "주거 지역에는 대규모 종교 시설 건축을 제한해야 한다"]},
                {"code": "CR-WK-PT-01", "type": "CR", "pair": "B", "religion": "PT",
                 "text": "직장 동료가 **수요 예배 참석**을 이유로 **매주 수요일 오후 일찍 퇴근**하겠다고 요청했어요. 어떻게 반응할 것 같나요?",
                 "options": ["종교 활동도 중요하니 기꺼이 배려한다", "업무에 지장이 없는 범위에서 괜찮다고 본다",
                             "개인 종교 때문에 업무 일정을 바꾸는 것은 좀 부담스럽다",
                             "직장에서 종교적 이유로 특별 대우를 받는 것은 적절하지 않다고 본다"]},
                {"code": "CR-PB-IS-02", "type": "CR", "pair": "A", "religion": "IS",
                 "text": "공원에서 **무슬림 몇 명이 조용히 예배(기도)**를 하고 있는 것을 봤어요. 어떤 느낌이 들 것 같나요?",
                 "options": ["자유로운 종교 활동으로 자연스럽게 여긴다", "좀 눈에 띄지만 신경 쓰지 않는다",
                             "왠지 불편하거나 어색하게 느껴진다", "공공장소에서 그런 행동을 하면 안 된다고 생각한다"]},
                {"code": "VC-VL-XX-04", "type": "VC",
                 "text": "특정 종교의 가르침이나 관행을 공개적으로 비판하는 것에 대해 어떻게 생각하세요?",
                 "options": ["종교적 신념의 표현이므로 자유롭게 허용되어야 한다",
                             "종교 공동체 내에서는 자유이나, 공적 영역에서는 자제해야 한다",
                             "대상이 되는 집단에 대한 차별을 조장할 수 있으므로, 특정 집단을 깎아내리는 발언에 가깝다",
                             "명확히 차별적 발언이므로 규제되어야 한다"]},
                {"code": "CR-PR-PT-04", "type": "CR", "pair": "C", "religion": "PT",
                 "text": "이사할 집을 알아보는데, 마음에 드는 집 바로 옆에 **대형 교회**가 있어요. 이 점이 결정에 영향을 줄 것 같나요?",
                 "options": ["종교 시설과 관계없이 집 자체의 조건으로 결정한다", "약간 고려하지만 결정적 요인은 아니다",
                             "이 점 때문에 고민이 좀 된다", "다른 집을 찾아볼 것 같다"]},
                {"code": "CR-WK-IS-01", "type": "CR", "pair": "B", "religion": "IS",
                 "text": "직장 동료가 **금요 합동 예배 참석**을 이유로 **매주 금요일 오후 일찍 퇴근**하겠다고 요청했어요. 어떻게 반응할 것 같나요?",
                 "options": ["종교 활동도 중요하니 기꺼이 배려한다", "업무에 지장이 없는 범위에서 괜찮다고 본다",
                             "개인 종교 때문에 업무 일정을 바꾸는 것은 좀 부담스럽다",
                             "직장에서 종교적 이유로 특별 대우를 받는 것은 적절하지 않다고 본다"]},
                {"code": "VC-PB-XX-01", "type": "VC",
                 "text": "공공 행사(졸업식, 개회식 등)에서 특정 종교의 기도나 축복이 포함되는 것에 대해 어떻게 생각하세요?",
                 "options": ["한국 문화의 일부이므로 자연스럽다", "참석자의 동의가 있다면 괜찮다",
                             "특정 종교 행위 없이 중립적으로 진행하는 것이 바람직하다",
                             "공적 행사에 종교 행위를 포함하는 것은 부적절하다"]},
                {"code": "CR-PR-IS-04", "type": "CR", "pair": "C", "religion": "IS",
                 "text": "이사할 집을 알아보는데, 마음에 드는 집 바로 옆에 **모스크**가 있어요. 이 점이 결정에 영향을 줄 것 같나요?",
                 "options": ["종교 시설과 관계없이 집 자체의 조건으로 결정한다", "약간 고려하지만 결정적 요인은 아니다",
                             "이 점 때문에 고민이 좀 된다", "다른 집을 찾아볼 것 같다"]},
            ],
            "cr_pairs": [(1, 4, "공적영역"), (3, 7, "직장"), (6, 9, "사적관계")],
            "vc_indices": [2, 5, 8], "dq_index": 0,
            "dq_label": "열성 종교인에 대한 고정관념",
            "dq_interp": {
                1: "종교를 개인의 영역으로 존중하며, 종교적 열성이 사람에 대한 판단에 영향을 주지 않는 태도입니다.",
                2: "호기심은 있지만 실질적 관계에는 영향을 주지 않는, 유연한 태도입니다.",
                3: "어떤 종교인지에 따라 인상이 달라질 수 있다는 반응은, 특정 종교에 대한 고정관념이 작동하고 있을 가능성을 시사합니다.",
                4: "열성 신자에 대한 부담감은 종교인 전반에 대한 부정적 고정관념을 반영할 수 있습니다.",
            },
        },
        "C": {
            "title": "퀵버전 C",
            "questions": [
                {"code": "DQ-VL-XX-01", "type": "DQ",
                 "text": "\"한국 사회에서 종교 간 갈등이 심각한 수준이다\"라는 의견에 대해 어떻게 생각하세요?",
                 "options": ["갈등이라기보다 자연스러운 다양성이라고 본다", "갈등이 있지만, 심각한 수준까지는 아니라고 본다",
                             "특정 종교의 배타적 행동 때문에 갈등이 있다고 본다", "한국의 종교 갈등은 심각한 편이라고 본다"]},
                {"code": "CR-PB-PT-04", "type": "CR", "pair": "A", "religion": "PT",
                 "text": "대중교통에서 옆자리에 **큰 십자가 목걸이를 한 사람**이 앉았어요. 어떤 느낌이 들 것 같나요?",
                 "options": ["전혀 신경 쓰이지 않는다", "잠깐 눈이 가지만 불편하지는 않다",
                             "약간 어색하거나 불편하다", "왠지 거리를 두고 싶다"]},
                {"code": "VC-VL-XX-03", "type": "VC",
                 "text": "종교 지도자가 선거 시기에 특정 정당이나 후보를 지지하는 발언을 하는 것에 대해 어떻게 생각하세요?",
                 "options": ["시민으로서의 정치적 표현이므로 자유롭게 할 수 있어야 한다",
                             "개인적 의견은 가능하지만, 교단 차원의 조직적 지지는 부적절하다",
                             "종교 지도자의 영향력을 고려하면 정치 발언을 자제해야 한다",
                             "종교와 정치의 완전한 분리가 필요하므로 법적으로 금지해야 한다"]},
                {"code": "CR-WK-PT-05", "type": "CR", "pair": "B", "religion": "PT",
                 "text": "점심시간에 동료가 주말에 **교회 소그룹 모임**에서 있었던 일을 즐겁게 이야기해요. 이 대화를 듣고 있을 때 어떤 감정이 드나요?",
                 "options": ["동료의 일상을 듣는 것이라 자연스럽고 편안하다", "별다른 감정 없이 듣는다",
                             "종교 이야기가 나오니 좀 어색하거나 불편하다", "은근히 전도하려는 것 같아 경계심이 든다"]},
                {"code": "CR-PB-IS-04", "type": "CR", "pair": "A", "religion": "IS",
                 "text": "대중교통에서 옆자리에 **히잡을 쓴 여성**이 앉았어요. 어떤 느낌이 들 것 같나요?",
                 "options": ["전혀 신경 쓰이지 않는다", "잠깐 눈이 가지만 불편하지는 않다",
                             "약간 어색하거나 불편하다", "왠지 거리를 두고 싶다"]},
                {"code": "VC-PR-XX-01", "type": "VC",
                 "text": "\"서로 다른 종교를 가진 사람들의 결혼은 갈등의 원인이 될 수 있으므로, 같은 종교인끼리 결혼하는 것이 낫다\"라는 의견에 대해 어떻게 생각하세요?",
                 "options": ["전혀 동의하지 않는다 — 종교가 결혼의 기준이 되어서는 안 된다",
                             "대체로 동의하지 않지만, 현실적 어려움이 있을 수는 있다",
                             "어느 정도 동의한다 — 종교가 다르면 갈등이 생기기 쉽다",
                             "동의한다 — 결혼 생활을 위해 같은 종교가 중요하다"]},
                {"code": "CR-PR-PT-05", "type": "CR", "pair": "C", "religion": "PT",
                 "text": "오랜 친구가 갑자기 **개신교**에 빠져서, 대화 중에 종교 이야기를 자주 해요. 어떤 느낌이 들 것 같나요?",
                 "options": ["친구가 좋은 것을 찾았으니 기쁘게 생각한다", "좀 뜬금없지만, 친구니까 들어줄 수 있다",
                             "전도하려는 건 아닌지 부담스럽다", "사이가 멀어질 것 같아 걱정되거나 답답하다"]},
                {"code": "CR-WK-IS-05", "type": "CR", "pair": "B", "religion": "IS",
                 "text": "점심시간에 동료가 주말에 **모스크 공동체 모임**에서 있었던 일을 즐겁게 이야기해요. 이 대화를 듣고 있을 때 어떤 감정이 드나요?",
                 "options": ["동료의 일상을 듣는 것이라 자연스럽고 편안하다", "별다른 감정 없이 듣는다",
                             "종교 이야기가 나오니 좀 어색하거나 불편하다", "은근히 전도하려는 것 같아 경계심이 든다"]},
                {"code": "VC-VL-XX-12", "type": "VC",
                 "text": "대형 종교 단체가 도심의 넓은 부지를 차지하고 있지만 지역 사회에 개방하지 않는 것에 대해 어떻게 생각하세요?",
                 "options": ["종교 단체의 재산이므로 사용 방법은 자유롭게 결정할 수 있다",
                             "자율에 맡기되, 지역 사회 공헌을 권장하는 것이 바람직하다",
                             "세금 면제 혜택을 받는 만큼 지역 사회에 공간을 개방해야 한다",
                             "공공 이익을 위해 법적으로 개방을 의무화해야 한다"]},
                {"code": "CR-PR-IS-05", "type": "CR", "pair": "C", "religion": "IS",
                 "text": "오랜 친구가 갑자기 **이슬람**에 빠져서, 대화 중에 종교 이야기를 자주 해요. 어떤 느낌이 들 것 같나요?",
                 "options": ["친구가 좋은 것을 찾았으니 기쁘게 생각한다", "좀 뜬금없지만, 친구니까 들어줄 수 있다",
                             "전도하려는 건 아닌지 부담스럽다", "사이가 멀어질 것 같아 걱정되거나 답답하다"]},
            ],
            "cr_pairs": [(1, 4, "공적영역"), (3, 7, "직장"), (6, 9, "사적관계")],
            "vc_indices": [2, 5, 8], "dq_index": 0,
            "dq_label": "종교 갈등 심각성 인식",
            "dq_interp": {
                1: "종교적 다양성을 자연스러운 현상으로 인식하며, 갈등 프레임보다 공존 프레임으로 바라보는 시선입니다.",
                2: "갈등의 존재를 인정하면서도 과장하지 않는, 현실적이고 균형 잡힌 인식입니다.",
                3: "갈등의 원인을 '특정 종교의 배타성'에 귀인하고 있으며, 이는 해당 종교에 대한 부정적 프레이밍으로 이어질 수 있습니다.",
                4: "종교 갈등을 심각하게 인식하는 것 자체가 문제는 아니지만, 이러한 인식이 강할수록 종교인 전반에 대한 경계심이 높아질 수 있습니다.",
            },
        },
    }
    return surveys


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 세션 초기화
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def init_session():
    if "initialized" not in st.session_state:
        st.session_state.initialized = True
        st.session_state.version = random.choice(["A", "B", "C"])
        # ★ 개선 1: 쌍별 독립 무작위화
        st.session_state.pair_orders = generate_pair_orders()
        st.session_state.pair_order_str = encode_pair_orders(st.session_state.pair_orders)
        # 기존 reverse는 선택지 역순 표시에만 사용 (쌍 교체와 독립)
        st.session_state.reverse = random.choice([True, False])
        st.session_state.page = "intro"
        st.session_state.answers = {}
        st.session_state.saved = False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 점수 산출
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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
    pt_avg = pt_sum / 3 if pt_sum else 0
    is_avg = is_sum / 3 if is_sum else 0
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
# ★ 개선 5: 삼각측정 프로파일 판별
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_triangulation_profile(cr, vc, dq, direction):
    """CR·VC·DQ 삼각측정 기반 프로파일 5유형 판별"""

    # 방향성 해석
    if direction < 0:
        dir_note = "이슬람 시나리오에서 더 부정적으로 반응하는 경향이 나타났습니다."
    elif direction > 0:
        dir_note = "개신교 시나리오에서 더 부정적으로 반응하는 경향이 나타났습니다."
    else:
        dir_note = ""

    if cr <= 1 and vc <= 6 and dq <= 2:
        return {
            "type": "consistent_open",
            "label": "일관된 개방적 태도",
            "emoji": "🌿",
            "description": (
                "종교에 관계없이 일관된 태도를 보이며, "
                "종교 활동에 대한 사회적 규범에서도 개방적 입장입니다."
            ),
            "reflection": "",
            "direction_note": dir_note,
        }

    if cr <= 1 and vc >= 9:
        return {
            "type": "sdb_possible",
            "label": "일관된 응답 + 높은 규범 선호",
            "emoji": "🔍",
            "description": (
                "종교별로 차이 없이 일관되게 응답했지만, "
                "종교 활동에 대해 사회적 규제를 선호하는 경향이 있습니다."
            ),
            "reflection": (
                "이 일관성이 진정한 태도의 반영인지, "
                "'종교마다 같게 답해야 한다'는 의식이 작용한 것인지 돌아보는 것도 의미 있습니다."
            ),
            "direction_note": dir_note,
        }

    if cr >= 4 and vc <= 6:
        return {
            "type": "unconscious_diff",
            "label": "가치와 반응의 간극",
            "emoji": "💡",
            "description": (
                "가치 판단에서는 종교에 대해 개방적 태도를 표명하면서도, "
                "구체적 상황에서는 종교에 따라 다른 반응을 보이고 있습니다."
            ),
            "reflection": (
                "이 간극이 어디에서 오는지 — 미디어 이미지, 주변 경험, "
                "또는 익숙하지 않은 것에 대한 자동적 반응인지 — 생각해 보세요. "
                "이런 자각 자체가 편견 예방의 첫걸음입니다."
            ),
            "direction_note": dir_note,
        }

    if cr >= 4 and vc >= 9:
        return {
            "type": "overall_restrictive",
            "label": "전반적 규제 선호 + 차등 반응",
            "emoji": "⚠️",
            "description": (
                "종교 활동에 대한 사회적 규제를 선호하는 동시에, "
                "종교에 따라 반응이 달라지는 경향이 포착되었습니다."
            ),
            "reflection": (
                "'모든 종교에 대해 같은 기준을 적용하고 있는지', "
                "특정 종교에 대해서만 더 엄격한 기준을 적용하고 있지는 않은지 돌아보세요."
            ),
            "direction_note": dir_note,
        }

    # 중간/혼합
    if cr >= 2:
        cr_desc = "종교에 따라 다소 다른 반응 경향이 관찰되었습니다."
    else:
        cr_desc = "종교별 응답은 비교적 일관된 편입니다."
    if vc >= 8:
        vc_desc = "종교 활동에 대한 사회적 규범을 중시하는 편입니다."
    elif vc <= 5:
        vc_desc = "종교 활동에 대해 개방적 입장입니다."
    else:
        vc_desc = "종교 활동의 사회적 규범에 대해 중립적 입장입니다."

    return {
        "type": "mixed",
        "label": "복합적 프로파일",
        "emoji": "📊",
        "description": f"{cr_desc} {vc_desc}",
        "reflection": (
            "대부분의 사람들은 이 영역에 위치합니다. "
            "중요한 것은 점수 자체가 아니라, "
            "'내가 어떤 상황에서 어떤 종교에 대해 다르게 반응하는지'를 인식하는 것입니다."
        ),
        "direction_note": dir_note,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 해석 생성 (v3)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def generate_interpretation(scores, survey_data):
    cr = scores["cr_total"]
    direction = scores["cr_direction_sum"]
    pt_avg = scores["pt_avg"]
    is_avg = scores["is_avg"]
    overall_avg = (pt_avg + is_avg) / 2 if (pt_avg + is_avg) else 0
    vc = scores["vc_total"]
    dq = scores["dq_score"]

    result = {}

    # ── 1. 종교에 대한 전반적 태도 ──
    if overall_avg <= 1.5:
        result["attitude_level"] = "매우 개방적"
        result["attitude_msg"] = (
            "종교와 관련된 상황 전반에서 매우 수용적이고 개방적인 태도를 보이고 있습니다."
        )
    elif overall_avg <= 2.2:
        result["attitude_level"] = "비교적 개방적"
        result["attitude_msg"] = (
            "종교와 관련된 상황에서 대체로 수용적인 태도를 보이고 있습니다. "
            "약간의 낯설음을 느끼는 경우가 있지만, 행동에까지 영향을 주지는 않는 수준입니다."
        )
    elif overall_avg <= 3.0:
        result["attitude_level"] = "다소 경계적"
        result["attitude_msg"] = (
            "종교와 관련된 상황에서 일정 수준의 불편함이나 경계심이 나타나고 있습니다. "
            "이는 종교인이나 종교 활동에 대해 심리적 거리를 두는 경향으로, "
            "직장이나 이웃 관계에서 미묘한 회피 행동으로 나타날 수 있습니다."
        )
    else:
        result["attitude_level"] = "뚜렷한 경계"
        result["attitude_msg"] = (
            "종교와 관련된 상황에서 뚜렷한 불편함이나 거부감이 나타나고 있습니다."
        )

    # ── 2. CR 일관성 ──
    if cr <= 1:
        result["consistency_level"] = "높은 일관성"
        result["consistency_msg"] = (
            "개신교와 이슬람이 등장하는 동일한 상황에서 거의 같은 반응을 선택했습니다. "
            "종교의 종류와 관계없이 상황 자체를 기준으로 판단하는 경향입니다."
        )
    elif cr <= 3:
        result["consistency_level"] = "대체로 일관"
        result["consistency_msg"] = (
            "대부분의 상황에서 비슷한 반응을 보였지만, 일부 상황에서 미세한 차이가 나타났습니다."
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
            "동일한 상황에서 종교에 따라 상당히 다른 반응을 보이고 있습니다."
        )

    # ── 3. 차별 경향 ──
    result["discrimination_msgs"] = []
    if cr >= 2:
        if direction < 0:
            result["discrimination_msgs"].append(
                "📌 **이슬람에 대한 더 강한 경계 반응**: 동일한 상황에서 이슬람이 관련될 때 "
                "개신교가 관련될 때보다 더 부정적이거나 조심스러운 반응을 보이고 있습니다."
            )
        elif direction > 0:
            result["discrimination_msgs"].append(
                "📌 **개신교에 대한 더 강한 경계 반응**: 동일한 상황에서 개신교가 관련될 때 "
                "이슬람이 관련될 때보다 더 부정적이거나 조심스러운 반응을 보이고 있습니다."
            )
    for domain, dev, pt_s, is_s in scores["cr_deviations"]:
        if dev >= 2:
            higher = "이슬람" if is_s > pt_s else "개신교"
            if domain == "공적영역":
                result["discrimination_msgs"].append(
                    f"📌 **공적 영역에서의 차등**: {higher} 관련 상황에서 더 부정적 반응을 보입니다."
                )
            elif domain == "직장":
                result["discrimination_msgs"].append(
                    f"📌 **직장 내 차등**: {higher} 신자인 동료에 대해 더 불편한 반응을 보입니다."
                )
            elif domain == "사적관계":
                result["discrimination_msgs"].append(
                    f"📌 **사적 관계에서의 차등**: {higher}와 관련된 사적 관계에서 더 부정적 반응을 보입니다."
                )

    # ── 4. VC 해석 ──
    if vc <= 5:
        result["vc_msg"] = "종교 활동의 자유를 폭넓게 인정하는 입장입니다."
    elif vc <= 8:
        result["vc_msg"] = (
            "종교의 자유를 존중하되, 공공 질서와의 균형을 중시하는 입장입니다. "
            "이는 한국 사회에서 가장 일반적인 시각입니다."
        )
    else:
        result["vc_msg"] = (
            "종교 활동에 대해 비교적 엄격한 사회적 규제를 지지하는 입장입니다. "
            "이 입장이 모든 종교에 동일하게 적용된다면 일관된 원칙이지만, "
            "특정 종교에만 더 엄격한 기준을 적용하고 있다면 차별적 태도로 이어질 수 있습니다."
        )

    # ── 5. DQ 해석 ──
    result["dq_msg"] = survey_data["dq_interp"].get(dq, "")
    result["dq_label"] = survey_data["dq_label"]

    # ── 6. ★ 삼각측정 프로파일 ──
    profile = get_triangulation_profile(cr, vc, dq, direction)
    result["profile_type"] = profile["type"]
    result["profile_label"] = profile["label"]
    result["profile_emoji"] = profile["emoji"]
    result["profile_description"] = profile["description"]
    result["profile_reflection"] = profile["reflection"]
    result["profile_direction"] = profile["direction_note"]

    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 화면 렌더링
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def render_intro():
    st.markdown('<div class="survey-header"><h1>종교와 사회 — 나의 시선 돌아보기</h1></div>', unsafe_allow_html=True)
    st.markdown("---")
    st.markdown(
        "이 설문은 종교와 관련된 다양한 일상 상황에 대한 여러분의 생각과 느낌을 묻는 "
        "**10문항**으로 구성되어 있습니다.\n\n⏱️ 소요 시간: 약 **3~4분**"
    )
    st.info(
        "• 옳고 그른 답은 없습니다. **평소 가장 먼저 떠오르는 생각**에 가까운 답을 고르시면 됩니다.\n\n"
        "• 응답은 익명으로 수집되며, 결과는 개인을 평가하거나 낙인찍는 용도가 아닙니다.\n\n"
        "• 참여는 언제든 중단할 수 있습니다."
    )
    st.markdown("")
    if st.button("설문 시작하기 →", type="primary", use_container_width=True):
        st.session_state.page = "demographics"      # ★ intro → demographics
        st.rerun()


# ★ 개선 2: 인구통계 페이지
def render_demographics():
    st.markdown('<div class="survey-header"><h1>종교와 사회 — 나의 시선 돌아보기</h1></div>', unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("### 기본 정보")
    st.markdown("아래 정보는 응답 패턴 분석에만 활용되며, 개인을 식별하는 데 사용되지 않습니다.")

    religion = st.radio(
        "현재 종교가 있으시면 선택해 주세요.",
        options=[
            "무종교 / 종교 없음",
            "개신교 (기독교)",
            "불교",
            "천주교 (가톨릭)",
            "이슬람",
            "기타 종교",
        ],
        index=None,
        key="radio_religion",
    )

    age_group = st.radio(
        "연령대를 선택해 주세요.",
        options=["10대", "20대", "30대", "40대", "50대 이상"],
        index=None,
        key="radio_age",
    )

    st.markdown("")
    both_answered = religion is not None and age_group is not None
    if st.button("다음 →", type="primary", use_container_width=True, disabled=not both_answered):
        st.session_state.dm_religion = religion
        st.session_state.dm_age_group = age_group
        st.session_state.start_time = datetime.now().isoformat()   # ★ 개선 4
        st.session_state.page = "survey"
        st.rerun()
    if not both_answered:
        st.caption("⬆️ 두 항목 모두 선택해 주세요.")


def render_survey():
    surveys = get_survey_data()
    survey = surveys[st.session_state.version]
    is_reverse = st.session_state.reverse

    # ★ 개선 1: 쌍별 순서 적용 — 문항 리스트를 교체된 버전으로 생성
    original_questions = survey["questions"]
    questions = apply_pair_swap(
        original_questions,
        st.session_state.pair_orders,
        survey["cr_pairs"],
    )

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
            f'<div class="question-text">{q["text"]}</div></div>',
            unsafe_allow_html=True,
        )
        choice = st.radio(
            f"Q{i+1} 선택", options=options, index=None,
            key=f"q_{i}", label_visibility="collapsed",
        )
        if choice is not None:
            selected_idx = options.index(choice)
            st.session_state.answers[i] = scores_list[selected_idx]
        else:
            all_answered = False
        st.markdown("---")

    st.markdown("")
    if st.button("다음 →", type="primary", use_container_width=True, disabled=not all_answered):
        st.session_state.page = "feedback"           # ★ survey → feedback
        st.rerun()
    if not all_answered:
        st.caption("⬆️ 모든 문항에 응답하면 다음으로 넘어갈 수 있습니다.")


# ★ 개선 3: 피드백 페이지
def render_feedback():
    st.markdown('<div class="survey-header"><h1>종교와 사회 — 나의 시선 돌아보기</h1></div>', unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("### 설문을 마치며")
    st.markdown("결과를 보여드리기 전에 몇 가지만 여쭤볼게요. **(선택 사항)**")

    noticed = st.radio(
        "비슷한 질문이 종교만 바꿔서 반복되는 것을 알아채셨나요?",
        options=["예", "아니오"],
        index=None,
        key="radio_noticed",
    )

    noticed_when = None
    if noticed == "예":
        noticed_when = st.radio(
            "알아채신 시점은 언제쯤인가요?",
            options=[
                "초반 (1~3번 문항)",
                "중반 (4~6번 문항)",
                "후반 (7~10번 문항)",
                "설문을 다 마친 후",
            ],
            index=None,
            key="radio_noticed_when",
        )

    survey_length = st.radio(
        "설문 길이가 어떠셨나요?",
        options=["적절하다", "약간 길다", "상당히 길다"],
        index=None,
        key="radio_length",
    )

    st.markdown("")
    if st.button("결과 보기 →", type="primary", use_container_width=True):
        st.session_state.fb_noticed = noticed or ""
        st.session_state.fb_noticed_when = noticed_when or ""
        st.session_state.fb_length = survey_length or ""
        st.session_state.end_time = datetime.now().isoformat()    # ★ 개선 4
        st.session_state.page = "result"
        st.rerun()
    st.caption("피드백을 건너뛰고 바로 결과를 보셔도 됩니다.")


def render_result():
    surveys = get_survey_data()
    survey = surveys[st.session_state.version]
    answers = st.session_state.answers

    # ★ 개선 1: 쌍 교체된 문항 기준으로 점수 산출
    original_questions = survey["questions"]
    questions = apply_pair_swap(
        original_questions,
        st.session_state.pair_orders,
        survey["cr_pairs"],
    )

    scores = compute_scores(answers, survey)
    interp = generate_interpretation(scores, survey)

    # Google Sheets 저장
    if not st.session_state.get("saved", False):
        save_ok = save_response_to_sheet(answers, survey, scores, interp)
        st.session_state.saved = True
        if not save_ok:
            st.caption("⚠️ 응답 저장에 실패했습니다. secrets.toml 설정을 확인해 주세요.")

    # ── 1. 종합 결과 카드 ──
    st.markdown(f"""
    <div class="result-main">
        <p style="font-size: 0.9rem; opacity: 0.9; margin-bottom: 0.3rem;">
            종교 다양성 태도 프로파일 (RDAP) 퀵 진단 결과</p>
        <h2>나의 종교 다양성 태도</h2>
        <p style="font-size: 1.1rem; margin: 0.8rem 0 0.3rem 0;">
            종교에 대한 전반적 태도: <strong>「{interp['attitude_level']}」</strong></p>
        <p style="font-size: 1.1rem; margin: 0.3rem 0;">
            종교 간 반응 일관성: <strong>「{interp['consistency_level']}」</strong></p>
    </div>
    """, unsafe_allow_html=True)

    # ── ★ 2. 삼각측정 프로파일 카드 ──
    st.markdown(f"""
    <div class="profile-card">
        <h3>{interp['profile_emoji']} 종합 프로파일: {interp['profile_label']}</h3>
        <p style="line-height: 1.8; margin-bottom: 0.5rem;">{interp['profile_description']}</p>
    </div>
    """, unsafe_allow_html=True)

    if interp["profile_reflection"]:
        st.markdown(f"""
        <div class="result-detail">
            <p style="margin: 0; line-height: 1.8;">
                💡 <strong>생각해 볼 점:</strong> {interp['profile_reflection']}</p>
        </div>
        """, unsafe_allow_html=True)

    if interp["profile_direction"]:
        st.markdown(f"""
        <div class="result-detail">
            <p style="margin: 0; line-height: 1.8;">
                🧭 <strong>방향성:</strong> {interp['profile_direction']}</p>
        </div>
        """, unsafe_allow_html=True)

    # ── 3. 종교에 대한 나의 태도 ──
    st.markdown(f"""
    <div class="result-section">
        <h4>🔹 종교에 대한 나의 태도</h4>
        <p style="line-height: 1.8;">{interp['attitude_msg']}</p>
    </div>
    """, unsafe_allow_html=True)

    # ── 4. 종교 간 반응 일관성 ──
    st.markdown(f"""
    <div class="result-section">
        <h4>🔹 종교 간 반응의 일관성</h4>
        <p style="line-height: 1.8;">{interp['consistency_msg']}</p>
    </div>
    """, unsafe_allow_html=True)

    # 영역별 시각화
    st.markdown("**영역별 반응 일관성**")
    for domain, dev, pt_s, is_s in scores["cr_deviations"]:
        if dev == 0:
            icon, label = "🟢", "일관됨"
        elif dev == 1:
            icon, label = "🟡", "미세한 차이"
        elif dev == 2:
            icon, label = "🟠", "차이 있음"
        else:
            icon, label = "🔴", "큰 차이"
        st.markdown(f"  {icon} **{domain}**: {label}")

    # ── 5. 차별 경향 ──
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

    # ── 6. VC ──
    st.markdown(f"""
    <div class="result-section">
        <h4>🔹 사회 속 종교에 대한 나의 기준</h4>
        <p style="line-height: 1.8;">{interp['vc_msg']}</p>
    </div>
    """, unsafe_allow_html=True)

    # ── 7. DQ ──
    if interp["dq_msg"]:
        st.markdown(f"""
        <div class="result-section">
            <h4>🔹 {interp['dq_label']}</h4>
            <p style="line-height: 1.8;">{interp['dq_msg']}</p>
        </div>
        """, unsafe_allow_html=True)

    # ── 8. 세부 지표 (접기) ──
    with st.expander("📋 세부 지표 보기"):
        duration = calculate_duration()
        st.markdown(f"- **버전:** {st.session_state.version}")
        st.markdown(f"- **쌍별 순서:** {st.session_state.pair_order_str}")
        st.markdown(f"- **CR 총 편차:** {scores['cr_total']} / 9")
        st.markdown(f"- **CR 방향:** {scores['cr_direction_sum']}")
        st.markdown(f"- **VC 총점:** {scores['vc_total']} / 12")
        st.markdown(f"- **DQ 점수:** {scores['dq_score']} / 4")
        st.markdown(f"- **프로파일:** {interp['profile_label']}")
        if duration:
            st.markdown(f"- **소요 시간:** {duration // 60}분 {duration % 60}초")

    # ── 마무리 ──
    st.markdown("---")
    st.markdown("""
    > **이 결과를 읽는 법**: 위의 분석은 '편견 있는 사람'을 낙인찍기 위한 것이 아닙니다.
    > 누구나 살아온 환경과 접해온 정보에 따라 특정 집단에 대한 인식 차이를 갖게 되며,
    > 그것을 **알아차리는 것** 자체가 더 공정한 시선을 갖는 첫걸음입니다.
    """)

    st.markdown("")
    if st.button("처음으로 돌아가기", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 메인
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main():
    init_session()
    page = st.session_state.page
    if page == "intro":
        render_intro()
    elif page == "demographics":        # ★ 신규
        render_demographics()
    elif page == "survey":
        render_survey()
    elif page == "feedback":            # ★ 신규
        render_feedback()
    elif page == "result":
        render_result()


if __name__ == "__main__":
    main()
