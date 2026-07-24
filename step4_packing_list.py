import streamlit as st
import pandas as pd
import io
import json
import traceback
import google.generativeai as genai
from PIL import Image

def init_gemini():
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=api_key)
        # 1.5 Flash 모델이 가볍고 빠르며 비전(이미지) 처리에 우수함
        return genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:
        return None

def extract_info_from_image(model, image_bytes):
    try:
        img = Image.open(io.BytesIO(image_bytes))
        prompt = """
        이 사진에는 택배 박스와 하얀색 라벨 스티커가 있습니다.
        1. 박스 위에 매직이나 펜으로 크게 쓰여진 '박스번호'(숫자)를 찾아주세요.
        2. 하얀색 라벨 스티커에 인쇄된 '모델명'(혹은 출고모델명, 단품명)과 '수량'을 찾아주세요. 라벨이 여러 개라면 모두 찾아주세요.
        
        반드시 아래의 순수 JSON 형식으로만 답변해주세요. 다른 설명은 절대 추가하지 마세요.
        [
          {
            "box_no": "매직으로 쓰인 박스번호 (예: 1, 2, 3... 없으면 빈문자열)",
            "model_name": "라벨에 적힌 모델명 및 단품명 전체 텍스트",
            "qty": 수량 (숫자만, 예: 10)
          }
        ]
        """
        response = model.generate_content([prompt, img])
        text = response.text.strip()
        
        # Markdown JSON block 제거 처리
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
            
        data = json.loads(text.strip())
        return data
    except Exception as e:
        st.error(f"이미지 판독 중 오류 발생: {e}")
        return []

def match_and_generate_packing_list(df_req, ocr_results):
    # df_req: 출고요청파일 데이터프레임
    # 필요한 열 확인
    req_cols = ['발주번호', '배송지', '단품명', '상품바코드', '출고모델명', '출고요청']
    for c in req_cols:
        if c not in df_req.columns:
            st.error(f"출고요청 엑셀 파일에 '{c}' 컬럼이 없습니다.")
            return None
            
    # 매칭을 위해 복사본 생성 및 박스번호 컬럼 추가
    df = df_req.copy()
    df['박스번호'] = ''
    df['출고요청'] = pd.to_numeric(df['출고요청'], errors='coerce').fillna(0).astype(int)
    
    # OCR 결과 매칭 (매우 단순화된 휴리스틱 매칭)
    # OCR에서 추출된 model_name 텍스트 안에 엑셀의 '출고모델명'이나 '단품명'이 포함되어 있고 수량이 일치하면 매칭
    matched_indices = set()
    
    for item in ocr_results:
        box_no = item.get('box_no', '')
        model_name = str(item.get('model_name', '')).strip().lower()
        qty = item.get('qty', 0)
        
        try:
            qty = int(qty)
        except:
            continue
            
        if not box_no or not model_name:
            continue
            
        # 매칭 후보 찾기
        for idx, row in df.iterrows():
            if idx in matched_indices:
                continue
                
            excel_model = str(row['출고모델명']).strip().lower()
            excel_item = str(row['단품명']).strip().lower()
            excel_qty = row['출고요청']
            
            # 수량이 일치하고, 라벨 텍스트에 출고모델명 또는 단품명이 포함되어 있는 경우
            if excel_qty == qty and (excel_model in model_name or excel_item in model_name):
                df.at[idx, '박스번호'] = box_no
                matched_indices.add(idx)
                break # 이 라벨은 매칭 완료
                
    # 최종 출력 양식 생성
    # A열 발주번호, B열 출고모델명, C열 단품명, D열 수량, E열 박스번호, F열 팔렛트번호, G열 배송지, H열 상품바코드, I열 매핑키
    
    out_df = pd.DataFrame()
    out_df['발주번호'] = df['발주번호']
    out_df['출고모델명'] = df['출고모델명']
    out_df['단품명'] = df['단품명']
    out_df['수량'] = df['출고요청']
    
    # 숫자형 정렬을 위해 박스번호를 숫자로 변환 시도 (문자열인 경우 대비)
    out_df['박스번호_raw'] = df['박스번호'] 
    out_df['박스번호'] = pd.to_numeric(df['박스번호'], errors='coerce').fillna(999999).astype(int)
    out_df.loc[out_df['박스번호'] == 999999, '박스번호'] = df['박스번호'] # 숫자로 안바뀌면 원래 문자열 유지
    
    out_df['팔렛트번호'] = ''
    out_df['배송지'] = df['배송지']
    out_df['상품바코드'] = df['상품바코드']
    
    # 정렬: 1순위 박스번호, 2순위 배송지
    # 박스번호가 혼합 타입(숫자+문자)일 수 있으므로 문자열로 강제 변환하여 정렬
    out_df['sort_box'] = out_df['박스번호'].astype(str).str.zfill(10)
    out_df = out_df.sort_values(by=['sort_box', '배송지']).drop(columns=['sort_box'])
    
    # 박스번호_raw로 복원 (매핑 안된 빈문자열 유지)
    out_df['박스번호'] = out_df['박스번호_raw']
    out_df = out_df.drop(columns=['박스번호_raw'])
    out_df = out_df.reset_index(drop=True)
    
    return out_df

