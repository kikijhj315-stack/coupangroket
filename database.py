import pandas as pd
import streamlit as st
from sqlalchemy import create_engine
import os

# 클라우드 DB 연결 엔진 생성
def get_engine():
    try:
        # st.secrets에 SUPABASE_DB_URL이 등록되어 있다면 가져옴
        db_url = st.secrets["SUPABASE_DB_URL"]
        # Supabase 기본 URI(postgres://)를 SQLAlchemy 호환(postgresql://)으로 변환
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        return create_engine(db_url)
    except Exception:
        # 클라우드 DB URL 세팅이 안 되어있거나 로컬 테스트 중인 경우, 기존의 로컬 SQLite 사용
        import sqlite3
        return sqlite3.connect('coupang_admin.db')

def save_table(df, table_name, mode='append'):
    """mode: 'append' or 'replace'"""
    engine = get_engine()
    df.to_sql(table_name, engine, if_exists=mode, index=False)

def load_table(table_name):
    engine = get_engine()
    try:
        return pd.read_sql(f"SELECT * FROM {table_name}", engine)
    except Exception:
        return pd.DataFrame()

def save_settings(df_settings):
    """모델그룹 단위의 사용자 설정(손익율, 판매가 등) 저장"""
    save_table(df_settings, 'model_settings', mode='replace')

def load_settings():
    return load_table('model_settings')

def save_sku_settings(df_sku):
    """SKU 단위의 사용자 설정(담당BM 등) 저장"""
    save_table(df_sku, 'sku_settings', mode='replace')

def load_sku_settings():
    return load_table('sku_settings')

def save_global_config(normal_ship, ski_ship):
    df = pd.DataFrame([{'normal_ship': normal_ship, 'ski_ship': ski_ship}])
    save_table(df, 'global_config', mode='replace')

def load_global_config():
    engine = get_engine()
    try:
        df = pd.read_sql("SELECT * FROM global_config", engine)
        if not df.empty:
            return df.iloc[0].to_dict()
    except Exception:
        pass
    return {'normal_ship': 500, 'ski_ship': 1250}
