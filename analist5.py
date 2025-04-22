#!/usr/bin/env python3
# analist_xgb.py  ― 制限率を予測し、XGBoost + 非対称損失 + ブートストラップで
#                  信頼区間を算出（下側誤差に 2 倍ペナルティ）

import sys, warnings
import numpy as np
import pandas as pd
import xgboost as xgb               # pip install xgboost

warnings.filterwarnings("ignore")

# -----------------------------
# 1. データ読み込み
# -----------------------------
def load_data(train_csv: str, test_csv: str):
    return pd.read_csv(train_csv), pd.read_csv(test_csv)

# -----------------------------
# 2. 前処理（共通）
# -----------------------------
def preprocess(df: pd.DataFrame, *, is_train=True, train_cols=None):
    df = df.copy()

    # 日付を分解
    df['開札日時'] = pd.to_datetime(df['開札日時'], errors='coerce')
    df['year']    = df['開札日時'].dt.year
    df['month']   = df['開札日時'].dt.month
    df['weekday'] = df['開札日時'].dt.weekday
    df = df.dropna(subset=['開札日時'])

    # 数値列
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
        for c in train_cols:
            if c not in df.columns:
                df[c] = 0
        df = df[train_cols]

    return df

# -----------------------------
# 3. 非対称二乗誤差（下側 2 倍）
# -----------------------------
def asym_square(preds, dtrain, k=10):
    y = dtrain.get_label()
    err = preds - y
    grad = np.where(err < 0, 2*k*err, 2 * err)      # 勾配
    hess = np.where(err < 0, 2*k, 2.0)              # ヘッセ
    return grad, hess

# -----------------------------
# 4. XGBoost + ブートストラップ信頼区間
# -----------------------------
def xgb_bootstrap_interval(X, y, X_test,
                           n_boot=50, alpha=0.01):
    y = y.clip(lower=0.90)
    mean_rate = y.mean()          # ★ 学習データの平均 ≒ 0.91〜0.92
    preds_all = []

    for _ in range(n_boot):
        idx = np.random.choice(len(X), len(X), replace=True)
        dtrain = xgb.DMatrix(X.iloc[idx], label=y.iloc[idx])
        dtest  = xgb.DMatrix(X_test)

        params = {
            'max_depth':5,
            'eta':0.05,
            'subsample':0.8,
            'colsample_bytree':0.8,
            'base_score': 0.93,#float(mean_rate),
            'verbosity':0
        }
        bst = xgb.train(params, dtrain, num_boost_round=400, obj=asym_square)
        preds_all.append(bst.predict(dtest))

    arr   = np.array(preds_all)          # (n_boot, n_test)
    mean  = arr.mean(axis=0)
    lower = np.percentile(arr, 100*alpha/2, axis=0)
    upper = np.percentile(arr, 100*(1-alpha/2), axis=0)
    return mean, lower, upper

# -----------------------------
# 5. 結果保存（万円 & 比率）
# -----------------------------
def save_result(mean, lower, upper, raw_df):
    out = raw_df.copy()

    out['予測最低制限価格（万円）'] = (upper  * out['予定価格']) / 10000
    out['予測制限率（%）']        = upper  * 100   

    out[['工事名', '予定価格', '予測最低制限価格（万円）',
          '予測制限率（%）']] \
        .to_csv("予測結果_XGB_非対称損失.csv",
                index=False, encoding="utf-8-sig")

    print("✅ 予測結果を書き出しました → 予測結果_XGB_非対称損失.csv")

# -----------------------------
# 6. メイン
# -----------------------------
def main():
    if len(sys.argv) != 3:
        print("使い方: python analist_xgb.py <学習CSV> <テストCSV>")
        sys.exit(1)

    train_csv, test_csv = sys.argv[1], sys.argv[2]
    train_raw, test_raw = load_data(train_csv, test_csv)

    train = preprocess(train_raw, is_train=True)
    X_train = train.drop(columns=['工事名', '開札日時', '契約相手',
                                  '最低制限価格'], errors='ignore')
    y_train = train['制限率']        # 0〜1

    test = preprocess(test_raw, is_train=False,
                      train_cols=X_train.columns.tolist())

    mean, lower, upper = xgb_bootstrap_interval(
        X_train, y_train, test, n_boot=50, alpha=0.05)

    save_result(mean, lower, upper, test_raw)

if __name__ == "__main__":
    main()
