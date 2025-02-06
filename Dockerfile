FROM python:3.13-alpine

COPY requirements.txt requirements.prod.txt /app/

RUN python -m pip install -r /app/requirements.prod.txt

COPY app/ /app/app/

WORKDIR /app

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--root-path", ""]
