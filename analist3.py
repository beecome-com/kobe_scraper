#!/usr/bin/env python3
import sys
import pandas as pd
import numpy as np
from datetime import datetime
from sklearn.ensemble import RandomForestRegressor

# -----------------------------
# データ読み込み
# -----------------------------
def load_data(train_path: str, test_path: str):
    return pd.read_csv(train_path), pd.read_csv(test_path)

# -----------------------------
# 前処理（共通）
# -----------------------------
def preprocess(df: pd.DataFrame, is_train=True, train_cols=None):
    df = df.copy()

    # 日付を分解（年・月・曜日）
    df['開札日時'] = pd.to_datetime(df['開札日時'], errors='coerce')
    df['year']  = df['開札日時'].dt.year
    df['month'] = df['開札日時'].dt.month
    df['weekday'] = df['開札日時'].dt.weekday
    df = df.dropna(subset=['開札日時'])

    # 数値列を float に＆欠損補完
    num_cols = ['予定価格']
    if is_train:
        num_cols.append('最低制限価格')
    for col in num_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')
        df[col].fillna(df[col].mean(), inplace=True)
    if is_train:
        df = df.dropna(subset=['最低制限価格'])

    # カテゴリ → ダミー
    df = pd.get_dummies(df, columns=['入札方式', '工事種別'], drop_first=True)

    # テストデータの列合わせ
    if not is_train and train_cols is not None:
        for col in train_cols:
            if col not in df.columns:
                df[col] = 0
        df = df[train_cols]

    return df

# -----------------------------
# RandomForest + ブートストラップ予測
# -----------------------------
def rf_bootstrap_interval(X_train, y_train, X_test,
                          n_boot=100, alpha=0.05):
    preds_all = []

    for _ in range(n_boot):
        idx = np.random.choice(len(X_train), len(X_train), replace=True)
        rf = RandomForestRegressor(
                n_estimators=400,
                max_depth=None,
                min_samples_leaf=2,
                random_state=None,
                n_jobs=-1)
        rf.fit(X_train.iloc[idx], y_train.iloc[idx])
        preds_all.append(rf.predict(X_test))

    arr = np.array(preds_all)          # shape (n_boot, n_test)
    mean  = arr.mean(axis=0)
    lower = np.percentile(arr, 100 * alpha/2, axis=0)
    upper = np.percentile(arr, 100 * (1-alpha/2), axis=0)
    return mean, lower, upper

# -----------------------------
# 結果を書き出し（万円 & 比率）
# -----------------------------
def save_result(mean, lower, upper, test_raw):
    out = test_raw.copy()

    # 予測値を価格（万円）へ
    out['予測最低制限価格（万円）'] = (mean  * out['予定価格']) / 10000
    out['信頼区間_下限（万円）']   = (lower * out['予定価格']) / 10000
    out['信頼区間_上限（万円）']   = (upper * out['予定価格']) / 10000

    # 比率（%）
    out['予測制限率（%）']   = mean  * 100
    out['下限制限率（%）']   = lower * 100
    out['上限制限率（%）']   = upper * 100

    # 予定価格を万円に
    out['予定価格（万円）'] = out['予定価格'] / 10000

    out[['工事名', '予定価格（万円）',
         '予測最低制限価格（万円）', '信頼区間_下限（万円）', '信頼区間_上限（万円）',
         '予測制限率（%）', '下限制限率（%）', '上限制限率（%）']] \
        .to_csv("予測結果_RF_信頼区間付き.csv",
                index=False, encoding="utf-8-sig")

    print("✅ 予測結果を書き出しました → 予測結果_RF_信頼区間付き.csv")

# -----------------------------
# メイン
# -----------------------------
def main():
    if len(sys.argv) != 3:
        print("使い方: python analist_rf.py <学習CSV> <テストCSV>")
        sys.exit(1)

    train_csv, test_csv = sys.argv[1], sys.argv[2]
    df_train_raw, df_test_raw = load_data(train_csv, test_csv)

    # 前処理
    df_train = preprocess(df_train_raw, is_train=True)
    X_train  = df_train.drop(columns=['工事名', '開札日時', '契約相手',
                                      '最低制限価格'], errors='ignore')
    y_train  = df_train['制限率']       # 0〜1 の割合
    df_test  = preprocess(df_test_raw, is_train=False,
                           train_cols=X_train.columns.tolist())
    df_test = df_test.fillna(0)

    # RF ブートストラップ予測
    mean, lower, upper = rf_bootstrap_interval(X_train, y_train, df_test,
                                               n_boot=100, alpha=0.05)

    # 書き出し
    save_result(mean, lower, upper, df_test_raw)

if __name__ == '__main__':
    main()
