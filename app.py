import streamlit as st
import pandas as pd
import numpy as np
import os
from datetime import datetime
import scraper

from step1_data_merge import merge_data
from step3_excel_export import create_dispatch_excel
from database import (
    save_table, load_table, 
    save_settings, load_settings, 
    save_sku_settings, load_sku_settings,
    save_global_config, load_global_config
)

# [New] Login credentials
CREDENTIALS = {
    "eidous00": {"password": "zxcv316900", "role": "admin"},
    "eidous01": {"password": "eidous1004", "role": "user"}
}

# 1. 브라우저 및 앱 타이틀 변경
st.set_page_config(layout="wide", page_title="[쿠팡 로켓 상품관리 시스템]")

# --- 로그인 로직 ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_role' not in st.session_state:
    st.session_state.user_role = None

if not st.session_state.logged_in:
    st.title("🔒 쿠팡 로켓 상품관리 시스템 로그인")
    st.markdown("접근 권한이 필요합니다. 부여받은 계정으로 로그인해주세요.")
    with st.form("login_form"):
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            username = st.text_input("아이디")
            password = st.text_input("비밀번호", type="password")
            submit = st.form_submit_button("로그인", use_container_width=True)
            
            if submit:
                if username in CREDENTIALS and CREDENTIALS[username]["password"] == password:
                    st.session_state.logged_in = True
                    st.session_state.user_role = CREDENTIALS[username]["role"]
                    st.rerun()
                else:
                    st.error("아이디 또는 비밀번호가 잘못되었습니다.")
    st.stop()  # 로그인 성공 전까지 화면 하단 렌더링 중지

is_admin = (st.session_state.user_role == "admin")

