from fastapi import FastAPI
from app.apis.v1 import router_evaluate, router_submission
from fastapi.middleware.cors import CORSMiddleware  # 1. CORS 미들웨어 임포트

app = FastAPI(title="CrewVoice Evaluation API (Python)")

# 2. CORS 미들웨어 설정 추가
# (app = FastAPI() 선언 바로 다음에 위치해야 합니다)

# Spring Boot 설정과 동일하게 허용할 출처(Origin) 목록을 설정합니다.
origins = [
    # 개발 환경
    "http://localhost:5173",  # Vite 개발 서버
    "http://localhost:3000",  # React/Vue 등 프론트엔드 개발 서버
    "http://localhost:8000",  # FastAPI 개발 서버
    "http://localhost:8080",  # Spring Boot 개발 서버

    # 배포 환경
    "https://server.crewvoice.cloud",   # Spring Boot 배포 서버
    "https://ai.crewvoice.cloud",       # FastAPI 배포 서버
    "https://chat.crewvoice.cloud",     # Chat 배포 서버
    "https://www.crewvoice.cloud",      # 프로덕션 메인
    "https://crew-voice-client-vercel.vercel.app" # Vercel 배포 클라이언트
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

# 음성 제출 API 라우터 (React 클라이언트 직접 호출)
app.include_router(
    router_submission.router,
    prefix="/api/v1",  # /api/v1/analysis/submit 주소로 API 등록
    tags=["Submission"]
)