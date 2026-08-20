# Python 3.11をベースイメージとして使用
FROM python:3.11-slim

# 作業ディレクトリを/appに設定
WORKDIR /app

# requirements.txtをコンテナにコピー
COPY requirements.txt .

# requirements.txtに記載されたライブラリをインストール
RUN pip install --no-cache-dir -r requirements.txt

# insightディレクトリ全体をコンテナの作業ディレクトリにコピー
COPY ./insight ./insight

# ADK Web UIを起動
CMD adk web --host 0.0.0.0 --port ${PORT:-8080} insight
