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
