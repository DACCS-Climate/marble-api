FROM python:3.13-alpine

COPY marble_api/ /app/marble_api/
COPY pyproject.toml /app/pyproject.toml

WORKDIR /app

RUN pip install .[prod] && rm pyproject.toml

CMD ["uvicorn", "marble_api:app", "--host", "0.0.0.0", "--port", "8000", "--root-path", ""]
