FROM python:3.12-slim

WORKDIR /app

# Копируем зависимости и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем файлы приложения
COPY bot.py .
COPY rus.txt .

# Создаём директорию для логов
RUN mkdir -p /app/logs
VOLUME /app/logs

# Запускаем бота
CMD ["python", "bot.py"]
