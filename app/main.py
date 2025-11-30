from fastapi import FastAPI
from app.apis.v1 import router_evaluate, router_asr, router_baseline
from fastapi.middleware.cors import CORSMiddleware  # 1. CORS 미들웨어 임포트

app = FastAPI(title="CrewVoice Evaluation API (Python)")

# 2. CORS 미들웨어 설정 추가
# (app = FastAPI() 선언 바로 다음에 위치해야 합니다)

# Spring Boot 서버(예: 8080)나 React/Vue 개발서버(예: 3000)의 주소를 등록
origins = [
    "http://localhost:8080",  # Spring Boot가 서빙하는 프론트엔드 주소
    "http://localhost:3000",  # (선택) React/Vue 등 프론트엔드 개발 서버 주소
    "http://127.0.0.1:8080",
    "http://127.0.0.1:3000",
    "https://crew-voice-client-vercel.vercel.app/",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,       # 3. 허용할 출처 목록
    allow_credentials=True,    # 4. 쿠키를 허용할지 여부
    allow_methods=["*"],       # 5. 허용할 HTTP 메소드 ("*"는 모두 허용)
    allow_headers=["*"],       # 6. 허용할 HTTP 헤더 ("*"는 모두 허용)
)

@app.get("/health", tags=["Monitoring"])
async def health_check():
    """Spring Boot가 이 서버의 생존 여부를 확인할 API"""
    return {"status": "ok"}

# Spring Boot가 호출할 메인 API 라우터
app.include_router(
    router_evaluate.router,
    prefix="/api/v1",  # /api/v1/evaluate 주소로 API 등록
    tags=["Evaluation"]
)

# ASR 분석 API 라우터
app.include_router(
    router_asr.router,
    prefix="/api/v1/asr",  # /api/v1/asr/analyze 주소로 API 등록
    tags=["ASR Analysis"]
)

# Baseline 관리 API 라우터
app.include_router(
    router_baseline.router,
    prefix="/api/v1/baseline",  # /api/v1/baseline/generate 주소로 API 등록
    tags=["Baseline Management"]
)