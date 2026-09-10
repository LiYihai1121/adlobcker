FROM python:3.11-slim

WORKDIR /app

# 先装依赖（利用层缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 再拷代码
COPY . .

# 数据目录（SQLite 持久化）
RUN mkdir -p /app/data
ENV ADBLOCK_DB_PATH=/app/data/adblock.db

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
