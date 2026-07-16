import pandas as pd

from database import load_table

def merge_data():
    """
    1단계: SQLite DB에서 데이터를 읽어와서 조건에 맞게 병합하는 로직
    """
    # 1. DB에서 테이블 읽어오기
    df_mapping = load_table('raw_mapping')
    df_inventory = load_table('raw_inventory')
    df_coupang = load_table('raw_coupang')
    df_product = load_table('raw_product')

    if df_mapping.empty:
        # 매핑키가 없더라도 상품등록을 베이스로 사용할 수 있도록 폴백 처리
        if not df_product.empty:
            base_df = df_product.copy()
            if '모델그룹' not in base_df.columns and '모델명' in base_df.columns:
                base_df['모델그룹'] = base_df['모델명'].astype(str).apply(
                    lambda x: '-'.join(x.split('-')[:2]) if pd.notna(x) and str(x).count('-') >= 1 else x
                )
        else:
            return None
    else:
        base_df = df_mapping.copy()
        # 매핑키에 모델그룹이 없고 모델명만 있다면 미리 파싱해둠 (이후의 모든 병합 기준키)
        if '모델그룹' not in base_df.columns and '모델명' in base_df.columns:
            base_df['모델그룹'] = base_df['모델명'].astype(str).apply(
                lambda x: '-'.join(x.split('-')[:2]) if pd.notna(x) and str(x).count('-') >= 1 else x
            )

    # 조건 1. 재고파일 매핑 (모델그룹 기준 가용재고 합산)
    try:
        if not df_inventory.empty and '가용재고' in df_inventory.columns and '모델명' in df_inventory.columns:
            df_inventory['가용재고'] = pd.to_numeric(df_inventory['가용재고'], errors='coerce').fillna(0)
            
            df_inventory['모델그룹_재고'] = df_inventory['모델명'].astype(str).apply(
                lambda x: '-'.join(x.split('-')[:2]) if pd.notna(x) and str(x).count('-') >= 1 else x
            )
            
            inv_grouped = df_inventory.groupby('모델그룹_재고', as_index=False)['가용재고'].sum()
            inv_grouped.rename(columns={'모델그룹_재고': '모델그룹', '가용재고': '몰재고_재고파일'}, inplace=True)
            
            if '모델그룹' in base_df.columns:
                merged_df = pd.merge(base_df, inv_grouped, on='모델그룹', how='left')
            else:
                merged_df = base_df
        else:
            merged_df = base_df
    except Exception as e:
        print(f"경고: 재고 병합 에러 - {e}")
        merged_df = base_df

    # 조건 2. 매핑키의 '바코드', 'SKU ID' 또는 '상품명'을 기준으로 쿠팡로켓 상품목록 데이터를 연결
    if not df_coupang.empty:
        if '바코드' in merged_df.columns and '바코드' in df_coupang.columns:
            merged_df = pd.merge(merged_df, df_coupang, on='바코드', how='left', suffixes=('', '_쿠팡'))
        elif 'SKU ID' in merged_df.columns and 'SKU ID' in df_coupang.columns:
            merged_df = pd.merge(merged_df, df_coupang, on='SKU ID', how='left', suffixes=('', '_쿠팡'))
        elif '상품명' in merged_df.columns and '상품명' in df_coupang.columns:
            merged_df = pd.merge(merged_df, df_coupang, on='상품명', how='left', suffixes=('', '_쿠팡'))

    # 조건 3. '모델그룹'을 기준으로 민영 상품등록 파일 데이터 연결 (base_df가 mapping일 경우에만 필요)
    if not df_product.empty and not df_mapping.empty:
        if '모델그룹' not in df_product.columns and '모델명' in df_product.columns:
            df_product['모델그룹'] = df_product['모델명'].astype(str).apply(
                lambda x: '-'.join(x.split('-')[:2]) if pd.notna(x) and str(x).count('-') >= 1 else x
            )
        try:
            merged_df = pd.merge(merged_df, df_product, on='모델그룹', how='outer', suffixes=('', '_등록'))
            # 상품등록의 메인 카테고리 정보가 _등록으로 빠졌다면 메인으로 복구
            for c in ['대분류', '계절', '중분류', '소분류', '성별', '원가']:
                if f"{c}_등록" in merged_df.columns:
                    if c in merged_df.columns:
                        merged_df[c] = merged_df[f"{c}_등록"].combine_first(merged_df[c])
                    else:
                        merged_df[c] = merged_df[f"{c}_등록"]
                    merged_df.drop(columns=[f"{c}_등록"], inplace=True)
        except KeyError:
            pass

    # app.py와 컬럼명 통일
    if 'SKU ID' in merged_df.columns:
        merged_df.rename(columns={'SKU ID': 'SKUID'}, inplace=True)
    if '단품명' not in merged_df.columns and '사이즈' in merged_df.columns:
        merged_df['단품명'] = merged_df['사이즈']

    return merged_df

if __name__ == "__main__":
    final_df = merge_data()
    if final_df is not None:
        print("병합 작업 완료")
