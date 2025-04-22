#!/usr/bin/env python3
import datetime
import subprocess
import sys


def parse_date(arg: str) -> datetime.date:
    """
    引数の文字列 "YYYY-M-D" をパースして date オブジェクトを返す。
    """
    parts = arg.split('-')
    if len(parts) != 3:
        raise ValueError
    y, m, d = map(int, parts)
    return datetime.date(y, m, d)


def add_month(d: datetime.date) -> datetime.date:
    """
    与えられた日付に1か月加算する（翌月の同じ日）。
    末日を超える場合はその月の末日に調整。
    例: 2024-01-31 → 2024-02-29（うるう年対応）
    """
    year = d.year + (d.month // 12)
    month = (d.month % 12) + 1
    day = min(d.day, [31,
                      29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
                      31, 30, 31, 30,
                      31, 31, 30, 31, 30, 31][month - 1])
    return datetime.date(year, month, day)


def main():
    # 引数チェック
    if len(sys.argv) != 3:
        print("使い方: python run_monthly.py START_DATE END_DATE")
        print("例: python run_monthly.py 2024-1-1 2024-4-1")
        sys.exit(1)

    # 日付パース
    try:
        start = parse_date(sys.argv[1])
        end   = parse_date(sys.argv[2])
    except ValueError:
        print("日付形式が正しくありません (YYYY-M-D)")
        sys.exit(1)

    # 開始日と終了日の関係チェック
    if start >= end:
        print("開始日は終了日より前の日付を指定してください")
        sys.exit(1)

    script = "bid_scraper.py"
    current = start

    # 1か月ずつ繰り返し
    while current < end:
        next_month = add_month(current)
        if next_month > end:
            next_month = end

        start_str = current.strftime("%Y-%m-%d")
        end_str   = next_month.strftime("%Y-%m-%d")
        print(f"[INFO] {start_str} から {end_str} の入札情報を取得します")

        # bid_scraper.py を呼び出し
        result = subprocess.run(
            [sys.executable, script, start_str, end_str],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print(f"[ERROR] {start_str} から {end_str} の取得に失敗しました")
            print(result.stderr)
        else:
            print(result.stdout)

        current = next_month


if __name__ == "__main__":
    main()
