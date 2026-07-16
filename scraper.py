import requests
from bs4 import BeautifulSoup
import urllib.parse
import re
import time

def get_lowest_price(model_name):
    """
    네이버 쇼핑 통합검색에서 모델명을 검색하여 
    첫 번째(상단) 상품의 최저가와 링크를 추출합니다.
    """
    if not model_name or str(model_name).strip() == '':
        return None, None
        
    query = urllib.parse.quote(str(model_name))
    url = f"https://search.shopping.naver.com/search/all?query={query}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    
    try:
        # 네이버 봇 차단을 방지하기 위해 잠시 대기
        time.sleep(1)
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        price_tags = soup.find_all('span', class_=re.compile('price_num'))
        prices = []
        for tag in price_tags:
            text = tag.text if hasattr(tag, 'text') else str(tag)
            clean_text = text.replace(',', '').replace('원', '').strip()
            if clean_text.isdigit():
                prices.append(int(clean_text))
                
        link = url  # 기본값은 검색 결과 페이지
        product_links = soup.find_all('a', class_=re.compile('product_link'))
        if product_links:
            href = product_links[0].get('href')
            if href and href.startswith('http'):
                link = href
                
        if prices:
            valid_prices = [p for p in prices if p > 1000]
            if valid_prices:
                return min(valid_prices), link
            return min(prices), link
            
    except Exception as e:
        print(f"[Scraper Error] {model_name}: {e}")
        pass
        
    return None, url
