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
# 2. 데이터 처리 함수 (안전하게 처리)
# ---------------------------------------------------------

def get_data(force_reload=False):
    # 세션 상태 초기화
    if 'last_df' not in st.session_state:
        st.session_state['last_df'] = pd.DataFrame(columns=[
            "student_id", "name", "daily_seconds", "monthly_seconds", 
            "is_active", "start_time", "last_update"
        ])

    try:
        if force_reload:
            conn.reset()
        
        # 평소엔 15초 캐시 사용
        df = conn.read(ttl=15)
        
        expected_cols = ["student_id", "name", "daily_seconds", "monthly_seconds", 
                         "is_active", "start_time", "last_update"]

        # 데이터가 없거나 컬럼이 깨졌을 때 방어
        if df.empty or 'student_id' not in df.columns:
            if not st.session_state['last_df'].empty:
                return st.session_state['last_df']
            return pd.DataFrame(columns=expected_cols)
        
        # [핵심] 1111.0 -> "1111"로 확실하게 변환
        df['student_id'] = df['student_id'].astype(str).apply(lambda x: x.replace('.0', '').strip())
        
        # 숫자 컬럼 변환
        df['daily_seconds'] = pd.to_numeric(df['daily_seconds'], errors='coerce').fillna(0)
        df['monthly_seconds'] = pd.to_numeric(df['monthly_seconds'], errors='coerce').fillna(0)
        df['is_active'] = pd.to_numeric(df['is_active'], errors='coerce').fillna(0)
        
        # 성공 데이터 저장
        st.session_state['last_df'] = df.copy()
        return df
        
    except Exception as e:
