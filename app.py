import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import time
import os

# ---------------------------------------------------------
# 1. 기본 설정
# ---------------------------------------------------------
st.set_page_config(layout="wide", page_title="OnEducation Study Rank")
conn = st.connection("gsheets", type=GSheetsConnection)

# ---------------------------------------------------------
# 2. 데이터 처리 함수
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
        
        # 데이터 변환
        df['student_id'] = df['student_id'].astype(str).apply(lambda x: x.replace('.0', '').strip())
        df['daily_seconds'] = pd.to_numeric(df['daily_seconds'], errors='coerce').fillna(0)
        df['monthly_seconds'] = pd.to_numeric(df['monthly_seconds'], errors='coerce').fillna(0)
        df['is_active'] = pd.to_numeric(df['is_active'], errors='coerce').fillna(0)
        
        st.session_state['last_df'] = df.copy()
        return df
        
    except Exception as e:
        # [수정됨] 여기 들여쓰기가 딱 맞아야 합니다
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
        last_update
