#!/usr/bin/env python3
# bid_scraper_selenium.py
# 使い方: python bid_scraper_selenium.py 2024-03-01 2024-03-15

import sys
import datetime as dt
from typing import List, Dict

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

SEARCH_URL = "https://nyusatsukekka.city.kobe.lg.jp/searchk.php"

def fetch_kobe_bids_selenium(start: dt.date, end: dt.date) -> List[Dict]:
    print(f"[INFO] 開始: {start} から {end} までの入札情報取得")
    # ChromeDriver のパスを指定
    service = Service(executable_path=r"C:\Tools\chromedriver.exe")
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--blink-settings=imagesEnabled=false")  # 画像読み込みオフ

    driver = webdriver.Chrome(service=service, options=options)
    wait = WebDriverWait(driver, 5)  # 待機は最長5秒に短縮

    # フォームページを開く
    print("[STEP] フォームページを開いています…")
    driver.get(SEARCH_URL)
    wait.until(EC.presence_of_element_located((By.NAME, "fromyy")))
    print("[DONE] フォームページ表示完了")

    # 日付をプルダウンで選択
    print(f"[STEP] 日付を選択: from {start} to {end}")
    Select(driver.find_element(By.NAME, "fromyy")).select_by_value(str(start.year))
    Select(driver.find_element(By.NAME, "frommm")).select_by_value(f"{start.month:02}")
    Select(driver.find_element(By.NAME, "fromdd")).select_by_value(f"{start.day:02}")
    Select(driver.find_element(By.NAME, "toyy")).select_by_value(str(end.year))
    Select(driver.find_element(By.NAME, "tomm")).select_by_value(f"{end.month:02}")
    Select(driver.find_element(By.NAME, "todd")).select_by_value(f"{end.day:02}")
    print("[DONE] 日付選択完了")

    # 検索実行ボタンをクリック
    print("[STEP] 検索実行ボタンをクリック")
    try:
        driver.find_element(By.CSS_SELECTOR, "input[value='検索実行']").click()
    except:
        driver.find_element(By.CSS_SELECTOR, "input[type=submit]").click()

    # 結果ページへの遷移を待つ
    wait.until(EC.url_contains("resultsk.php"))
    print("[DONE] 結果ページに遷移しました")

    # テーブル取得
    print("[STEP] 結果テーブルを探しています…")
    try:
        header_cell = wait.until(EC.presence_of_element_located(
            (By.XPATH, "//th[contains(text(),'開札年月日')]")
        ))
    except:
        header_cell = wait.until(EC.presence_of_element_located(
            (By.XPATH, "//td[contains(text(),'開札年月日')]")
        ))
    table = header_cell.find_element(By.XPATH, "./ancestor::table")
    print("[DONE] テーブル取得完了")

    # 一覧ページからリンクを取得
    print("[STEP] 一覧ページから result_url, contract_url を収集します")
    bids: List[Dict] = []
    for idx, tr in enumerate(table.find_elements(By.TAG_NAME, "tr")[1:], start=1):
        cols = tr.find_elements(By.TAG_NAME, "td")
        if len(cols) < 8:
            print(f"  [SKIP] 行{idx} 列数不足 ({len(cols)})")
            continue
        result_url = ""
        contract_url = ""
        try:
            result_url = cols[6].find_element(By.TAG_NAME, "a").get_attribute("href")
        except:
            pass
        try:
            contract_url = cols[7].find_element(By.TAG_NAME, "a").get_attribute("href")
        except:
            pass
        print(f"  [ROW {idx}] result_url={result_url or 'なし'} / contract_url={contract_url or 'なし'}")
        bids.append({"result_url": result_url, "contract_url": contract_url})
    print(f"[DONE] リンク収集完了: {len(bids)} 件")

    # ―― 詳細ページから追加情報を取得 ――
    print("[STEP] 各詳細ページから情報取得を開始します")
    for idx, bid in enumerate(bids, start=1):
        print(f"  ■ 件目 {idx}")
        # 開札結果ページ
        if bid["result_url"]:
            print(f"    [DETAIL] 開札結果ページへアクセス: {bid['result_url']}")
            driver.get(bid["result_url"])
            # 入札日時
            try:
                bid["入札日時"] = driver.find_element(
                    By.XPATH, "//dt[normalize-space(text())='入札日時']/following-sibling::dd[1]"
                ).text.strip()
            except:
                bid["入札日時"] = ""
            print(f"      → 入札日時 = {bid['入札日時'] or '取得失敗'}")
            # 入札方式
            try:
                bid["入札方式"] = driver.find_element(
                    By.XPATH, "//dt[normalize-space(text())='入札方式']/following-sibling::dd[1]"
                ).text.strip()
            except:
                bid["入札方式"] = ""
            print(f"      → 入札方式 = {bid['入札方式'] or '取得失敗'}")
            # 指名・参加数
            try:
                bid["指名・参加数"] = driver.find_element(
                    By.XPATH, "//dt[normalize-space(text())='指名・参加数']/following-sibling::dd[1]"
                ).text.strip()
            except:
                bid["指名・参加数"] = ""
            print(f"      → 指名・参加数 = {bid['指名・参加数'] or '取得失敗'}")
            # 決定金額
            try:
                bid["決定金額(税抜)"] = driver.find_element(
                    By.XPATH, "//dt[normalize-space(text())='決定金額(税抜)']/following-sibling::dd[1]"
                ).text.strip()
            except:
                bid["決定金額(税抜)"] = ""
            print(f"      → 決定金額(税抜) = {bid['決定金額(税抜)'] or '取得失敗'}")
            # 予定価格
            try:
                bid["予定価格(税抜)"] = driver.find_element(
                    By.XPATH, "//dt[normalize-space(text())='予定価格(税抜)']/following-sibling::dd[1]"
                ).text.strip()
            except:
                bid["予定価格(税抜)"] = ""
            print(f"      → 予定価格(税抜) = {bid['予定価格(税抜)'] or '取得失敗'}")
            # 最低制限価格
            try:
                bid["最低制限価格(税抜)"] = driver.find_element(
                    By.XPATH, "//dt[normalize-space(text())='最低制限価格または調査基準価格(税抜)']/following-sibling::dd[1]"
                ).text.strip()
            except:
                bid["最低制限価格(税抜)"] = ""
            print(f"      → 最低制限価格(税抜) = {bid['最低制限価格(税抜)'] or '取得失敗'}")
            # 契約相手
            try:
                bid["契約相手"] = driver.find_element(
                    By.XPATH, "//dt[normalize-space(text())='契約の相手方']/following-sibling::dd[1]"
                ).text.strip()
            except:
                bid["契約相手"] = ""
            print(f"      → 契約相手 = {bid['契約相手'] or '取得失敗'}")

        # 契約内容ページ
        if bid["contract_url"]:
            print(f"    [DETAIL] 契約内容ページへアクセス: {bid['contract_url']}")
            driver.get(bid["contract_url"])
            try:
                bid["工事種別"] = driver.find_element(
                    By.XPATH, "//dt[normalize-space(text())='工事種別']/following-sibling::dd[1]"
                ).text.strip()
            except:
                bid["工事種別"] = ""
            print(f"      → 工事種別 = {bid['工事種別'] or '取得失敗'}")

    driver.quit()
    print(f"[INFO] 完了: 合計 {len(bids)} 件の詳細情報を取得しました")
    return bids

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

    rows = fetch_kobe_bids_selenium(start, end)
    print(f"\n最終結果: {len(rows)} 件取得")

if __name__ == "__main__":
    main()
