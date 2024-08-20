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

# スプレッドシートのURLまたはシートIDを指定
sheet = client.open_by_url("").sheet1

# スプレッドシートからURLリストを取得
url_list = sheet.col_values(1)  # 1列目からURLを取得

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
        postal_code_pattern = re.compile(r'\b\d{3}-\d{4}\b', re.UNICODE)  # 郵便番号の正規表現

        text = zenkaku_to_hankaku(soup.get_text())
        phones = set(phone_pattern.findall(text))
        postal_codes = set(postal_code_pattern.findall(text))  # 郵便番号を抽出

        print(f"Found phones: {phones}")  # デバッグ用出力

        filtered_phones = []
        for phone in phones:
            # 電話番号と郵便番号の区別をする
            digits = re.sub(r'\D', '', phone)
            if len(digits) >= 10:  # 電話番号の最小桁数を設定（例: 日本の電話番号は通常10桁以上）
                if not re.search(r'\d{3}-\d{4}', phone) or phone not in postal_codes:
                    filtered_phones.append(phone)
        
        print(f"Filtered phones: {filtered_phones}")  # デバッグ用出力

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
            link_text = link.get_text(strip=True).lower()
            full_url = urljoin(url, href)

            if 'contact' in link_text or 'form' in link_text or 'contact' in href.lower() or 'form' in href.lower():
                contact_links.add(full_url)
        
        return list(contact_links)
    except Exception as e:
        print(f"Failed to retrieve contact form links from {url}: {e}")
        return []

# スプレッドシートに結果を返す
for i, main_url in enumerate(url_list, start=2):
    phone_numbers = find_phone_numbers(main_url)
    emails = find_email_addresses(main_url)
    contact_forms = find_contact_form_links(main_url)

    phone_output = ', '.join(phone_numbers) if phone_numbers else 'ー'
    email_output = emails[0] if emails else 'ー'
    
    # メールアドレスが見つかった場合はコンタクトフォームリンクは無視する
    if emails:
        contact_form_output = 'ー'
    else:
        contact_form_output = contact_forms[0] if contact_forms else 'ー'

    # メインのURLをD列に設定
    sheet.update_cell(i, 4, main_url)  # D列にメインのURLを挿入
    sheet.update_cell(i, 5, phone_output)  # E列に電話番号を挿入
    sheet.update_cell(i, 6, email_output)  # F列にメールアドレスを挿入（またはコンタクトフォームリンク）
    sheet.update_cell(i, 7, contact_form_output)  # G列にコンタクトフォームリンクを挿入

    # メインページのリンクを取得してさらに探索
    try:
        response = requests.get(main_url, verify=False)
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'html.parser')
        links = soup.find_all('a', href=True)

        # メインページのリンクの探索
        found_phone = False
        found_email_or_form = False

        for link in links:
            href = link['href']
            full_url = urljoin(main_url, href)

            if not found_phone:
                phone_numbers = find_phone_numbers(full_url)
                if phone_numbers:
                    print(f"Found phone numbers at {full_url}: {phone_numbers}")
                    sheet.update_cell(i, 5, ', '.join(phone_numbers))
                    found_phone = True

            if not found_email_or_form:
                emails = find_email_addresses(full_url)
                contact_forms = find_contact_form_links(full_url)
                if emails:
                    print(f"Found email addresses at {full_url}: {emails}")
                    sheet.update_cell(i, 6, emails[0])
                    contact_forms = []  # メールアドレスが見つかればコンタクトフォームリンクは無視
                    found_email_or_form = True
                elif contact_forms:
                    print(f"Found contact forms at {full_url}: {contact_forms}")
                    sheet.update_cell(i, 7, contact_forms[0])
                    found_email_or_form = True

            # どちらも見つかった場合は次のURLへ
            if found_phone and found_email_or_form:
                break
    except Exception as e:
        print(f"Failed to process links from {main_url}: {e}")
