FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir -r requirements.txt
# Full app tree: db_v21/, alembic.v21.ini, migrations_v21/, workflow/admin, tests
COPY . .
RUN test -f alembic.v21.ini \
 && test -d migrations_v21/versions \
 && test -d db_v21 \
 && test -f models.py
# 내부에서 8000번 포트로 서버 실행
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
