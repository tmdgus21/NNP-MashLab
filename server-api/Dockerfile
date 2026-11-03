# Build context is the REPOSITORY ROOT (docker-compose.yml: context ".", dockerfile server-api/Dockerfile)
# so that experiments/potato-agent can be installed as a real package.
FROM python:3.11-slim
WORKDIR /app
COPY server-api/requirements.txt server-api/requirements.lock ./
COPY experiments/potato-agent /opt/potato-agent
# One resolver pass with the lock as constraints: a version conflict between the
# server and potato_agent fails the BUILD, not the first request.
RUN pip install --no-cache-dir -r requirements.txt  && pip install --no-cache-dir -c requirements.lock /opt/potato-agent  && python -c "import potato_agent, langgraph.checkpoint.postgres, langgraph.checkpoint.sqlite"
# Full app tree: db_v21/, alembic.v21.ini, migrations_v21/, workflow/admin, tests
COPY server-api/ .
RUN test -f alembic.v21.ini  && test -d migrations_v21/versions  && test -d db_v21  && test -f models.py  && test -f agent_worker_main.py
# 내부에서 8000번 포트로 서버 실행 (Agent Worker는 같은 이미지를 `python agent_worker_main.py`로 실행)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
