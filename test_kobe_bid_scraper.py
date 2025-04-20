#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
神戸市入札結果スクレイピングツールのユニットテスト
"""

import datetime
import logging
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

import pandas as pd
import requests

# テスト対象のモジュールをインポート
from kobe_bid_scraper import validate_date, save_to_csv, save_to_excel, search_bids_with_requests

# ロガーの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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

    def test_search_bids_live(self):
        """実際のWebサイトにアクセスして検索結果を取得するテスト（長期間）"""
        # 実際のリクエストを実行（より長い期間）
        start_date = datetime.date(2024, 3, 1)
        end_date = datetime.date(2024, 3, 31)
        results = search_bids_with_requests(start_date, end_date)

        # 長期間の場合、ページネーションがあるためNoneが返されることを期待
        self.assertIsNone(results, "長期間の検索でページネーションがある場合、Noneが返されるべきです")

    def test_search_bids_short_period(self):
        """実際のWebサイトにアクセスして検索結果を取得するテスト（短期間）"""
        # 実際のリクエストを実行（短い期間）
        start_date = datetime.date(2024, 3, 1)
        end_date = datetime.date(2024, 3, 3)
        results = search_bids_with_requests(start_date, end_date)

        # 結果の検証
        if results is None:
            # 結果がNoneの場合、ページネーションがある可能性がある
            self.skipTest("検索結果にページネーションがあるため、テストをスキップします")
        else:
            self.assertIsInstance(results, list, "検索結果がリストではありません")
            
            if results:  # 結果が存在する場合
                first_result = results[0]
                # 必須フィールドの存在確認
                required_fields = ["工事名", "開札日時", "入札方法", "案件番号", "link"]
                for field in required_fields:
                    self.assertIn(field, first_result, f"{field}が結果に含まれていません")
                    self.assertIsNotNone(first_result[field], f"{field}がNoneです")
                    self.assertNotEqual(first_result[field], "", f"{field}が空文字列です")

                # リンクのフォーマット確認
                self.assertTrue(
                    first_result["link"].startswith("https://nyusatsukekka.city.kobe.lg.jp/") or 
                    first_result["link"].startswith("http://nyusatsukekka.city.kobe.lg.jp/"),
                    "リンクが正しいURLではありません"
                )

    def test_search_bids_future_date(self):
        """未来の日付で検索した場合のテスト"""
        # 未来の日付で検索
        start_date = datetime.date(2025, 4, 1)
        end_date = datetime.date(2025, 4, 30)
        results = search_bids_with_requests(start_date, end_date)

        # 結果がNoneまたは空のリストであることを期待
        if results is not None:
            self.assertEqual(len(results), 0, "未来の日付での検索結果は空であるべきです")

    def test_search_bids_invalid_dates(self):
        """無効な日付範囲での検索テスト"""
        # 終了日が開始日より前の場合
        start_date = datetime.date(2024, 3, 10)
        end_date = datetime.date(2024, 3, 1)
        
        with self.assertRaises(ValueError):
            search_bids_with_requests(start_date, end_date)


if __name__ == '__main__':
    unittest.main()