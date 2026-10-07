from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "success", "message": "Caddy를 통과하여 FastAPI에 정상 연결되었습니다!"}