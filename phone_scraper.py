import requests
from bs4 import BeautifulSoup
import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from urllib.parse import urljoin
import warnings
from requests.packages.urllib3.exceptions import InsecureRequestWarning

# SSL証明書の検証を無効にしないために警告を抑制
warnings.filterwarnings("ignore", category=InsecureRequestWarning)

# Google Sheets API認証情報の設定
scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
client = gspread.authorize(creds)

# 新しいシートを作成
spreadsheet = client.open_by_url("")
new_sheet = spreadsheet.add_worksheet(title="Extracted Data", rows="100", cols="10")

# スプレッドシートからURLリストを取得
url_list = spreadsheet.sheet1.col_values(1)  # 1列目からURLを取得

# 電話番号を探す関数
def find_phone_numbers(url):
    try:
        response = requests.get(url, verify=False)
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'html.parser')

        def zenkaku_to_hankaku(text):
            hankaku = text.translate(str.maketrans('０１２３４５６７８９ー－', '0123456789--'))
            return hankaku

        phone_pattern = re.compile(r'\(?\d{2,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,4}', re.UNICODE)
        text = zenkaku_to_hankaku(soup.get_text())
        phones = set(phone_pattern.findall(text))

        filtered_phones = []
        for phone in phones:
            if "fax" not in phone.lower():  # FAXではない電話番号をフィルタリング
                digits = re.sub(r'\D', '', phone)
                if len(digits) >= 10:  # 電話番号の最小桁数を設定（例: 日本の電話番号は通常10桁以上）
                    filtered_phones.append(phone)

        return filtered_phones
    except Exception as e:
        print(f"Failed to retrieve phone numbers from {url}: {e}")
        return []

# メールアドレスを探す関数
def find_email_addresses(url):
    try:
        response = requests.get(url, verify=False)
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'html.parser')

        email_pattern = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', re.UNICODE)
        emails = set(email_pattern.findall(soup.get_text()))

        return list(emails)
    except Exception as e:
        print(f"Failed to retrieve email addresses from {url}: {e}")
        return []

# コンタクトフォームのリンクを探す関数
def find_contact_form_links(url):
    try:
        response = requests.get(url, verify=False)
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'html.parser')

        contact_links = set()
        links = soup.find_all('a', href=True)
        for link in links:
            href = link['href']
            full_url = urljoin(url, href)

            if '/contact' in href.lower() or 'contact' in href.lower() or '特定商取引法' in link.get_text():
                contact_links.add(full_url)
        
        return list(contact_links)
    except Exception as e:
        print(f"Failed to retrieve contact form links from {url}: {e}")
        return []

# 「特定商品法に基づく表記」を探す関数
def find_tokushoho_links(url):
    try:
        response = requests.get(url, verify=False)
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'html.parser')

        tokushoho_links = set()
        links = soup.find_all('a', href=True)
        for link in links:
            href = link['href']
            full_url = urljoin(url, href)

            if '特定商取引法' in link.get_text():
                tokushoho_links.add(full_url)
        
        return list(tokushoho_links)
    except Exception as e:
        print(f"Failed to retrieve 特定商取引法 links from {url}: {e}")
        return []

# スプレッドシートに結果を返す
for i, main_url in enumerate(url_list, start=2):
    phone_numbers = find_phone_numbers(main_url)
    emails = find_email_addresses(main_url)
    contact_forms = find_contact_form_links(main_url)

    # 特定商取引法ページがあるかを確認
    tokushoho_links = find_tokushoho_links(main_url)
    if tokushoho_links:
        tokushoho_url = tokushoho_links[0]
        # 特定商取引法ページで電話番号やメールアドレスを探す
        phone_numbers += find_phone_numbers(tokushoho_url)
        emails += find_email_addresses(tokushoho_url)

    # ABC列にそれぞれURL、電話番号、メールアドレスまたはコンタクトフォームリンクを出力
    new_sheet.update_cell(i, 1, main_url)  # A列にメインのURLを挿入
    new_sheet.update_cell(i, 2, ', '.join(set(phone_numbers)) if phone_numbers else 'ー')  # B列に電話番号を挿入
    new_sheet.update_cell(i, 3, emails[0] if emails else (contact_forms[0] if contact_forms else 'ー'))  # C列にメールアドレスまたはコンタクトフォームリンクを挿入
