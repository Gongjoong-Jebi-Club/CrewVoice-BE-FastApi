# 🎤 CrewVoice FastAPI - 음성 평가 시스템 전체 문서

## 📋 목차
1. [프로젝트 개요](#1-프로젝트-개요)
2. [최근 주요 수정 사항](#2-최근-주요-수정-사항)
3. [시스템 아키텍처](#3-시스템-아키텍처)
4. [음성 평가 로직 상세](#4-음성-평가-로직-상세)
5. [API 명세](#5-api-명세)
6. [동적 가중치 시스템](#6-동적-가중치-시스템)
7. [데이터 흐름 및 타임라인](#7-데이터-흐름-및-타임라인)
8. [파일 관리 및 저장](#8-파일-관리-및-저장)
9. [배포 및 운영](#9-배포-및-운영)
10. [트러블슈팅](#10-트러블슈팅)

---

## 1. 프로젝트 개요

### 1.1 시스템 소개

**CrewVoice FastAPI**는 항공 승무원 음성 평가를 위한 AI 기반 음성 분석 시스템입니다.

**핵심 기능:**
- ✅ 7개 전문 분석 에이전트를 통한 다차원 음성 평가
- ✅ Azure Speech SDK 기반 발음 정확도 분석
- ✅ Librosa 기반 음향 특징 분석
- ✅ OpenAI GPT-4를 활용한 AI 피드백 생성
- ✅ Spring Boot와의 비동기 연동 (콜백 메커니즘)
- ✅ **동적 가중치 시스템** (매 요청마다 다른 평가 기준 적용 가능)

### 1.2 기술 스택

| 분류 | 기술 | 버전 | 용도 |
|------|------|------|------|
| **Framework** | FastAPI | 0.115.12 | 웹 프레임워크 |
| **ASGI Server** | Uvicorn | 0.32.1 | 비동기 서버 |
| **음성 인식** | Azure Speech SDK | 1.47.0 | STT, 발음 평가 |
| **음성 분석** | librosa | 0.11.0 | 피치, MFCC, 스펙트럼 분석 |
| **자연어 처리** | NLTK | 3.9.2 | 품사 태깅 (내용어/기능어 구분) |
| **AI 피드백** | OpenAI API | GPT-4 | 자연어 피드백 생성 |
| **수치 계산** | NumPy, SciPy | - | 신호 처리 및 통계 분석 |
| **HTTP 클라이언트** | httpx | 0.28.1 | 비동기 HTTP 요청 (S3, 콜백) |
| **스키마 검증** | Pydantic | 2.x | 요청/응답 데이터 검증 |
| **패키지 관리** | uv | - | 초고속 의존성 관리 |
| **컨테이너** | Docker | - | 배포 및 격리 |
| **배포** | AWS EC2, Nginx | - | 프로덕션 환경 |

### 1.3 평가 지표 (6개)

| # | 지표 | 영문명 | 점수 범위 | 주요 분석 방법 |
|---|------|--------|----------|--------------|
| 1 | **발음** | Pronunciation | 0-100 | Azure Pronunciation Assessment |
| 2 | **쉼** | Pause | 0-100 | Azure 타임스탬프 기반 쉼 간격 분석 |
| 3 | **억양** | Intonation | 0-100 | Librosa 피치 변화 패턴 분석 |
| 4 | **강세** | Accent | 0-100 | Azure Prosody + NLTK 품사 태깅 |
| 5 | **음색** | Tone | 0-100 | Librosa MFCC, Spectral Centroid 분석 |
| 6 | **속도** | Speed | 0-100 | 분당 단어 수(WPM) 계산 |

**총점**: 6개 지표의 평균 (0-100점)

---

## 2. 최근 주요 수정 사항

### 2.1 동적 가중치 파라미터 시스템 구현 (2025-12)

#### 배경
- 기존: 모든 평가에 동일한 가중치 적용 (하드코딩)
- 문제점: 사용자별/평가 유형별로 다른 기준 적용 불가능
- 요구사항: SpringBoot에서 매 요청마다 다른 가중치를 전달할 수 있어야 함

#### 구현 내용

**1) WeightsConfig 스키마 추가** (`app/schemas/springboot_evaluation.py`)
```python
class WeightsConfig(BaseModel):
    """
    평가 가중치 설정 (SpringBoot → FastAPI)

    제약 조건:
    - 일반 가중치: 0.0 ~ 1.0, 0.05 단위
    - Speed deviation_threshold: 5.0 ~ 10.0, 0.5 단위
    - 평가요소별 가중치 합 = 1.0
    """
    # Tone 가중치 (4개, 합 = 1.0)
    weight_clarity: Optional[float] = Field(None, ge=0.0, le=1.0)
    weight_stability: Optional[float] = Field(None, ge=0.0, le=1.0)
    weight_brightness: Optional[float] = Field(None, ge=0.0, le=1.0)
    weight_pitch_position: Optional[float] = Field(None, ge=0.0, le=1.0)

    # Pause 가중치 (3개, 합 = 1.0)
    weight_fluency: Optional[float] = Field(None, ge=0.0, le=1.0)
    weight_position: Optional[float] = Field(None, ge=0.0, le=1.0)
    weight_length: Optional[float] = Field(None, ge=0.0, le=1.0)

    # Accent 가중치 (2개, 합 = 1.0)
    weight_pitch: Optional[float] = Field(None, ge=0.0, le=1.0)
    weight_energy: Optional[float] = Field(None, ge=0.0, le=1.0)

    # Intonation 가중치 (2개, 합 = 1.0)
    weight_baseline: Optional[float] = Field(None, ge=0.0, le=1.0)
    weight_iso: Optional[float] = Field(None, ge=0.0, le=1.0)

    # Speed 편차 임계값 (5.0 ~ 10.0, 0.5 단위)
    deviation_threshold: Optional[float] = Field(None, ge=5.0, le=10.0)

    # 성별 (M/F)
    gender: Optional[str] = Field(None, pattern="^(M|F)$")

    @model_validator(mode='after')
    def validate_weights(self):
        """가중치 검증: 0.05 단위 + 카테고리별 합=1.0"""
        # 0.05 단위 검증, 카테고리별 합 검증 로직
        # ...
```

**2) EvaluationRequest에 weights 필드 추가**
```python
class EvaluationRequest(BaseModel):
    task_id: str = Field(..., alias="taskId")
    audio_url: str = Field(..., alias="audioUrl")
    script: str
    language: str
    callback_url: str = Field(..., alias="callbackUrl")
    weights: Optional[WeightsConfig] = None  # 🆕 추가
```

**3) router_springboot.py 수정** (Lines 135-172)
```python
# 가중치 파라미터 추출 및 kwargs 구성
kwargs = {
    "reference_text": request.script,
    "language_code": request.language
}

if request.weights:
    # WeightsConfig의 모든 필드를 kwargs에 추가
    weights_dict = request.weights.model_dump(exclude_none=True)
    kwargs.update(weights_dict)
    logger.info(f"[{request.task_id}] 커스텀 가중치 적용: {list(weights_dict.keys())}")

    # 각 평가요소별 가중치 로깅 (디버깅용)
    logger.info(f"[{request.task_id}] Tone 가중치: clarity={weights_dict.get('weight_clarity')}, ...")
else:
    logger.info(f"[{request.task_id}] 기본 가중치 사용")

# asyncio.wait_for로 타임아웃 처리
result = await asyncio.wait_for(
    asyncio.to_thread(
        analyzer_manager.analyze_parallel,
        wav_path=tmp_path,
        **kwargs  # 🔑 가중치 파라미터 전달
    ),
    timeout=300
)
```

**4) analyzer_manager.py 수정**
- `analyze_parallel()` 메서드가 `**kwargs`로 가중치 수신
- 각 에이전트에 가중치 전달
- 에이전트는 전달받은 가중치가 있으면 사용, 없으면 기본값 사용

#### 검증 로직

**Pydantic Validator 사용:**
1. **0.05 단위 검증** (일반 가중치)
   - 예: 0.0, 0.05, 0.10, ..., 0.95, 1.0만 허용
   - 0.07 같은 값은 거부

2. **0.5 단위 검증** (Speed deviation_threshold)
   - 예: 5.0, 5.5, 6.0, ..., 9.5, 10.0만 허용

3. **카테고리별 가중치 합 = 1.0 검증**
   - Tone: clarity + stability + brightness + pitch_position = 1.0
   - Pause: fluency + position + length = 1.0
   - Accent: pitch + energy = 1.0
   - Intonation: baseline + iso = 1.0

4. **에러 메시지 예시:**
```json
{
  "detail": [
    {
      "type": "value_error",
      "msg": "Tone 가중치의 합이 1.0이 아닙니다: 1.05"
    }
  ]
}
```

#### 하위 호환성
- `weights` 필드는 `Optional` → SpringBoot가 보내지 않아도 작동
- 기존 API 호출 방식은 변경 없이 그대로 사용 가능
- 가중치가 없으면 각 Analyzer의 기본값 사용

---

### 2.2 NLTK 데이터 다운로드 Dockerfile 추가 (2025-12)

#### 배경
- Accent Analyzer에서 NLTK의 품사 태거(`averaged_perceptron_tagger`) 사용
- 컨테이너 실행 시 NLTK 데이터가 없어 에러 발생
```
Resource averaged_perceptron_tagger_eng not found.
```

#### 해결
**Dockerfile에 NLTK 데이터 다운로드 추가** (Lines 38-43)
```dockerfile
# 6. NLTK 데이터 다운로드 (품사 태거)
# Accent Analyzer에서 내용어/기능어 구분을 위해 필요
RUN python -c "import nltk; \
    nltk.download('averaged_perceptron_tagger_eng', quiet=True); \
    nltk.download('averaged_perceptron_tagger', quiet=True); \
    print('NLTK 데이터 다운로드 완료')"
```

**다운로드 위치:**
- 컨테이너 내부: `/root/nltk_data/taggers/`
- NLTK가 자동으로 이 경로에서 데이터 로드

**검증 방법 (EC2에서):**
```bash
# 컨테이너 접속
docker exec -it <container_id> /bin/bash

# NLTK 데이터 확인
python -c "
import nltk
try:
    nltk.data.find('taggers/averaged_perceptron_tagger_eng')
    print('✅ averaged_perceptron_tagger_eng 설치됨')
except:
    print('❌ averaged_perceptron_tagger_eng 없음')
"
```

---

### 2.3 Git Merge Conflict 해결 (router_springboot.py)

#### 상황
- 로컬 브랜치(HEAD): `weights_dict` 방식 + 멀티라인 로깅
- 원격 브랜치(origin): `kwargs` 방식 + 싱글라인 로깅
- Git 충돌 발생

#### 해결 방법
**두 접근법의 장점을 결합:**
- `kwargs` 방식 채택 (reference_text, language_code 포함) ✅
- 멀티라인 로깅 유지 (디버깅 편의성) ✅

**최종 코드:**
```python
kwargs = {
    "reference_text": request.script,
    "language_code": request.language
}

if request.weights:
    weights_dict = request.weights.model_dump(exclude_none=True)
    kwargs.update(weights_dict)  # kwargs에 가중치 추가

    # 상세 로깅 (각 평가요소별로 분리)
    logger.info(f"[{request.task_id}] Tone 가중치: ...")
    logger.info(f"[{request.task_id}] Pause 가중치: ...")
    # ...
```

---

### 2.4 기타 개선 사항

**1) Validate.py Azure 점수 추출 버그 수정 (진행 중)**
- 문제: `PronunciationAssessmentResult` 객체 속성 오류
```python
# 기존 (잘못된 코드)
pronunciation_score = result._pronunciation_score  # AttributeError

# 수정 필요 (JSON 파싱 방식)
result_json = json.loads(result.json)
pronunciation_score = result_json["NBest"][0]["PronunciationAssessment"]["PronScore"]
```

**2) Azure JSON 결과 저장 확인**
- **실시간 평가**: Azure 원본 JSON은 별도 저장 안 됨 (최종 결과에 포함만)
- **Baseline 생성**: `baselines/pause_reference/{파일명}.json`에 Azure JSON 저장

**3) 로깅 개선**
- 각 요청별 task_id 로깅 추가
- 가중치 적용 여부 명시
- 디버깅을 위한 상세 로깅 (평가요소별 가중치)

---

## 3. 시스템 아키텍처

### 3.1 전체 구조도

```
┌─────────────────────────────────────────────────────────────┐
│                     Spring Boot Backend                      │
│                  (server.crewvoice.cloud:8080)               │
│                                                               │
│  - 사용자 요청 수신                                           │
│  - 음성 파일을 S3에 업로드                                    │
│  - FastAPI로 평가 요청 전송                                   │
│  - 평가 결과 콜백 수신 및 DB 저장                             │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        │ ① POST /api/evaluate
                        │    {taskId, audioUrl, script, weights}
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Server                          │
│                   (ai.crewvoice.cloud:8000)                  │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐│
│  │           router_springboot.py (Main Router)            ││
│  │  - 즉시 200 OK 응답                                      ││
│  │  - BackgroundTasks에 분석 작업 등록                     ││
│  └─────────────────────┬───────────────────────────────────┘│
│                        │                                      │
│                        │ ② Background 처리 시작               │
│                        ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐│
│  │         process_evaluation_async() 함수                 ││
│  │  1. S3에서 WAV 다운로드 (Pre-signed URL)                ││
│  │  2. WAV 파일 헤더 검증                                   ││
│  │  3. analyzer_manager.analyze_parallel() 호출            ││
│  │  4. CommentGenerator로 AI 피드백 생성                   ││
│  │  5. 임시 파일 삭제 (finally 블록)                        ││
│  └─────────────────────┬───────────────────────────────────┘│
│                        │                                      │
│                        │ ③ 분석 요청                          │
│                        ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐│
│  │      SpeechAnalysisManager (analyzer_manager.py)        ││
│  │                                                          ││
│  │  ┌──────────────────────────────────────────────────┐  ││
│  │  │  Step 1: Validate (순차 실행 필수)               │  ││
│  │  │   - Azure STT로 음성 인식                        │  ││
│  │  │   - 완전성 & 유사도 검증                         │  ││
│  │  │   - 실패 시 즉시 중단                            │  ││
│  │  └────────────┬─────────────────────────────────────┘  ││
│  │               │ 성공 시                                 ││
│  │               ▼                                          ││
│  │  ┌──────────────────────────────────────────────────┐  ││
│  │  │  Step 2: Accent (순차 실행)                      │  ││
│  │  │   - Azure STT 재실행 (Prosody 평가)              │  ││
│  │  │   - NLTK 품사 태깅 (내용어/기능어 구분)          │  ││
│  │  │   - 억양 자연스러움 점수 계산                    │  ││
│  │  └────────────┬─────────────────────────────────────┘  ││
│  │               │                                          ││
│  │               ▼                                          ││
│  │  ┌──────────────────────────────────────────────────┐  ││
│  │  │  Step 3: 병렬 실행 (5개 에이전트)                │  ││
│  │  │   - Pronunciation (Azure 데이터 재사용)          │  ││
│  │  │   - Pause (Azure 타임스탬프 기반)                │  ││
│  │  │   - Intonation (Librosa 피치 분석)               │  ││
│  │  │   - Speed (WPM 계산)                             │  ││
│  │  │   - Tone (MFCC, Spectral 분석)                   │  ││
│  │  │                                                   │  ││
│  │  │   ThreadPoolExecutor(max_workers=5)              │  ││
│  │  └──────────────────────────────────────────────────┘  ││
│  │                                                          ││
│  │  결과 집계:                                              ││
│  │   - individual_scores: {발음, 쉼, 억양, 강세, 음색, 속도}││
│  │   - overall_score: 평균 점수                            ││
│  │   - detailed_results: 각 에이전트 상세 결과             ││
│  └─────────────────────┬───────────────────────────────────┘│
│                        │                                      │
│                        │ ④ 분석 결과 반환                     │
│                        ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐│
│  │         CommentGenerator (OpenAI GPT-4)                 ││
│  │  - 6개 점수를 자연어 피드백으로 변환                     ││
│  │  - 500자 이내 요약                                       ││
│  │  - 개선점 제시                                           ││
│  └─────────────────────┬───────────────────────────────────┘│
│                        │                                      │
│                        │ ⑤ 콜백 전송                          │
│                        ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐│
│  │              send_callback() 함수                        ││
│  │  POST {callbackUrl}                                      ││
│  │  Headers: X-API-Key                                      ││
│  │  Body: {task_id, status, scores, feedback_summary}      ││
│  └─────────────────────────────────────────────────────────┘│
└───────────────────────┬─────────────────────────────────────┘
                        │
                        │ ⑥ 콜백 수신
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                     Spring Boot Backend                      │
│  - 콜백 수신 (/api/v1/evaluations/callback)                 │
│  - X-API-Key 검증                                            │
│  - DB에 결과 저장                                            │
│  - 사용자에게 결과 전달                                      │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 디렉토리 구조

```
FastApi/
├── app/                              # 메인 애플리케이션
│   ├── main.py                       # FastAPI 진입점, CORS 설정
│   │
│   ├── apis/                         # API 라우터
│   │   ├── router_springboot.py      # 🔑 Spring Boot 연동 메인 API
│   │   └── v1/                       # V1 API (레거시)
│   │       ├── router_evaluate.py
│   │       └── router_submission.py
│   │
│   ├── schemas/                      # Pydantic 스키마
│   │   ├── springboot_evaluation.py  # 🆕 WeightsConfig, EvaluationRequest
│   │   ├── evaluation.py
│   │   └── submission.py
│   │
│   ├── agents/                       # 음성 분석 에이전트
│   │   ├── analyzers/                # 7개 분석 에이전트
│   │   │   ├── validate.py           # [1] 완전성 & 유사도 검증
│   │   │   ├── accent.py             # [2] 억양 자연스러움 (🆕 NLTK 사용)
│   │   │   ├── pronunciation.py      # [3] 발음 정확도
│   │   │   ├── pause.py              # [4] 적절한 쉼
│   │   │   ├── intonation.py         # [5] 억양 패턴
│   │   │   ├── speed.py              # [6] 말하기 속도
│   │   │   └── tone.py               # [7] 음색 품질
│   │   │
│   │   ├── managers/                 # 에이전트 관리
│   │   │   ├── analyzer_manager.py   # 🔑 에이전트 조율 및 병렬 실행
│   │   │   └── baseline_manager.py   # Azure STT 기본 매니저
│   │   │
│   │   ├── utils/
│   │   │   └── comment_generator.py  # AI 피드백 생성 (OpenAI)
│   │   │
│   │   └── baselines/                # Baseline 데이터
│   │       ├── pause_reference/      # Pause 분석 기준 데이터
│   │       │   ├── *.txt             # 정답 스크립트
│   │       │   └── *.json            # Azure STT 결과 (자동 생성)
│   │       ├── intonation_baseline/  # Intonation 기준 피치
│   │       └── tone_baseline/        # Tone 기준 음색
│   │
│   └── utils/                        # 유틸리티
│
├── deployment/                       # 배포 설정
│   ├── deploy.sh                     # 배포 스크립트 (롤백 포함)
│   ├── fastapi.service               # Systemd 서비스
│   ├── nginx-fastapi.conf            # Nginx 리버스 프록시
│   ├── DEPLOYMENT_GUIDE.md
│   ├── SPRINGBOOT_INTEGRATION.md
│   └── AUDIO_FILE_LIFECYCLE.md
│
├── log/                              # 로그 저장 (gitignore)
│   ├── analysis_*.log                # 분석 로그
│   └── result_*.json                 # 평가 결과 JSON
│
├── temp/                             # 임시 파일 (gitignore)
│   └── tmp*.wav                      # S3에서 다운로드한 WAV 파일
│
├── Dockerfile                        # 🆕 NLTK 데이터 다운로드 추가
├── pyproject.toml                    # Python 의존성 관리 (uv)
├── uv.lock                           # 의존성 잠금 파일
├── .env.example                      # 환경 변수 템플릿
├── .env.production                   # 프로덕션 환경 변수 템플릿
└── README.md
```

---

## 4. 음성 평가 로직 상세

### 4.1 평가 프로세스 전체 흐름

```
[SpringBoot 요청]
    ↓
[FastAPI 수신] → 즉시 200 OK 반환
    ↓
[BackgroundTask 시작]
    ↓
┌─────────────────────────────────────┐
│ 1. S3에서 WAV 다운로드 (30초 타임아웃) │
│    - Pre-signed URL 검증             │
│    - 파일 크기 확인 (최대 50MB)       │
│    - /temp/tmp_{uuid}.wav 저장       │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 2. WAV 파일 헤더 검증                │
│    - RIFF/WAVE 포맷 확인             │
│    - 채널 수 (1: Mono, 2: Stereo)    │
│    - 샘플레이트 (16000 Hz 권장)      │
│    - 재생시간 (최대 5분)             │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 3. 음성 분석 (300초 타임아웃)         │
│    analyzer_manager.analyze_parallel()│
│    ↓                                  │
│    ┌─────────────────────────────┐  │
│    │ Step 1: Validate (순차)     │  │
│    │  - Azure STT 실행            │  │
│    │  - 완전성 & 유사도 계산      │  │
│    │  - 실패 시 → 즉시 중단       │  │
│    └───────────┬─────────────────┘  │
│                │ 통과                │
│                ▼                     │
│    ┌─────────────────────────────┐  │
│    │ Step 2: Accent (순차)       │  │
│    │  - Azure STT 재실행          │  │
│    │  - NLTK 품사 태깅            │  │
│    │  - 억양 점수 계산            │  │
│    └───────────┬─────────────────┘  │
│                │                     │
│                ▼                     │
│    ┌─────────────────────────────┐  │
│    │ Step 3: 병렬 실행 (5개)     │  │
│    │  ├─ Pronunciation            │  │
│    │  ├─ Pause                    │  │
│    │  ├─ Intonation               │  │
│    │  ├─ Speed                    │  │
│    │  └─ Tone                     │  │
│    │  (ThreadPoolExecutor)        │  │
│    └───────────┬─────────────────┘  │
│                │                     │
│                ▼                     │
│    결과 집계 및 평균 점수 계산        │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 4. AI 피드백 생성 (GPT-4)            │
│    - 6개 점수를 자연어로 변환         │
│    - 500자 이내 요약                 │
│    - 개선점 제시                     │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 5. 임시 파일 삭제 (finally 블록)     │
│    os.remove(/temp/tmp_{uuid}.wav)  │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 6. 콜백 전송 (10초 타임아웃)         │
│    POST {callbackUrl}                │
│    Headers: X-API-Key                │
│    Body: {scores, feedback}          │
└─────────────────────────────────────┘
    ↓
[SpringBoot 결과 수신]
```

### 4.2 각 분석 에이전트 상세

#### 🔍 Validate Agent (`validate.py`)

**목적**: 음성이 대본과 일치하는지 검증 (평가의 전제 조건)

**분석 방법**:
1. Azure Speech SDK의 Continuous Recognition 사용
2. 음성을 실시간으로 텍스트로 변환
3. 대본(reference_text)과 인식된 텍스트 비교

**평가 지표**:
- **완전성 (Completeness)**: 대본 중 몇 퍼센트를 말했는가
  ```python
  completeness = (인식된 단어 수 / 대본 단어 수) * 100
  ```

- **유사도 (Similarity)**: 말한 내용이 대본과 얼마나 일치하는가
  ```python
  from difflib import SequenceMatcher
  similarity = SequenceMatcher(None, recognized, reference).ratio() * 100
  ```

**검증 기준** (하드코딩):
- `COMPLETENESS_THRESHOLD = 90.0%` (validate.py:38)
- `SIMILARITY_THRESHOLD = 0.9 (90%)` (validate.py:39)

**출력 데이터**:
```python
{
    "pass": True/False,
    "completeness": 98.5,  # %
    "similarity": 99.2,    # %
    "recognized_text": "안녕하세요 승객 여러분...",
    "azure_data": {  # 🔑 다른 에이전트에서 재사용
        "NBest": [...],  # 발음 점수 포함
        "Duration": 125000000,  # 100ns 단위
        "Offset": 0,
        "Words": [
            {
                "Word": "안녕하세요",
                "Offset": 3000000,
                "Duration": 5000000,
                "Confidence": 0.98
            },
            # ...
        ]
    }
}
```

**주요 코드**:
```python
# Azure Speech Recognizer 생성
speech_recognizer = speechsdk.SpeechRecognizer(
    speech_config=speech_config,
    audio_config=audio_config
)
pronunciation_config.apply_to(speech_recognizer)

# 이벤트 핸들러 연결
def recognized_cb(evt):
    if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
        recognized_text = evt.result.text
        recognized_text_parts.append(recognized_text)

        # JSON 결과 파싱
        json_result = json.loads(evt.result.properties.get(
            speechsdk.PropertyId.SpeechServiceResponse_JsonResult))
        all_json_results.append(json_result)

speech_recognizer.recognized.connect(recognized_cb)
speech_recognizer.start_continuous_recognition()

# 180초 타임아웃 대기
done.wait(timeout=180)
```

**에러 처리**:
- 타임아웃 (180초) 초과 시 → 실패
- Azure API 에러 → 실패
- 완전성/유사도 미달 → 실패 (다른 에이전트 실행 안 함)

---

#### 🎤 Accent Agent (`accent.py`)

**목적**: 억양의 자연스러움 평가 (외국인 억양 감지)

**분석 방법**:
1. Azure STT의 Prosody Assessment API 사용
2. **NLTK 품사 태깅**으로 내용어/기능어 구분 ← 🆕 NLTK 데이터 필요
3. 각 단어별 억양 점수를 가중 평균

**가중치 적용**:
- **내용어 (Content Words)**: 명사, 동사, 형용사, 부사 → 가중치 높음
- **기능어 (Function Words)**: 조사, 접속사, 관사 → 가중치 낮음

**NLTK 품사 태깅 예시**:
```python
import nltk
from nltk import pos_tag

# 한국어 텍스트를 단어로 분리
words = ["안녕하세요", "승객", "여러분"]

# 영어로 변환 후 품사 태깅 (간접적 방법)
# 또는 KoNLPy 사용 (한국어 전용)
tagged = pos_tag(words)
# [('안녕하세요', 'NN'), ('승객', 'NN'), ('여러분', 'NN')]
```

**평가 기준**:
- Azure Prosody 점수 (0-100)
- 내용어의 억양 점수가 높을수록 좋음
- 기능어는 억양 변화가 적어도 됨

**출력 데이터**:
```python
{
    "score": 85.5,  # 0-100
    "accent_details": {
        "word_scores": [
            {"word": "안녕하세요", "accent_score": 88.2, "is_content_word": False},
            {"word": "승객", "accent_score": 90.5, "is_content_word": True},
            # ...
        ],
        "content_word_avg": 88.7,
        "function_word_avg": 82.1
    }
}
```

**가중치 파라미터**:
- `weight_pitch`: 피치 변화 가중치 (0.0-1.0)
- `weight_energy`: 에너지 변화 가중치 (0.0-1.0)
- 합계 = 1.0

---

#### 📢 Pronunciation Agent (`pronunciation.py`)

**목적**: 발음 정확도 평가

**분석 방법**:
1. Validate 또는 Accent의 Azure STT 결과 재사용 (중복 API 호출 방지)
2. 각 단어별 발음 점수(PronunciationAssessment) 추출
3. 평균 점수 계산

**Azure Pronunciation Score**:
```json
{
  "NBest": [{
    "Words": [
      {
        "Word": "안녕하세요",
        "PronunciationAssessment": {
          "AccuracyScore": 92.5,
          "ErrorType": "None"
        }
      },
      {
        "Word": "승객",
        "PronunciationAssessment": {
          "AccuracyScore": 88.3,
          "ErrorType": "Mispronunciation"
        }
      }
    ]
  }]
}
```

**평가 기준**:
- 각 단어의 AccuracyScore 평균
- ErrorType 분포 (None, Mispronunciation, Omission)

**출력 데이터**:
```python
{
    "score": 90.2,  # 평균 발음 점수
    "pronunciation_details": {
        "total_words": 25,
        "error_words": [
            {"word": "여러분", "score": 72.1, "error_type": "Mispronunciation"}
        ],
        "accuracy_distribution": {
            "excellent": 15,  # 90-100점
            "good": 8,        # 80-90점
            "fair": 2,        # 70-80점
            "poor": 0         # 70점 미만
        }
    }
}
```

---

#### ⏸️ Pause Agent (`pause.py`)

**목적**: 적절한 쉼 분석 (문장 부호 위치에서 쉬는지)

**분석 방법**:
1. Validate의 Azure STT 타임스탬프 데이터 활용
2. 단어 간 간격(gap) 계산
3. 쉼표/마침표 위치에서 쉼 확인
4. Baseline 데이터와 비교 (정답 스크립트의 이상적인 쉼 패턴)

**타임스탬프 데이터**:
```python
# Azure STT 결과의 Words 배열
[
    {"Word": "안녕하세요", "Offset": 3000000, "Duration": 5000000},
    {"Word": "승객", "Offset": 9000000, "Duration": 4000000},
    {"Word": "여러분,", "Offset": 14000000, "Duration": 5000000},  # 쉼표
    # gap = 20000000 - (14000000 + 5000000) = 1000000 (0.1초)
    {"Word": "잠시", "Offset": 20000000, "Duration": 3000000},
]
```

**평가 기준**:
- **Fluency**: 불필요한 긴 쉼이 없는지
- **Position**: 쉼표/마침표 위치에서 쉬는지
- **Length**: 쉼의 길이가 적절한지

**가중치 파라미터**:
- `weight_fluency`: 유창성 가중치 (0.0-1.0)
- `weight_position`: 위치 적절성 가중치 (0.0-1.0)
- `weight_length`: 길이 적절성 가중치 (0.0-1.0)
- 합계 = 1.0

**Baseline 데이터**:
```
baselines/pause_reference/F_ko-KR_track1.txt  # 정답 스크립트
baselines/pause_reference/F_ko-KR_track1.json # Azure STT 결과 (이상적인 쉼 패턴)
```

**출력 데이터**:
```python
{
    "score": 88.5,
    "pause_details": {
        "fluency_score": 90.2,
        "position_score": 87.3,
        "length_score": 88.0,
        "pause_analysis": [
            {
                "position": "쉼표 뒤",
                "expected_pause": True,
                "actual_pause": True,
                "gap_ms": 150,
                "ideal_gap_ms": 120
            },
            # ...
        ]
    }
}
```

---

#### 🎵 Intonation Agent (`intonation.py`)

**목적**: 억양 패턴 분석 (문장 끝 억양 변화)

**분석 방법**:
1. Librosa로 피치(F0) 추출
2. 문장 끝에서 피치 변화 분석
3. 의문문(↗) vs 평서문(↘) 패턴 확인
4. Baseline 데이터와 비교

**Librosa 피치 추출**:
```python
import librosa
import numpy as np

# WAV 파일 로드
y, sr = librosa.load(wav_path, sr=16000)

# 피치 추출 (F0)
f0, voiced_flag, voiced_probs = librosa.pyin(
    y,
    fmin=librosa.note_to_hz('C2'),  # 남성: 65 Hz
    fmax=librosa.note_to_hz('C7')   # 여성: 2093 Hz
)

# NaN 값 제거 (무성음 구간)
f0_clean = f0[~np.isnan(f0)]

# 문장 끝 피치 변화 계산
sentence_end_slope = (f0_clean[-5:].mean() - f0_clean[-10:-5].mean()) / 5
```

**평가 기준**:
- **Baseline Score**: 기준 피치 패턴과의 유사도
- **ISO Score**: 억양 표준 편차 (단조로움 감지)

**가중치 파라미터**:
- `weight_baseline`: 기준 패턴 가중치 (0.0-1.0)
- `weight_iso`: 억양 변화 가중치 (0.0-1.0)
- 합계 = 1.0

**성별 파라미터**:
- `gender`: "M" (남성) 또는 "F" (여성)
- 남성/여성별 다른 피치 범위 적용

**Baseline 데이터**:
```
baselines/intonation_baseline/F_ko-KR_baseline.npy  # 여성 한국어 기준 피치
baselines/intonation_baseline/M_ko-KR_baseline.npy  # 남성 한국어 기준 피치
```

**출력 데이터**:
```python
{
    "score": 87.2,
    "intonation_details": {
        "baseline_score": 88.5,
        "iso_score": 85.9,
        "pitch_mean": 220.5,  # Hz
        "pitch_std": 45.2,    # Hz
        "sentence_patterns": [
            {"type": "평서문", "slope": -12.3, "expected_slope": -15.0},
            {"type": "의문문", "slope": 8.7, "expected_slope": 10.0}
        ]
    }
}
```

---

#### ⚡ Speed Agent (`speed.py`)

**목적**: 말하기 속도 평가 (분당 단어 수)

**분석 방법**:
1. Librosa로 음성 구간 감지 (음성/무음 구분)
2. 실제 발화 시간 계산 (무음 제외)
3. 단어 수 / 발화 시간 = WPM (Words Per Minute)
4. 적정 속도 범위와 비교

**음성 구간 감지**:
```python
import librosa

# WAV 파일 로드
y, sr = librosa.load(wav_path, sr=16000)

# 음성 구간 감지 (에너지 기반)
intervals = librosa.effects.split(y, top_db=20)

# 실제 발화 시간 계산
speech_duration = sum((end - start) / sr for start, end in intervals)
```

**WPM 계산**:
```python
total_words = len(reference_text.split())
wpm = (total_words / speech_duration) * 60
```

**평가 기준**:
- 적정 속도: 150-180 WPM (한국어 기준)
- 편차 임계값: `deviation_threshold` (5.0-10.0) ← 🆕 동적 파라미터

**점수 계산**:
```python
if abs(wpm - ideal_wpm) <= deviation_threshold:
    score = 100
else:
    penalty = abs(wpm - ideal_wpm) - deviation_threshold
    score = max(0, 100 - penalty * 5)
```

**가중치 파라미터**:
- `deviation_threshold`: 편차 허용 범위 (5.0-10.0, 0.5 단위)
  - 예: 5.0 → 엄격한 평가 (150-180 WPM만 만점)
  - 예: 10.0 → 관대한 평가 (140-190 WPM도 만점)

**출력 데이터**:
```python
{
    "score": 92.5,
    "speed_details": {
        "wpm": 165.3,
        "ideal_wpm": 165.0,
        "deviation": 0.3,
        "deviation_threshold": 7.5,
        "total_words": 45,
        "speech_duration": 16.3,  # 초
        "total_duration": 20.5    # 초 (무음 포함)
    }
}
```

---

#### 🎙️ Tone Agent (`tone.py`)

**목적**: 음색 품질 평가 (명확성, 안정성, 밝기)

**분석 방법**:
1. Librosa로 음향 특징 추출
   - **MFCC** (Mel-frequency cepstral coefficients): 음색 특성
   - **Spectral Centroid**: 주파수 무게중심 (밝기)
   - **Zero Crossing Rate**: 신호 변화율 (명확성)
   - **RMS Energy**: 음량 안정성

2. Baseline 데이터와 비교
3. 가중 평균으로 종합 점수 계산

**음향 특징 추출**:
```python
import librosa
import numpy as np

# WAV 파일 로드
y, sr = librosa.load(wav_path, sr=16000)

# MFCC 추출 (13차원)
mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
mfcc_mean = np.mean(mfccs, axis=1)

# Spectral Centroid (밝기)
spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
brightness = np.mean(spectral_centroid)

# Zero Crossing Rate (명확성)
zcr = librosa.feature.zero_crossing_rate(y)
clarity = np.mean(zcr)

# RMS Energy (안정성)
rms = librosa.feature.rms(y=y)
stability = np.std(rms)  # 낮을수록 안정적
```

**평가 기준**:
- **Clarity**: Zero Crossing Rate 기반
- **Stability**: RMS Energy 표준편차 기반
- **Brightness**: Spectral Centroid 기반
- **Pitch Position**: 피치 위치 (성별에 따라 다름)

**가중치 파라미터**:
- `weight_clarity`: 명확성 가중치 (0.0-1.0)
- `weight_stability`: 안정성 가중치 (0.0-1.0)
- `weight_brightness`: 밝기 가중치 (0.0-1.0)
- `weight_pitch_position`: 피치 위치 가중치 (0.0-1.0)
- 합계 = 1.0

**성별 파라미터**:
- `gender`: "M" (남성) 또는 "F" (여성)
- 남성/여성별 다른 Baseline 사용

**Baseline 데이터**:
```
baselines/tone_baseline/F_ko-KR_tone.npy  # 여성 한국어 기준 음색
baselines/tone_baseline/M_ko-KR_tone.npy  # 남성 한국어 기준 음색
```

**출력 데이터**:
```python
{
    "score": 85.3,
    "tone_details": {
        "clarity_score": 88.2,
        "stability_score": 82.5,
        "brightness_score": 86.1,
        "pitch_position_score": 84.3,
        "mfcc_similarity": 0.87,
        "spectral_centroid": 2850.5,  # Hz
        "zcr_mean": 0.125,
        "rms_std": 0.032
    }
}
```

---

### 4.3 에이전트 실행 순서 및 의존성

```
┌─────────────────────────────────────────────────────────┐
│  Validate (순차 실행 필수)                               │
│  - Azure STT 실행                                        │
│  - 완전성/유사도 검증                                    │
│  - 실패 시 즉시 중단 ❌                                  │
│  ✅ 출력: azure_data (다른 에이전트에서 재사용)          │
└──────────────┬──────────────────────────────────────────┘
               │ 성공 시
               ▼
┌─────────────────────────────────────────────────────────┐
│  Accent (순차 실행)                                      │
│  - Azure STT 재실행 (Prosody 평가)                       │
│  - NLTK 품사 태깅                                        │
│  ✅ 출력: azure_data_accent (Pronunciation에서 재사용)   │
└──────────────┬──────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────┐
│  병렬 실행 (ThreadPoolExecutor, max_workers=5)           │
│                                                          │
│  ┌──────────────────┐  ┌──────────────────┐            │
│  │ Pronunciation    │  │ Pause            │            │
│  │ (Azure 재사용)   │  │ (Azure 타임스탬프)│            │
│  └──────────────────┘  └──────────────────┘            │
│                                                          │
│  ┌──────────────────┐  ┌──────────────────┐            │
│  │ Intonation       │  │ Speed            │            │
│  │ (Librosa 피치)   │  │ (Librosa WPM)    │            │
│  └──────────────────┘  └──────────────────┘            │
│                                                          │
│  ┌──────────────────┐                                   │
│  │ Tone             │                                   │
│  │ (Librosa MFCC)   │                                   │
│  └──────────────────┘                                   │
└─────────────────────────────────────────────────────────┘
```

**병렬 실행 코드** (`analyzer_manager.py`):
```python
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {
        executor.submit(self._run_agent, "pronunciation", wav_path, **kwargs),
        executor.submit(self._run_agent, "pause", wav_path, **kwargs),
        executor.submit(self._run_agent, "intonation", wav_path, **kwargs),
        executor.submit(self._run_agent, "speed", wav_path, **kwargs),
        executor.submit(self._run_agent, "tone", wav_path, **kwargs),
    }

    for future in as_completed(futures):
        result = future.result()
        results[result["agent_name"]] = result
```

---

## 5. API 명세

### 5.1 Spring Boot → FastAPI

#### `POST /api/evaluate`

**설명**: 음성 평가 요청 수신

**요청 헤더**:
```
Content-Type: application/json
```

**요청 바디** (JSON):
```json
{
  "taskId": "550e8400-e29b-41d4-a716-446655440000",
  "audioUrl": "https://s3.ap-northeast-2.amazonaws.com/bucket/audio.wav?X-Amz-Algorithm=...",
  "script": "안녕하세요 승객 여러분, 잠시 후 이륙하겠습니다.",
  "language": "ko-KR",
  "callbackUrl": "https://server.crewvoice.cloud/api/v1/evaluations/callback",
  "weights": {
    "weight_clarity": 0.4,
    "weight_stability": 0.3,
    "weight_brightness": 0.2,
    "weight_pitch_position": 0.1,
    "weight_fluency": 0.7,
    "weight_position": 0.2,
    "weight_length": 0.1,
    "weight_pitch": 0.6,
    "weight_energy": 0.4,
    "weight_baseline": 0.7,
    "weight_iso": 0.3,
    "deviation_threshold": 7.5,
    "gender": "F"
  }
}
```

**필드 설명**:
| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `taskId` | string | ✅ | Spring Boot에서 생성한 고유 UUID |
| `audioUrl` | string | ✅ | S3 Pre-signed URL (15분 유효) |
| `script` | string | ✅ | 정답 스크립트 (사용자가 읽어야 할 텍스트) |
| `language` | string | ✅ | 언어 코드 (`ko-KR` 또는 `en-US`) |
| `callbackUrl` | string | ✅ | 결과를 받을 Spring Boot callback URL |
| `weights` | object | ❌ | 가중치 설정 (없으면 기본값 사용) |

**응답 (즉시 반환, 200 OK)**:
```json
{
  "message": "Request received",
  "task_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**응답 시간**: < 100ms (즉시 응답)

---

### 5.2 FastAPI → Spring Boot (콜백)

#### `POST {callbackUrl}`

**설명**: 분석 완료 후 결과 전송

**요청 헤더**:
```
Content-Type: application/json
X-API-Key: sk_callback_7f8e9d2a4b6c1e3f5a9b8c7d6e4f2a1b
```

**성공 시 요청 바디** (status = "completed"):
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
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
  "feedback_summary": "전반적으로 우수한 발음을 보였습니다. 억양 조절과 액센트 개선이 필요합니다. 말하기 속도는 적절했으며, 음색도 명확합니다."
}
```

**실패 시 요청 바디** (status = "failed"):
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "failed",
  "error_message": "S3 다운로드 실패: HTTP 403 Forbidden"
}
```

**응답 기대**:
```
200 OK (Spring Boot가 성공적으로 수신)
403 Forbidden (X-API-Key 불일치)
```

---

### 5.3 기타 엔드포인트

#### `GET /health`

**설명**: 헬스 체크

**응답**:
```json
{
  "status": "ok"
}
```

#### `GET /docs`

**설명**: Swagger UI API 문서

**URL**: `https://ai.crewvoice.cloud/docs`

---

## 6. 동적 가중치 시스템

### 6.1 개요

**문제점 (기존)**:
- 모든 평가에 동일한 가중치 적용
- 사용자별/평가 유형별 맞춤 평가 불가능

**해결 (동적 가중치)**:
- Spring Boot에서 매 요청마다 다른 가중치 전달 가능
- 예: 발음 중심 평가 vs 억양 중심 평가

### 6.2 가중치 파라미터 전체 목록

| 카테고리 | 파라미터 | 범위 | 단위 | 제약 조건 |
|---------|---------|------|------|----------|
| **Tone** | `weight_clarity` | 0.0-1.0 | 0.05 | 4개 합 = 1.0 |
| | `weight_stability` | 0.0-1.0 | 0.05 | |
| | `weight_brightness` | 0.0-1.0 | 0.05 | |
| | `weight_pitch_position` | 0.0-1.0 | 0.05 | |
| **Pause** | `weight_fluency` | 0.0-1.0 | 0.05 | 3개 합 = 1.0 |
| | `weight_position` | 0.0-1.0 | 0.05 | |
| | `weight_length` | 0.0-1.0 | 0.05 | |
| **Accent** | `weight_pitch` | 0.0-1.0 | 0.05 | 2개 합 = 1.0 |
| | `weight_energy` | 0.0-1.0 | 0.05 | |
| **Intonation** | `weight_baseline` | 0.0-1.0 | 0.05 | 2개 합 = 1.0 |
| | `weight_iso` | 0.0-1.0 | 0.05 | |
| **Speed** | `deviation_threshold` | 5.0-10.0 | 0.5 | - |
| **공통** | `gender` | "M" or "F" | - | Tone, Intonation에서 사용 |

**총 14개 파라미터** (11개 가중치 + 1개 편차 임계값 + 1개 성별 + 1개 예비)

### 6.3 사용 예시

**예시 1: 발음 중심 평가**
```json
{
  "weights": {
    "weight_clarity": 0.5,
    "weight_stability": 0.5,
    "weight_brightness": 0.0,
    "weight_pitch_position": 0.0,
    "deviation_threshold": 10.0,
    "gender": "F"
  }
}
```
→ 명확성과 안정성만 평가, 밝기와 피치 위치는 무시

**예시 2: 억양 중심 평가**
```json
{
  "weights": {
    "weight_baseline": 0.8,
    "weight_iso": 0.2,
    "deviation_threshold": 5.0,
    "gender": "M"
  }
}
```
→ 기준 패턴 유사도를 중요하게 평가

**예시 3: 균형 잡힌 평가 (기본값)**
```json
{
  "weights": {
    "weight_clarity": 0.25,
    "weight_stability": 0.25,
    "weight_brightness": 0.25,
    "weight_pitch_position": 0.25,
    "weight_fluency": 0.4,
    "weight_position": 0.3,
    "weight_length": 0.3,
    "weight_pitch": 0.5,
    "weight_energy": 0.5,
    "weight_baseline": 0.5,
    "weight_iso": 0.5,
    "deviation_threshold": 7.5,
    "gender": "F"
  }
}
```

### 6.4 검증 로직

**Pydantic Validator** (`app/schemas/springboot_evaluation.py:44-127`):
```python
@model_validator(mode='after')
def validate_weights(self):
    # 1. 0.05 단위 검증
    for field_name, value in weight_fields:
        if value is not None:
            remainder = round((value * 100) % 5, 2)
            if remainder != 0.0:
                raise ValueError(f"{field_name}은 0.05 단위여야 합니다")

    # 2. Speed deviation_threshold 0.5 단위 검증
    if self.deviation_threshold is not None:
        remainder = round((self.deviation_threshold * 10) % 5, 2)
        if remainder != 0.0:
            raise ValueError(f"deviation_threshold는 0.5 단위여야 합니다")

    # 3. Tone 가중치 합 = 1.0 검증
    if all([self.weight_clarity, self.weight_stability, ...]):
        tone_sum = round(sum([...]), 2)
        if abs(tone_sum - 1.0) > 0.01:
            raise ValueError(f"Tone 가중치의 합이 1.0이 아닙니다: {tone_sum}")

    # 4. 다른 카테고리도 동일하게 검증
    # ...
```

### 6.5 기본값 (weights가 없을 때)

각 Analyzer의 `__init__()` 메서드에서 기본값 설정:

```python
# tone.py
class ToneAnalyzer:
    def __init__(self):
        self.default_weights = {
            "clarity": 0.25,
            "stability": 0.25,
            "brightness": 0.25,
            "pitch_position": 0.25
        }

    def analyze(self, wav_path, **kwargs):
        # kwargs에 가중치가 있으면 사용, 없으면 기본값
        weight_clarity = kwargs.get("weight_clarity", self.default_weights["clarity"])
        # ...
```

---

## 7. 데이터 흐름 및 타임라인

### 7.1 전체 타임라인

| 시간 (초) | 단계 | 설명 | 담당 컴포넌트 |
|-----------|------|------|--------------|
| **0** | 요청 수신 | Spring Boot → FastAPI | `router_springboot.py:springboot_evaluate()` |
| **0.1** | 즉시 응답 | FastAPI → Spring Boot (200 OK) | BackgroundTasks |
| **1-5** | S3 다운로드 | Pre-signed URL에서 WAV 다운로드 | `download_from_s3()` |
| **5-10** | WAV 검증 | 파일 헤더 파싱 및 검증 | `validate_wav_file()` |
| **10-30** | Validate | 완전성 & 유사도 검증 (Azure STT) | `ValidateAnalyzer` |
| **30-60** | Accent | 억양 자연스러움 분석 (Azure + NLTK) | `AccentAnalyzer` |
| **60-120** | 병렬 분석 | 5개 에이전트 동시 실행 | ThreadPoolExecutor |
| **120-150** | 결과 집계 | 평균 점수 계산 | `analyzer_manager._aggregate_results()` |
| **150-160** | AI 피드백 | GPT-4로 자연어 피드백 생성 | `CommentGenerator` |
| **160** | 파일 삭제 | 임시 WAV 파일 삭제 | `finally: os.remove()` |
| **160-165** | 콜백 전송 | 결과를 Spring Boot로 전송 | `send_callback()` |
| **165** | 콜백 수신 | Spring Boot가 결과 저장 | Spring Boot Controller |

**총 소요 시간**: 약 2.5-3분 (음성 길이에 따라 다름)

### 7.2 데이터 흐름 상세

```
[Spring Boot]
    │
    │ POST /api/evaluate
    │ {taskId, audioUrl, script, language, callbackUrl, weights}
    ▼
[FastAPI: router_springboot.py]
    │
    ├─ Request 검증 (Pydantic)
    │   ├─ WeightsConfig 검증 (0.05 단위, 합=1.0)
    │   └─ Field 별칭 변환 (camelCase → snake_case)
    │
    ├─ 즉시 200 OK 반환
    │   └─ {message: "Request received", task_id: "..."}
    │
    └─ BackgroundTasks.add_task(process_evaluation_async)
        │
        ▼
[Background Process]
    │
    ├─ ① S3 다운로드 (30초 타임아웃)
    │   ├─ httpx.AsyncClient.get(audio_url)
    │   ├─ 파일 크기 검증 (최대 50MB)
    │   └─ /temp/tmp_{uuid}.wav 저장
    │
    ├─ ② WAV 파일 검증
    │   ├─ RIFF/WAVE 헤더 파싱
    │   ├─ 채널, 샘플레이트, 재생시간 추출
    │   └─ 로깅: "WAV 파일 정보: ..."
    │
    ├─ ③ 가중치 추출 및 kwargs 구성
    │   │
    │   ├─ kwargs = {
    │   │     "reference_text": script,
    │   │     "language_code": language
    │   │   }
    │   │
    │   └─ if weights:
    │         weights_dict = weights.model_dump()
    │         kwargs.update(weights_dict)
    │         로깅: "커스텀 가중치 적용"
    │
    ├─ ④ 음성 분석 (300초 타임아웃)
    │   │
    │   └─ analyzer_manager.analyze_parallel(wav_path, **kwargs)
    │       │
    │       ├─ Step 1: Validate (순차)
    │       │   ├─ Azure STT Continuous Recognition
    │       │   ├─ 완전성 & 유사도 계산
    │       │   ├─ 실패 시 → return {"error": "..."}
    │       │   └─ 성공 시 → azure_data 저장
    │       │
    │       ├─ Step 2: Accent (순차)
    │       │   ├─ Azure STT + Prosody Assessment
    │       │   ├─ NLTK 품사 태깅
    │       │   └─ 억양 점수 계산
    │       │
    │       └─ Step 3: 병렬 실행 (5개)
    │           ├─ Pronunciation (Azure 재사용)
    │           ├─ Pause (Azure 타임스탬프)
    │           ├─ Intonation (Librosa 피치)
    │           ├─ Speed (Librosa WPM)
    │           └─ Tone (Librosa MFCC)
    │
    │   결과:
    │   {
    │     "summary": {
    │       "individual_scores": {
    │         "pronunciation": 85.5,
    │         "pause": 90.2,
    │         "intonation": 88.7,
    │         "tone": 87.3,
    │         "speed": 92.1,
    │         "accent": 89.4
    │       },
    │       "overall_score": 88.87
    │     },
    │     "detailed_results": { ... }
    │   }
    │
    ├─ ⑤ AI 피드백 생성
    │   │
    │   └─ comment_generator.generate_comment(result)
    │       ├─ OpenAI GPT-4 호출
    │       ├─ 프롬프트: "음성 평가 결과:\n- 발음: 85.5점\n..."
    │       └─ 응답: "전반적으로 우수한 발음..."
    │
    ├─ ⑥ 임시 파일 삭제 (finally)
    │   └─ os.remove(/temp/tmp_{uuid}.wav)
    │
    └─ ⑦ 콜백 전송 (10초 타임아웃)
        │
        └─ send_callback(callback_url, payload)
            ├─ httpx.AsyncClient.post(callback_url)
            ├─ Headers: X-API-Key
            ├─ Body: {task_id, status, scores, feedback}
            └─ 로깅: "콜백 전송 성공/실패"

[Spring Boot]
    │
    └─ POST /api/v1/evaluations/callback
        ├─ X-API-Key 검증
        ├─ 결과 DB 저장
        └─ 사용자에게 알림
```

---

## 8. 파일 관리 및 저장

### 8.1 임시 파일 라이프사이클

```
[S3 Pre-signed URL]
    ↓ download_from_s3()
[/temp/tmp_{uuid}.wav]  ← 분석 중에만 존재
    ↓ analyze_parallel()
[분석 완료]
    ↓ finally: os.remove()
[삭제됨] ✅
```

**코드** (`router_springboot.py:239-248`):
```python
tmp_path = None
try:
    # S3 다운로드
    tmp_path = await download_from_s3(request.audio_url, request.task_id)

    # 분석 실행
    result = await asyncio.to_thread(
        analyzer_manager.analyze_parallel,
        wav_path=tmp_path,
        **kwargs
    )

finally:
    # 무조건 파일 삭제 (에러 발생 시에도)
    if tmp_path and os.path.exists(tmp_path):
        os.remove(tmp_path)
        logger.info(f"[{request.task_id}] 임시 파일 삭제: {tmp_path}")
```

### 8.2 디버그 모드 (DEBUG_SAVE_AUDIO=true)

**활성화 방법**:
```bash
# .env 파일
DEBUG_SAVE_AUDIO=true
```

**동작**:
- 분석 완료 후 WAV 파일을 `debug_audio/` 폴더에 영구 저장
- 파일명: `{timestamp}_{task_id}.wav`

**코드** (`router_springboot.py:402-425`):
```python
def save_debug_audio(tmp_path: str, task_id: str):
    if os.getenv("DEBUG_SAVE_AUDIO", "false").lower() == "true":
        debug_dir = Path("debug_audio")
        debug_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        debug_path = debug_dir / f"{timestamp}_{task_id}.wav"

        shutil.copy(tmp_path, debug_path)
        logger.info(f"디버그 파일 저장: {debug_path}")
```

### 8.3 평가 결과 JSON 파일

**저장 위치**: `log/result_{timestamp}.json`

**저장 시점**: 분석 완료 후 자동 저장

**코드** (`analyzer_manager.py:377-390`):
```python
def _save_result(self, result: Dict[str, Any]):
    """결과를 JSON 파일로 저장"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = self.log_dir / f"result_{timestamp}.json"

    try:
        # numpy 타입 변환
        converted_result = self._convert_to_python_types(result)

        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(converted_result, f, ensure_ascii=False, indent=2)
        self.logger.info(f"결과 저장 완료: {result_file}")
    except Exception as e:
        self.logger.error(f"결과 저장 실패: {str(e)}")
```

**파일 내용 예시**:
```json
{
  "summary": {
    "individual_scores": {
      "pronunciation": 85.5,
      "pause": 90.2,
      "intonation": 88.7,
      "tone": 87.3,
      "speed": 92.1,
      "accent": 89.4
    },
    "overall_score": 88.87
  },
  "detailed_results": {
    "validate": {
      "pass": true,
      "completeness": 98.5,
      "similarity": 99.2,
      "recognized_text": "안녕하세요 승객 여러분..."
    },
    "pronunciation": {
      "score": 85.5,
      "pronunciation_details": { ... }
    },
    // ...
  },
  "execution_time": 125.3,
  "timestamp": "2025-12-16T05:30:15"
}
```

### 8.4 Azure JSON 결과 저장

**실시간 평가**: ❌ 별도 저장 안 됨 (최종 결과 JSON에 포함만)

**Baseline 생성**: ✅ `baselines/pause_reference/{파일명}.json` 저장

**코드** (`baseline_manager.py:546-549`):
```python
# JSON 저장
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(result_json, f, ensure_ascii=False, indent=2)
self.logger.info(f"💾 JSON 저장: {json_path.name}")
```

### 8.5 로그 파일

**저장 위치**: `log/analysis_{timestamp}.log`

**저장 내용**:
- 모든 에이전트 실행 로그
- 에러 로그
- 디버깅 정보 (가중치 적용 여부, Azure API 응답 등)

**로그 레벨**:
- **파일**: DEBUG 레벨 (모든 로그)
- **콘솔**: INFO 레벨 (중요 로그만)

**코드** (`analyzer_manager.py:63-94`):
```python
def _setup_logger(self) -> logging.Logger:
    logger = logging.getLogger("SpeechAnalysisManager")
    logger.setLevel(logging.INFO)

    # 파일 핸들러
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = self.log_dir / f"analysis_{timestamp}.log"
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)  # 파일에는 모든 로그

    # 콘솔 핸들러
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)  # 콘솔에는 중요 로그만

    # ...
```

**로그 예시**:
```
2025-12-16 05:30:15 | INFO     | [550e8400] S3 다운로드 시작
2025-12-16 05:30:18 | INFO     | [550e8400] 다운로드 완료: /temp/tmp_550e8400.wav
2025-12-16 05:30:18 | INFO     | [550e8400] WAV 파일 정보: 채널=1, 샘플레이트=16000, 재생시간=20.5초
2025-12-16 05:30:18 | INFO     | [550e8400] 커스텀 가중치 적용: ['weight_clarity', 'weight_stability', ...]
2025-12-16 05:30:18 | DEBUG    | [550e8400] Tone 가중치: clarity=0.4, stability=0.3, brightness=0.2, pitch_position=0.1
2025-12-16 05:30:20 | INFO     | [VALIDATE] Azure STT 세션 시작
2025-12-16 05:30:25 | INFO     | [VALIDATE] Azure STT 전사 (청크 1): '안녕하세요 승객 여러분'
2025-12-16 05:30:30 | INFO     | [VALIDATE] 검증 통과: 완전성=98.5%, 유사도=99.2%
2025-12-16 05:30:35 | INFO     | [ACCENT] Azure STT 세션 시작
2025-12-16 05:30:40 | INFO     | [ACCENT] 억양 점수: 89.4
2025-12-16 05:31:00 | INFO     | [PRONUNCIATION] 발음 점수: 85.5
2025-12-16 05:31:15 | INFO     | 음성 분석 완료 (총 소요 시간: 125.3초)
2025-12-16 05:31:20 | INFO     | [550e8400] 콜백 전송 성공 (HTTP 200)
```

---

## 9. 배포 및 운영

### 9.1 EC2 배포 구조

```
┌─────────────────────────────────────────────────────────────┐
│                       EC2 Instance                           │
│                    (Ubuntu 22.04 LTS)                        │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                 Nginx (Port 443/80)                     ││
│  │  - SSL/TLS 인증서 (Let's Encrypt)                       ││
│  │  - 리버스 프록시                                        ││
│  │  - 정적 파일 서빙                                       ││
│  └────────────────────┬────────────────────────────────────┘│
│                       │ Reverse Proxy                        │
│                       ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐│
│  │          Uvicorn (Port 8000)                            ││
│  │  - Workers: 5개                                         ││
│  │  - ASGI Server                                          ││
│  │  - Systemd로 관리                                       ││
│  └────────────────────┬────────────────────────────────────┘│
│                       │                                      │
│                       ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐│
│  │               FastAPI Application                        ││
│  │  - 7개 Analyzer                                         ││
│  │  - Azure Speech SDK                                     ││
│  │  - Librosa                                              ││
│  │  - OpenAI API                                           ││
│  └─────────────────────────────────────────────────────────┘│
│                                                               │
│  디렉토리 구조:                                              │
│  /home/ubuntu/FastApi/                                       │
│  ├── app/                                                   │
│  ├── .venv/            (가상환경)                            │
│  ├── .env              (환경 변수)                           │
│  ├── log/              (로그 파일)                           │
│  ├── temp/             (임시 WAV 파일)                       │
│  └── debug_audio/      (디버그 모드 시)                      │
└─────────────────────────────────────────────────────────────┘
```

### 9.2 배포 스크립트 (`deployment/deploy.sh`)

**9단계 배포 프로세스**:

```bash
#!/bin/bash
set -e  # 에러 발생 시 즉시 중단

PROJECT_DIR="/home/ubuntu/FastApi"
BACKUP_DIR="$PROJECT_DIR/.backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_PATH="$BACKUP_DIR/backup_$TIMESTAMP"

# 롤백 함수 정의
rollback() {
    echo "❌ 배포 실패! 롤백 시작..."
    cp -r $BACKUP_PATH/* $PROJECT_DIR/
    sudo systemctl restart fastapi
    echo "✅ 롤백 완료"
    exit 1
}

# 에러 시 자동 롤백
trap rollback ERR

echo "🚀 FastAPI 배포 시작..."

# 1단계: 프로젝트 디렉토리 이동
cd $PROJECT_DIR

# 2단계: 백업 생성
mkdir -p $BACKUP_DIR
cp -r app/ $BACKUP_PATH/
echo "✅ 백업 생성: $BACKUP_PATH"

# 3단계: Git Pull
git pull origin main
echo "✅ Git Pull 완료"

# 4단계: 가상환경 활성화
source .venv/bin/activate
echo "✅ 가상환경 활성화"

# 5단계: 의존성 설치
uv sync
echo "✅ 의존성 설치 완료"

# 6단계: .env 파일 확인
if [ ! -f .env ]; then
    cp .env.production .env
    echo "⚠️  .env 파일 생성됨 (실제 API 키 입력 필요)"
fi

# 7단계: 로그 디렉토리 생성
mkdir -p log temp debug_audio
echo "✅ 로그 디렉토리 생성"

# 8단계: Systemd 서비스 재시작
sudo systemctl restart fastapi
echo "✅ FastAPI 서비스 재시작"

# 9단계: 상태 확인
sleep 3
if systemctl is-active --quiet fastapi; then
    echo "✅ 배포 성공!"

    # 7일 이상 된 백업 삭제
    find $BACKUP_DIR -type d -mtime +7 -exec rm -rf {} +
    echo "✅ 오래된 백업 삭제"
else
    echo "❌ FastAPI 서비스 시작 실패"
    rollback
fi
```

**실행 방법**:
```bash
cd /home/ubuntu/FastApi
bash deployment/deploy.sh
```

### 9.3 Systemd 서비스 설정 (`deployment/fastapi.service`)

```ini
[Unit]
Description=FastAPI Voice Evaluation Server
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/FastApi
Environment="PATH=/home/ubuntu/FastApi/.venv/bin"

# Uvicorn 실행 (5개 워커)
ExecStart=/home/ubuntu/FastApi/.venv/bin/uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 5 \
    --log-level info

# 리소스 제한
MemoryLimit=2G
CPUQuota=150%

# 재시작 정책
Restart=on-failure
RestartSec=5s

# 로그 설정
StandardOutput=append:/var/log/fastapi/output.log
StandardError=append:/var/log/fastapi/error.log

[Install]
WantedBy=multi-user.target
```

**서비스 관리 명령어**:
```bash
# 서비스 시작
sudo systemctl start fastapi

# 서비스 중지
sudo systemctl stop fastapi

# 서비스 재시작
sudo systemctl restart fastapi

# 서비스 상태 확인
sudo systemctl status fastapi

# 서비스 자동 시작 활성화
sudo systemctl enable fastapi

# 로그 확인
sudo journalctl -u fastapi -n 100 -f
```

### 9.4 Nginx 리버스 프록시 설정 (`deployment/nginx-fastapi.conf`)

```nginx
server {
    listen 80;
    server_name ai.crewvoice.cloud;

    # HTTP → HTTPS 리다이렉트
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name ai.crewvoice.cloud;

    # SSL 인증서 (Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/ai.crewvoice.cloud/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/ai.crewvoice.cloud/privkey.pem;

    # SSL 설정
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers 'ECDHE-RSA-AES128-GCM-SHA256:...';
    ssl_prefer_server_ciphers on;

    # 보안 헤더
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;

    # 클라이언트 최대 업로드 크기
    client_max_body_size 50M;

    # 타임아웃 (음성 분석용)
    proxy_connect_timeout 300s;
    proxy_send_timeout 300s;
    proxy_read_timeout 300s;

    # 리버스 프록시
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Health check
    location /health {
        proxy_pass http://localhost:8000/health;
        access_log off;
    }
}
```

**Nginx 관리 명령어**:
```bash
# 설정 파일 테스트
sudo nginx -t

# Nginx 재시작
sudo systemctl restart nginx

# 로그 확인
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log
```

### 9.5 Docker 배포 (대안)

**Dockerfile** (Lines 1-55):
```dockerfile
# 1. 베이스 이미지
FROM python:3.12-slim

# 2. 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    curl \
    libasound2 \
    libsndfile1 \
    ffmpeg \
    default-jdk && \
    rm -rf /var/lib/apt/lists/*

# 3. Java 환경변수 설정 (NLTK용)
ENV JAVA_HOME=/usr/lib/jvm/default-java
ENV PATH="${JAVA_HOME}/bin:${PATH}"

# 4. 작업 디렉토리
WORKDIR /app

# 5. 의존성 파일 복사
COPY pyproject.toml uv.lock ./

# 6. uv 설치 및 의존성 설치
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    export PATH="/root/.local/bin:${PATH}" && \
    uv pip compile pyproject.toml --output-file=requirements.txt && \
    uv pip sync --system requirements.txt

# 7. NLTK 데이터 다운로드 (🆕 추가)
RUN python -c "import nltk; \
    nltk.download('averaged_perceptron_tagger_eng', quiet=True); \
    nltk.download('averaged_perceptron_tagger', quiet=True); \
    print('NLTK 데이터 다운로드 완료')"

# 8. 애플리케이션 소스 코드 복사
COPY ./app ./app

# 9. 포트 노출
EXPOSE 8000

# 10. 서버 실행
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Docker 빌드 및 실행**:
```bash
# 이미지 빌드
docker build -t fastapi-voice-eval .

# 컨테이너 실행
docker run -d \
    --name fastapi \
    -p 8000:8000 \
    -v $(pwd)/log:/app/log \
    -v $(pwd)/.env:/app/.env \
    fastapi-voice-eval

# 컨테이너 로그 확인
docker logs -f fastapi

# 컨테이너 내부 접속
docker exec -it fastapi /bin/bash
```

### 9.6 환경 변수 관리

**.env 파일** (프로덕션):
```bash
# Azure Speech API
AZURE_SPEECH_KEY=your_azure_speech_key_here
AZURE_SPEECH_REGION=koreacentral

# OpenAI API
OPENAI_API_KEY=your_openai_api_key_here

# Spring Boot 콜백 인증
CALLBACK_API_KEY=sk_callback_7f8e9d2a4b6c1e3f5a9b8c7d6e4f2a1b

# 디버그 설정
DEBUG_SAVE_AUDIO=false  # 프로덕션: false
```

**환경 변수 보안**:
1. `.env` 파일은 **절대 Git에 커밋하지 않음** (`.gitignore`에 포함)
2. EC2에서만 실제 API 키 보관
3. GitHub Secrets 사용 (CI/CD 시)

---

## 10. 트러블슈팅

### 10.1 NLTK 데이터 오류

**증상**:
```
Resource averaged_perceptron_tagger_eng not found.
```

**원인**: NLTK 데이터가 다운로드되지 않음

**해결**:
1. Dockerfile에 다운로드 명령 추가 (이미 완료 ✅)
2. 컨테이너 재빌드
```bash
docker build --no-cache -t fastapi-voice-eval .
docker-compose up -d
```

3. 수동 다운로드 (긴급 시)
```bash
docker exec -it fastapi python -c "
import nltk
nltk.download('averaged_perceptron_tagger_eng')
nltk.download('averaged_perceptron_tagger')
"
```

### 10.2 Azure STT 타임아웃

**증상**:
```
[VALIDATE] Azure STT 타임아웃 (180초 초과)
```

**원인**:
- 네트워크 연결 불안정
- Azure API 과부하
- 음성 파일이 너무 김 (5분 초과)

**해결**:
1. 네트워크 연결 확인
```bash
ping speech.microsoft.com
```

2. Azure API 키 확인
```bash
echo $AZURE_SPEECH_KEY
```

3. 타임아웃 시간 증가 (validate.py:180)
```python
# 기존: 180초
done.wait(timeout=180)

# 수정: 300초
done.wait(timeout=300)
```

### 10.3 S3 다운로드 실패 (403 Forbidden)

**증상**:
```
[task_id] S3 다운로드 실패: HTTP 403 Forbidden
```

**원인**:
- Pre-signed URL 만료 (15분)
- S3 버킷 권한 문제

**해결**:
1. Spring Boot에서 URL 유효기간 확인
```java
// 15분 유효기간
Date expiration = new Date();
expiration.setTime(expiration.getTime() + 15 * 60 * 1000);

GeneratePresignedUrlRequest request = new GeneratePresignedUrlRequest(bucketName, key)
    .withMethod(HttpMethod.GET)
    .withExpiration(expiration);
```

2. FastAPI 로그에서 다운로드 시간 확인
```bash
grep "S3 다운로드" log/analysis_*.log
```

### 10.4 WeightsConfig 검증 오류

**증상**:
```json
{
  "detail": [
    {
      "type": "value_error",
      "msg": "Tone 가중치의 합이 1.0이 아닙니다: 1.05"
    }
  ]
}
```

**원인**: 가중치 합이 1.0이 아님

**해결**:
1. Spring Boot에서 가중치 합 검증 추가
```java
double toneSum = weightClarity + weightStability + weightBrightness + weightPitchPosition;
if (Math.abs(toneSum - 1.0) > 0.01) {
    throw new IllegalArgumentException("Tone 가중치의 합이 1.0이 아닙니다: " + toneSum);
}
```

2. FastAPI 에러 메시지 확인
```bash
curl -X POST "https://ai.crewvoice.cloud/api/evaluate" \
  -H "Content-Type: application/json" \
  -d '{...}'
```

### 10.5 콜백 전송 실패

**증상**:
```
[task_id] 콜백 전송 실패 (HTTP 403)
```

**원인**:
- `X-API-Key` 헤더 불일치
- Spring Boot 서버 다운

**해결**:
1. API Key 확인
```bash
# FastAPI .env
grep CALLBACK_API_KEY .env

# Spring Boot application.yml
grep callback-api-key application.yml
```

2. Spring Boot 서버 상태 확인
```bash
curl https://server.crewvoice.cloud/actuator/health
```

3. 네트워크 연결 확인
```bash
curl -X POST "https://server.crewvoice.cloud/api/v1/evaluations/callback" \
  -H "X-API-Key: sk_callback_..." \
  -H "Content-Type: application/json" \
  -d '{"task_id": "test"}'
```

### 10.6 메모리 부족

**증상**:
```
MemoryError: Unable to allocate array
```

**원인**:
- Librosa 분석 시 메모리 과다 사용
- 동시 요청 과다

**해결**:
1. Systemd 메모리 제한 증가
```ini
# fastapi.service
MemoryLimit=4G  # 기존 2G → 4G
```

2. Uvicorn 워커 수 감소
```bash
# 5개 → 3개
uvicorn app.main:app --workers 3
```

3. EC2 인스턴스 타입 업그레이드
```
t3.medium (2 vCPU, 4GB RAM) → t3.large (2 vCPU, 8GB RAM)
```

### 10.7 파일 삭제 실패 (Windows)

**증상**:
```
[task_id] 임시 파일 삭제 실패: PermissionError
```

**원인**: 파일 핸들이 해제되지 않음 (Azure SDK)

**해결**:
validate.py에서 명시적 해제 추가
```python
# Azure Speech Recognizer 정지
speech_recognizer.stop_continuous_recognition()

# 🔑 핸들 명시적 해제 (Windows 호환)
del speech_recognizer
del audio_config

# 파일 삭제
os.remove(wav_path)
```

---

## 📊 부록

### A. 의존성 목록 (pyproject.toml)

```toml
[project]
name = "crewvoice-fastapi"
version = "1.0.0"
requires-python = ">=3.12"

dependencies = [
    "fastapi==0.115.12",
    "uvicorn==0.32.1",
    "pydantic==2.10.3",
    "azure-cognitiveservices-speech==1.47.0",
    "librosa==0.11.0",
    "nltk==3.9.2",
    "openai>=1.0.0",
    "httpx==0.28.1",
    "numpy>=1.24.0",
    "scipy>=1.11.0",
    "python-dotenv>=1.0.0",
]
```

### B. 참고 문서

- **FastAPI 공식 문서**: https://fastapi.tiangolo.com/
- **Azure Speech SDK**: https://learn.microsoft.com/en-us/azure/ai-services/speech-service/
- **Librosa 문서**: https://librosa.org/doc/latest/
- **NLTK 문서**: https://www.nltk.org/
- **OpenAI API**: https://platform.openai.com/docs/

### C. 프로젝트 정보

- **프로젝트명**: CrewVoice FastAPI
- **버전**: 1.0.0
- **최종 업데이트**: 2025-12-16
- **라이선스**: MIT
- **저장소**: GitHub (비공개)
- **프로덕션 URL**: https://ai.crewvoice.cloud

---

**이 문서는 CrewVoice FastAPI 음성 평가 시스템의 전체 구조, 로직, 최근 수정 사항을 포괄적으로 설명합니다.**
