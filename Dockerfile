# syntax=docker/dockerfile:1
# Docker-образ бота MAX «IT-служба колледжа»
# Контекст сборки — корень репозитория (чтобы пакет max_bot был виден целиком):
#   docker build -t max-it-bot .

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Зависимости сначала — для кэширования layered build
COPY max_bot/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходники пакета
COPY max_bot/ ./max_bot/

# Непривилегированный пользователь
RUN useradd --create-home --shell /usr/sbin/nologin botuser
USER botuser

# Порт webhook-сервера (aiohttp)
EXPOSE 8080

# Точка входа: запуск webhook-сервера
CMD ["python", "-m", "max_bot.main"]