st.markdown("""
<style>
    section[data-testid="stSidebar"] div[role="radiogroup"] > label {
        padding: 10px 15px;
        background-color: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(128, 128, 128, 0.2);
        border-radius: 10px;
        margin-bottom: 8px;
        transition: all 0.2s ease-in-out;
        cursor: pointer;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover {
        background-color: rgba(128, 128, 128, 0.1);
        transform: translateY(-2px);
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. 사이드바 - 타이틀, 메인 메뉴 및 설정
# ==========================================
st.sidebar.title("📦 쿠팡 로켓\n상품관리 시스템")
st.sidebar.markdown("---")

# 커스텀 메뉴 상태 관리
if 'active_menu' not in st.session_state:
    st.session_state.active_menu = "📊 등록 현황"

def nav_button(menu_name):
    # 선택된 메뉴는 primary(색상 강조), 나머지는 secondary 테마 적용
    btn_type = "primary" if st.session_state.active_menu == menu_name else "secondary"
    if st.sidebar.button(menu_name, type=btn_type, use_container_width=True):
        st.session_state.active_menu = menu_name
        st.rerun()

st.sidebar.markdown("#### 📂 상품관리")
if is_admin:
    nav_button("📤 데이터 업로드")
nav_button("📊 등록 현황")
nav_button("🎁 프로모션 관리")
if is_admin:
    nav_button("🏷️ SKU 관리")

st.sidebar.markdown("<br>", unsafe_allow_html=True) # 간격 띄우기
st.sidebar.markdown("#### 📂 출고")
nav_button("🚚 출고리스트 파일 생성")

menu = st.session_state.active_menu

st.sidebar.markdown("---")
st.sidebar.markdown(f"**👤 접속 계정:** `{'관리자 (Admin)' if is_admin else '일반 사용자 (조회전용)'}`")
if st.sidebar.button("🚪 로그아웃", use_container_width=True):
    st.session_state.logged_in = False
    st.session_state.user_role = None
    st.session_state.active_menu = "📊 등록 현황"
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("⚙️ 배송비 전역 설정")
global_conf = load_global_config()

normal_ship = st.sidebar.number_input("일반 배송비", value=int(global_conf.get('normal_ship', 500)), step=100, disabled=not is_admin)
ski_ship = st.sidebar.number_input("스키복 배송비", value=int(global_conf.get('ski_ship', 1250)), step=100, disabled=not is_admin)

if is_admin:
    if st.sidebar.button("💾 배송비 DB 저장"):
        save_global_config(normal_ship, ski_ship)
        st.sidebar.success("저장 완료!")
else:
    st.sidebar.info("설정은 관리자만 수정 가능합니다.")

# ==========================================
# 2. 메인 화면 로직
# ==========================================
if menu == "📤 데이터 업로드":
    st.header("📤 데이터 업로드")
    st.markdown("엑셀 데이터를 데이터베이스에 업로드합니다. **추가등록** 또는 **덮어쓰기**를 선택하고 저장하세요.")
    
    mode_text = st.radio("업로드 모드 선택", ["추가등록 (기존 데이터에 이어서 저장)", "덮어쓰기 (기존 데이터를 지우고 새로 저장)"])
    db_mode = 'replace' if "덮어쓰기" in mode_text else 'append'
    
    col1, col2 = st.columns(2)
    with col1:
        map_file = st.file_uploader("1. 민영 매핑키 (Base)", type=['xlsx'])
        if map_file and st.button("매핑키 DB 저장"):
            df = pd.read_excel(map_file)
            save_table(df, 'raw_mapping', db_mode)
            st.success("매핑키 저장 완료!")
            
        inv_file = st.file_uploader("2. 재고파일 (CSV/Excel)", type=['csv', 'xlsx'])
        if inv_file and st.button("재고파일 DB 저장"):
            try:
                df = pd.read_csv(inv_file, encoding='utf-8-sig') if inv_file.name.endswith('.csv') else pd.read_excel(inv_file)
            except UnicodeDecodeError:
                df = pd.read_csv(inv_file, encoding='cp949')
            save_table(df, 'raw_inventory', db_mode)
            st.success("재고파일 저장 완료!")
            
    with col2:
        prod_file = st.file_uploader("3. 민영 상품등록", type=['xlsx'])
        if prod_file and st.button("상품등록 DB 저장"):
            df = pd.read_excel(prod_file)
            save_table(df, 'raw_product', db_mode)
            st.success("상품등록 저장 완료!")
            
        coup_file = st.file_uploader("4. 쿠팡로켓 상품목록", type=['xlsx'])
        if coup_file and st.button("쿠팡로켓 DB 저장"):
            df = pd.read_excel(coup_file)
            save_table(df, 'raw_coupang', db_mode)
            st.success("쿠팡로켓 저장 완료!")

elif menu in ["📊 등록 현황", "🎁 프로모션 관리", "🏷️ SKU 관리"]:
    
    with st.spinner("DB에서 데이터를 불러와 병합 중입니다..."):
        merged_df = merge_data()
        
    if merged_df is None or merged_df.empty:
        st.warning("데이터가 부족합니다. [데이터 업로드] 메뉴에서 기초 엑셀 파일들을 DB에 저장해 주세요.")
    else:
        # DB 저장된 설정값 불러오기
        db_settings = load_settings()
        db_sku_settings = load_sku_settings()
        
        # --- 사이드바 필터링 적용 (접기/펼치기 가능) ---
        with st.expander("🔍 데이터 필터", expanded=True):
            filtered_df = merged_df.copy()
            if '담당BM' in filtered_df.columns and '담당 BM' not in filtered_df.columns:
                filtered_df.rename(columns={'담당BM': '담당 BM'}, inplace=True)
                
            # SKU 설정 테이블에 담당 BM이 있다면 업데이트
            if not db_sku_settings.empty and 'SKUID' in db_sku_settings.columns and '담당 BM' in db_sku_settings.columns:
                # 병합된 데이터의 담당 BM을 SKU DB 설정값으로 덮어씌움
                filtered_df = pd.merge(filtered_df, db_sku_settings[['SKUID', '담당 BM']], on='SKUID', how='left', suffixes=('', '_db'))
                filtered_df['담당 BM'] = filtered_df['담당 BM_db'].combine_first(filtered_df['담당 BM'])
                filtered_df.drop(columns=['담당 BM_db'], inplace=True)

            filter_cols = ['대분류', '계절', '중분류', '소분류', '성별', '담당 BM']
            cols = st.columns(len(filter_cols))
            for i, col in enumerate(filter_cols):
                if col in filtered_df.columns:
                    unique_vals = [v for v in filtered_df[col].unique() if pd.notna(v) and str(v).strip() != '']
                    if unique_vals:
                        selected = cols[i].multiselect(f"{col}", options=unique_vals, default=[])
                        if selected:
                            filtered_df = filtered_df[filtered_df[col].isin(selected)]
            
            # 모델그룹 검색 (부분 검색 가능)
            if '모델그룹' in filtered_df.columns:
                search_model = st.text_input("🔍 모델그룹 검색 (예: 00-00000 또는 00000)")
                if search_model.strip():
                    filtered_df = filtered_df[filtered_df['모델그룹'].astype(str).str.contains(search_model.strip(), case=False, na=False)]
        
        # --- 모델그룹 단위 Groupby 로직 (등록 현황, 프로모션 관리 공통) ---
        def get_grouped_and_calculated(df, db_settings_df):
            group_cols = ['대분류', '계절', '중분류', '소분류', '성별', '모델그룹']
            existing_group_cols = [c for c in group_cols if c in df.columns]
            
            if existing_group_cols:
                agg_dict = {}
                if '몰재고_재고파일' in df.columns: agg_dict['몰재고_재고파일'] = 'first'
                cols_to_first = ['원가', '담당 BM', '로켓등록', '민영 희망손익율', '쿠팡 판매가', '쿠팡판매가']
                if '쿠팡 판매가' in df.columns and '쿠팡판매가' not in df.columns:
                    df.rename(columns={'쿠팡 판매가': '쿠팡판매가'}, inplace=True)
                for c in cols_to_first:
                    if c in df.columns: agg_dict[c] = 'first'
                grouped = df.groupby(existing_group_cols, dropna=False).agg(agg_dict).reset_index()
            else:
                grouped = df.copy()

            if '몰재고_재고파일' in grouped.columns:
                grouped.rename(columns={'몰재고_재고파일': '몰재고'}, inplace=True)
            
            if '몰재고' not in grouped.columns: grouped['몰재고'] = 0
            if '원가' not in grouped.columns: grouped['원가'] = 0
            
            # DB 설정 덮어쓰기
            if not db_settings_df.empty and '모델그룹' in db_settings_df.columns:
                grouped = pd.merge(grouped, db_settings_df, on='모델그룹', how='left', suffixes=('', '_db'))
                for c in ['로켓등록', '민영 희망손익율', '쿠팡판매가', '프로모션 할인', '쿠팡 현재 판매가', '타판매처 최저가', '판매처 링크']:
                    if f"{c}_db" in grouped.columns:
                        grouped[c] = grouped[f"{c}_db"].combine_first(grouped.get(c, pd.Series(dtype=float)))
                        grouped.drop(columns=[f"{c}_db"], inplace=True)
            
            # 기본값 설정
            if '로켓등록' not in grouped.columns: grouped['로켓등록'] = '등록준비중'
            if '민영 희망손익율' not in grouped.columns: grouped['민영 희망손익율'] = 15.0
            if '쿠팡판매가' not in grouped.columns: grouped['쿠팡판매가'] = 25000
            if '프로모션 할인' not in grouped.columns: grouped['프로모션 할인'] = 0
            if '쿠팡 현재 판매가' not in grouped.columns: grouped['쿠팡 현재 판매가'] = grouped['쿠팡판매가']

            # Vectorized 연쇄 계산
            shipping = np.where(grouped.get('대분류', '') == '스키복', ski_ship, normal_ship)
            cost = pd.to_numeric(grouped['원가'], errors='coerce').fillna(0)
            raw_margin = pd.to_numeric(grouped['민영 희망손익율'], errors='coerce').fillna(0)
            desired_margin = np.where(raw_margin > 1, raw_margin / 100.0, raw_margin)
            c_price = pd.to_numeric(grouped['쿠팡판매가'], errors='coerce').fillna(0)
            promo_discount = pd.to_numeric(grouped['프로모션 할인'], errors='coerce').fillna(0)
            current_c_price = pd.to_numeric(grouped['쿠팡 현재 판매가'], errors='coerce').fillna(0)

            grouped['몰재고'] = pd.to_numeric(grouped['몰재고'], errors='coerce').fillna(0).astype(int)
            grouped['원가'] = cost.astype(int)
            grouped['쿠팡판매가'] = c_price.astype(int)
            grouped['프로모션 할인'] = promo_discount.astype(int)
            grouped['쿠팡 현재 판매가'] = current_c_price.astype(int)

            num = (desired_margin * shipping) - shipping - cost
            den = desired_margin - 1
            safe_den = np.where(den == 0, -1, den)
            raw_supply = num / safe_den
            minyoung_supply = np.where(den == 0, 0, np.ceil(raw_supply / 100.0) * 100)
            grouped['민영 공급가'] = minyoung_supply.astype(int)
            
            minyoung_profit = minyoung_supply - shipping - cost
            grouped['민영 손익'] = minyoung_profit.astype(int)
            grouped['민영 손익율'] = np.where(minyoung_supply != 0, (minyoung_profit / minyoung_supply) * 100, 0)
            
            grouped['쿠팡손익'] = (c_price - minyoung_supply).astype(int)
            grouped['쿠팡손익율'] = np.where(c_price != 0, (grouped['쿠팡손익'] / c_price) * 100, 0)
            
            promo_price = np.maximum(0, c_price - promo_discount)
            grouped['프로모션 손익'] = (promo_price - minyoung_supply).astype(int)
            grouped['프로모션 손익율'] = np.where(promo_price != 0, (grouped['프로모션 손익'] / promo_price) * 100, 0)
            
            grouped['쿠팡 현재 손익'] = (current_c_price - minyoung_supply).astype(int)
            grouped['쿠팡 현재 손익율'] = np.where(current_c_price != 0, (grouped['쿠팡 현재 손익'] / current_c_price) * 100, 0)
            
            return grouped

        # --- 메뉴 렌더링 ---
        if menu == "📊 등록 현황":
            st.subheader("📊 등록 현황")
            st.markdown("전체 상품의 기초 현황과 수수료 구조를 확인하는 화면입니다. 관리자는 표를 **더블클릭**하여 수정할 수 있습니다.")
            
            if is_admin:
                with st.expander("📤 등록 현황 일괄 업데이트 (Excel/CSV)"):
                    st.markdown("엑셀 파일을 업로드하여 여러 모델그룹의 상태를 한 번에 변경합니다. (필수 컬럼: **모델그룹, 로켓등록, 희망손익율, 쿠팡판매가**)")
                    status_file = st.file_uploader("상태 업데이트 파일 업로드", type=['xlsx', 'csv'], key='status_up')
                    if status_file and st.button("파일 적용 및 저장"):
                        try:
                            if status_file.name.endswith('.csv'):
                                up_df = pd.read_csv(status_file)
                            else:
                                up_df = pd.read_excel(status_file)
                            
                            if '희망손익율' in up_df.columns and '민영 희망손익율' not in up_df.columns:
                                up_df.rename(columns={'희망손익율': '민영 희망손익율'}, inplace=True)
                                
                            req_cols = ['모델그룹', '로켓등록', '민영 희망손익율', '쿠팡판매가']
                            missing = [c for c in req_cols if c not in up_df.columns]
                            if missing:
                                st.error(f"업로드된 파일에 다음 필수 컬럼이 누락되었습니다: {missing}")
                            else:
                                update_df = up_df[req_cols].copy()
                                update_df['민영 희망손익율'] = pd.to_numeric(update_df['민영 희망손익율'], errors='coerce')
                                update_df['쿠팡판매가'] = pd.to_numeric(update_df['쿠팡판매가'], errors='coerce')
                                save_settings(update_df)
                                st.success(f"{len(update_df)}개의 데이터가 성공적으로 일괄 업데이트되었습니다!")
                                st.rerun()
                        except Exception as e:
                            st.error(f"파일을 읽는 중 오류가 발생했습니다: {e}")

            grouped_df = get_grouped_and_calculated(filtered_df, db_settings)
            
            cols_1_1 = [
                '대분류', '계절', '중분류', '소분류', '성별', '모델그룹', '몰재고', '원가', '담당 BM', '로켓등록',
                '민영 희망손익율', '민영 공급가', '민영 손익', '민영 손익율', '쿠팡판매가', '쿠팡손익', '쿠팡손익율'
            ]
            for c in cols_1_1:
                if c not in grouped_df.columns: grouped_df[c] = ''
            df_1_1 = grouped_df[cols_1_1]
            
            # 일반 조회자(User)는 '등록완료' 항목만 노출
            if not is_admin:
                df_1_1 = df_1_1[df_1_1['로켓등록'] == '등록완료'].reset_index(drop=True)
            
            # 카테고리 컬럼 타입 지정 (로켓등록)
            df_1_1['로켓등록'] = pd.Categorical(df_1_1['로켓등록'], categories=["등록준비중", "가격검수중", "상품검수중", "등록완료", "반려"])
            
            save_btn_1 = False
            if is_admin:
                col_save, _ = st.columns([1, 5])
                with col_save:
                    save_btn_1 = st.button("💾 변경사항 DB 저장", key="save_1_1")
            else:
                st.info("조회 전용 권한이므로 데이터를 수정할 수 없습니다.")
            
            # column_config_1_1은 기존 그대로 유지
            column_config_1_1 = {
                "몰재고": st.column_config.NumberColumn("몰재고", step=1, format="%,d"),
                "원가": st.column_config.NumberColumn("원가", step=1, format="%,d"),
                "민영 공급가": st.column_config.NumberColumn("민영 공급가", step=1, format="%,d"),
                "민영 손익": st.column_config.NumberColumn("민영 손익", step=1, format="%,d"),
                "쿠팡판매가": st.column_config.NumberColumn("쿠팡판매가", step=1, format="%,d"),
                "쿠팡손익": st.column_config.NumberColumn("쿠팡손익", step=1, format="%,d"),
                "민영 희망손익율": st.column_config.NumberColumn("희망손익율", format="%.1f %%"),
                "민영 손익율": st.column_config.NumberColumn("민영 손익율", format="%.1f %%"),
                "쿠팡손익율": st.column_config.NumberColumn("쿠팡손익율", format="%.1f %%")
            }

            # 더블클릭 수정을 위해 쿠팡판매가를 다시 편집 가능 목록에 포함시킴
            editor_disabled_1_1 = [c for c in cols_1_1 if c not in ['로켓등록', '민영 희망손익율', '쿠팡판매가']] if is_admin else True

            # Pandas Styler를 활용한 특정 컬럼 배경색 지정 (다크/라이트 모드 모두 잘 어울리도록 rgba 반투명 사용)
            def fmt_num(x):
                try:
                    if pd.isna(x) or str(x).strip() == '': return ""
                    return "{:,.0f}".format(float(x))
                except:
                    return str(x)

            styled_df_1_1 = df_1_1.style.set_properties(
                subset=['민영 공급가'], **{'background-color': 'rgba(255, 182, 193, 0.2)'}  # 연한 핑크
            ).set_properties(
                subset=['쿠팡판매가'], **{'background-color': 'rgba(135, 206, 235, 0.2)'}  # 하늘색
            ).format(
                {col: fmt_num for col in ["몰재고", "원가", "민영 공급가", "민영 손익", "쿠팡판매가", "쿠팡손익"] if col in df_1_1.columns}
            )

            edited_df_1_1 = st.data_editor(
                styled_df_1_1,
                disabled=editor_disabled_1_1,
                key="editor_1_1",
                use_container_width=True,
                height=600,
                hide_index=True,
                column_config=column_config_1_1
            )
            
            if is_admin and save_btn_1:
                # 원본 grouped_df에 에디터의 변경사항을 덮어씌움
                update_cols = ['모델그룹', '로켓등록', '민영 희망손익율', '쿠팡판매가']
                save_settings(edited_df_1_1[update_cols])
                st.success("데이터베이스에 성공적으로 반영되었습니다!")
                st.rerun()
            
        elif menu == "🎁 프로모션 관리":
            st.subheader("🎁 프로모션 관리")
            st.markdown("프로모션 관련 설정 화면입니다. 변경 후 **[저장 버튼]**을 눌러 DB에 반영하세요.")
            
            grouped_df = get_grouped_and_calculated(filtered_df, db_settings)
            
            cols_1_2 = ['모델그룹', '로켓등록', '원가', '민영 공급가', '쿠팡판매가', '프로모션 할인', '프로모션 손익', '프로모션 손익율', '쿠팡 현재 판매가', '쿠팡 현재 손익', '쿠팡 현재 손익율', '타판매처 최저가', '판매처 링크']
            
            for c in cols_1_2:
                if c not in grouped_df.columns: grouped_df[c] = ''
            df_1_2 = grouped_df[cols_1_2]
            
            # '등록완료' 상태인 항목만 필터링
            df_1_2 = df_1_2[df_1_2['로켓등록'] == '등록완료'].reset_index(drop=True)
            
            save_btn_2 = False
            scrape_btn_2 = False
            if is_admin:
                col_save, col_scrape, _ = st.columns([1, 1, 4])
                with col_save:
                    save_btn_2 = st.button("💾 변경사항 DB 저장", key="save_1_2")
                with col_scrape:
                    scrape_btn_2 = st.button("🔍 최저가 자동 수집 실행", key="scrape_1_2")
            else:
                st.info("조회 전용 권한이므로 데이터를 수정할 수 없습니다.")
                
            if is_admin and scrape_btn_2:
                with st.spinner("네이버 쇼핑에서 최저가를 수집 중입니다... (시간이 걸릴 수 있습니다)"):
                    # 조건: 쿠팡 현재 판매가 < 쿠팡판매가
                    target_mask = (df_1_2['쿠팡 현재 판매가'] < df_1_2['쿠팡판매가']) & pd.notna(df_1_2['쿠팡 현재 판매가']) & pd.notna(df_1_2['쿠팡판매가'])
                    target_df = df_1_2[target_mask]
                    
                    updates = []
                    for idx, row in target_df.iterrows():
                        model_group = row['모델그룹']
                        price, link = scraper.get_lowest_price(model_group)
                        if price is not None:
                            updates.append({'모델그룹': model_group, '타판매처 최저가': price, '판매처 링크': link})
                    
                    if updates:
                        update_df = pd.DataFrame(updates)
                        if not db_settings.empty:
                            merged_update = pd.merge(db_settings, update_df, on='모델그룹', how='right', suffixes=('_old', ''))
                            for c in ['타판매처 최저가', '판매처 링크']:
                                if f"{c}_old" in merged_update.columns:
                                    merged_update.drop(columns=[f"{c}_old"], inplace=True)
                            save_settings(merged_update)
                        else:
                            save_settings(update_df)
                        st.success(f"총 {len(updates)}개 상품의 최저가 수집 및 저장이 완료되었습니다!")
                    else:
                        st.warning("조건을 만족하거나 수집에 성공한 상품이 없습니다.")
                    st.rerun()
            
            column_config_1_2 = {
                "원가": st.column_config.NumberColumn("원가", step=1, format="%,d"),
                "민영 공급가": st.column_config.NumberColumn("민영 공급가", step=1, format="%,d"),
                "쿠팡판매가": st.column_config.NumberColumn("쿠팡판매가", step=1, format="%,d"),
                "프로모션 할인": st.column_config.NumberColumn("프로모션 할인", step=1, format="%,d"),
                "프로모션 손익": st.column_config.NumberColumn("프로모션 손익", step=1, format="%,d"),
                "쿠팡 현재 판매가": st.column_config.NumberColumn("쿠팡 현재 판매가", step=1, format="%,d"),
                "쿠팡 현재 손익": st.column_config.NumberColumn("쿠팡 현재 손익", step=1, format="%,d"),
                "프로모션 손익율": st.column_config.NumberColumn("프로모션 손익율", format="%.1f %%"),
                "쿠팡 현재 손익율": st.column_config.NumberColumn("쿠팡 현재 손익율", format="%.1f %%"),
                "타판매처 최저가": st.column_config.NumberColumn("타판매처 최저가", step=1, format="%,d"),
                "판매처 링크": st.column_config.LinkColumn("판매처 링크", display_text="링크 이동")
            }

            editor_disabled_1_2 = [c for c in cols_1_2 if c not in ['프로모션 할인', '쿠팡 현재 판매가', '타판매처 최저가', '판매처 링크']] if is_admin else True

            # Pandas Styler를 활용한 특정 컬럼 배경색 지정
            def fmt_num_2(x):
                try:
                    if pd.isna(x) or str(x).strip() == '': return ""
                    return "{:,.0f}".format(float(x))
                except:
                    return str(x)

            styled_df_1_2 = df_1_2.style.set_properties(
                subset=['민영 공급가'], **{'background-color': 'rgba(255, 182, 193, 0.2)'}  # 연한 핑크
            ).set_properties(
                subset=['쿠팡판매가'], **{'background-color': 'rgba(135, 206, 235, 0.2)'}  # 하늘색
            ).set_properties(
                subset=['쿠팡 현재 판매가'], **{'background-color': 'rgba(144, 238, 144, 0.2)'}  # 연두색
            ).format(
                {col: fmt_num_2 for col in ["원가", "민영 공급가", "쿠팡판매가", "프로모션 할인", "프로모션 손익", "쿠팡 현재 판매가", "쿠팡 현재 손익", "타판매처 최저가"] if col in df_1_2.columns}
            )

            edited_df_1_2 = st.data_editor(
                styled_df_1_2,
                disabled=editor_disabled_1_2,
                key="editor_1_2",
                use_container_width=True,
                height=600,
                hide_index=True,
                column_config=column_config_1_2
            )
            
            if is_admin and save_btn_2:
                update_cols = ['모델그룹', '프로모션 할인', '쿠팡 현재 판매가', '타판매처 최저가', '판매처 링크']
                # 기존 db_settings와 머지해서 누락 방지
                if not db_settings.empty:
                    merged_update = pd.merge(db_settings, edited_df_1_2[update_cols], on='모델그룹', how='right', suffixes=('_old', ''))
                    for c in update_cols:
                        if c != '모델그룹':
                            if f"{c}_old" in merged_update.columns:
                                merged_update[c] = merged_update[c].combine_first(merged_update[f"{c}_old"])
                                merged_update.drop(columns=[f"{c}_old"], inplace=True)
                    save_settings(merged_update)
                else:
                    save_settings(edited_df_1_2[update_cols])
                st.success("프로모션 정보가 데이터베이스에 성공적으로 반영되었습니다!")
                st.rerun()
            
        elif menu == "🏷️ SKU 관리":
            st.subheader("🏷️ SKU 관리")
            st.markdown("단품(SKU) 단위 정보 관리 화면입니다. 담당BM을 수정하고 **[저장 버튼]**을 누르면 전체 시스템에 반영됩니다.")
            
            target_sku_cols = [
                'SKUID', '상품명', '매핑키', '모델명', '컬러명', 
                '한글컬러명', '사이즈', '쿠팡등록상품명', '바코드', '담당 BM', '발주담당자'
            ]
            
            sku_df = filtered_df.copy()
            for c in target_sku_cols:
                if c not in sku_df.columns: sku_df[c] = ''
            
            save_btn_3 = False
            if is_admin:
                col_save, _ = st.columns([1, 5])
                with col_save:
                    save_btn_3 = st.button("💾 변경사항 DB 저장", key="save_1_3")
            else:
                st.info("조회 전용 권한이므로 데이터를 수정할 수 없습니다.")
                
            editor_disabled_1_3 = [c for c in target_sku_cols if c not in ['담당 BM']] if is_admin else True

            edited_sku_df = st.data_editor(
                sku_df[target_sku_cols],
                disabled=editor_disabled_1_3,
                key="editor_1_3",
                use_container_width=True,
                height=600,
                hide_index=True
            )
            
            if is_admin and save_btn_3:
                save_sku_settings(edited_sku_df[['SKUID', '담당 BM']])
                st.success("SKU 정보가 데이터베이스에 성공적으로 반영되었습니다!")
                st.rerun()

# ==========================================
# 2-1. 출고리스트 파일 생성
# ==========================================
elif menu == "🚚 출고리스트 파일 생성":
    st.subheader("🚚 2 출고리스트 파일 생성")
    st.markdown("출고요청 파일을 업로드하고, 쿠팡 로켓 규격에 맞춘 엑셀 서식 파일을 생성하여 다운로드할 수 있습니다.")
    
    with st.expander("📁 출고요청 파일 업로드", expanded=True):
        dispatch_file = st.file_uploader("출고요청 (Excel)", type=['xlsx'])
    
    if dispatch_file:
        with open('출고요청.xlsx', "wb") as f:
            f.write(dispatch_file.getbuffer())
            
        if st.button("🚀 출고 리스트 엑셀 생성 및 다운로드"):
            with st.spinner("엑셀 파일에 완벽한 서식을 적용하여 생성 중입니다..."):
                today_str = datetime.now().strftime("%Y%m%d")
                output_filename = f'쿠팡로켓_출고리스트_{today_str}.xlsx'
                
                create_dispatch_excel(input_filename='출고요청.xlsx', output_filename=output_filename)
                
                if os.path.exists(output_filename):
                    with open(output_filename, 'rb') as f:
                        excel_data = f.read()
                    st.success(f"✅ 생성이 완료되었습니다! 파일명: {output_filename}")
                    st.download_button(
                        label="📥 다운로드 (Excel)",
                        data=excel_data,
                        file_name=output_filename,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
