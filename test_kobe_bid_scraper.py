
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