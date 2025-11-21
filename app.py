import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import time
import os

# ---------------------------------------------------------
# 1. 기본 설정 및 DB 연결
# ---------------------------------------------------------
st.set_page_config(layout="wide", page_title="OnEducation Study Rank")

def get_connection():
    return sqlite3.connect('study_room_v2.db', timeout=30)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS students
                 (phone TEXT PRIMARY KEY, 
                  name TEXT, 
                  daily_seconds INTEGER DEFAULT 0, 
                  monthly_seconds INTEGER DEFAULT 0,
                  is_active INTEGER DEFAULT 0, 
                  start_time TEXT,
                  last_update DATE)''')
    conn.commit()
    conn.close()

def check_date_reset():
    """날짜가 바뀌면 일간 기록 초기화 및 월간 누적"""
    conn = get_connection()
    c = conn.cursor()
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    current_month = datetime.now().strftime("%Y-%m")
    
    c.execute("SELECT phone, last_update FROM students")
    rows = c.fetchall()
    
    for phone, last_update in rows:
        if last_update != today_str:
            c.execute("SELECT daily_seconds, monthly_seconds FROM students WHERE phone=?", (phone,))
            result = c.fetchone()
            if result:
                d_sec, m_sec = result
                new_monthly = m_sec + d_sec
                
                # 월이 바뀌었으면 월간 기록도 0으로 초기화
                if last_update is None or last_update[:7] != current_month:
                    new_monthly = 0
                
                c.execute('''UPDATE students 
                             SET daily_seconds=0, monthly_seconds=?, last_update=? 
                             WHERE phone=?''', (new_monthly, today_str, phone))
    conn.commit()
    conn.close()

# ---------------------------------------------------------
# 2. 기능 로직 (등록, 입퇴실)
# ---------------------------------------------------------
def register_or_update(name, phone):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM students WHERE phone=?", (phone,))
    data = c.fetchone()
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    if data is None: 
        c.execute("INSERT INTO students VALUES (?, ?, 0, 0, 0, NULL, ?)", (phone, name, today_str))
        st.toast(f"환영합니다, {name} 학생 등록 완료!", icon="🎉")
    else:
        st.warning("이미 등록된 번호입니다.")
    conn.commit()
    conn.close()

def check_in_out(phone):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT name, daily_seconds, is_active, start_time FROM students WHERE phone=?", (phone,))
    user = c.fetchone()
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    if user:
        name, daily_sec, is_active, start_time_str = user
        now = datetime.now()
        
        if is_active == 0: # 입실
            c.execute("UPDATE students SET is_active=1, start_time=?, last_update=? WHERE phone=?", (str(now), today_str, phone))
            st.success(f"🔥 [{name}]님 열공 시작! ({now.strftime('%H:%M')})")
        else: # 퇴실
            try:
                start_time = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S.%f")
            except ValueError:
                start_time = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")

            study_duration = (now - start_time).seconds
            new_daily = daily_sec + study_duration
            
            c.execute("UPDATE students SET is_active=0, daily_seconds=?, start_time=NULL, last_update=? WHERE phone=?", (new_daily, today_str, phone))
            
            hours = study_duration // 3600
            mins = (study_duration % 3600) // 60
            st.info(f"👋 [{name}]님 고생했어요! 오늘 {hours}시간 {mins}분 추가했습니다.")
    else:
        st.error("등록되지 않은 번호입니다.")
    
    conn.commit()
    conn.close()

# ---------------------------------------------------------
# 3. 메인 실행 코드
# ---------------------------------------------------------

# DB 초기화 및 CSS 적용
init_db()
check_date_reset()

st.markdown("""
    <style>
    .rank-card { 
        padding: 15px; 
        border-radius: 15px; 
        margin-bottom: 12px; 
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

# --- 사이드바 메뉴 ---
with st.sidebar:
    st.header("⚙️ 모드 선택")
    mode = st.radio(
        "화면 모드",
        ["📺 대시보드 모드 (모니터용)", "✅ 출석체크 모드 (데스크용)"]
    )
    st.write("---")
    st.caption("모니터용은 자동으로 새로고침 됩니다.")

# =========================================================
# 화면 1: 대시보드 (입력창 아예 없음)
# =========================================================
if mode == "📺 대시보드 모드 (모니터용)":
    
    # 배너 이미지
    if os.path.exists("image_0.png"):
        st.image("image_0.png", use_container_width=True)
    
    # 랭킹 로직
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM students", conn)
    conn.close()
    
    if not df.empty:
        now = datetime.now()
        real_daily = []
        real_monthly = []
        
        for idx, row in df.iterrows():
            d_sec = row['daily_seconds']
            m_sec = row['monthly_seconds']
            # 실시간 시간 더하기
            if row['is_active'] == 1 and row['start_time']:
                try:
                    try: start_dt = datetime.strptime(row['start_time'], "%Y-%m-%d %H:%M:%S.%f")
                    except: start_dt = datetime.strptime(row['start_time'], "%Y-%m-%d %H:%M:%S")
                    elapsed = (now - start_dt).total_seconds()
                    d_sec += elapsed
                except: pass
            real_daily.append(d_sec)
            real_monthly.append(m_sec + d_sec)

        df['real_daily'] = real_daily
        df['real_monthly'] = real_monthly

        col_d, col_m = st.columns(2)

        # [왼쪽] Daily Rank
        with col_d:
            st.markdown("<div class='section-title'>☀️ 오늘의 공부왕 (Daily)</div>", unsafe_allow_html=True)
            df_daily = df.sort_values(by='real_daily', ascending=False).reset_index(drop=True)
            
            for i, row in df_daily.iterrows():
                if row['real_daily'] < 1: continue
                rank = i + 1
                total_sec = int(row['real_daily'])
                hours, mins, secs = total_sec // 3600, (total_sec % 3600) // 60, total_sec % 60
                
                emoji = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"{rank}위"
                status_badge = f"<span class='status-active'>🔥 열공중</span>" if row['is_active'] else f"<span class='status-rest'>💤 휴식</span>"
                
                st.markdown(f"""
                <div class="rank-card">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div><span class="big-emoji">{emoji}</span> <b style="font-size:1.1em;">{row['name']}</b> {status_badge}</div>
                        <div style='font-family: monospace; color: #4CAF50; font-size: 1.1em;'>{hours}h {mins}m {secs:02d}s</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        # [오른쪽] Monthly Rank
        with col_m:
            st.markdown("<div class='section-title'>📅 이달의 명예의 전당 (Monthly)</div>", unsafe_allow_html=True)
            df_monthly = df.sort_values(by='real_monthly', ascending=False).reset_index(drop=True)
            
            for i, row in df_monthly.iterrows():
                if row['real_monthly'] < 1: continue
                rank = i + 1
                total_sec = int(row['real_monthly'])
                hours, mins = total_sec // 3600, (total_sec % 3600) // 60
                
                rank_mark = "👑" if rank == 1 else f"{rank}."
                bg_color = "rgba(255, 215, 0, 0.1)" if rank == 1 else "transparent"
                
                st.markdown(f"""
                <div style="padding: 12px; border-bottom: 1px solid rgba(128,128,128,0.1); background-color: {bg_color}; border-radius: 5px; display: flex; justify-content: space-between; align-items: center;">
                    <div><span style='font-weight:bold; width: 30px; display:inline-block;'>{rank_mark}</span> <span style="font-size:1.05em;">{row['name']}</span></div>
                    <div style="font-weight: bold;">{hours}시간 {mins}분</div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("아직 공부 기록이 없습니다.")

    # 대시보드 모드일 때만 새로고침 (1초 간격)
    time.sleep(1)
    st.rerun()

# =========================================================
# 화면 2: 출석체크 (여기에만 입력창 존재)
# =========================================================
elif mode == "✅ 출석체크 모드 (데스크용)":
    
    st.title("✅ OnEducation 데스크 관리")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("👋 입실 / 퇴실 처리")
        with st.form(key='check_in_form', clear_on_submit=True):
            input_phone = st.text_input("전화번호 뒷자리 (4자리)", max_chars=4)
            if st.form_submit_button("확인", type="primary", use_container_width=True):
                if input_phone:
                    check_in_out(input_phone)
                    time.sleep(1.5)
                    st.rerun()

    with col2:
        st.subheader("🆕 신규 학생 등록")
        with st.container(border=True):
            new_name = st.text_input("학생 이름")
            new_phone = st.text_input("전화번호 뒷자리 (4자리)", key="new_phone", max_chars=4)
            if st.button("학생 등록하기", use_container_width=True):
                if new_name and new_phone:
                    register_or_update(new_name, new_phone)