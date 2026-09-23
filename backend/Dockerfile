FROM python:3.11-alpine

WORKDIR /app

# Устанавливаем зависимости для сборки некоторых Python пакетов, если понадобятся
RUN apk add --no-cache gcc musl-dev libffi-dev

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Создаем директорию для постоянного хранения базы данных SQLite
RUN mkdir -p /data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
