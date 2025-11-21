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

# 구글 시트 연결 객체 생성
conn = st.connection("gsheets", type=GSheetsConnection)

# ---------------------------------------------------------
# 2. 데이터 처리 함수
# ---------------------------------------------------------

def get_data():
    """구글 시트 데이터 읽기 (캐시 5초)"""
    try:
        df = conn.read(ttl=5)
        if df.empty or len(df.columns) < 7:
            return pd.DataFrame(columns=[
                "phone", "name", "daily_seconds", "monthly_seconds", 
                "is_active", "start_time", "last_update"
            ])
        
        # --- [수정된 부분 시작] ---
        # 데이터 타입 정리 (NaN 값을 0으로 채우기)
        df['daily_seconds'] = pd.to_numeric(df['daily_seconds'], errors='coerce').fillna(0)
        df['monthly_seconds'] = pd.to_numeric(df['monthly_seconds'], errors='coerce').fillna(0)
        df['is_active'] = pd.to_numeric(df['is_active'], errors='coerce').fillna(0)

        # 전화번호 처리 핵심 로직:
        # 1. 문자로 변환
        # 2. 소수점(.0)이 붙어있다면 제거
        # 3. 앞뒤 공백 제거
        df['phone'] = df['phone'].apply(lambda x: str(x).split('.')[0].strip())
        # --- [수정된 부분 끝] ---
        
        return df
    except Exception as e:
        # 디버깅을 위해 에러 메시지를 출력해보는 것이 좋습니다.
        st.error(f"데이터 로드 중 오류 발생: {e}") 
        return pd.DataFrame()

def update_sheet(df):
    """구글 시트 업데이트"""
    try:
        conn.update(data=df)
    except Exception as e:
        st.error(f"저장 중 오류: {e}")

def check_date_reset():
    """날짜 변경 시 초기화 로직"""
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
# 3. 핵심 기능
# ---------------------------------------------------------
def register_student(name, phone):
    df = get_data()
    if not df.empty and str(phone) in df['phone'].values:
        st.warning("이미 등록된 번호입니다.")
        return

    today_str = datetime.now().strftime("%Y-%m-%d")
    new_data = pd.DataFrame([{
        "phone": str(phone), "name": name, "daily_seconds": 0, 
        "monthly_seconds": 0, "is_active": 0, "start_time": None, "last_update": today_str
    }])
    
    updated_df = pd.concat([df, new_data], ignore_index=True)
    update_sheet(updated_df)
    st.toast(f"환영합니다, {name} 학생 등록 완료!", icon="🎉")

def check_in_out(phone):
    df = get_data()
    mask = df['phone'] == str(phone)
    
    if not mask.any():
        st.error("등록되지 않은 번호입니다. 관리자에게 문의하세요.")
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
            st.error("오류가 있어 강제 퇴실 처리했습니다.")

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
    st.write("---")
    st.caption("🔒 신규 등록은 관리자 비밀번호가 필요합니다.")

# === 대시보드 모드 ===
if mode == "📺 대시보드 모드 (모니터용)":
    if os.path.exists("image_0.png"):
        st.image("image_0.png", use_container_width=True)
    
    df = get_data()
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
            phone = st.text_input("전화번호 뒷자리 (4자리)", max_chars=4)
            if st.form_submit_button("확인", type="primary", use_container_width=True):
                if phone:
                    check_in_out(phone)
                    time.sleep(1)
                    st.rerun()

    with c2:
        st.subheader("🔒 신규 학생 등록 (관리자)")
        # 비밀번호 검사 로직
        admin_pw = st.text_input("관리자 비밀번호 입력", type="password")
        
        if "admin_password" in st.secrets and admin_pw == st.secrets["admin_password"]:
            st.success("관리자 인증 완료 ✨")
            with st.container(border=True):
                new_name = st.text_input("학생 이름")
                new_phone = st.text_input("전화번호 뒷자리", key="new_phone", max_chars=4)
                if st.button("등록하기", use_container_width=True):
                    if new_name and new_phone:
                        register_student(new_name, new_phone)
                        time.sleep(1)
                        st.rerun()
        elif admin_pw:
            st.error("비밀번호가 틀렸습니다.")


def register_student(name, phone):
    # ... (기존 코드) ...
    
    updated_df = pd.concat([df, new_data], ignore_index=True)
    update_sheet(updated_df)
    
    # [추가] 캐시를 비워서 즉시 반영되도록 함
    st.cache_data.clear() 
    conn.reset() # 연결 재설정 (확실한 갱신)
    
    st.toast(f"환영합니다, {name} 학생 등록 완료!", icon="🎉")

