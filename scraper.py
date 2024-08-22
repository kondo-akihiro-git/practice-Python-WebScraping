import requests
from bs4 import BeautifulSoup
import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from urllib.parse import urljoin
import warnings
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from datetime import datetime

# SSL証明書の検証を無効にしないために警告を抑制
warnings.filterwarnings("ignore", category=InsecureRequestWarning)

# Google Sheets API認証情報の設定
scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
client = gspread.authorize(creds)

# 現在の日付と時刻を取得してシート名に追加
current_time = datetime.now().strftime('%Y%m%d_%H%M%S')
sheet_title = f"Extracted Data_{current_time}"

# 新しいシートを作成
spreadsheet = client.open_by_url("")
new_sheet = spreadsheet.add_worksheet(title=sheet_title, rows="100", cols="10")

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
                if len(digits) >= 10 and '.' not in phone:  # 電話番号の最小桁数を設定し、ピリオドを含むものは除外
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

        def get_page_text(url):
            try:
                response = requests.get(url, verify=False)
                response.encoding = response.apparent_encoding
                soup = BeautifulSoup(response.text, 'html.parser')
                scripts = soup.find_all('script')
                script_text = " ".join(script.string for script in scripts if script.string)
                return soup.get_text(), script_text
            except Exception as e:
                print(f"Failed to retrieve text from {url}: {e}")
                return "", ""

        # メールアドレスを含むすべてのテキストを取得
        page_text, script_text = get_page_text(url)
        
        # HTML内とJavaScript内のメールアドレスを抽出する正規表現
        email_pattern = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', re.UNICODE)
        emails = set(email_pattern.findall(page_text + ' ' + script_text))

        # @ が含まれている全てのメールアドレスを抽出
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

            if '/contact' in href.lower() or 'contact' in href.lower():
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
    email_output = ', '.join(emails) if emails else 'ー'
    
    # メールアドレスが見つかった場合はコンタクトフォームリンクは無視する
    if emails:
        contact_form_output = 'ー'
    else:
        contact_form_output = contact_forms[0] if contact_forms else 'ー'

    # 新しいシートにデータを挿入
    new_sheet.update_cell(i, 1, main_url)  # A列にメインのURLを挿入
    new_sheet.update_cell(i, 2, phone_output)  # B列に電話番号を挿入
    new_sheet.update_cell(i, 3, email_output if email_output != 'ー' else contact_form_output)  # C列にメールアドレスまたはコンタクトフォームリンクを挿入

    # メインページのリンクを取得してさらに探索
    try:
        response = requests.get(main_url, verify=False)
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'html.parser')
        links = soup.find_all('a', href=True)

        found_phone = False
        found_email_or_form = False

        for link in links:
            href = link['href']
            full_url = urljoin(main_url, href)

            if not found_phone:
                phone_numbers = find_phone_numbers(full_url)
                if phone_numbers:
                    print(f"Found phone numbers at {full_url}: {phone_numbers}")
                    new_sheet.update_cell(i, 2, ', '.join(phone_numbers))
                    found_phone = True

            if not found_email_or_form:
                emails = find_email_addresses(full_url)
                contact_forms = find_contact_form_links(full_url)
                if emails:
                    print(f"Found email addresses at {full_url}: {emails}")
                    new_sheet.update_cell(i, 3, ', '.join(emails))
                    contact_forms = []  # メールアドレスが見つかればコンタクトフォームリンクは無視
                    found_email_or_form = True
                elif contact_forms:
                    print(f"Found contact forms at {full_url}: {contact_forms}")
                    new_sheet.update_cell(i, 3, contact_forms[0])
                    found_email_or_form = True

            # どちらも見つかった場合は次のURLへ
            if found_phone and found_email_or_form:
                break
    except Exception as e:
        print(f"Failed to process links from {main_url}: {e}")
