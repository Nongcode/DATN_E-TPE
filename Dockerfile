FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/
RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . /app/

RUN if [ -d /app/media ]; then cp -a /app/media /app/initial_media; fi

EXPOSE 8000

CMD ["sh", "/app/docker-entrypoint.sh"]
