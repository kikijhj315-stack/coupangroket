import pandas as pd
from step1_data_merge import merge_data
merged_df = merge_data()
target_sku_cols = ['SKUID', '상품명', '바코드', '담당 BM', '발주담당자']
sku_df = merged_df.copy()
for c in target_sku_cols:
    if c not in sku_df.columns:
        sku_df[c] = ''
print(sku_df[target_sku_cols].head(10))
