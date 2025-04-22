#!/usr/bin/env python3
import sys
import pandas as pd
import numpy as np
from datetime import datetime
from sklearn.linear_model import Ridge


# -----------------------------
# データ読み込み
# -----------------------------
def load_data(train_path: str, test_path: str):
    df_train = pd.read_csv(train_path)
    df_test = pd.read_csv(test_path)
    return df_train, df_test


# -----------------------------
# 前処理（共通）
# -----------------------------
def preprocess(df: pd.DataFrame, is_train: bool = True, train_columns=None):
    df = df.copy()

    # 日付から年・月・曜日を作成
    df['開札日時'] = pd.to_datetime(df['開札日時'], errors='coerce')
    df['year'] = df['開札日時'].dt.year
    df['month'] = df['開札日時'].dt.month
    df['weekday'] = df['開札日時'].dt.weekday
    df = df.dropna(subset=['開札日時'])

    # 数値列の補完
    num_cols = ['予定価格']
    if is_train:
        num_cols.append('最低制限価格')

    for col in num_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')
        df[col].fillna(df[col].mean(), inplace=True)

    if is_train:
        df = df.dropna(subset=['最低制限価格'])

    # カテゴリ列をダミー変数に
    df = pd.get_dummies(df, columns=['入札方式', '工事種別'], drop_first=True)

    # テストデータは学習データと同じ列構成に揃える
    if not is_train and train_columns is not None:
        for col in train_columns:
            if col not in df.columns:
                df[col] = 0
        df = df[train_columns]

    return df


# -----------------------------
# ブートストラップによる信頼区間付き予測
# -----------------------------
def bootstrap_predict_interval(X_train, y_train, X_test, n_bootstrap=100, alpha=0.05):
    preds_all = []

    for i in range(n_bootstrap):
        # ランダムにサンプリング
        idx = np.random.choice(len(X_train), size=len(X_train), replace=True)
        X_sample = X_train.iloc[idx]
        y_sample = y_train.iloc[idx]

        # Ridge回帰で学習・予測
        model = Ridge(alpha=1.0)
        model.fit(X_sample, y_sample)
        preds = model.predict(X_test)
        preds_all.append(preds)

    preds_array = np.array(preds_all)
    lower = np.percentile(preds_array, 100 * (alpha / 2), axis=0)
    upper = np.percentile(preds_array, 100 * (1 - alpha / 2), axis=0)
    mean = np.mean(preds_array, axis=0)

    return mean, lower, upper


# -----------------------------
# 結果を書き出す（信頼区間と比率付き）
# -----------------------------
def 書き出し(mean, lower, upper, test_raw):
    output = test_raw.copy()

    # 金額の予測（万円に変換）
    output['予測最低制限価格（万円）'] = (mean * output['予定価格']) / 10000
    output['信頼区間_下限（万円）'] = (lower * output['予定価格']) / 10000
    output['信頼区間_上限（万円）'] = (upper * output['予定価格']) / 10000

    # 比率（%に変換）
    output['予測制限率（%）'] = mean * 100
    output['下限制限率（%）'] = lower * 100
    output['上限制限率（%）'] = upper * 100

    # 予定価格も万円単位に変換
    output['予定価格（万円）'] = output['予定価格'] / 10000

    # 並び替え＆出力
    output[['工事名', '予定価格（万円）',
            '予測最低制限価格（万円）', '信頼区間_下限（万円）', '信頼区間_上限（万円）',
            '予測制限率（%）', '下限制限率（%）', '上限制限率（%）']] \
        .to_csv("予測結果.csv", index=False, encoding="utf-8-sig")

    print("✅ 予測結果を書き出しました → 予測結果.csv")


# -----------------------------
# メイン処理
# -----------------------------
def main():
    if len(sys.argv) != 3:
        print("使い方: python analist.py <学習用CSV> <予測用CSV>")
        sys.exit(1)

    train_path = sys.argv[1]
    test_path = sys.argv[2]

    # データ読み込み
    df_train_raw, df_test_raw = load_data(train_path, test_path)

    # 前処理（学習用）
    df_train = preprocess(df_train_raw, is_train=True)
    X = df_train.drop(columns=['工事名', '開札日時', '契約相手', '最低制限価格'], errors='ignore')
    y = df_train['制限率']
    train_columns = X.columns.tolist()

    # 前処理（テスト用）
    df_test = preprocess(df_test_raw, is_train=False, train_columns=train_columns)
    df_test = df_test.fillna(0)  # 念のため欠損値をゼロ埋め

    # ブートストラップ予測
    mean, lower, upper = bootstrap_predict_interval(X, y, df_test, n_bootstrap=100, alpha=0.05)

    # 書き出し
    書き出し(mean, lower, upper, df_test_raw)


if __name__ == '__main__':
    main()
