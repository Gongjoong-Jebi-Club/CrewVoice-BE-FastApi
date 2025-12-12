# CrewVoice Evaluation API (FastAPI)

CrewVoice 프로젝트의 음성 평가 API 서버입니다. Spring Boot 백엔드로부터 음성 파일과 메타데이터를 받아 평가 결과를 반환합니다.

## 프로젝트 구조

```
CrewVoice-BE-FastApi/
├── app/
│   ├── main.py                     # FastAPI 애플리케이션 진입점
│   │
│   ├── apis/                       # API 라우터
│   │   └── v1/
│   │       └── router_evaluate.py  # 평가 API 라우터 (외부 요청 접수)
│   │
│   ├── agents/                     # 평가 항목 전문 에이전트
│   │   └── __init__.py
│   │
│   ├── orchestrators/              # 에이전트 조율 및 피드백 생성
│   │   └── __init__.py
│   │
│   ├── schemas/                    # Pydantic 스키마 (API 요청/응답)
│   │   ├── __init__.py
│   │   └── evaluation.py
│   │
│   ├── services/                   # Spring Boot 연동 서비스
│   │   └── __init__.py
│   │
│   ├── core/                       # 핵심 설정
│   │   └── __init__.py
│   │
│   ├── middleware/                 # 미들웨어
│   │   └── __init__.py
│   │
│   └── utils/                      # 유틸리티
│       └── __init__.py
│
├── pyproject.toml                  # 프로젝트 메타데이터 및 의존성 관리
├── uv.lock                         # uv 의존성 잠금 파일
├── .python-version                 # Python 3.12
├── .env.example                    # 환경변수 템플릿
├── .gitignore                      # Git 제외 파일 목록
└── README.md
```

### 디렉토리 역할

#### 📁 `app/apis/`
- **역할**: 외부 요청을 받는 API 엔드포인트 정의
- **설명**: FastAPI 라우터를 통해 HTTP 요청을 처리하고, 비즈니스 로직은 다른 레이어로 위임
- **예시**: 평가 API 엔드포인트 (`/api/v1/evaluate`)

#### 📁 `app/agents/`
- **역할**: 6개 평가 항목을 담당하는 전문 에이전트 모음
- **설명**: 각 에이전트는 특정 평가 항목(발음, 쉼, 억양, 강세, 톤, 속도)을 독립적으로 분석
- **구현 예정**:
  - `base_agent.py` - 공통 인터페이스 (BaseAgent 추상 클래스)
  - `pronunciation_agent.py` - Azure Pronunciation Assessment
  - `pause_agent.py` - Azure Offset/Duration 기반 쉼 분석
  - `intonation_agent.py` - parselmouth F0 분석
  - `accent_agent.py` - parselmouth Intensity 분석
  - `tone_agent.py` - parselmouth 종합 분석 (pitch range 등)
  - `speed_agent.py` - SPS 규칙 기반 속도 계산
  - 위 파일 구조는 파일 리펙토링 시 임의로 지정. 폴더 안에 파일 구조는 로직 담당이 임의로 지정.

#### 📁 `app/orchestrators/`
- **역할**: 여러 에이전트를 조율하고 최종 피드백 생성
- **설명**:
  - `evaluation_orchestrator.py` - 6개 에이전트를 병렬/순차 실행하고 결과 수집
  - `feedback_generator.py` - LLM을 활용해 에이전트 결과를 종합하여 사용자 친화적 피드백 생성

#### 📁 `app/schemas/`
- **역할**: API 요청/응답 데이터 검증 및 직렬화
- **설명**: Pydantic 모델을 사용한 타입 안전성 보장
- **예시**: `EvaluationRequest`, `EvaluationResponse`, `AgentResponse`

#### 📁 `app/services/`
- **역할**: 외부 시스템(Spring Boot, S3)과의 통신
- **설명**:
  - `springboot_client.py` - Spring Boot API 호출 전담 (httpx 사용)
  - `storage_service.py` - S3 presigned URL 처리

#### 📁 `app/core/`
- **역할**: 애플리케이션 핵심 설정 및 구성
- **설명**:
  - `config.py` - 환경변수, Azure/OpenAI API 키 관리
  - `logging_config.py` - 로깅 설정

#### 📁 `app/middleware/`
- **역할**: 요청/응답 처리 과정에서 공통 로직 실행
- **설명**:
  - `cors.py` - CORS 설정
  - `request_logging.py` - 요청/응답 로깅

#### 📁 `app/utils/`
- **역할**: 범용 유틸리티 함수 모음
- **설명**:
  - `audio_processing.py` - 샘플링 레이트 변환, 포맷 변환
  - `file_handler.py` - 임시 파일 관리, S3 연동
  - `metrics.py` - SPS, Duration 계산 공통 함수

## 주요 기능

### API 엔드포인트

