import pandas as pd
from database import load_table
df_c = load_table('raw_coupang')
df_m = load_table('raw_mapping')
with open('cols.txt', 'w', encoding='utf-8') as f:
    f.write('Coupang: ' + str(df_c.columns.tolist()) + '\n')
    f.write('Mapping: ' + str(df_m.columns.tolist()) + '\n')
