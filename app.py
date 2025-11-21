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
# 2. 데이터 처리 함수 (숫자/문자 강제 통일)
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
        
        # [핵심 수정] 1111이든 1111.0이든 무조건 깔끔한 문자 "1111"로 만듦
        df['student_id'] = df['student_id'].astype(str).apply(lambda x: x.replace('.0', '').strip())
        
        # 나머지 숫자 처리
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
        conn.reset() # 저장 후 캐시 즉시 초기화
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

# ---------------------------------------------------------
# 3. 기능 함수
# ---------------------------------------------------------
def register_student(name, student_id):
    df = get_data(force_reload=True)
    clean_id = str(student_id).strip()
    
    # 중복 체크
    if not df.empty and clean_id in df['student_id'].values:
        st.warning(f"이미 존재하는 비밀번호({clean_id})입니다.")
        return

    today_str = datetime.now().strftime("%Y-%m-%d")
    new_data = pd.DataFrame([{
        "student_id": clean_id, "name": name, "daily_seconds": 0, 
        "monthly_seconds": 0, "is_active": 0, "start_time": None, "last_update": today_str
    }])
    
    updated_df = pd.concat([df, new_data], ignore_index=True)
    update_sheet(updated_df)
    st.toast(f"환영합니다, {name} 학생 등록 완료!", icon="🎉")

def check_in_out(input_id):
    df = get_data(force_reload=True)
    clean_input = str(input_id).strip()
    
    # [디버깅용] 못 찾으면 저장된 번호 리스트를 에러 메시지에 띄워줌
    mask = df['student_id'] == clean_input
    
    if not mask.any():
        # 현재 등록된 번호들을 확인해봅니다.
        st.error(f"입력하신 '{clean_input}' 번호가 없습니다.")
        # (잠깐 디버깅용: 보안상 나중엔 지우세요)
        st.caption(f"📌 현재 등록된 번호들: {df['student_id'].tolist()}")
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
            st.error("기록 오류로 강제 퇴실 처리되었습니다.")

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
    </style>
    """, unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ 모드 선택")
    mode = st.radio("화면 모드", ["📺 대시보드 모드 (모니터용)", "✅ 출석체크 모드 (데스크용)"])
    
    # [여기 보세요!] 등록된 명단을 사이드바에서 확인 가능
    if mode == "✅ 출석체크 모드 (데스크용)":
        st.write("---")
        with st.expander("📋 현재 등록된 학생 명단 확인", expanded=True):
            df_debug = get_data(force_reload=False)
            if not df_debug.empty:
                # 비밀번호와 이름을 표로 보여줍니다.
                st.dataframe(df_debug[['name', 'student_id']], hide_index=True)
            else:
                st.warning("데이터가 비어있거나 불러오지 못했습니다.")
                
    st.write("---")
    st.caption("🔒 신규 등록은 관리자 비밀번호가 필요합니다.")

# === 대시보드 모드 ===
if mode == "📺 대시보드 모드 (모니터용)":
    if os.path.exists("image_0.png"):
        st.image("image_0.png", use_container_width=True)
    
    df = get_data(force_reload=False)
    
    if not df.empty:
        now = datetime.now()
        real_daily, real_monthly = [], []
        
        for idx, row in df.iterrows():
            d, m = float(row['daily_seconds']), float(row['monthly_seconds'])
            if row['is_active'] == 1 and pd.notna(row['start_time']):
                try:
                    st_t = str(row['start_time'])
                    try: s_dt = datetime.strptime(st_t, "%Y-%m-%d %H:%M:%S.%f")
                    except: s_dt = datetime.strptime(st_t, "%Y-%m-%d %H:%M:%S")
                    elapsed = (now - s_dt).total_seconds()
                    d += elapsed
                except: pass
            real_daily.append(d)
            real_monthly.append(m + d)

        df['real_daily'] = real_daily
        df['real_monthly'] = real_monthly

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("<div class='section-title'>☀️ 오늘의 공부왕 (Daily)</div>", unsafe_allow_html=True)
            for i, r in df.sort_values(by='real_daily', ascending=False).reset_index(drop=True).iterrows():
                if r['real_daily'] < 1: continue
                rank = i + 1
                ts = int(r['real_daily'])
                emoji = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"{rank}위"
                badge = f"<span class='status-active'>🔥 열공중</span>" if r['is_active'] else f"<span class='status-rest'>💤 휴식</span>"
                st.markdown(f"""<div class="rank-card"><div><span class="big-emoji">{emoji}</span> <b>{r['name']}</b> {badge}</div><div style='font-family:monospace; color:#4CAF50;'>{ts//3600}h {(ts%3600)//60}m {ts%60:02d}s</div></div>""", unsafe_allow_html=True)

        with c2:
            st.markdown("<div class='section-
