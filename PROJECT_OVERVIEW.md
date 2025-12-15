# 🎤 CrewVoice FastAPI - 음성 평가 시스템

## 📋 목차
1. [프로젝트 개요](#프로젝트-개요)
2. [프로젝트 구조](#프로젝트-구조)
3. [주요 기능](#주요-기능)
4. [API 엔드포인트](#api-엔드포인트)
5. [음성 분석 에이전트](#음성-분석-에이전트)
6. [데이터 흐름](#데이터-흐름)
7. [환경 설정](#환경-설정)
8. [로컬 개발](#로컬-개발)
9. [배포](#배포)
10. [파일별 상세 설명](#파일별-상세-설명)

---

## 📌 프로젝트 개요

**CrewVoice FastAPI**는 음성 파일을 분석하여 발음, 억양, 속도, 톤 등 6가지 지표를 평가하고 AI 피드백을 제공하는 음성 평가 시스템입니다.

### 핵심 기술 스택
- **Framework**: FastAPI 0.115.12
- **음성 인식**: Azure Speech SDK
- **음성 분석**: librosa, numpy, scipy
- **AI 피드백**: OpenAI GPT-4
- **비동기 처리**: asyncio, BackgroundTasks
- **배포**: AWS EC2, Nginx, Systemd

### 시스템 특징
- ✅ **7개 전문 에이전트**를 통한 다차원 음성 분석
- ✅ **비동기 처리**로 빠른 응답 시간 (즉시 200 OK 반환)
- ✅ **Spring Boot 연동** (camelCase ↔ snake_case 자동 변환)
- ✅ **롤백 메커니즘**이 포함된 안전한 배포
- ✅ **자동 임시파일 정리**로 디스크 관리

---

## 📂 프로젝트 구조

```
FastApi/
├── app/                          # 메인 애플리케이션
│   ├── main.py                   # FastAPI 앱 진입점, CORS 설정
│   ├── agents/                   # 음성 분석 에이전트
│   │   ├── analyzers/            # 7개 분석 에이전트
│   │   │   ├── validate.py       # [1] 완전성 & 유사도 검증
│   │   │   ├── accent.py         # [2] 억양 분석
│   │   │   ├── pronunciation.py  # [3] 발음 정확도
│   │   │   ├── pause.py          # [4] 적절한 쉼 분석
│   │   │   ├── intonation.py     # [5] 억양 패턴 분석
│   │   │   ├── speed.py          # [6] 말하기 속도
│   │   │   └── tone.py           # [7] 음색 분석
│   │   ├── managers/             # 에이전트 관리
│   │   │   ├── analyzer_manager.py  # 에이전트 조율 및 병렬 실행
│   │   │   └── baseline_manager.py  # Azure STT 기본 매니저
│   │   └── utils/
│   │       └── comment_generator.py # AI 피드백 생성 (OpenAI)
│   ├── apis/                     # API 라우터
│   │   ├── router_springboot.py  # Spring Boot 연동 API
│   │   └── v1/                   # V1 API (레거시)
│   │       ├── router_evaluate.py
│   │       └── router_submission.py
│   ├── schemas/                  # Pydantic 스키마
│   │   ├── springboot_evaluation.py  # Spring Boot 요청/응답
│   │   ├── evaluation.py
│   │   └── submission.py
│   ├── services/                 # 비즈니스 로직
│   │   └── submission_service.py
│   └── utils/                    # 유틸리티
├── deployment/                   # 배포 설정
│   ├── deploy.sh                 # 배포 스크립트 (롤백 포함)
│   ├── fastapi.service           # Systemd 서비스 설정
│   ├── nginx-fastapi.conf        # Nginx 리버스 프록시
│   ├── DEPLOYMENT_GUIDE.md       # 배포 가이드
│   ├── SPRINGBOOT_INTEGRATION.md # Spring Boot 연동 가이드
│   └── AUDIO_FILE_LIFECYCLE.md   # 오디오 파일 라이프사이클
├── .env.example                  # 환경 변수 템플릿
├── .env.production               # 프로덕션 환경 변수 템플릿
├── requirements.txt              # Python 의존성
└── Dockerfile                    # Docker 이미지 빌드

무시되는 파일들:
├── .env                          # 실제 API 키 (gitignore)
├── .venv/                        # 가상환경 (gitignore)
├── debug_audio/                  # 디버그 음성 파일 (gitignore)
└── .backups/                     # 배포 백업 (gitignore)
```

---

## 🎯 주요 기능

### 1. 음성 평가 API (Spring Boot 연동)
- **엔드포인트**: `POST /api/evaluate`
- **기능**: Spring Boot에서 음성 평가 요청을 받아 비동기 처리
- **처리 흐름**:
  1. Spring Boot → FastAPI: 평가 요청 (JSON)
  2. FastAPI → 즉시 200 OK 반환 (BackgroundTasks)
  3. S3에서 WAV 파일 다운로드
  4. 7개 에이전트 병렬 분석 (2-3분 소요)
  5. AI 피드백 생성 (OpenAI GPT-4)
  6. FastAPI → Spring Boot: 콜백 전송 (결과)

### 2. 7개 전문 에이전트 분석
각 에이전트는 독립적으로 특정 음성 특징을 평가합니다:

| # | 에이전트 | 평가 항목 | 점수 범위 |
|---|---------|----------|----------|
| 1 | **Validate** | 완전성 & 유사도 | 0-100 |
| 2 | **Accent** | 억양 자연스러움 | 0-100 |
| 3 | **Pronunciation** | 발음 정확도 | 0-100 |
| 4 | **Pause** | 적절한 쉼 | 0-100 |
| 5 | **Intonation** | 억양 패턴 | 0-100 |
| 6 | **Speed** | 말하기 속도 | 0-100 |
| 7 | **Tone** | 음색 품질 | 0-100 |

**총점**: 600점 만점 (각 100점)

### 3. AI 피드백 생성
- OpenAI GPT-4를 사용하여 자연어 피드백 생성
- 에이전트 분석 결과를 종합하여 개선점 제시
- 500자 이내로 요약

### 4. 파일 관리
- **S3 다운로드**: Pre-signed URL에서 WAV 파일 다운로드
- **임시 저장**: `/tmp/tmp*.wav` (분석 중에만 존재)
- **자동 삭제**: 분석 완료 후 즉시 삭제 (finally 블록)
- **디버그 모드**: `DEBUG_SAVE_AUDIO=true` 시 `debug_audio/` 폴더에 영구 저장

---

## 🔌 API 엔드포인트

### 1. Spring Boot 연동 API

#### `POST /api/evaluate`
**설명**: Spring Boot에서 음성 평가 요청 수신

**요청 (Request)**:
```json
{
  "taskId": "uuid-task-id",
  "audioUrl": "https://s3.amazonaws.com/bucket/audio.wav",
  "script": "평가할 대본 텍스트",
  "language": "ko-KR",
  "callbackUrl": "http://server.crewvoice.cloud/api/v1/evaluations/callback"
}
```

**응답 (Response)**: 즉시 200 OK
```json
{
  "message": "Request received",
  "task_id": "uuid-task-id"
}
```

**콜백 (Callback to Spring Boot)**: 분석 완료 시
```json
{
  "task_id": "uuid-task-id",
  "status": "completed",
  "scores": {
    "score_pronunciation": 85.5,
    "score_pause": 90.2,
    "score_intonation": 88.7,
    "score_tone": 87.3,
    "score_speed": 92.1,
    "score_accent": 89.4,
    "overall_score": 88.87
  },
  "feedback_summary": "전반적으로 우수한 발음입니다..."
}
```

**에러 콜백**:
```json
{
  "task_id": "uuid-task-id",
  "status": "failed",
  "error_message": "S3 다운로드 실패: HTTP 403"
}
```

#### `GET /health`
**설명**: 헬스 체크 엔드포인트
**응답**:
```json
{
  "status": "healthy"
}
```

#### `GET /docs`
**설명**: Swagger UI 문서
**URL**: `https://ai.crewvoice.cloud/docs`

---

## 🤖 음성 분석 에이전트

### 실행 순서

```
┌─────────────────────────────────────┐
│  1. Validate (순차 실행 필수)        │
│     - Azure STT로 음성 인식         │
│     - 완전성 & 유사도 검증          │
│     - 실패 시 분석 중단             │
└──────────────┬──────────────────────┘
               │ 성공 시
               ▼
┌─────────────────────────────────────┐
│  2. Accent (순차 실행)               │
│     - Azure STT 재실행               │
│     - 억양 자연스러움 분석           │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  3-7. 병렬 실행 (5개 에이전트)       │
│     ├─ Pronunciation                │
│     ├─ Pause                        │
│     ├─ Intonation                   │
│     ├─ Speed                        │
│     └─ Tone                         │
└─────────────────────────────────────┘
```

### 각 에이전트 상세

#### 1. **Validate Agent** (`validate.py`)
**목적**: 음성이 대본과 일치하는지 검증

**분석 방법**:
- Azure Speech SDK로 음성 인식 (Continuous Recognition)
- 대본과 인식된 텍스트 비교

**평가 지표**:
- **완전성 (Completeness)**: 대본 중 몇 퍼센트를 말했는가
- **유사도 (Similarity)**: 말한 내용이 대본과 얼마나 일치하는가

**주요 기능**:
- 180초 타임아웃 설정
- 파일 핸들 명시적 해제 (Windows 호환)
- 상세 로깅 (청크별 전사 결과)

**코드 위치**: `app/agents/analyzers/validate.py`

---

#### 2. **Accent Agent** (`accent.py`)
**목적**: 억양의 자연스러움 평가

**분석 방법**:
- Azure STT로 발음 평가 API 사용
- 각 단어별 정확도, 억양 점수 수집

**평가 기준**:
- 억양이 자연스러운가
- 외국인 억양이 강하지 않은가

**코드 위치**: `app/agents/analyzers/accent.py`

---

#### 3. **Pronunciation Agent** (`pronunciation.py`)
**목적**: 발음 정확도 평가

**분석 방법**:
- Validate 또는 Accent의 Azure STT 결과 재사용
- 단어별 발음 점수 집계

**평가 기준**:
- 각 단어의 발음이 정확한가
- 평균 발음 점수

**코드 위치**: `app/agents/analyzers/pronunciation.py`

---

#### 4. **Pause Agent** (`pause.py`)
**목적**: 적절한 쉼 분석

**분석 방법**:
- Validate의 타임스탬프 데이터 활용
- 단어 간 간격 계산
- 쉼표/마침표 위치에서 쉼 확인

**평가 기준**:
- 문장 부호에서 적절히 쉬는가
- 불필요한 긴 쉼이 없는가

**코드 위치**: `app/agents/analyzers/pause.py`

---

#### 5. **Intonation Agent** (`intonation.py`)
**목적**: 억양 패턴 분석

**분석 방법**:
- librosa로 피치(pitch) 추출
- 문장 끝에서 피치 변화 분석
- 의문문/평서문 패턴 확인

**평가 기준**:
- 문장 끝 억양이 자연스러운가
- 단조로운 말투가 아닌가

**코드 위치**: `app/agents/analyzers/intonation.py`

---

#### 6. **Speed Agent** (`speed.py`)
**목적**: 말하기 속도 평가

**분석 방법**:
- librosa로 음성 구간 감지
- 단어 수 / 발화 시간 계산
- 분당 단어 수(WPM) 산출

**평가 기준**:
- 너무 빠르거나 느리지 않은가
- 적정 속도(분당 150-180단어) 유지

**코드 위치**: `app/agents/analyzers/speed.py`

---

#### 7. **Tone Agent** (`tone.py`)
**목적**: 음색 품질 평가

**분석 방법**:
- librosa로 음향 특징 추출:
  - MFCC (Mel-frequency cepstral coefficients)
  - Spectral Centroid (주파수 무게중심)
  - Zero Crossing Rate (신호 변화율)

**평가 기준**:
- 음색이 명확한가
- 노이즈가 적은가
- 음질이 좋은가

**코드 위치**: `app/agents/analyzers/tone.py`

---

### 에이전트 매니저 (`analyzer_manager.py`)

**역할**:
- 7개 에이전트의 실행 순서 조율
- 병렬 처리 관리 (ThreadPoolExecutor)
- 결과 집계 및 평균 점수 계산

**실행 로직**:
```python
# 1단계: Validate (순차)
validate_result = self._run_agent("validate", wav_path, ...)
if not validate_result["pass"]:
    return {"error": "Validation failed"}

# 2단계: Accent (순차)
accent_result = self._run_agent("accent", wav_path, ...)

# 3단계: 나머지 5개 병렬 실행
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {
        executor.submit(self._run_agent, "pronunciation", ...),
        executor.submit(self._run_agent, "pause", ...),
        executor.submit(self._run_agent, "intonation", ...),
        executor.submit(self._run_agent, "speed", ...),
        executor.submit(self._run_agent, "tone", ...),
    }
    results = [f.result() for f in futures]
```

**코드 위치**: `app/agents/managers/analyzer_manager.py`

---

## 🔄 데이터 흐름

### 전체 흐름도

```
┌─────────────┐
│ Spring Boot │
└──────┬──────┘
       │ 1. POST /api/evaluate
       │    {taskId, audioUrl, script, callbackUrl}
       ▼
┌─────────────────────────────────────────┐
│  FastAPI (router_springboot.py)         │
│  ┌────────────────────────────────────┐ │
│  │ 1. 즉시 200 OK 반환                │ │
│  │ 2. BackgroundTasks에 등록         │ │
│  └────────────────────────────────────┘ │
└──────┬──────────────────────────────────┘
       │
       │ 3. 백그라운드 처리 시작
       ▼
┌─────────────────────────────────────────┐
│  process_evaluation_async()              │
│  ┌────────────────────────────────────┐ │
│  │ 1. S3에서 WAV 다운로드            │ │
│  │    → /tmp/tmp*.wav                │ │
│  │                                    │ │
│  │ 2. WAV 파일 헤더 검증             │ │
│  │    (채널, 샘플레이트, 재생시간)     │ │
│  │                                    │ │
│  │ 3. 음성 분석 (analyzer_manager)   │ │
│  │    ├─ Validate (순차)             │ │
│  │    ├─ Accent (순차)               │ │
│  │    └─ 5개 에이전트 (병렬)         │ │
│  │                                    │ │
│  │ 4. AI 피드백 생성 (GPT-4)         │ │
│  │                                    │ │
│  │ 5. 임시 파일 삭제                 │ │
│  │    os.remove(/tmp/tmp*.wav)       │ │
│  └────────────────────────────────────┘ │
└──────┬──────────────────────────────────┘
       │
       │ 6. 콜백 전송
       ▼
┌─────────────────────────────────────────┐
│  send_callback()                         │
│  POST {callbackUrl}                      │
│  {task_id, status, scores, feedback}     │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────┐
│ Spring Boot │ 결과 수신
└─────────────┘
```

### 타임라인

| 시간 | 단계 | 설명 |
|------|------|------|
| **0초** | 요청 수신 | Spring Boot → FastAPI |
| **0초** | 즉시 응답 | FastAPI → Spring Boot (200 OK) |
| **1-5초** | S3 다운로드 | 음성 파일 다운로드 및 검증 |
| **5-10초** | Validate | 완전성/유사도 검증 |
| **10-60초** | Accent | 억양 분석 |
| **60-180초** | 병렬 분석 | 5개 에이전트 동시 실행 |
| **180초** | AI 피드백 | GPT-4 피드백 생성 |
| **181초** | 콜백 전송 | 결과를 Spring Boot로 전송 |

---

## ⚙️ 환경 설정

### 필수 환경 변수

`.env` 파일에 다음 값들을 설정해야 합니다:

```bash
# Azure Speech API (필수)
AZURE_SPEECH_KEY=your_azure_speech_key_here
AZURE_SPEECH_REGION=koreacentral

# OpenAI API (필수)
OPENAI_API_KEY=your_openai_api_key_here

# Spring Boot 콜백 인증 (필수)
CALLBACK_API_KEY=your_callback_api_key_here

# 디버그 설정
DEBUG_SAVE_AUDIO=false  # 프로덕션: false, 개발: true
```

### 환경 변수 획득 방법

1. **Azure Speech API Key**:
   - Azure Portal (https://portal.azure.com) 접속
   - "Speech Services" 생성
   - "Keys and Endpoint" 메뉴에서 Key 복사

2. **OpenAI API Key**:
   - OpenAI Platform (https://platform.openai.com) 접속
   - "API Keys" 메뉴에서 새 키 생성

3. **Callback API Key**:
   - Spring Boot의 `application.yml`에 설정된 값과 동일하게 설정
   - 임의의 긴 문자열 (예: `sk_callback_랜덤문자열`)

---

## 💻 로컬 개발

### 1. 저장소 클론
```bash
git clone <repository-url>
cd FastApi
```

### 2. 가상환경 생성 및 활성화
```bash
# Python 3.12 이상 필요
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/Mac
source .venv/bin/activate
```

### 3. 의존성 설치
```bash
pip install -r requirements.txt
```

### 4. 환경 변수 설정
```bash
# .env.example을 .env로 복사
cp .env.example .env

# .env 파일을 편집하여 실제 API 키 입력
vim .env  # 또는 원하는 에디터 사용
```

### 5. 서버 실행
```bash
# 개발 서버 (핫 리로드 활성화)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 또는 uv 사용
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 6. API 문서 확인
브라우저에서 http://localhost:8000/docs 접속

### 7. 테스트
```bash
# 로컬 WAV 파일로 테스트
python test_analyzer_simple.py

# API 엔드포인트 테스트
python test_fastapi_endpoint.py
```

---

## 🚀 배포

### EC2 배포 가이드

자세한 배포 가이드는 다음 문서를 참조하세요:
- **[deployment/DEPLOYMENT_GUIDE.md](deployment/DEPLOYMENT_GUIDE.md)** - EC2 배포 전체 가이드
- **[deployment/SPRINGBOOT_INTEGRATION.md](deployment/SPRINGBOOT_INTEGRATION.md)** - Spring Boot 연동
- **[deployment/AUDIO_FILE_LIFECYCLE.md](deployment/AUDIO_FILE_LIFECYCLE.md)** - 파일 관리

### 빠른 배포 (EC2)

```bash
# 1. EC2 인스턴스에 접속
ssh ubuntu@<ec2-ip>

# 2. 저장소 클론
git clone <repository-url>
cd FastApi

# 3. 환경 변수 설정
cp .env.production .env
vim .env  # 실제 API 키 입력

# 4. 배포 스크립트 실행
bash deployment/deploy.sh
```

### 배포 스크립트 기능
- ✅ 자동 백업 생성 (`.backups/`)
- ✅ 실패 시 자동 롤백
- ✅ Systemd 서비스 재시작
- ✅ Health check 검증
- ✅ 7일 이상 된 백업 자동 삭제

---

## 📄 파일별 상세 설명

### 🔹 핵심 파일

#### `app/main.py`
**역할**: FastAPI 애플리케이션 진입점

**주요 기능**:
- FastAPI 앱 생성
- CORS 미들웨어 설정 (9개 허용 도메인)
- 라우터 등록 (`/api`, `/api/v1`)
- Health check 엔드포인트 (`/health`)

**CORS 설정**:
```python
origins = [
    "http://localhost:8080",  # Spring Boot 로컬
    "https://server.crewvoice.cloud",  # Spring Boot 프로덕션
    "https://ai.crewvoice.cloud",  # FastAPI 프로덕션
    # ...
]
```

---

#### `app/apis/router_springboot.py` (481줄)
**역할**: Spring Boot 연동 API 핵심 로직

**주요 함수**:

1. **`springboot_evaluate()`** (67-103줄)
   - Spring Boot로부터 평가 요청 수신
   - 즉시 200 OK 반환
   - BackgroundTasks에 비동기 처리 등록

2. **`process_evaluation_async()`** (106-249줄)
   - S3에서 WAV 다운로드
   - 음성 분석 실행 (타임아웃 300초)
   - AI 피드백 생성
   - 콜백 전송
   - 에러 처리 및 자동 파일 삭제

3. **`download_from_s3()`** (252-331줄)
   - S3 Pre-signed URL에서 파일 다운로드
   - 파일 크기 검증 (최대 50MB)
   - Content-Type 확인
   - 로컬 파일 경로 지원 (개발용)

4. **`validate_wav_file()`** (334-399줄)
   - WAV 파일 헤더 파싱
   - RIFF/WAVE 포맷 검증
   - 채널, 샘플레이트, 재생시간 추출

5. **`save_debug_audio()`** (402-425줄)
   - 디버그 모드 시 음성 파일 영구 저장
   - 타임스탬프 포함 파일명 생성

6. **`send_callback()`** (428-471줄)
   - Spring Boot로 결과 전송
   - X-API-Key 헤더 인증
   - 타임아웃 10초
   - 에러 로깅

**핵심 특징**:
- Pydantic Field 별칭으로 camelCase ↔ snake_case 변환
- `finally` 블록으로 임시 파일 자동 삭제
- 모든 에러를 Spring Boot로 콜백 전송

---

#### `app/schemas/springboot_evaluation.py`
**역할**: Spring Boot 연동 데이터 스키마

**주요 클래스**:

1. **`EvaluationRequest`**
   - Spring Boot → FastAPI 요청 스키마
   - Field 별칭으로 camelCase 지원
   ```python
   task_id: str = Field(..., alias="taskId")
   audio_url: str = Field(..., alias="audioUrl")
   ```

2. **`ScoresPayload`**
   - 6개 지표 점수 + 총점

3. **`CallbackSuccessPayload`**
   - 성공 시 콜백 데이터

4. **`CallbackFailurePayload`**
   - 실패 시 콜백 데이터

---

#### `app/agents/managers/analyzer_manager.py` (500+ 줄)
**역할**: 7개 에이전트 조율 및 관리

**주요 메서드**:

1. **`analyze_parallel()`**
   - 전체 분석 프로세스 진입점
   - 실행 시간 측정
   - 결과 집계

2. **`_run_validate_first()`**
   - Validate 에이전트 실행
   - 실패 시 즉시 중단

3. **`_run_remaining_agents()`**
   - 6개 에이전트 병렬 실행
   - ThreadPoolExecutor 사용 (5개 워커)

4. **`_aggregate_results()`**
   - 평균 점수 계산
   - 총점 산출

**병렬 처리 로직**:
```python
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {
        executor.submit(self._run_agent, "pronunciation", ...),
        executor.submit(self._run_agent, "pause", ...),
        executor.submit(self._run_agent, "intonation", ...),
        executor.submit(self._run_agent, "speed", ...),
        executor.submit(self._run_agent, "tone", ...),
    }
```

---

#### `app/agents/utils/comment_generator.py`
**역할**: OpenAI GPT-4로 AI 피드백 생성

**주요 메서드**:

1. **`generate_comment()`**
   - 에이전트 분석 결과를 자연어로 변환
   - 500자 이내 요약
   - 개선점 제시

**프롬프트 구조**:
```
음성 평가 결과:
- 완전성: 98.23%
- 유사도: 99.78%
- 발음: 85.5점
- 억양: 90.2점
...

위 결과를 바탕으로 피드백을 작성하세요.
```

---

### 🔹 배포 파일

#### `deployment/deploy.sh`
**역할**: EC2 자동 배포 스크립트 (롤백 포함)

**배포 단계** (9단계):
1. 프로젝트 디렉토리 이동
2. **백업 생성** (`.backups/backup_YYYYMMDD_HHMMSS/`)
3. Git Pull (최신 코드)
4. 가상환경 활성화
5. 의존성 설치
6. .env.production → .env 복사
7. 로그 디렉토리 생성
8. Systemd 서비스 재시작
9. 상태 확인

**롤백 메커니즘**:
```bash
trap rollback ERR  # 에러 발생 시 자동 롤백

rollback() {
    cp -r $BACKUP_PATH/* $PROJECT_DIR/
    sudo systemctl restart fastapi
}
```

---

#### `deployment/fastapi.service`
**역할**: Systemd 서비스 설정

**주요 설정**:
- **워커 수**: 5개 (t3.medium 2 vCPU 기준)
- **메모리 제한**: 2GB
- **CPU 제한**: 150%
- **재시작 정책**: 실패 시만 재시작 (on-failure)
- **로그**: `/var/log/fastapi/`

---

#### `deployment/nginx-fastapi.conf`
**역할**: Nginx 리버스 프록시 설정

**주요 기능**:
- HTTPS 강제 리다이렉트
- SSL/TLS 1.2+ 사용
- 보안 헤더 (HSTS, X-Frame-Options 등)
- 타임아웃 300초 (음성 분석용)
- Health check 엔드포인트 (`/health`)

---

## 📊 성능 및 제한사항

### 성능 지표
- **응답 시간**: < 100ms (즉시 200 OK 반환)
- **분석 시간**: 120-180초 (음성 길이에 따라 다름)
- **동시 처리**: 5개 요청 (워커 5개 기준)
- **최대 파일 크기**: 50MB
- **최대 음성 길이**: 5분 (타임아웃 300초)

### 제한사항
- Azure Speech SDK 사용량 제한
- OpenAI API 사용량 제한 (GPT-4)
- 디스크 공간 (임시 파일)

---

## 🔐 보안

### API 인증
- **콜백 인증**: `X-API-Key` 헤더 검증
- **Spring Boot 요청**: 현재 인증 없음 (추후 추가 권장)

### 파일 보안
- 임시 파일 권한: `600` (소유자만 접근)
- S3 Pre-signed URL 유효기간: 15분
- 자동 파일 삭제 (분석 완료 후)

### 환경 변수 관리
- `.env` 파일은 **절대 커밋하지 않음** (gitignore)
- 프로덕션 키는 EC2에서 별도 관리

---

## 🐛 트러블슈팅

### 일반적인 문제

1. **"Module not found" 에러**
   ```bash
   pip install -r requirements.txt
   ```

2. **Azure STT 타임아웃**
   - 네트워크 연결 확인
   - Azure API 키 확인
   - 로그 확인: `[VALIDATE] Azure STT 타임아웃`

3. **S3 다운로드 실패 (403)**
   - Pre-signed URL 만료 (15분)
   - S3 권한 확인

4. **파일 삭제 실패 (Windows)**
   - 파일 핸들이 해제되지 않음
   - `validate.py`에서 `del speech_recognizer` 확인

5. **콜백 전송 실패**
   - Spring Boot 서버 실행 확인
   - `CALLBACK_API_KEY` 일치 확인
   - 네트워크 연결 확인

---

## 📚 추가 문서

- **[deployment/DEPLOYMENT_GUIDE.md](deployment/DEPLOYMENT_GUIDE.md)** - EC2 배포 가이드
- **[deployment/SPRINGBOOT_INTEGRATION.md](deployment/SPRINGBOOT_INTEGRATION.md)** - Spring Boot 연동 가이드
- **[deployment/AUDIO_FILE_LIFECYCLE.md](deployment/AUDIO_FILE_LIFECYCLE.md)** - 음성 파일 라이프사이클
- **[requirements.txt](requirements.txt)** - Python 의존성 목록

---

## 👥 기여

이 프로젝트는 CrewVoice 팀에서 개발했습니다.

---

## 📄 라이선스

MIT License

---

**마지막 업데이트**: 2025년 12월
**버전**: 1.0.0
**문의**: [GitHub Issues](https://github.com/your-org/FastApi/issues)
