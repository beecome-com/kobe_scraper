#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
神戸市入札結果スクレイピングツール

指定した日付範囲の入札結果を検索し、各案件の詳細情報を取得してファイルに保存します。
対応フォーマット: CSV, Excel(.xlsx), Google Spreadsheet
"""

import argparse
import csv
import datetime
import logging
import os
import random
import re
import sys
import time
from typing import Dict, List, Optional, Tuple, Union

import pandas as pd
import requests
from bs4 import BeautifulSoup

# 条件付きインポート - 必要に応じて動的にインポート
selenium_imported = False
gspread_imported = False


def setup_logger(verbose: bool = False) -> logging.Logger:
    """ロギング設定を行います

    Args:
        verbose: 詳細なログ出力を行うかどうか

    Returns:
        設定されたロガーオブジェクト
    """
    logger = logging.getLogger("kobe_bid_scraper")
    handler = logging.StreamHandler()
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    # ログレベル設定
    if verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    
    return logger


def validate_date(date_str: str) -> datetime.date:
    """日付文字列を検証し、datetime.date オブジェクトに変換します

    Args:
        date_str: YYYY-MM-DD 形式の日付文字列

    Returns:
        datetime.date オブジェクト

    Raises:
        ValueError: 日付形式が不正な場合
    """
    try:
        return datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"無効な日付形式です: {date_str}。YYYY-MM-DD 形式で指定してください。")


def setup_selenium() -> Tuple:
    """Seleniumを設定し、WebDriverを返します

    Returns:
        Tuple[webdriver.Chrome, Options]: WebDriverとOptionsのタプル

    Raises:
        ImportError: Seleniumのインポートに失敗した場合
    """
    global selenium_imported
    
    if not selenium_imported:
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.support.ui import Select, WebDriverWait
            from selenium.common.exceptions import TimeoutException
            
            try:
                from webdriver_manager.chrome import ChromeDriverManager
                has_webdriver_manager = True
            except ImportError:
                has_webdriver_manager = False
                
            selenium_imported = True
            logger.info("Seleniumを正常にインポートしました")
        except ImportError as e:
            logger.error(f"Seleniumのインポートに失敗しました: {e}")
            logger.error("pip install selenium webdriver-manager を実行してください")
            raise
    else:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import Select, WebDriverWait
        from selenium.common.exceptions import TimeoutException
        
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            has_webdriver_manager = True
        except ImportError:
            has_webdriver_manager = False
    
    # Chrome オプション設定
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")  # 新しいヘッドレスモード
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    
    try:
        # WebDriver 設定
        if has_webdriver_manager:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            logger.debug("ChromeDriverをwebdriver-managerで自動インストールしました")
        else:
            driver = webdriver.Chrome(options=chrome_options)
            logger.debug("既存のChromeDriverを使用します")
        
        # ページの読み込みタイムアウトを設定
        driver.set_page_load_timeout(30)
        
        # User-Agentを設定
        driver.execute_cdp_cmd("Network.setUserAgentOverride", {
            "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        })
        
        return (driver, By, WebDriverWait, EC, Select)
    
    except Exception as e:
        logger.error(f"ChromeDriverの設定に失敗しました: {e}")
        raise


def setup_gspread() -> Tuple:
    """Google Sheets APIを設定し、必要なオブジェクトを返します

    Returns:
        Tuple: (gspread.Client, ServiceAccountCredentials)

    Raises:
        ImportError: gspreadのインポートに失敗した場合
        FileNotFoundError: 認証ファイルが見つからない場合
    """
    global gspread_imported
    
    if not gspread_imported:
        try:
            import gspread
            from oauth2client.service_account import ServiceAccountCredentials
            
            gspread_imported = True
            logger.info("gspreadを正常にインポートしました")
        except ImportError as e:
            logger.error(f"gspreadのインポートに失敗しました: {e}")
            logger.error("pip install gspread oauth2client を実行してください")
            raise
    else:
        import gspread
        from oauth2client.service_account import ServiceAccountCredentials
    
    # 認証設定
    # credentials.json ファイルがカレントディレクトリにあることを期待
    cred_file = "credentials.json"
    
    if not os.path.exists(cred_file):
        logger.error(f"認証ファイル {cred_file} が見つかりません")
        logger.error("Google Sheets API の認証情報を credentials.json として保存してください")
        raise FileNotFoundError(f"認証ファイル {cred_file} が見つかりません")
    
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    
    credentials = ServiceAccountCredentials.from_json_keyfile_name(cred_file, scope)
    client = gspread.authorize(credentials)
    
    return (client, credentials)


def random_sleep() -> None:
    """ランダムな時間（1〜3秒）スリープします"""
    sleep_time = 1 + random.random() * 2
    logger.debug(f"{sleep_time:.2f}秒スリープします")
    time.sleep(sleep_time)


def search_bids_with_requests(start_date: datetime.date, end_date: datetime.date) -> Optional[List[Dict]]:
    """requestsを使用して入札結果を検索します

    Args:
        start_date: 検索開始日
        end_date: 検索終了日

    Returns:
        検索結果のリスト（失敗した場合はNone）
    """

    s = requests.Session()                
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        ),
        "Referer": "https://nyusatsukekka.city.kobe.lg.jp/searchk.php",
    })
    s.get("https://nyusatsukekka.city.kobe.lg.jp/searchk.php", timeout=15)

    url = "https://nyusatsukekka.city.kobe.lg.jp/resultsk.php"
    
    # 年月日を個別に取得
    start_year = start_date.year
    start_month = start_date.month
    start_day = start_date.day
    
    end_year = end_date.year
    end_month = end_date.month
    end_day = end_date.day
    
    # POSTパラメータ作成
    params = {
        "fromyy": f"{start_date.year}",
        "frommm": f"{start_date.month:02}",
        "fromdd": f"{start_date.day:02}",
        "toyy"  : f"{end_date.year}",
        "tomm"  : f"{end_date.month:02}",
        "todd"  : f"{end_date.day:02}",
        "koujimei": "",  # 工事名
        "nyusatsu1": "一般競争入札",
        "nyusatsu2": "指名競争入札",
        "nyusatsu3": "制限付一般競争入札",
        "fromkin": "",  # 金額下限
        "tokin": "",  # 金額上限
        "anken": "",  # 案件番号
    }
    headers = {
        "Referer": "https://nyusatsukekka.city.kobe.lg.jp/searchk.php",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    
    try:
        response = s.post(url, data=params,timeout=15)
        response.raise_for_status()
        response.encoding = "cp932" 
        
        # レスポンスをパース
        soup = BeautifulSoup(response.text, "html.parser")
        
        # 結果テーブルを探す
        result_table = soup.find("table", class_="kekka")
        
        if result_table is None:
            logger.warning("検索結果テーブルが見つかりません。結果がないか、ページ構造が変更された可能性があります。")
            return None
        
        # 結果行を解析
        results = []
        rows = result_table.find_all("tr")[1:]  # ヘッダー行をスキップ
        
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 5:  # 最低5列あることを期待
                continue
            
            # リンクを取得
            link_elem = cols[0].find("a")
            if not link_elem:
                continue
                
            link = link_elem.get("href")
            if not link:
                continue
            
            # 相対パスなら絶対パスに変換
            if not link.startswith("http"):
                link = f"https://nyusatsukekka.city.kobe.lg.jp/{link}"
            
            # 基本情報を取得
            bid_info = {
                "工事名": cols[0].text.strip(),
                "開札日時": cols[1].text.strip(),
                "入札方法": cols[2].text.strip(),
                "案件番号": cols[3].text.strip(),
                "link": link
            }
            
            results.append(bid_info)
        
        # ページネーションを確認
        next_page = soup.find("a", string=re.compile(r"次へ|次ページ|>"))
        
        if next_page and next_page.get("href"):
            logger.info("次のページが存在します。Seleniumに切り替えます。")
            return None  # ページネーションがある場合はSeleniumに切り替え
        
        logger.info(f"{len(results)}件の入札結果を取得しました")
        return results
    
    except Exception as e:
        logger.warning(f"requestsによる検索でエラーが発生しました: {e}")
        logger.info("Seleniumに切り替えます")
        return None


def get_onclick_url(onclick_text: str) -> Optional[str]:
    """JavaScriptのonclickイベントからURLを抽出します"""
    try:
        # onclick="window.open('resultk.php?xxx')" のようなパターンを処理
        match = re.search(r"window\.open\('([^']+)'\)", onclick_text)
        if match:
            return match.group(1)
        return None
    except:
        return None


def extract_link_from_cell(cell) -> Optional[str]:
    """セルからリンクを抽出します"""
    try:
        links = cell.find_elements(By.TAG_NAME, "a")
        for link in links:
            # まずhref属性をチェック
            href = link.get_attribute("href")
            if href and "resultk.php" in href:
                return href
            
            # onclick属性をチェック
            onclick = link.get_attribute("onclick")
            if onclick:
                url = get_onclick_url(onclick)
                if url:
                    return url
        return None
    except:
        return None


def search_bids_with_selenium(start_date: datetime.date, end_date: datetime.date) -> List[Dict]:
    """Seleniumを使用して入札結果を検索します"""
    driver, By, WebDriverWait, EC, Select = setup_selenium()
    url = "https://nyusatsukekka.city.kobe.lg.jp/searchk.php"
    results = []
    
    try:
        driver.get(url)
        logger.debug(f"URL {url} にアクセスしました")
        
        # フォームが読み込まれるまで待機
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "form")))
        
        # 日付入力
        Select(driver.find_element(By.NAME, "fromyy")).select_by_value(str(start_date.year))
        Select(driver.find_element(By.NAME, "frommm")).select_by_value(str(start_date.month).zfill(2))
        Select(driver.find_element(By.NAME, "fromdd")).select_by_value(str(start_date.day).zfill(2))
        
        Select(driver.find_element(By.NAME, "toyy")).select_by_value(str(end_date.year))
        Select(driver.find_element(By.NAME, "tomm")).select_by_value(str(end_date.month).zfill(2))
        Select(driver.find_element(By.NAME, "todd")).select_by_value(str(end_date.day).zfill(2))
        
        # 入札方式のチェックボックスを選択
        for checkbox_name in ["nyusatsu1", "nyusatsu2", "nyusatsu3"]:
            try:
                checkbox = driver.find_element(By.NAME, checkbox_name)
                if not checkbox.is_selected():
                    checkbox.click()
            except:
                continue
        
        # 検索実行
        search_button = driver.find_element(By.XPATH, "//input[@type='submit'][@value='検索実行']")
        search_button.click()
        logger.debug("検索ボタンをクリックしました")
        time.sleep(2)  # 結果の読み込みを待機
        
        page_num = 1
        while True:
            logger.info(f"検索結果ページ {page_num} を処理中...")
            
            # 検索結果テーブルを探す
            try:
                tables = driver.find_elements(By.TAG_NAME, "table")
                result_table = None
                
                # 検索フォーム以外のテーブルを探す
                for table in tables:
                    if "base-table" not in (table.get_attribute("class") or ""):
                        result_table = table
                        break
                
                if not result_table:
                    break
                
                logger.debug("結果テーブルを見つけました")
                rows = result_table.find_elements(By.TAG_NAME, "tr")[1:]  # ヘッダーをスキップ
                
                for row in rows:
                    try:
                        cols = row.find_elements(By.TAG_NAME, "td")
                        if len(cols) < 4:
                            continue
                        
                        # リンクを探す
                        link = extract_link_from_cell(cols[0])
                        if not link:
                            continue
                        
                        if not link.startswith("http"):
                            link = f"https://nyusatsukekka.city.kobe.lg.jp/{link}"
                        
                        # データを取得
                        bid_info = {
                            "工事名": cols[0].text.strip(),
                            "開札日時": cols[1].text.strip(),
                            "入札方法": cols[2].text.strip(),
                            "案件番号": cols[3].text.strip(),
                            "link": link
                        }
                        
                        if all(v.strip() for v in bid_info.values()):
                            results.append(bid_info)
                            logger.debug(f"入札情報を取得: {bid_info['工事名']}")
                    
                    except Exception as e:
                        logger.debug(f"行の処理でエラー: {str(e)}")
                        continue
                
                # 次ページの確認
                try:
                    next_links = driver.find_elements(By.XPATH, 
                        "//a[contains(text(),'次へ') or contains(text(),'次ページ') or contains(text(),'>')]")
                    if not next_links:
                        break
                    
                    next_links[0].click()
                    logger.debug("次ページをクリックしました")
                    page_num += 1
                    time.sleep(2)
                except:
                    break
                
            except Exception as e:
                logger.error(f"ページの処理でエラー: {str(e)}")
                break
        
        if not results:
            logger.warning("検索結果が0件でした")
        else:
            logger.info(f"合計 {len(results)} 件の入札結果を取得しました")
        
        return results
    
    except Exception as e:
        logger.error(f"Seleniumによる検索でエラー: {str(e)}")
        raise
    
    finally:
        driver.quit()
        logger.debug("Seleniumドライバを終了しました")


def get_bid_details_with_requests(bid_info: Dict) -> Dict:
    """requestsを使用して入札詳細情報を取得します

    Args:
        bid_info: 基本的な入札情報（リンクを含む）

    Returns:
        詳細情報を含む辞書
    """
    link = bid_info["link"]
    
    try:
        response = requests.get(link)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # 詳細テーブルを探す
        detail_table = soup.find("table", class_="detail")
        
        if not detail_table:
            logger.warning(f"詳細テーブルが見つかりません: {link}")
            return bid_info
        
        # 詳細情報を取得
        rows = detail_table.find_all("tr")
        details = {}
        
        for row in rows:
            cells = row.find_all(["th", "td"])
            if len(cells) >= 2:
                key = cells[0].text.strip()
                value = cells[1].text.strip()
                
                details[key] = value
        
        # 必要な情報を取得して辞書を更新
        # 既に基本情報はbid_infoに入っているため、それ以外の項目を追加/更新
        bid_details = bid_info.copy()
        
        # 対象フィールドの対応
        field_mapping = {
            "工事（業務）名": "工事名",
            "開札日時": "開札日時",
            "入札方式": "入札方法",
            "参加者数": "参加数",
            "落札金額（税込）": "決定金額",
            "予定価格（税込）": "予定価格",
            "最低制限価格（税込）": "最低制限価格",
            "契約の相手方": "契約相手",
        }
        
        for jp_key, en_key in field_mapping.items():
            if jp_key in details:
                bid_details[en_key] = details[jp_key]
            elif en_key not in bid_details:
                bid_details[en_key] = ""
        
        return bid_details
    
    except Exception as e:
        logger.warning(f"requestsによる詳細取得でエラーが発生しました: {e}")
        return bid_info


def get_bid_details_with_selenium(bid_info: Dict) -> Dict:
    """Seleniumを使用して入札詳細情報を取得します

    Args:
        bid_info: 基本的な入札情報（リンクを含む）

    Returns:
        詳細情報を含む辞書
    """
    driver, By, WebDriverWait, EC, _ = setup_selenium()
    link = bid_info["link"]
    
    try:
        driver.get(link)
        logger.debug(f"URL {link} にアクセスしました")
        
        # 詳細テーブルが読み込まれるまで待機
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "detail")))
        
        # 詳細テーブルを取得
        detail_table = driver.find_element(By.CLASS_NAME, "detail")
        rows = detail_table.find_elements(By.TAG_NAME, "tr")
        
        details = {}
        
        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) >= 2:
                key = cells[0].text.strip()
                value = cells[1].text.strip()
                
                details[key] = value
        
        # 必要な情報を取得して辞書を更新
        bid_details = bid_info.copy()
        
        # 対象フィールドの対応
        field_mapping = {
            "工事（業務）名": "工事名",
            "開札日時": "開札日時",
            "入札方式": "入札方法",
            "参加者数": "参加数",
            "落札金額（税込）": "決定金額",
            "予定価格（税込）": "予定価格",
            "最低制限価格（税込）": "最低制限価格",
            "契約の相手方": "契約相手",
        }
        
        for jp_key, en_key in field_mapping.items():
            if jp_key in details:
                bid_details[en_key] = details[jp_key]
            elif en_key not in bid_details:
                bid_details[en_key] = ""
        
        return bid_details
    
    except Exception as e:
        logger.warning(f"Seleniumによる詳細取得でエラーが発生しました: {e}")
        return bid_info
    
    finally:
        driver.quit()
        logger.debug("Seleniumドライバを終了しました")


def save_to_csv(data: List[Dict], filepath: str, append: bool = True) -> None:
    """データをCSVファイルに保存します

    Args:
        data: 保存するデータ
        filepath: 保存先ファイルパス
        append: 既存ファイルに追記する場合はTrue、上書きする場合はFalse
    """
    # 列順序を定義
    columns = ["工事名", "開札日時", "入札方法", "参加数", "決定金額", "予定価格", "最低制限価格", "契約相手"]
    
    # 重複チェック用の既存データ読み込み
    existing_data = []
    if append and os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                existing_data = list(reader)
            
            logger.info(f"既存ファイル {filepath} から {len(existing_data)} 件のデータを読み込みました")
        except Exception as e:
            logger.warning(f"既存ファイルの読み込みに失敗しました: {e}")
            existing_data = []
    
    # 重複排除
    existing_keys = {(row.get("工事名", ""), row.get("開札日時", "")) for row in existing_data}
    new_data = [row for row in data if (row.get("工事名", ""), row.get("開札日時", "")) not in existing_keys]
    
    logger.info(f"重複排除後: {len(new_data)} 件の新規データ")
    
    # 書き込みモード決定
    mode = "a" if append and os.path.exists(filepath) else "w"
    write_header = not (append and os.path.exists(filepath))
    
    # CSVに保存
    with open(filepath, mode, encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        
        if write_header:
            writer.writeheader()
        
        for row in new_data:
            # 必要なフィールドのみ抽出
            filtered_row = {col: row.get(col, "") for col in columns}
            writer.writerow(filtered_row)
    
    logger.info(f"{len(new_data)} 件のデータを {filepath} に保存しました")


def save_to_excel(data: List[Dict], filepath: str, append: bool = True) -> None:
    """データをExcelファイルに保存します

    Args:
        data: 保存するデータ
        filepath: 保存先ファイルパス
        append: 既存ファイルに追記する場合はTrue、上書きする場合はFalse
    """
    # 列順序を定義
    columns = ["工事名", "開札日時", "入札方法", "参加数", "決定金額", "予定価格", "最低制限価格", "契約相手"]
    
    # データフレームを作成
    df = pd.DataFrame(data)
    
    # 必要な列のみ抽出して順序を調整
    for col in columns:
        if col not in df.columns:
            df[col] = ""
    
    df = df[columns]
    
    # 既存ファイルが存在するかチェック
    if append and os.path.exists(filepath):
        try:
            existing_df = pd.read_excel(filepath)
            logger.info(f"既存ファイル {filepath} から {len(existing_df)} 件のデータを読み込みました")
            
            # 重複チェック (工事名と開札日時の組み合わせ)
            existing_keys = set(zip(existing_df["工事名"], existing_df["開札日時"]))
            
            # 重複しない行を抽出
            new_data = df[~df.apply(lambda row: (row["工事名"], row["開札日時"]) in existing_keys, axis=1)]
            
            # 既存データと新規データを結合
            combined_df = pd.concat([existing_df, new_data], ignore_index=True)
            
            logger.info(f"重複排除後: {len(new_data)} 件の新規データ")
            
            # 保存
            combined_df.to_excel(filepath, index=False)
            logger.info(f"{len(new_data)} 件のデータを {filepath} に追記しました")
        
        except Exception as e:
            logger.warning(f"Excelファイルの追記処理に失敗しました: {e}")
            logger.warning("新規ファイルとして保存します")
            df.to_excel(filepath, index=False)
            logger.info(f"{len(df)} 件のデータを {filepath} に保存しました")
    
    else:
        # 新規ファイルとして保存
        df.to_excel(filepath, index=False)
        logger.info(f"{len(df)} 件のデータを {filepath} に保存しました")


def save_to_gsheet(data: List[Dict], spreadsheet_id: str) -> None:
    """データをGoogle Spreadsheetに保存します

    Args:
        data: 保存するデータ
        spreadsheet_id: Google Spreadsheet ID
    """
    # Google Sheets APIを初期化
    client, _ = setup_gspread()
    
    # スプレッドシートを開く
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        
        # デフォルトで最初のシートを使用
        worksheet = spreadsheet.sheet1
        
        # 既存データを取得
        existing_data = worksheet.get_all_records()
        logger.info(f"スプレッドシート {spreadsheet_id} から {len(existing_data)} 件のデータを読み込みました")
        
        # 列順序を定義
        columns = ["工事名", "開札日時", "入札方法", "参加数", "決定金額", "予定価格", "最低制限価格", "契約相手"]
        
        # ヘッダーがない場合は追加
        if not existing_data and worksheet.row_count == 0:
            worksheet.append_row(columns)
            
        # または既存のヘッダーが異なる場合は調整
        elif not existing_data and worksheet.row_count > 0:
            header_row = worksheet.row_values(1)
            if header_row != columns:
                worksheet.clear()
                worksheet.append_row(columns)
        
        # 重複チェック
        existing_keys = {(row.get("工事名", ""), row.get("開札日時", "")) for row in existing_data}
        
        # 追加するデータを準備
        rows_to_add = []
        for item in data:
            key = (item.get("工事名", ""), item.get("開札日時", ""))
            if key not in existing_keys:
                # 列順に値を並べる
                row = [item.get(col, "") for col in columns]
                rows_to_add.append(row)
        
        logger.info(f"重複排除後: {len(rows_to_add)} 件の新規データ")
        
        # データを追加
        if rows_to_add:
            worksheet.append_rows(rows_to_add)
            logger.info(f"{len(rows_to_add)} 件のデータをスプレッドシートに追記しました")
        else:
            logger.info("追加するデータはありません")
        
    except Exception as e:
        logger.error(f"Google Spreadsheetへの保存でエラーが発生しました: {e}")
        raise

def main() -> None:
    """メイン関数"""
    global logger
    
    # コマンドライン引数のパース
    parser = argparse.ArgumentParser(description="神戸市入札結果スクレイピングツール")
    
    parser.add_argument("start_date", help="検索開始日 (YYYY-MM-DD形式)")
    parser.add_argument("end_date", help="検索終了日 (YYYY-MM-DD形式)")
    parser.add_argument("--csv", metavar="FILE", help="CSVファイルに保存")
    parser.add_argument("--xlsx", metavar="FILE", help="Excelファイルに保存")
    parser.add_argument("--gsheet", metavar="SPREADSHEET_ID", help="Google Spreadsheetに保存")
    parser.add_argument("--verbose", action="store_true", help="詳細なログ出力")
    
    args = parser.parse_args()
    
    # ロガーの設定
    logger = setup_logger(args.verbose)
    
    # 出力先の指定が必要
    if not any([args.csv, args.xlsx, args.gsheet]):
        logger.error("出力先を少なくとも1つ指定してください (--csv, --xlsx, --gsheet)")
        sys.exit(1)
    
    # 日付のバリデーション
    try:
        start_date = validate_date(args.start_date)
        end_date = validate_date(args.end_date)
        
        if start_date > end_date:
            logger.error("開始日が終了日より後になっています")
            sys.exit(1)
        
        # 日付範囲が広すぎる場合は警告
        date_range = (end_date - start_date).days + 1
        if date_range > 31:
            logger.warning(f"指定された日付範囲が広すぎます ({date_range}日間)。処理に時間がかかる可能性があります。")
    
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)
    
    logger.info(f"検索期間: {start_date} から {end_date} まで")
    
    try:
        # まずrequestsで試行
        logger.info("requestsを使用して検索を実行します...")
        bids = search_bids_with_requests(start_date, end_date)
        
        # requestsが失敗したらSeleniumにフォールバック
        if bids is None:
            logger.info("Seleniumを使用して検索を実行します...")
            bids = search_bids_with_selenium(start_date, end_date)
        
        if not bids:
            logger.warning("指定期間内の入札結果は見つかりませんでした")
            sys.exit(0)
        
        # 詳細情報の取得
        logger.info(f"{len(bids)}件の入札案件の詳細情報を取得します...")
        
        detailed_bids = []
        for i, bid in enumerate(bids, 1):
            logger.info(f"案件 {i}/{len(bids)} の詳細を取得中: {bid.get('工事名', 'Unknown')}")
            
            # まずrequestsで試す
            detailed_bid = get_bid_details_with_requests(bid)
            
            # 必要な情報が取得できなかった場合、Seleniumで再試行
            required_fields = ["工事名", "開札日時", "入札方法", "参加数", "決定金額", "予定価格", "最低制限価格", "契約相手"]
            missing_fields = [field for field in required_fields if field not in detailed_bid or not detailed_bid[field]]
            
            if missing_fields:
                logger.debug(f"不足しているフィールド: {', '.join(missing_fields)}")
                logger.info("Seleniumで詳細情報を再取得します...")
                detailed_bid = get_bid_details_with_selenium(bid)
            
            detailed_bids.append(detailed_bid)
            
            # サーバー負荷軽減のためのスリープ
            if i < len(bids):
                random_sleep()
        
        # データの保存
        if args.csv:
            save_to_csv(detailed_bids, args.csv)
        
        if args.xlsx:
            save_to_excel(detailed_bids, args.xlsx)
        
        if args.gsheet:
            save_to_gsheet(detailed_bids, args.gsheet)
        
        # 実行サマリー出力
        logger.info("====== 実行サマリー ======")
        logger.info(f"処理期間: {start_date} から {end_date} まで")
        logger.info(f"取得案件数: {len(detailed_bids)}")
        
        if args.csv:
            logger.info(f"CSV出力: {os.path.abspath(args.csv)}")
        if args.xlsx:
            logger.info(f"Excel出力: {os.path.abspath(args.xlsx)}")
        if args.gsheet:
            logger.info(f"Google Spreadsheet出力: {args.gsheet}")
        
    except Exception as e:
        logger.error(f"処理中にエラーが発生しました: {e}")
        if args.verbose:
            import traceback
            logger.debug(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()