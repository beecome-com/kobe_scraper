#!/usr/bin/env python3
# bid_scraper_selenium.py
# 使い方: python bid_scraper_selenium.py 2024-03-01 2024-03-15

import sys
import os
import csv
import datetime as dt
from typing import List, Dict
import re
import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException


SEARCH_URL = "https://nyusatsukekka.city.kobe.lg.jp/searchk.php"
OUTPUT_CSV = "kobe_bids.csv"
FIELDNAMES = [
    "工事名",
    "開札日時",
    "入札方式",
    "参加数",
    "決定金額",
    "予定価格",
    "最低制限価格",
    "契約相手",
    "工事種別",
    "制限率"
]

def fetch_kobe_bids_selenium(start: dt.date, end: dt.date) -> List[Dict]:
    service = Service(executable_path=r"C:\Tools\chromedriver.exe")
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--blink-settings=imagesEnabled=false")

    driver = webdriver.Chrome(service=service, options=options)
    wait = WebDriverWait(driver, 5)

    # フォームページを開く
    driver.get(SEARCH_URL)
    wait.until(EC.presence_of_element_located((By.NAME, "fromyy")))

    # 日付をプルダウンで選択
    Select(driver.find_element(By.NAME, "fromyy")).select_by_value(str(start.year))
    Select(driver.find_element(By.NAME, "frommm")).select_by_value(f"{start.month:02}")
    Select(driver.find_element(By.NAME, "fromdd")).select_by_value(f"{start.day:02}")
    Select(driver.find_element(By.NAME, "toyy")).select_by_value(str(end.year))
    Select(driver.find_element(By.NAME, "tomm")).select_by_value(f"{end.month:02}")
    Select(driver.find_element(By.NAME, "todd")).select_by_value(f"{end.day:02}")

    # 検索実行
    print("[INFO] 検索実行中...")
    try:
        driver.find_element(By.CSS_SELECTOR, "input[value='検索実行']").click()
    except:
        driver.find_element(By.CSS_SELECTOR, "input[type=submit]").click()

    # ——— 検索結果件数表示を待って 0 件判定 ———
    try:
        count_elem = wait.until(EC.presence_of_element_located((By.ID, "searchkensu")))
        count_text = count_elem.text  # 例: "検索結果：0 - 0 / 0 件"
        if "0 件" in count_text:
            print("[INFO] 検索結果が0件です")
            driver.quit()
            return []
    except TimeoutException:
        # 件数表示要素が無ければ次へ（テーブルヘッダーで判定）
        pass

    # ——— テーブルヘッダーでデータの有無をチェック ———
    try:
        header = wait.until(EC.presence_of_element_located(
            (By.XPATH, "//th[contains(normalize-space(.),'開札年月日')]")
        ))
    except TimeoutException:
        print("[INFO] テーブルヘッダーが見つかりませんでした（検索結果0件）")
        driver.quit()
        return []
    

    # テーブル取得
    print("[INFO] 検索結果を取得中...")
    try:
        header = wait.until(EC.presence_of_element_located((By.XPATH, "//th[contains(text(),'開札年月日')]")))
    except:
        header = wait.until(EC.presence_of_element_located((By.XPATH, "//td[contains(text(),'開札年月日')]")))
    table = header.find_element(By.XPATH, "./ancestor::table")

    # フェーズ1: 一覧から URL リストを収集
    url_list: List[Dict[str, str]] = []
    for tr in table.find_elements(By.TAG_NAME, "tr")[1:]:
        cols = tr.find_elements(By.TAG_NAME, "td")
        if len(cols) < 8:
            continue
        try:
            result_url = cols[6].find_element(By.TAG_NAME, "a").get_attribute("href")
        except:
            result_url = ""
        try:
            contract_url = cols[7].find_element(By.TAG_NAME, "a").get_attribute("href")
        except:
            contract_url = ""
        # どちらかのURLが空ならスキップ
        if not result_url or not contract_url:
            continue
        url_list.append({
            "result_url": result_url,
            "contract_url": contract_url
        })

    # フェーズ2: 詳細ページを巡回して情報取得
    bids: List[Dict] = []
    for urls in url_list:
        bid = {key: "" for key in FIELDNAMES}

        # 開札結果ページから
        if urls["result_url"]:
            driver.get(urls["result_url"])
            for key, xpath in [
                ("開札日時",       "//dt[normalize-space(text())='開札日時']/following-sibling::dd[1]"),
                ("入札方式",       "//dt[normalize-space(text())='入札方式']/following-sibling::dd[1]"),
                ("参加数",         "//dt[normalize-space(text())='指名・参加数']/following-sibling::dd[1]"),
                ("決定金額",       "//dt[normalize-space(text())='決定金額(税抜)']/following-sibling::dd[1]"),
                ("予定価格",       "//dt[normalize-space(text())='予定価格(税抜)']/following-sibling::dd[1]"),
                ("最低制限価格",   "//dt[normalize-space(text())='最低制限価格または調査基準価格(税抜)']/following-sibling::dd[1]"),
                ("契約相手",       "//dt[normalize-space(text())='契約の相手方']/following-sibling::dd[1]")
            ]:
                try:
                    value = driver.find_element(By.XPATH, xpath).text.strip()

                    # 入札日時を変換して別キーに保存
                    if key == "開札日時":
                        parsed_date = parse_reiwa_date(value)
                        if parsed_date:
                             bid[key] = parsed_date.strftime("%Y-%m-%d")  # ← 和暦を上書きで西暦に
                        else:
                            bid[key] = value  # 解析失敗したら元のまま入れる（保険）
                    elif key == "参加数":
                        match = re.search(r"\d+", value)
                        bid[key] = match.group(0) if match else value
                    elif key in ["決定金額", "予定価格", "最低制限価格"]:
                        # 例: "157,850,000円（税抜）" → "157850000"
                        clean_value = re.sub(r"[^\d]", "", value)  # 数字以外すべて削除
                        bid[key] = clean_value if clean_value else value
                    else:
                        bid[key] = value        
                except:
                    pass

        # 契約内容ページから
        if urls["contract_url"]:
            driver.get(urls["contract_url"])
            try:
                bid["工事種別"] = driver.find_element(
                    By.XPATH, "//dt[normalize-space(text())='工事種別']/following-sibling::dd[1]"
                ).text.strip()
                bid["工事名"] = driver.find_element(
                    By.XPATH, "//dt[normalize-space(text())='工事名']/following-sibling::dd[1]"
                ).text.strip()
            except:
                pass
        
        try:
            if bid["最低制限価格"] and bid["予定価格"]:
                min_limit = int(bid["最低制限価格"])
                planned = int(bid["予定価格"])
                if planned != 0:
                    bid["制限率"] = round(min_limit / planned, 3)  # 小数第3位まで
                else:
                    bid["制限率"] = ""
            else:
                bid["制限率"] = ""
        except:
            bid["制限率"] = ""

        bids.append(bid)

    driver.quit()
    return bids

