FROM python:3.13-slim
WORKDIR /code

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt
COPY ./return_line_notify /code/return_line_notify

# /health は MQTT が繋がっていて直近に受信があるときだけ 200 を返す
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -fsS http://127.0.0.1:3333/health

EXPOSE 3333
CMD ["uvicorn", "return_line_notify.main:app", "--host", "0.0.0.0", "--port", "3333"]
