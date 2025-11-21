import streamlit as st
# [안전장치] 여기서 에러나면 바로 알 수 있게 try-except로 감싸지 않음 (설정은 맨 위 필수)
st.set_page_config(layout="wide", page_title="OnEducation Study Rank")

# 라이브러리 임포트
try:
    from streamlit_gsheets import GSheetsConnection
    import pandas as pd
    from datetime import datetime
    import time
    import os
except Exception as e:
    st.error(f"라이브러리 로딩 실패! requirements.txt를 확인하세요. 에러내용: {e}")
    st.stop()

# ---------------------------------------------------------
# 1. 데이터베이스 연결
# ---------------------------------------------------------
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"구글 시트 연결 실패! secrets 설정을 확인하세요. 에러내용: {e}")
    st.stop()

# ---------------------------------------------------------
# 2. 데이터 처리 함수들
# ---------------------------------------------------------
def get_data(force_reload=False):
    if 'last_df' not in st.session_state:
        st.session_state['last_df'] = pd.DataFrame(columns=[
            "student_id", "name", "daily_seconds", "monthly_seconds", 
            "is_active", "start_time", "last_update"
        ])

    try:
        if force_reload:
            conn.reset()
        
        df = conn.read(ttl=15)
        
        expected_cols = ["student_id", "name", "daily_seconds", "monthly_seconds", 
                         "is_active", "start_time", "last_update"]

        if df.empty or 'student_id' not in df.columns:
            if not st.session_state['last_df'].empty:
                return st.session_state['last_df']
            return pd.DataFrame(columns=expected_cols)
        
        # 데이터 정리 (1111.0 -> 1111)
        df['student_id'] = df['student_id'].astype(str).apply(lambda x: x.replace('.0', '').strip())
        df['daily_seconds'] = pd.to_numeric(df['daily_seconds'], errors='coerce').fillna(0)
        df['monthly_seconds'] = pd.to_numeric(df['monthly_seconds'], errors='coerce').fillna(0)
        df['is_active'] = pd.to_numeric(df['is_active'], errors='coerce').fillna(0)
        
        st.session_state['last_df'] = df.copy()
        return df
        
    except Exception as e:
        if not st.session_state['last_df'].empty:
            return st.session_state['last_df']
        return pd.DataFrame(columns=["student_id", "name", "daily_seconds", "monthly_seconds", 
                                     "is_active", "start_time", "last_update"])

def update_sheet(df):
    try:
        conn.update(data=df)
        conn.reset()
    except Exception as e:
        st.error(f"저장 실패: {e}")

def check_date_reset():
    df = get_data(force_reload=False)
    if df.empty: return

    today_str = datetime.now().strftime("%Y-%m-%d")
    current_month = datetime.now().strftime("%Y-%m")
    is_changed = False
    
    for idx, row in df.iterrows():
        last_update = str(row['last_update']) if pd.notna(row['last_update']) else ""
        
        if last_update != today_str:
            is_changed = True
            d_sec = row['daily_seconds']
            m_sec = row['monthly_seconds']
            new_monthly = m_sec + d_sec
            if not last_update or last_update[:7] != current_month:
                new_monthly = 0
            df.at[idx, 'daily_seconds'] = 0
            df.at[idx, 'monthly_seconds'] = new_monthly
            df.at[idx, 'last_update'] = today_str
            
    if is_changed:
        update_sheet(df)

def register_student(name, student_id):
    df = get_data(force_reload=True)
