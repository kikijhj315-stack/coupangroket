import math

def calculate_profits(category: str, cost: float, desired_margin_rate: float, coupang_price: float, supply_price_param: float = 0.0) -> dict:
    """
    웹 화면에서 입력받은 값을 바탕으로 배송비, 공급가, 손익 등을 연쇄적으로 계산하여 반환하는 함수입니다.

    :param category: 대분류 (예: '스키복')
    :param cost: 원가
    :param desired_margin_rate: 민영 희망손익율 (예: 10% -> 0.1)
    :param coupang_price: 쿠팡 판매가
    :param supply_price_param: 민영 공급가 역산 수식의 '공급가' 파라미터 (Excel 원본 수식 매칭용 변수)
    :return: 연쇄 계산 결과가 담긴 딕셔너리
    """
    
    # 1. 배송비 설정
    # 대분류 데이터가 '스키복'이면 배송비를 1250으로, 그 외 나머지는 500으로 설정
    if category == '스키복':
        shipping_fee = 1250
    else:
        shipping_fee = 500

    # 2. 민영 공급가 역산
    # 수식: ceiling((민영 희망손익율*배송비-배송비-원가)/(민영 희망손익율+공급가-(민영 희망손익율*0)-1), 100)
    try:
        numerator = (desired_margin_rate * shipping_fee) - shipping_fee - cost
        # -(민영 희망손익율*0) 부분은 항상 0이므로 실제 수식 계산에서는 0으로 반영
        denominator = desired_margin_rate + supply_price_param - (desired_margin_rate * 0) - 1
        
        raw_minyoung_supply_price = numerator / denominator
        
        # Excel의 ceiling(값, 100)과 동일하게 작동하도록 100단위 올림 처리
        minyoung_supply_price = math.ceil(raw_minyoung_supply_price / 100.0) * 100
    except ZeroDivisionError:
        # 분모가 0이 되어 발생하는 에러 방지
        minyoung_supply_price = 0

    # 3. 기타 손익 연쇄 계산
    # 민영 손익 = (민영 공급가 - 배송비 - 원가)
    minyoung_profit = minyoung_supply_price - shipping_fee - cost

    # 민영 손익율 = (민영 손익 / 민영 공급가)
    if minyoung_supply_price != 0:
        minyoung_profit_rate = minyoung_profit / minyoung_supply_price
    else:
        minyoung_profit_rate = 0.0

    # 쿠팡 손익 = (쿠팡 판매가 - 민영 공급가)
    coupang_profit = coupang_price - minyoung_supply_price

    # 쿠팡 손익율 = (쿠팡 손익 / 쿠팡 판매가)
    if coupang_price != 0:
        coupang_profit_rate = coupang_profit / coupang_price
    else:
        coupang_profit_rate = 0.0

    # 결과를 딕셔너리 형태로 반환 (API나 웹 백엔드에서 JSON으로 응답하기 좋음)
    return {
        '배송비': shipping_fee,
        '민영 공급가': minyoung_supply_price,
        '민영 손익': minyoung_profit,
        '민영 손익율': minyoung_profit_rate,
        '쿠팡 손익': coupang_profit,
        '쿠팡 손익율': coupang_profit_rate
    }

# [테스트 블록] 이 파일을 직접 실행했을 때 계산 결과를 확인할 수 있습니다.
if __name__ == "__main__":
    # 테스트용 가상의 입력값 세팅
    test_category = '스키복'
    test_cost = 10000             # 원가 10,000원
    test_margin_rate = 0.15       # 민영 희망손익율 15% (소수로 입력)
    test_coupang_price = 25000    # 쿠팡 판매가 25,000원
    test_supply_param = 0.0       # 수식 내 '공급가' 파라미터 (Excel 수식에 있는 변수 대응)

    print("입력값 설정:")
    print(f"- 대분류: {test_category}")
    print(f"- 원가: {test_cost:,}원")
    print(f"- 민영 희망손익율: {test_margin_rate*100}%")
    print(f"- 쿠팡 판매가: {test_coupang_price:,}원\n")

    result = calculate_profits(
        category=test_category,
        cost=test_cost,
        desired_margin_rate=test_margin_rate,
        coupang_price=test_coupang_price,
        supply_price_param=test_supply_param
    )

    print("=== 2단계 마진/손익 연쇄 계산 결과 ===")
    for key, value in result.items():
        if '율' in key:
            print(f"{key}: {value*100:.2f}%")
        else:
            print(f"{key}: {value:,.0f}원")
