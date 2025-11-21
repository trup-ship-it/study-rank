def check_date_reset():
    """날짜 변경 시 자동 초기화 로직 (자정 기준)"""
    df = get_data()
    if df.empty: return

    # 현재 날짜 정보
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")        # 예: 2023-10-25
    current_month_str = now.strftime("%Y-%m")   # 예: 2023-10

    is_changed = False
    
    for idx, row in df.iterrows():
        # 1. 마지막 업데이트 날짜 확인 (비어있으면 오늘로 설정)
        last_update = str(row['last_update']) if pd.notna(row['last_update']) else today_str
        
        # 저장된 날짜와 오늘 날짜가 다르다면 (자정이 지났다면)
        if last_update != today_str:
            is_changed = True
            
            # 현재까지의 일일 공부 시간
            daily_sec = float(row['daily_seconds'])
            # 현재까지의 월간 공부 시간
            monthly_sec = float(row['monthly_seconds'])

            # --- [핵심 로직] ---
            
            # A. 월(Month)이 바뀌었는지 확인 (예: 9월 -> 10월)
            last_update_month = last_update[:7] # "2023-09" 추출

            if last_update_month != current_month_str:
                # 월이 바뀌었으면: 
                # 어제(전달 말일) 공부한 시간은 전달 기록이므로 누적하지 않고,
                # 새 달이 시작되었으니 월별 시간도 0으로 초기화 (혹은 어제자만 반영하고 싶다면 로직이 복잡해지니 보통 0으로 둡니다)
                new_monthly = 0
                print(f"[{row['name']}] 월 변경! 초기화 완료")
            else:
                # 월이 같다면 (같은 달 내에서 날짜만 변경):
                # 어제 공부한 시간을 월별 시간에 누적
                new_monthly = monthly_sec + daily_sec
                print(f"[{row['name']}] 일 변경! 월별 누적: {monthly_sec} + {daily_sec} -> {new_monthly}")

            # B. 값 업데이트
            df.at[idx, 'daily_seconds'] = 0           # 일별 시간은 0으로 리셋
            df.at[idx, 'monthly_seconds'] = new_monthly # 월별 시간은 누적(또는 리셋)됨
            df.at[idx, 'last_update'] = today_str       # 업데이트 날짜를 오늘로 갱신
            
            # 만약 밤새 공부 중(입실 상태)이었다면? -> 강제 퇴실 처리 (오류 방지)
            if row['is_active'] == 1:
                df.at[idx, 'is_active'] = 0
                df.at[idx, 'start_time'] = None

    if is_changed:
        update_sheet(df)
        st.toast("📅 날짜가 변경되어 공부 시간이 정리되었습니다.", icon="✅")
        time.sleep(1) # 업데이트 반영 대기
        st.rerun()    # 화면 새로고침
