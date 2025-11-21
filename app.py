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
# 2. 데이터 처리 함수 (스마트 캐싱 + 에러 방어 적용)
# ---------------------------------------------------------

def get_data(force_reload=False):
    """
    구글 시트 데이터 읽기
    - 평소에는: 캐시된 데이터를 써서 API 횟수를 아낌 (TTL=15)
    - force_reload=True일 때: 강제로 최신 데이터를 가져옴
    """
    # 세션에 마지막 데이터 저장소 만들기
    if 'last_df' not in st.session_state:
        st.session_state['last_df'] = pd.DataFrame(columns=[
            "student_id", "name", "daily_seconds", "monthly_seconds", 
            "is_active", "start_time", "last_update"
        ])

    try:
        # 강제 새로고침이 필요하면 캐시 초기화
        if force_reload:
            conn.reset()
        
        # 15초 동안은 저장된 거 쓰고, 15초 지나면 새로 가져옴 (API 보호)
        df = conn.read(ttl=15)
        
        expected_cols = ["student_id", "name", "daily_seconds", "monthly_seconds", 
                         "is_active", "start_time", "last_update"]

        # 데이터가 비정상이면(컬럼 깨짐 등) 빈 표 리턴
        if df.empty or 'student_id' not in df.columns:
            # 만약 읽어왔는데 비어있다면, 혹시 모르니 마지막 성공 데이터를 반환 (방어 코드)
            if not st.session_state['last_df'].empty:
                return st.session_state['last_df']
            return pd.DataFrame(columns=expected_cols)
        
        # 데이터 타입 안전 변환
        df['daily_seconds'] = pd.to_numeric(df['daily_seconds'], errors='coerce').fillna(0)
        df['monthly_seconds'] = pd.to_numeric(df['monthly_seconds'], errors='coerce').fillna(0)
        df['is_active'] = pd.to_numeric(df['is_active'], errors='coerce').fillna(0)
        df['student_id'] = df['student_id'].astype(str).apply(lambda x: x.split('.')[0])
        
        # 성공적으로 가져왔으면 '마지막 데이터'로 저장해둠 (에러 날 때 쓰려고)
        st.session_state['last_df'] = df.copy()
        
        return df
        
    except Exception as e:
        # 구글이 429 에러(차단)를 보내면, 당황하지 않고 저장해둔 데이터를 보여줌
        # -> 이렇게 해야 공부시간이 0으로 리셋되지 않음!
        if not st.session_state['last_df'].empty:
            return st.session_state['last_df']
        
        return pd.DataFrame(columns=["student_id", "name", "daily_seconds", "monthly_seconds", 
                                     "is_active", "start_time", "last_update"])

def update_sheet(df):
    try:
        conn.update(data=df)
        # 저장 후에는 캐시를 날려줘야 바로 반영됨
        conn.reset()
    except Exception as e:
        st.error(f"저장 실패: {e}")

def check_date_reset():
    """날짜 변경 체크"""
    # 여기서는 굳이 강제 로딩 안 해도 됨
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
# 3. 기능 함수 (여기는 버튼 누를 때라 즉시 반영 필요)
# ---------------------------------------------------------
def register_student(name, student_id):
    # 등록 전엔 최신 데이터 확실히 확인 (force_reload=True)
    df = get_data(force_reload=True)
    str_id = str(student_id).strip()
    
    if not df.empty and str_id in df['student_id'].values:
        st.warning(f"이미 존재하는 비밀번호({str_id})입니다.")
        return

    today_str = datetime.now().strftime("%Y-%m-%d")
    
    new_data = pd.DataFrame([{
        "student_id": str_id, 
        "name": name, 
        "daily_seconds": 0, 
        "monthly_seconds": 0, 
        "is_active": 0, 
        "start_time": None, 
        "last_update": today_str
    }])
    
    updated_df = pd.concat([df, new_data], ignore_index=True)
    update_sheet(updated_df)
    st.toast(f"환영합니다, {name} 학생 등록 완료!", icon="🎉")

def check_in_out(input_id):
    # 입퇴실 때도 최신 데이터 확인 필수
    df = get_data(force_reload=True)
    target_id = str(input_id).strip()
    
    mask = df['student_id'] == target_id
    
    if not mask.any():
        st.error(f"등록되지 않은 비밀번호입니다.")
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
# 4. 화면 구성
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
    st.write("---")
    st.caption("🔒 신규 등록은 관리자 비밀번호가 필요합니다.")

# === 대시보드 모드 ===
if mode == "📺 대시보드 모드 (모니터용)":
    if os.path.exists("image_0.png"):
        st.image("image_0.png", use_container_width=True)
    
    # 대시보드는 평소에 API 안 부르고 캐시된거 쓰다가 15초마다 갱신 (force_reload=False)
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
                    
                    # 여기서 실시간 시간 계산은 Python이 하므로 API 안 씀
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
            st.markdown("<div class='section-title'>📅 이달의 명예의 전당 (Monthly)</div>", unsafe_allow_html=True)
            for i, r in df.sort_values(by='real_monthly', ascending=False).reset_index(drop=True).iterrows():
                if r['real_monthly'] < 1: continue
                rank = i + 1
                ts = int(r['real_monthly'])
                mark = "👑" if rank == 1 else f"{rank}."
                bg = "rgba(255,215,0,0.1)" if rank == 1 else "transparent"
                st.markdown(f"""<div style="padding:12px; border-bottom:1px solid #eee; background:{bg}; display:flex; justify-content:space-between;"><div><b>{mark}</b> {r['name']}</div><div>{ts//3600}시간 {(ts%3600)//60}분</div></div>""", unsafe_allow_html=True)
    else:
        st.info("등록된 학생이 없습니다.")
    time.sleep(1)
    st.rerun()

# === 출석체크 모드 ===
elif mode == "✅ 출석체크 모드 (데스크용)":
    st.title("✅ OnEducation 데스크 관리")
    
    c1, c2 = st.columns([1, 1])
    
    with c1:
        st.subheader("👋 입실 / 퇴실 처리")
        with st.form("check_in"):
            student_id = st.text_input("학생 비밀번호 입력", type="password", max_chars=4)
            if st.form_submit_button("확인", type="primary", use_container_width=True):
                if student_id:
                    check_in_out(student_id)
                    time.sleep(1) # 처리 대기
                    st.rerun()

    with c2:
        st.subheader("🔒 신규 학생 등록 (관리자)")
        admin_pw = st.text_input("관리자 비밀번호 입력", type="password")
        
        if "admin_password" in st.secrets and admin_pw == st.secrets["admin_password"]:
            st.success("관리자 인증 완료 ✨")
            with st.container(border=True):
                new_name = st.text_input("학생 이름")
                new_student_id = st.text_input("학생 비밀번호 (4자리)", key="new_student_id", max_chars=4)
                if st.button("등록하기", use_container_width=True):
                    if new_name and new_student_id:
                        register_student(new_name, new_student_id)
                        time.sleep(1) # 처리 대기
                        st.rerun()
        elif admin_pw:
            st.error("비밀번호가 틀렸습니다.")
