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

# 구글 시트 연결
conn = st.connection("gsheets", type=GSheetsConnection)

# ---------------------------------------------------------
# 2. 데이터 처리 함수
# ---------------------------------------------------------

def get_data():
    """구글 시트 데이터 읽기"""
    try:
        df = conn.read(ttl=5)
        if df.empty or len(df.columns) < 7:
            return pd.DataFrame(columns=[
                "phone", "name", "daily_seconds", "monthly_seconds", 
                "is_active", "start_time", "last_update"
            ])
        
        df['daily_seconds'] = pd.to_numeric(df['daily_seconds'], errors='coerce').fillna(0)
        df['monthly_seconds'] = pd.to_numeric(df['monthly_seconds'], errors='coerce').fillna(0)
        df['is_active'] = pd.to_numeric(df['is_active'], errors='coerce').fillna(0)
        
        # 전화번호 정제
        df['phone'] = df['phone'].astype(str)
        df['phone'] = df['phone'].str.replace(r'\.0$', '', regex=True)
        df['phone'] = df['phone'].str.strip()
        
        return df
    except Exception:
        return pd.DataFrame()

def update_sheet(df):
    try:
        conn.update(data=df)
    except Exception:
        pass

def check_date_reset():
    """자정 초기화 로직"""
    df = get_data()
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

# ---------------------------------------------------------
# 3. 기능 함수
# ---------------------------------------------------------
def register_student(name, phone):
    clean_phone = str(phone).strip()
    df = get_data()
    
    if not df.empty and clean_phone in df['phone'].values:
        st.warning(f"이미 등록된 번호입니다: {clean_phone}")
        return

    today_str = datetime.now().strftime("%Y-%m-%d")
    new_data = pd.DataFrame([{
        "phone": clean_phone, "name": name, "daily_seconds": 0, 
        "monthly_seconds": 0, "is_active": 0, "start_time": None, "last_update": today_str
    }])
    
    updated_df = pd.concat([df, new_data], ignore_index=True)
    update_sheet(updated_df)
    st.toast(f"환영합니다, {name} 학생 등록 완료!", icon="🎉")

def check_in_out(phone):
    clean_phone = str(phone).strip()
    df = get_data()
    mask = df['phone'] == clean_phone
    
    if not mask.any():
        st.error(f"등록되지 않은 번호입니다 ({clean_phone}).")
        return

    idx = df[mask].index[0]
    row = df.loc[idx]
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    
    if row['is_active'] == 0: # 입실
        df.at[idx, 'is_active'] = 1
        df.at[idx, 'start_time'] = str(now)
        df.at[idx, 'last_update'] = today_str
        update_sheet(df)
        st.success(f"🔥 [{row['name']}]님 열공 시작!")
        
    else: # 퇴실
        try:
            st_time = str(row['start_time'])
            try: start_dt = datetime.strptime(st_time, "%Y-%m-%d %H:%M:%S.%f")
            except: start_dt = datetime.strptime(st_time, "%Y-%m-%d %H:%M:%S")
            
            duration = (now - start_dt).seconds
            df.at[idx, 'daily_seconds'] += duration
            df.at[idx, 'is_active'] = 0
            df.at[idx, 'start_time'] = None
            df.at[idx, 'last_update'] = today_str
            
            update_sheet(df)
            h, m = duration // 3600, (duration % 3600) // 60
            st.info(f"👋 [{row['name']}]님 고생했어요! ({h}시간 {m}분 추가)")
        except:
            df.at[idx, 'is_active'] = 0
            update_sheet(df)
            st.error("오류 처리됨")

# ---------------------------------------------------------
# 4. UI 구성
# ---------------------------------------------------------
check_date_reset()

st.markdown("""
    <style>
    .rank-card { 
        padding: 15px; border-radius: 15px; margin-bottom: 12px; 
        background-color: var(--secondary-background-color); 
        border: 1px solid rgba(128, 128, 128, 0.2);
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .status-active { color: #4CAF50; font-weight: bold; border: 1px solid #4CAF50; padding: 2px 6px; border-radius: 5px; font-size: 0.7em; }
    .status-rest { color: #888; font-weight: bold; border: 1px solid #888; padding: 2px 6px; border-radius: 5px; font-size: 0.7em; }
    .section-title { font-size: 1.5em; font-weight: bold; margin-top: 20px; margin-bottom: 15px; }
    .big-emoji { font-size: 1.2em; }
    /* 스트림릿 기본 실행 애니메이션 숨기기 */
    .stApp > header {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ 모드 선택")
    mode = st.radio("화면 모드", ["📺 대시보드 모드 (모니터용)", "✅ 출석체크 모드 (데스크용)"])
    st.write("---")
    st.caption("🔒 신규 등록은 관리자 비밀번호가 필요합니다.")

# ---------------------------------------------------------
# 화면 로직
# ---------------------------------------------------------

if mode == "📺 대시보드 모드 (모니터용)":
    # [수정됨] 전체 화면을 감싸는 빈 상자를 먼저 만듭니다.
    # 이 안에 이미지와 랭킹을 모두 넣어야 잔상이 남지 않습니다.
    main_placeholder = st.empty()
    
    while True:
        # 데이터를 먼저 읽어옵니다
        df = get_data()
        
        # 상자 안을 비우고 새로 그립니다
        with main
