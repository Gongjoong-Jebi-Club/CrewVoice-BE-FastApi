# CrewVoice Evaluation API (FastAPI)

CrewVoice 프로젝트의 음성 평가 API 서버입니다. Spring Boot 백엔드로부터 음성 파일과 메타데이터를 받아 평가 결과를 반환합니다.

## 프로젝트 구조

```
CrewVoice-BE-FastApi/
├── app/
│   ├── main.py              # FastAPI 애플리케이션 진입점
│   ├── apis/
│   │   └── v1/
│   │       └── router_evaluate.py  # 평가 API 라우터
│   ├── schemas/
│   │   └── evaluation.py    # Pydantic 스키마 정의
│   ├── core/                # 핵심 설정 (추후 확장)
│   └── services/            # 비즈니스 로직 (추후 확장)
├── pyproject.toml           # 프로젝트 메타데이터 및 의존성 관리
├── uv.lock                  # uv 의존성 잠금 파일
├── .python-version          # Python 버전 지정
├── .gitignore               # Git 제외 파일 목록
└── README.md
```

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