#### 1. Health Check
- **URL**: `GET /health`
- **설명**: 서버 상태 확인용 API
- **응답 예시**:
  ```json
  {
    "status": "ok"
  }
  ```

#### 2. 음성 평가 API
- **URL**: `POST /api/v1/evaluate`
- **Content-Type**: `multipart/form-data`
- **Request Parameters**:
  - `audio_file`: 음성 파일 (UploadFile)
  - `script_id`: 스크립트 ID (int)
  - `user_id`: 사용자 ID (string)

- **Response** (`EvaluationResponse`):
  ```json
  {
    "eval_id": "mock-eval-999",
    "pron_accuracy": 85.0,
    "speed_wpm": 140.0,
    "feedback_summary": "[Mock] FastAPI 서버 연동 테스트 성공",
    "error_words": ["test", "mock"]
  }
  ```

## 설치 방법

### 사전 요구사항
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (Python 패키지 관리자)

uv 설치:
```bash
# Linux/Mac
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 1. 저장소 클론
```bash
git clone https://github.com/Gongjoong-Jebi-Club/CrewVoice-BE-FastApi.git
cd CrewVoice-BE-FastApi
```

### 2. 의존성 설치
```bash
# pyproject.toml 기반 자동 설치 (권장)
uv sync
```

또는 수동으로 설치:
```bash
# 가상환경 생성 및 Python 버전 확인
uv venv

# 가상환경 활성화
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 의존성 설치 (pyproject.toml에서 자동 읽음)
uv sync
```

## 실행 방법

### 개발 서버 실행
```bash
# uv run을 사용한 실행 (권장)
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

또는 가상환경 활성화 후 실행:
```bash
source .venv/bin/activate  # Windows: .venv\Scripts\activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**옵션 설명**:
- `--reload`: 코드 변경 시 자동 재시작 (개발 환경용)
- `--host 0.0.0.0`: 모든 네트워크 인터페이스에서 접근 허용
- `--port 8000`: 포트 번호 지정 (기본값: 8000)

### 서버 실행 확인
브라우저 또는 curl로 다음 URL에 접속하여 확인:

```bash
# Health Check
curl http://localhost:8000/health

# API 문서 (Swagger UI)
http://localhost:8000/docs

# API 문서 (ReDoc)
http://localhost:8000/redoc
```

## CORS 설정

현재 다음 Origin에서의 요청을 허용하도록 설정되어 있습니다:
- `http://localhost:8080` (Spring Boot 프론트엔드)
- `http://localhost:3000` (React/Vue 개발 서버)
- `http://127.0.0.1:8080`
- `http://127.0.0.1:3000`
- `https://crew-voice-client-vercel.vercel.app/`

추가 Origin이 필요한 경우 [app/main.py](app/main.py)의 `origins` 리스트를 수정하세요.

## API 테스트

### cURL 예시
```bash
curl -X POST "http://localhost:8000/api/v1/evaluate" \
  -H "Content-Type: multipart/form-data" \
  -F "audio_file=@/path/to/audio.wav" \
  -F "script_id=1" \
  -F "user_id=test_user"
```

### Python requests 예시
```python
import requests

url = "http://localhost:8000/api/v1/evaluate"

files = {
    'audio_file': open('audio.wav', 'rb')
}
data = {
    'script_id': 1,
    'user_id': 'test_user'
}

response = requests.post(url, files=files, data=data)
print(response.json())
```

## 기술 스택

- **FastAPI** 0.115.5 - 고성능 웹 프레임워크
- **Uvicorn** 0.32.1 - ASGI 서버
- **Pydantic** 2.10.3 - 데이터 검증 및 스키마 정의
- **Python** 3.12+
- **uv** - 초고속 Python 패키지 관리자

## 개발 참고사항

### 현재 상태
- Mock 데이터 반환 (AI 평가 로직 미구현)
- Spring Boot와의 연동 테스트용 API 구현 완료

## 문제 해결

### 포트 이미 사용 중 에러
다른 포트 번호를 사용하세요:
```bash
uv run uvicorn app.main:app --reload --port 8001
```

### 모듈을 찾을 수 없음 에러
의존성을 다시 동기화하세요:
```bash
uv sync
```

### 패키지 관리 방법

#### 패키지 추가
```bash
# 단일 패키지 추가 (pyproject.toml에 자동 추가됨)
uv add <package-name>

# 여러 패키지 추가
uv add <package1> <package2> <package3>

# 특정 버전 지정
uv add "fastapi==0.115.5"

# 개발 의존성으로 추가
uv add --dev pytest black ruff
```

#### 패키지 제거
```bash
uv remove <package-name>
```

#### 의존성 확인
```bash
# 설치된 패키지 목록
uv pip list

# 의존성 트리 확인
uv pip tree
```

### pyproject.toml 수정 후
`pyproject.toml`을 직접 수정한 경우:
```bash
uv sync
```
