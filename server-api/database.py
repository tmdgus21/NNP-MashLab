import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

env_file = Path(__file__).resolve().parent / ".env.local"
load_dotenv(env_file)  # .env.local 파일의 값을 프로그램이 읽을 수 있게 불러옴

database_url = os.getenv("DATABASE_URL")  # 불러온 값 중 DATABASE_URL을 가져옴
if not database_url:
    raise RuntimeError("server-api/.env.local에 DATABASE_URL이 없습니다.")

engine = create_engine(database_url)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()