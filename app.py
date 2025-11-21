# ---------------------------------------------------------
# 2. 데이터 처리 함수 (수정됨)
# ---------------------------------------------------------

def get_data():
    """구글 시트 데이터 읽기"""
    try:
        # ttl=0으로 설정하여 캐시를 끄거나 짧게 가져가야 즉시 반영됨
        # 하지만 API 호출 제한을 고려해 5초 유지하되, update 시 캐시를 날리는 방식 사용
        df = conn.read(ttl=5) 
        
        if df.empty or len(df.columns) < 7:
            return pd.DataFrame(columns=[
                "phone", "name", "daily_seconds", "monthly_seconds", 
                "is_active", "start_time", "last_update"
            ])
        
        # [중요] 숫자 처리를 더 확실하게 (1234.0 -> 1234)
        df['phone'] = df['phone'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        
        df['daily_seconds'] = pd.to_numeric(df['daily_seconds'], errors='coerce').fillna(0)
        df['monthly_seconds'] = pd.to_numeric(df['monthly_seconds'], errors='coerce').fillna(0)
        df['is_active'] = pd.to_numeric(df['is_active'], errors='coerce').fillna(0)
        
        return df
    except Exception as e:
        return pd.DataFrame()

def update_sheet(df):
    """구글 시트 업데이트 및 캐시 초기화"""
    try:
        conn.update(data=df)
        # [핵심 해결] 업데이트 후에는 기존 캐시를 날려버려야 바로 반영됨
        st.cache_data.clear() 
    except Exception as e:
        st.error(f"저장 중 오류: {e}")