def generate_excel_bytes(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='패킹리스트')
        worksheet = writer.sheets['패킹리스트']
        
        # I열 수식 삽입 (=A2&"_"&H2) - 엑셀은 1-based index이고 헤더가 1행이므로 데이터는 2행부터
        # 헤더 삽입
        worksheet.cell(row=1, column=9, value="매핑키")
        for idx in range(len(df)):
            row_num = idx + 2
            # I열 (column=9)
            worksheet.cell(row=row_num, column=9, value=f'=A{row_num}&"_"&H{row_num}')
            
        # 열 너비 조정
        for col_letter, width in zip(['A','B','C','D','E','F','G','H','I'], [15, 20, 15, 8, 10, 15, 20, 15, 25]):
            worksheet.column_dimensions[col_letter].width = width
            
    return output.getvalue()

def render_packing_list_page():
    st.subheader("📦 패킹리스트 파일 생성 (AI 자동인식)")
    st.markdown("출고요청파일 엑셀과 박스 패킹 사진을 업로드하면, AI 비전이 사진의 **박스번호**와 **라벨(모델명/수량)**을 자동으로 판독하여 엑셀과 매칭해 줍니다!")
    
    gemini_model = init_gemini()
    if not gemini_model:
        st.error("⚠️ 구글 Gemini API 키가 설정되지 않았거나 올바르지 않습니다. 스트림릿 Secrets에 `GEMINI_API_KEY`를 설정해주세요.")
        return

    req_file = st.file_uploader("1. 출고요청파일 업로드 (Excel)", type=['xlsx'])
    img_files = st.file_uploader("2. 박스 패킹 사진 다중 업로드 (JPG/PNG)", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True)
    
    if req_file and img_files:
        if st.button("🚀 패킹리스트 AI 생성 시작"):
            with st.spinner("엑셀 데이터를 분석하고 AI가 사진들을 판독 중입니다... (사진 수에 따라 시간이 걸릴 수 있습니다)"):
                try:
                    df_req = pd.read_excel(req_file)
                    
                    all_ocr_results = []
                    progress_bar = st.progress(0)
                    total_imgs = len(img_files)
                    
                    for i, img_file in enumerate(img_files):
                        img_bytes = img_file.read()
                        res = extract_info_from_image(gemini_model, img_bytes)
                        if res:
                            all_ocr_results.extend(res)
                        progress_bar.progress((i + 1) / total_imgs)
                        
                    st.success(f"총 {total_imgs}장의 사진에서 {len(all_ocr_results)}개의 라벨 정보를 판독했습니다!")
                    with st.expander("AI 판독 결과 (디버깅용)"):
                        st.json(all_ocr_results)
                        
                    final_df = match_and_generate_packing_list(df_req, all_ocr_results)
                    if final_df is not None:
                        excel_data = generate_excel_bytes(final_df)
                        
                        st.success("패킹리스트 생성이 완료되었습니다! 아래 버튼을 눌러 다운로드하세요.")
                        st.download_button(
                            label="📥 패킹리스트_완성.xlsx 다운로드",
                            data=excel_data,
                            file_name="패킹리스트_완성.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                        
                        st.markdown("### 📊 최종 결과 미리보기")
                        st.dataframe(final_df)
                        
                except Exception as e:
                    st.error(f"처리 중 오류가 발생했습니다: {e}")
                    st.error(traceback.format_exc())
