import streamlit as st
import requests
import re
from datetime import datetime, timedelta

# 🔑 본인의 나이스 오픈 API 인증키를 여기에 입력하세요!
API_KEY = st.secrets["API_KEY"]  # Streamlit Secrets

# 1. 학교 이름으로 학교 코드(SD_SCHUL_CODE)를 찾는 함수
def find_school(office_code, school_name):
    url = "https://open.neis.go.kr/hub/schoolInfo"
    params = {
        "KEY": API_KEY, 
        "Type": "json",
        "pIndex": 1, 
        "pSize": 5,
        "ATPT_OFCDC_SC_CODE": office_code,
        "SCHUL_NM": school_name
    }
    try:
        response = requests.get(url, params=params)
        data = response.json()
        school = data["schoolInfo"][1]["row"][0]
        return school["SD_SCHUL_CODE"]
    except Exception:
        return None

# 2. 학교 코드와 날짜로 급식 정보를 가져오는 함수
def get_meal_detail(office_code, school_code, date_str):
    url = "https://open.neis.go.kr/hub/mealServiceDietInfo"
    params = {
        "KEY": API_KEY, 
        "Type": "json",
        "pIndex": 1, 
        "pSize": 5,
        "ATPT_OFCDC_SC_CODE": office_code,
        "SD_SCHUL_CODE": school_code,
        "MLSV_YMD": date_str
    }
    try:
        response = requests.get(url, params=params)
        data = response.json()
        meal_row = data["mealServiceDietInfo"][1]["row"][0]
        
        raw_menu = meal_row.get("DDISH_NM", "")
        clean_menu = raw_menu.replace("<br/>", "\n")
        calories = meal_row.get("CAL_INFO", "정보 없음")
        nutrition = meal_row.get("NTR_INFO", "정보 없음")
        
        return clean_menu, calories, nutrition
    except Exception:
        return None, None, None

# --- 🎨 Streamlit 웹 화면 디자인 ---
st.set_page_config(page_title="SafePlate - 맞춤형 급식 알레르기 조회", page_icon="🥪", layout="wide")

st.title("🥪 학교 급식 알레르기 분석기 🍖")
st.markdown("우리 학교의 이번 주 식단을 모아보고, 내 알레르기 유발 성분이 포함된 요일을 미리 확인하세요!")

# 사이드바: 개인 알레르기 설정 및 학교 검색 설정
st.sidebar.header("⚙️ 검색 및 맞춤 설정")

# 교육청 코드 선택
office_dict = {
    "서울특별시교육청": "B10", "부산광역시교육청": "C10",
    "대구광역시교육청": "D10", "인천광역시교육청": "E10",
    "광주광역시교육청": "F10", "대전광역시교육청": "G10",
    "울산광역시교육청": "H10", "세종특별자치시교육청": "I10",
    "경기도교육청": "J10", "강원특별자치도교육청": "K10",
    "충청북도교육청": "M10", "충청남도교육청": "N10",
    "전북특별자치도교육청": "P10", "전라남도교육청": "Q10",
    "경상북도교육청": "R10", "경상남도교육청": "S10",
    "제주특별자치도교육청": "T10"
}
selected_office_name = st.sidebar.selectbox("지역 교육청 선택", list(office_dict.keys()))
office_code = office_dict[selected_office_name]

school_name = st.sidebar.text_input("학교 이름 입력", value="광명고등학교")

# 날짜 선택 (특정 주간을 선택하기 위한 기준 날짜)
default_date = datetime.now()
date_input = st.sidebar.date_input("조회할 주간의 기준 날짜 선택", value=default_date)

st.sidebar.markdown("---")
st.sidebar.subheader("🚨 나의 알레르기 체크")
st.sidebar.write("주의할 알레르기 성분을 선택하세요.")

# 나이스 19대 알레르기 정보 매핑
allergy_dict = {
    "1: 난류(달걀)": "1",
    "2: 우유": "2",
    "3: 메밀": "3",
    "4: 땅콩": "4",
    "5: 대두(콩)": "5",
    "6: 밀": "6",
    "7: 고등어": "7",
    "8: 게": "8",
    "9: 새우": "9",
    "10: 돼지고기": "10",
    "11: 복숭아": "11",
    "12: 토마토": "12",
    "13: 아황산류": "13",
    "14: 호두": "14",
    "15: 닭고기": "15",
    "16: 쇠고기": "16",
    "17: 오징어": "17",
    "18: 조개류(굴,전복,홍합 등)": "18",
    "19: 잣": "19"
}

user_allergies = []
for label, code in allergy_dict.items():
    if st.sidebar.checkbox(label):
        user_allergies.append(code)

