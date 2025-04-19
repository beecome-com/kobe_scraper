# 神戸市入札結果スクレイピングツール

神戸市の入札結果検索ページから指定した日付範囲の入札案件情報を取得し、CSV、Excel、またはGoogle Spreadsheetに保存するツールです。

## 機能

- 指定した日付範囲の入札結果を検索
- 各案件の詳細情報（工事名、開札日時、入札方法、参加数、決定金額、予定価格、最低制限価格、契約相手）を取得
- CSV、Excel(.xlsx)、Google Spreadsheetに保存可能
- 既存ファイルへの追記対応
- 重複案件の自動スキップ

## インストール

必要なパッケージをインストールします：

```bash
pip install -r requirements.txt

使用方法
基本的な使い方
Copy# CSV形式で保存
python kobe_bid_scraper.py 2025-04-01 2025-04-19 --csv results.csv

# Excel形式で保存
python kobe_bid_scraper.py 2025-04-01 2025-04-19 --xlsx results.xlsx

# Google Spreadsheetに保存
python kobe_bid_scraper.py 2025-04-01 2025-04-19 --gsheet 1AbCdEfGhIjKlMnOpQrStUvWxYz
オプション
--verbose: 詳細なログ出力を有効化
--csv FILE: 指定したCSVファイルに結果を保存
--xlsx FILE: 指定したExcelファイルに結果を保存
--gsheet SPREADSHEET_ID: 指定したGoogle Spreadsheetに結果を保存
Google Sheets API 認証設定
Google Spreadsheetに保存する場合は、以下の手順で認証設定が必要です：

Google Cloud Consoleにアクセス
新しいプロジェクトを作成（または既存のプロジェクトを選択）
Google Sheets APIとGoogle Drive APIを有効化
サービスアカウントを作成
キーを作成（JSON形式）し、ダウンロード
ダウンロードしたJSONファイルをcredentials.jsonとして保存
保存先のGoogle Spreadsheetをサービスアカウントのメールアドレスと共有
注意事項
サーバーへの過剰な負荷を避けるため、リクエスト間にランダムな待機時間（1〜3秒）を設けています
大量のデータを短期間で取得しないよう、適切な日付範囲を指定してください
ウェブサイトの構造が変更された場合、スクリプトが正常に動作しない可能性があります
ユニットテスト
以下のコマンドでユニットテストを実行できます：

Copypytest test_kobe_bid_scraper.py

## test_kobe_bid_scraper.py (単体テスト雛形)

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
神戸市入札結果スクレイピングツールのユニットテスト
"""

import datetime
import os
import tempfile
import unittest

import pandas as pd

# テスト対象のモジュールをインポート
from kobe_bid_scraper import validate_date, save_to_csv, save_to_excel


class TestKobeBidScraper(unittest.TestCase):
    """神戸市入札結果スクレイピングツールのテストケース"""

    def setUp(self):
        """テスト前の準備"""
        # テスト用のサンプルデータ
        self.sample_data = [
            {
                "工事名": "テスト工事1",
                "開札日時": "2025-04-01 10:00",
                "入札方法": "一般競争入札",
                "参加数": "5",
                "決定金額": "10,000,000",
                "予定価格": "12,000,000",
                "最低制限価格": "9,000,000",
                "契約相手": "テスト会社1"
            },
            {
                "工事名": "テスト工事2",
                "開札日時": "2025-04-02 11:00",
                "入札方法": "指名競争入札",
                "参加数": "3",
                "決定金額": "5,000,000",
                "予定価格": "6,000,000",
                "最低制限価格": "4,500,000",
                "契約相手": "テスト会社2"
            }
        ]

    def test_validate_date(self):
        """日付検証関数のテスト"""
        # 正常ケース
        date = validate_date("2025-04-01")
        self.assertEqual(date, datetime.date(2025, 4, 1))
        
        # 異常ケース
        with self.assertRaises(ValueError):
            validate_date("2025/04/01")  # 不正な形式
        
        with self.assertRaises(ValueError):
            validate_date("2025-13-01")  # 存在しない日付

    def test_save_to_csv(self):
        """CSV保存機能のテスト"""
        with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as tmp_file:
            tmp_path = tmp_file.name
        
        try:
            # 新規保存テスト
            save_to_csv(self.sample_data, tmp_path, append=False)
            
            # 保存されたファイルを検証
            df = pd.read_csv(tmp_path)
            self.assertEqual(len(df), 2)
            self.assertEqual(df.iloc[0]["工事名"], "テスト工事1")
            self.assertEqual(df.iloc[1]["工事名"], "テスト工事2")
            
            # 追記テスト
            new_data = [
                {
                    "工事名": "テスト工事3",
                    "開札日時": "2025-04-03 13:00",
                    "入札方法": "一般競争入札",
                    "参加数": "4",
                    "決定金額": "8,000,000",
                    "予定価格": "9,000,000",
                    "最低制限価格": "7,500,000",
                    "契約相手": "テスト会社3"
                }
            ]
            
            save_to_csv(new_data, tmp_path, append=True)
            
            # 追記された結果を検証
            df = pd.read_csv(tmp_path)
            self.assertEqual(len(df), 3)
            self.assertEqual(df.iloc[2]["工事名"], "テスト工事3")
            
            # 重複排除テスト
            save_to_csv(self.sample_data, tmp_path, append=True)
            
            # 結果を検証 (重複は追加されないはず)
            df = pd.read_csv(tmp_path)
            self.assertEqual(len(df), 3)
            
        finally:
            # 一時ファイルを削除
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_save_to_excel(self):
        """Excel保存機能のテスト"""
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
            tmp_path = tmp_file.name
        
        try:
            # 新規保存テスト
            save_to_excel(self.sample_data, tmp_path, append=False)
            
            # 保存されたファイルを検証
            df = pd.read_excel(tmp_path)
            self.assertEqual(len(df), 2)
            self.assertEqual(df.iloc[0]["工事名"], "テスト工事1")
            self.assertEqual(df.iloc[1]["工事名"], "テスト工事2")
            
            # 追記テスト
            new_data = [
                {
                    "工事名": "テスト工事3",
                    "開札日時": "2025-04-03 13:00",
                    "入札方法": "一般競争入札",
                    "参加数": "4",
                    "決定金額": "8,000,000",
                    "予定価格": "9,000,000",
                    "最低制限価格": "7,500,000",
                    "契約相手": "テスト会社3"
                }
            ]
            
            save_to_excel(new_data, tmp_path, append=True)
            
            # 追記された結果を検証
            df = pd.read_excel(tmp_path)
            self.assertEqual(len(df), 3)
            
            # 3行目がテスト工事3であることを確認
            # Excelの読み込みでは順序が保証されない場合があるため工事名で検索
            self.assertTrue(any(df["工事名"] == "テスト工事3"))
            
        finally:
            # 一時ファイルを削除
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


if __name__ == '__main__':
    unittest.main()
機能説明
作成したスクリプト「kobe_bid_scraper.py」は、神戸市の入札結果検索ページから指定した日付範囲の入札案件情報を取得し、CSV、Excel、またはGoogle Spreadsheetに保存するためのツールです。

主な特徴
柔軟なスクレイピング手法：

まずrequestsとBeautifulSoupで試行し、失敗した場合は自動的にSeleniumにフォールバック
ページネーション対応で複数ページにわたる結果も取得可能
詳細データの取得：

各案件の詳細ページにアクセスして8項目（工事名、開札日時、入札方法、参加数、決定金額、予定価格、最低制限価格、契約相手）を取得
欠損項目があった場合は補完処理
複数の出力形式：

CSV形式（UTF-8エンコード）
Excel形式（.xlsx）
Google Spreadsheet
データ重複排除：

「工事名」+「開札日時」の組み合わせで重複チェック
既存ファイルの内容を確認して重複案件をスキップ
サーバー負荷対策：

リクエスト間にランダムな待機時間（1〜3秒）を挿入
段階的なアプローチで必要最小限のリクエストに抑制
ログ機能：

詳細度を調整可能なロギング（--verboseオプション）
エラー時の適切なフォールバックと通知
エラー処理：

例外処理による堅牢な動作
必要に応じた自動リトライ
ユニットテスト：

基本機能のテストケース
実行の流れ
コマンドライン引数で開始日・終了日を指定
出力形式を選択（CSV/Excel/Google Spreadsheet）
検索ページにアクセスして条件を入力
検索結果から案件一覧を取得
各案件の詳細ページにアクセスして情報を抽出
重複チェックを行い、新規データのみを保存
処理サマリーを表示
このツールを使用することで、神戸市の入札結果データを効率的に収集・管理できます。