FROM python:3.13-alpine
WORKDIR /code
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt
COPY ./return-line-notify /code/return-line-notify

HEALTHCHECK --interval=1m --timeout=5s --start-period=20s --retries=1 CMD curl -S --fail http://127.0.0.1:3333/health

EXPOSE 3333
CMD ["uvicorn", "return-line-notify.main:app", "--host", "0.0.0.0", "--port", "3333"]