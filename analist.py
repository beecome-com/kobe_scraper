#!/usr/bin/env python3
import sys
import pandas as pd
import numpy as np
from datetime import datetime
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score


def load_data(train_path: str, test_path: str):
    """CSVファイルを読み込み、DataFrameを返す"""
    df_train = pd.read_csv(train_path)
    df_test = pd.read_csv(test_path)
    return df_train, df_test


def preprocess(df: pd.DataFrame, is_train: bool = True, train_columns=None):
    df = df.copy()

    # 日付型に変換
    df['開札日時'] = pd.to_datetime(df['開札日時'], errors='coerce')
    df['year'] = df['開札日時'].dt.year
    df['month'] = df['開札日時'].dt.month
    df['weekday'] = df['開札日時'].dt.weekday
    df = df.dropna(subset=['開札日時'])

    # 数値変換 + 欠損補完
    num_cols = ['参加数', '決定金額', '予定価格']
    if is_train:
        num_cols.append('最低制限価格')

    for col in num_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')
        df[col].fillna(df[col].mean(), inplace=True)

    if is_train:
        df = df.dropna(subset=['最低制限価格'])

    # ワンホットエンコーディング
    df = pd.get_dummies(df, columns=['入札方式', '工事種別'], drop_first=True)

    # testセットなら学習時の列構成に合わせる
    if not is_train and train_columns is not None:
        for col in train_columns:
            if col not in df.columns:
                df[col] = 0  # 存在しないカテゴリは0で補完
        df = df[train_columns]  # 列の順序も合わせる

    return df


def train_model(X, y):
    """Ridge回帰 + グリッドサーチでモデル訓練"""
    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)

    model = Ridge()
    param_grid = {'alpha': np.logspace(-3, 3, 7)}

    grid = GridSearchCV(model, param_grid, cv=5, scoring='neg_mean_absolute_error', n_jobs=-1)
    grid.fit(X_train, y_train)

    best_model = grid.best_estimator_
    print(f"Best alpha: {grid.best_params_['alpha']}")

    y_pred = best_model.predict(X_val)
    mae = mean_absolute_error(y_val, y_pred)
    r2 = r2_score(y_val, y_pred)
    print(f"Validation MAE: {mae:.2f}")
    print(f"Validation R2: {r2:.3f}")

    # 全データで再学習
    best_model.fit(X, y)
    return best_model


def predict_and_save(model, df_test: pd.DataFrame, test_raw: pd.DataFrame):
    preds = model.predict(df_test)
    output = test_raw.copy()
    output['predicted_min_price'] = preds
    output[['工事名', 'predicted_min_price']].to_csv('predicted_min_price.csv', index=False, encoding='utf-8-sig')
    print("✅ 予測結果を書き出しました → predicted_min_price.csv")


def main():
    if len(sys.argv) != 3:
        print("Usage: python analist.py <train_csv> <test_csv>")
        sys.exit(1)

    train_path = sys.argv[1]
    test_path = sys.argv[2]

    # データ読み込み
    df_train_raw, df_test_raw = load_data(train_path, test_path)

    # 前処理（学習用）
    df_train = preprocess(df_train_raw, is_train=True)
    X = df_train.drop(columns=['工事名', '開札日時', '契約相手', '最低制限価格'], errors='ignore')
    y = df_train['最低制限価格']

    # 特徴量カラム名を保存
    train_columns = X.columns.tolist()

    # 前処理（テスト用）→ 最低制限価格列を除いたカラムで構成
    df_test = preprocess(df_test_raw, is_train=False, train_columns=train_columns)

    # 👇このすぐ下に追加！
    df_test = df_test.fillna(0)

    # モデル訓練
    model = train_model(X, y)

    # 予測＆保存
    predict_and_save(model, df_test, df_test_raw)


if __name__ == '__main__':
    main()
