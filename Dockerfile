FROM python:3.12

WORKDIR /app

COPY app/* /app/

ENTRYPOINT ["python", "app"]