def parse_reiwa_date(text: str) -> datetime.date | None:
    match = re.search(r"令和(\d+)年(\d+)月(\d+)日", text)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3))
        western_year = 2018 + year  # 令和元年は2019年
        return datetime.date(western_year, month, day)
    return None

def append_to_csv(rows: List[Dict], path: str):
    file_exists = os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in FIELDNAMES})
    print(f"[INFO] {path} に {len(rows)} 件を追記しました")

def main():
    if len(sys.argv) != 3:
        print("使い方: python bid_scraper_selenium.py YYYY-MM-DD YYYY-MM-DD")
        sys.exit(1)

    try:
        start = dt.datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
        end   = dt.datetime.strptime(sys.argv[2], "%Y-%m-%d").date()
    except ValueError:
        print("日付形式が正しくありません (YYYY-MM-DD)")
        sys.exit(1)
    if start > end:
        print("開始日が終了日より後です")
        sys.exit(1)

    print(f"[INFO] {start} から {end} までの入札情報を取得します")
    rows = fetch_kobe_bids_selenium(start, end)
    if rows:
        print(f"[INFO] {len(rows)} 件の入札情報を取得しました")
        append_to_csv(rows, OUTPUT_CSV)
    else:
        print("[WARN] 取得データなし、CSV への追記は行いませんでした")

if __name__ == "__main__":
    main()
