import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin

# 電話番号を探す関数
def find_phone_numbers(url):
    try:
        # Webページを取得
        response = requests.get(url)
        response.encoding = response.apparent_encoding

        # ページの内容を解析するためにBeautifulSoupを使用
        soup = BeautifulSoup(response.text, 'html.parser')

        # 半角に変換する関数
        def zenkaku_to_hankaku(text):
            hankaku = text.translate(str.maketrans(
                '０１２３４５６７８９ー－',
                '0123456789--'
            ))
            return hankaku

        # 電話番号のパターンを定義（全角・半角に対応、国内形式に対応）
        phone_pattern = re.compile(r'(\(?\d{2,4}\)?[-.\s]?\d{2,4}[-.\s]?\d{2,4}[-.\s]?\d{2,4}|\d{3,4}[-.\s]?\d{2,4}[-.\s]?\d{4})')

        # ページ内のすべてのテキストを取得して、電話番号を検索
        text = zenkaku_to_hankaku(soup.get_text())
        phones = phone_pattern.findall(text)

        # 電話番号のフォーマットを整える
        formatted_phones = set()
        for phone in phones:
            phone = re.sub(r'[^\d]', '', phone)  # 非数字を削除
            if len(phone) >= 10:  # 10桁以上の数字を有効とする
                formatted_phone = f"{phone[:4]}-{phone[4:7]}-{phone[7:]}"  # 標準的なフォーマットに変換
                formatted_phones.add(formatted_phone)

        return list(formatted_phones)
    except Exception as e:
        print(f"Failed to retrieve {url}: {e}")
        return []

# 調べたいURLリスト
urls = [

]

# 各URLから電話番号を探す
for main_url in urls:
    phone_numbers = find_phone_numbers(main_url)
    print(f"Phone numbers found on main page: {phone_numbers}")

    # メインページのリンクを取得
    try:
        response = requests.get(main_url)
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'html.parser')

        # ページ内のすべてのリンクを取得
        links = soup.find_all('a', href=True)

        # 各リンク先ページから電話番号を探す
        for link in links:
            href = link['href']
            full_url = urljoin(main_url, href)  # 絶対URLを作成

            phone_numbers = find_phone_numbers(full_url)
            if phone_numbers:
                print(f"Phone numbers found on {full_url}: {phone_numbers}")

    except Exception as e:
        print(f"Failed to process links from {main_url}: {e}")
