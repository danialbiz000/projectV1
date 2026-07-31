FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    "fastapi>=0.110" "uvicorn[standard]>=0.29" "sqlalchemy>=2.0" \
    "pydantic>=2.6" "pydantic-settings>=2.2" "pyjwt>=2.8" \
    "email-validator>=2.1" "psycopg2-binary>=2.9"

COPY app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
