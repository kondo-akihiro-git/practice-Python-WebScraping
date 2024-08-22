import requests
from bs4 import BeautifulSoup
import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from urllib.parse import urljoin
import warnings
from requests.packages.urllib3.exceptions import InsecureRequestWarning

# SSL証明書の警告を抑制
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
def find_phone_numbers(text):
    phone_pattern = re.compile(r'\(?\d{2,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,4}', re.UNICODE)
    phones = set(phone_pattern.findall(text))

    filtered_phones = []
    for phone in phones:
        if "fax" not in phone.lower():  # FAXではない電話番号をフィルタリング
            # ピリオドを含む電話番号を除外
            if '.' not in phone:
                digits = re.sub(r'\D', '', phone)
                if len(digits) >= 10:  # 電話番号の最小桁数を設定（例: 日本の電話番号は通常10桁以上）
                    filtered_phones.append(phone)

    return filtered_phones

# メールアドレスを探す関数
def find_email_addresses(text):
    # 全角の「＠」を半角の「@」に変換
    text = text.replace('＠', '@')
    
    email_pattern = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', re.UNICODE)
    emails = set(email_pattern.findall(text))
    return list(emails)

# ページ内テキストとJavaScript内テキストを取得する関数
def get_page_text(url):
    try:
        response = requests.get(url, verify=False)
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'html.parser')
        scripts = soup.find_all('script')
        script_text = " ".join(script.string for script in scripts if script.string)

        return soup.get_text(), script_text, soup
    except Exception as e:
        print(f"Failed to retrieve text from {url}: {e}")
        return "", "", None

# コンタクトフォームのリンクを探す関数
def find_contact_form_links(url, soup):
    contact_links = set()
    links = soup.find_all('a', href=True)
    for link in links:
        href = link['href']
        full_url = urljoin(url, href) if not href.startswith('http') else href

        if any(keyword in href.lower() for keyword in ['/contact', '/問い合わせ', 'contact', '問い合わせ']):
            contact_links.add(full_url)

    # メインURLに「問い合わせ」などの文言が含まれている場合かつフォームが存在する場合にURLを追加
    if any(keyword in soup.get_text().lower() for keyword in ['問い合わせ', 'contact']):
        forms = soup.find_all('form')
        if forms:
            contact_links.add(url)
    
    # 入力要素（input）をチェック
    inputs = soup.find_all('input')
    if any(input.get('type') in ['text', 'email', 'tel'] for input in inputs):
        contact_links.add(url)

    return list(contact_links)

# 全てのページをクロールする関数
def crawl_all_pages(url, visited_urls):
    to_visit = [url]
    all_links = set()
    
    while to_visit:
        current_url = to_visit.pop()
        if current_url in visited_urls:
            continue
        
        visited_urls.add(current_url)
        
        page_text, script_text, soup = get_page_text(current_url)
        
        # リンクを抽出して追加
        links = soup.find_all('a', href=True)
        for link in links:
            href = link['href']
            full_url = urljoin(url, href) if not href.startswith('http') else href
            if full_url not in visited_urls:
                to_visit.append(full_url)
                all_links.add(full_url)
        
        # 電話番号やメールアドレスの抽出
        phone_numbers = find_phone_numbers(page_text) + find_phone_numbers(script_text)
        emails = find_email_addresses(page_text) + find_email_addresses(script_text)
        contact_forms = find_contact_form_links(current_url, soup)
        
        # スプレッドシートに書き込み
        new_sheet.append_row([current_url, ', '.join(set(phone_numbers)) if phone_numbers else 'ー', emails[0] if emails else (contact_forms[0] if contact_forms else 'ー')])

        # 取得した情報をプリント出力
        print(f"URL: {current_url}")
        print(f"Phone Numbers: {', '.join(set(phone_numbers)) if phone_numbers else 'ー'}")
        print(f"Emails/Contact Forms: {emails[0] if emails else (contact_forms[0] if contact_forms else 'ー')}")
        print("-" * 40)
    
    return all_links

# スプレッドシートに結果を返す
visited_urls = set()
for main_url in url_list:
    crawl_all_pages(main_url, visited_urls)