# --- 메인 화면 로직 (주간 조회) ---
if st.sidebar.button("이번 주 급식 & 알레르기 분석하기", type="primary"):
    with st.spinner("나이스 서버에서 이번 주(월~금) 급식 데이터를 불러오는 중입니다..."):
        school_code = find_school(office_code, school_name)
        
        if not school_code:
            st.error(f"'{school_name}'을(를) 찾을 수 없습니다. 학교 이름을 정확히 확인해 주세요.")
        else:
            # 선택한 날짜가 속한 주의 월요일부터 금요일까지 날짜 계산
            start_monday = date_input - timedelta(days=date_input.weekday())
            week_days = [start_monday + timedelta(days=i) for i in range(5)] # 월~금 (5일)
            
            day_names = ["월요일", "화요일", "수요일", "목요일", "금요일"]
            short_day_names = ["월", "화", "수", "목", "금"]
            
            # 요일별 데이터 미리 수집
            weekly_data = {}
            risk_summary = [] # 위험한 요일을 기록할 리스트
            
            for i, target_date in enumerate(week_days):
                date_str = target_date.strftime("%Y%m%d")
                menu, calories, nutrition = get_meal_detail(office_code, school_code, date_str)
                
                has_risk = False
                processed_menus = []
                
                if menu:
                    dish_list = menu.split("\n")
                    for dish in dish_list:
                        if not dish.strip():
                            continue
                        found_numbers = re.findall(r'\(([^)]+)\)', dish)
                        is_risky = False
                        matched_codes = []
                        
                        if found_numbers:
                            for group in found_numbers:
                                codes = re.findall(r'\d+', group)
                                for code in codes:
                                    if code in user_allergies:
                                        is_risky = True
                                        has_risk = True
                                        matched_codes.append(code)
                        
                        processed_menus.append({
                            "dish": dish,
                            "is_risky": is_risky,
                            "matched_codes": matched_codes
                        })
                
                if has_risk:
                    risk_summary.append(day_names[i])
                
                weekly_data[i] = {
                    "date_obj": target_date,
                    "date_str": target_date.strftime("%m월 %d일"),
                    "menu_data": processed_menus,
                    "calories": calories,
                    "nutrition": nutrition,
                    "has_data": True if menu else False
                }
            
            # --- 📅 월~금 미니 요약 카드 (5칸) ---
            st.markdown(f"#### 🔍 [{school_name}] 요일별 알레르기 한눈에 보기")
            cols = st.columns(5)
            
            for idx, col in enumerate(cols):
                with col:
                    day_info = weekly_data[idx]
                    if not day_info["has_data"]:
                        bg_color = "#f0f2f6"
                        text_color = "#666666"
                        count_text = "데이터 없음"
                    else:
                        risk_count = sum(1 for item in day_info["menu_data"] if item["is_risky"])
                        if risk_count == 0:
                            bg_color = "#e6f4ea"  # 연한 초록색
                            text_color = "#137333"
                            count_text = "안심 (0개)"
                        else:
                            bg_color = "#fce8e6"  # 연한 빨간색
                            text_color = "#c5221f"
                            count_text = f"주의 ({risk_count}개)"
                    
                    st.markdown(
                        f"""
                        <div style="
                            background-color: {bg_color}; 
                            padding: 10px; 
                            border-radius: 8px; 
                            text-align: center; 
                            border: 1px solid {text_color}44;
                        ">
                            <p style="margin: 0; font-weight: bold; color: {text_color}; font-size: 1.05em;">{short_day_names[idx]}</p>
                            <p style="margin: 5px 0 0 0; color: {text_color}; font-size: 0.9em;">{count_text}</p>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
            
            st.markdown("---")
            
            # --- 📅 요일별 상세 탭(Tab) 구성 ---
            tab_labels = [f"{day_names[i]} ({weekly_data[i]['date_str']})" for i in range(5)]
            tabs = st.tabs(tab_labels)
            
            for i, tab in enumerate(tabs):
                with tab:
                    day_info = weekly_data[i]
                    
                    if day_info["has_data"]:
                        col1, col2 = st.columns([1.2, 0.8])
                        
                        with col1:
                            st.subheader(f"{day_names[i]} ({day_info['date_str']}) 식단")
                            st.markdown("---")
                            
                            for item in day_info["menu_data"]:
                                if item["is_risky"]:
                                    dish_text = item['dish']
                                    match = re.match(r'^(.*?)\s*(\(.*\))$', dish_text)
                                    if match:
                                        food_name = match.group(1)
                                        allergy_part = match.group(2)
                                    else:
                                        food_name = dish_text
                                        allergy_part = ""
                                    
                                    # 괄호 안의 숫자 중 내가 체크한 알레르기 번호만 빨간색으로 강조
                                    colored_allergy_part = allergy_part
                                    for code in item['matched_codes']:
                                        colored_allergy_part = re.sub(
                                            r'(?<!\d)' + code + r'(?!\d)', 
                                            f"<span style='color: #ff4b4b; font-weight: bold;'>{code}</span>", 
                                            colored_allergy_part
                                        )
                                    
                                    matched_str = ', '.join(item['matched_codes'])
                                    
                                    st.markdown(
                                        f"• <span style='color: #ff4b4b; font-weight: bold;'>{food_name}</span> "
                                        f"<span style='color: #888888; font-size: 0.9em;'>{colored_allergy_part}</span>"
                                        f"<br>&nbsp;&nbsp;&nbsp;&nbsp;<span style='font-size: 0.9em; color: #555555;'>👉 주의: 선택하신 알레르기 번호 [<span style='color: #ff4b4b; font-weight: bold;'>{matched_str}</span>] 포함됨</span>",
                                        unsafe_allow_html=True
                                    )
                                    st.markdown("")
                                else:
                                    # 알레르기가 없는 안전한 음식은 지정하신 #228B22 색상과 굵은 글씨로 표시
                                    st.markdown(
                                        f"• <span style='color: #228B22; font-weight: bold;'>{item['dish']}</span>",
                                        unsafe_allow_html=True
                                    )
                        
                        with col2:
                            st.subheader("영양 및 칼로리")
                            st.metric(label="총 칼로리", value=day_info["calories"])
                            
                            with st.expander("상세 영양 성분 보기"):
                                st.text(day_info["nutrition"].replace("<br/>", "\n"))
                    else:
                        st.warning(f"해당 일자({day_info['date_str']})에 등록된 급식 데이터가 없습니다. (주말, 공휴일 또는 방학 기간일 수 있습니다)")
else:
    st.info("👈 왼쪽 사이드바에서 학교와 기준 날짜를 확인하고 **[이번 주 급식 & 알레르기 분석하기]** 버튼을 눌러주세요!")