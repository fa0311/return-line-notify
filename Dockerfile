FROM python:3.13-alpine
WORKDIR /code
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt
COPY ./src /code/src
CMD ["uvicorn", "return-line-notify.main:app", "--host", "0.0.0.0", "--port", "3333"]