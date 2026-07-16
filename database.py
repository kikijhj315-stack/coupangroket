import sqlite3
import pandas as pd
import os

DB_NAME = 'coupang_admin.db'

def get_conn():
    return sqlite3.connect(DB_NAME)

def save_table(df, table_name, mode='append'):
    """mode: 'append' or 'replace'"""
    with get_conn() as conn:
        df.to_sql(table_name, conn, if_exists=mode, index=False)

def load_table(table_name):
    with get_conn() as conn:
        try:
            return pd.read_sql(f"SELECT * FROM {table_name}", conn)
        except Exception:
            return pd.DataFrame()

def save_settings(df_settings):
    """모델그룹 단위의 사용자 설정(손익율, 판매가 등) 저장"""
    with get_conn() as conn:
        df_settings.to_sql('model_settings', conn, if_exists='replace', index=False)

def load_settings():
    return load_table('model_settings')

def save_sku_settings(df_sku):
    """SKU 단위의 사용자 설정(담당BM 등) 저장"""
    with get_conn() as conn:
        df_sku.to_sql('sku_settings', conn, if_exists='replace', index=False)

def load_sku_settings():
    return load_table('sku_settings')

def save_global_config(normal_ship, ski_ship):
    df = pd.DataFrame([{'normal_ship': normal_ship, 'ski_ship': ski_ship}])
    with get_conn() as conn:
        df.to_sql('global_config', conn, if_exists='replace', index=False)

def load_global_config():
    with get_conn() as conn:
        try:
            df = pd.read_sql("SELECT * FROM global_config", conn)
            if not df.empty:
                return df.iloc[0].to_dict()
        except Exception:
            pass
    return {'normal_ship': 500, 'ski_ship': 1250}
