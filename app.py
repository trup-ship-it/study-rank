if mode == "📺 대시보드 모드 (모니터용)":
    # 로고 (루프 밖에서 1회 로드)
    if os.path.exists("image_0.png"):
        st.image("image_0.png", use_container_width=True)
    
    # === [핵심] 깜빡임 방지 컨테이너 ===
    dashboard_placeholder = st.empty()

    while True:
        # 1. 데이터 가져오기
        df = get_data()
        
        # 2. 상자 안에서 UI 그리기 (컬럼 제거 -> 수직 배치로 변경)
        with dashboard_placeholder.container():
            if not df.empty:
                now = datetime.now()
                real_daily, real_monthly = [], []
                
                # 실시간 시간 계산
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

                # ------------------------------------------------
                # [1] 상단: 오늘의 공부왕 (Daily)
                # ------------------------------------------------
                st.markdown("<div class='section-title'>☀️ 오늘의 공부왕 (Daily)</div>", unsafe_allow_html=True)
                
                # 1등부터 3등까지만 크게 보여주거나, 전체를 리스트로 보여줌
                sorted_daily = df.sort_values(by='real_daily', ascending=False).reset_index(drop=True)
                
                # 보기 좋게 2열로 나누어 카드 배치 (일간 랭킹 내부에서만 나눔)
                d_col1, d_col2 = st.columns(2)
                
                for i, r in sorted_daily.iterrows():
                    if r['real_daily'] < 1: continue
                    
                    rank = i + 1
                    ts = int(r['real_daily'])
                    emoji = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"{rank}위"
                    badge = f"<span class='status-active'>🔥 열공중</span>" if r['is_active'] else f"<span class='status-rest'>💤 휴식</span>"
                    
                    card_html = f"""
                    <div class="rank-card">
                        <div style="font-size:1.1em;"><span class="big-emoji">{emoji}</span> <b>{r['name']}</b> {badge}</div>
                        <div style='font-family:monospace; color:#4CAF50; font-size:1.2em; font-weight:bold; margin-top:5px;'>
                            {ts//3600}h {(ts%3600)//60}m {ts%60:02d}s
                        </div>
                    </div>
                    """
                    
                    # 홀수/짝수 번갈아 가며 배치하여 공간 활용
                    if i % 2 == 0:
                        with d_col1: st.markdown(card_html, unsafe_allow_html=True)
                    else:
                        with d_col2: st.markdown(card_html, unsafe_allow_html=True)

                # ------------------------------------------------
                # 구분선
                # ------------------------------------------------
                st.write("---") 

                # ------------------------------------------------
                # [2] 하단: 이달의 명예의 전당 (Monthly)
                # ------------------------------------------------
                st.markdown("<div class='section-title'>📅 이달의 명예의 전당 (Monthly)</div>", unsafe_allow_html=True)
                
                sorted_monthly = df.sort_values(by='real_monthly', ascending=False).reset_index(drop=True)
                
                # 월간 데이터는 깔끔한 리스트 형태로 하단에 쭉 나열
                for i, r in sorted_monthly.iterrows():
                    if r['real_monthly'] < 1: continue
                    
                    rank = i + 1
                    ts = int(r['real_monthly'])
                    mark = "👑" if rank == 1 else f"{rank}."
                    # 1등 강조 색상 (다크모드에서도 잘 보이게 조정)
                    bg = "rgba(255, 215, 0, 0.15)" if rank == 1 else "rgba(128, 128, 128, 0.05)"
                    border = "1px solid #FFD700" if rank == 1 else "1px solid rgba(128,128,128,0.1)"
                    
                    st.markdown(f"""
                    <div style="padding:12px 20px; margin-bottom:8px; border-radius:10px; background:{bg}; border:{border}; display:flex; justify-content:space-between; align-items:center;">
                        <div style="font-size:1.1em;"><b>{mark}</b> &nbsp; {r['name']}</div>
                        <div style="font-family:monospace; font-weight:bold; font-size:1.1em;">
