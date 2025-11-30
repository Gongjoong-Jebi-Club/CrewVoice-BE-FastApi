# ASR 음성 분석 API 가이드

## 개요

CrewVoice FastAPI 프로젝트에 통합된 음성 분석 API입니다. WAV 파일을 업로드하면 6가지 항목에 대한 종합 분석 결과를 JSON 형태로 제공합니다.

## 🎯 분석 항목 (6가지)

각 항목은 **100점 만점**으로 평가됩니다.

| 항목 | 설명 | 분석 내용 |
|------|------|----------|
| **Pronunciation** (발음) | Azure Cognitive Services 기반 발음 평가 | 정확도, 유창성, 완전성 |
| **Accent** (강조) | 단어별 에너지 및 피치 변화 분석 | 강조 표현의 적절성 |
| **Intonation** (억양) | 억양 패턴 및 리듬 분석 | 억양 곡선, 문장 종결 패턴 |
| **Pause** (휴지) | 쉼의 위치 및 길이 평가 | 문장부호 기반 휴지 적절성 |
| **Speed** (속도) | 발화 속도 분석 | 음절/초 기준 속도 평가 |
| **Tone** (톤) | 음색 및 톤 품질 평가 | 명료도, 안정성, 밝기, 음높이 |

## 🚀 서버 실행

### 1. 의존성 설치

```bash
uv sync
```

### 2. 환경 변수 설정 (선택사항)

Azure Speech API를 사용하려면 `.env` 파일을 생성하세요:

```bash
# .env
SPEECH_KEY=your_azure_speech_key
SPEECH_REGION=your_azure_region  # 예: koreacentral
```

**Note**: Azure 키가 없으면 Pronunciation 분석만 실패하고, 나머지 5개 항목은 정상 작동합니다.

### 3. 서버 시작

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8005 --reload
```

서버가 `http://localhost:8005`에서 실행됩니다.

## 📡 API 엔드포인트

### 1. 헬스체크

```bash
GET /api/v1/asr/health
```

**응답 예시:**
```json
{
  "status": "ok",
  "module": "asr_analysis",
  "agents": [
    "pronunciation",
    "accent",
    "intonation",
    "pause",
    "speed",
    "tone"
  ]
}
```

### 2. 음성 분석

```bash
POST /api/v1/asr/analyze
```

**요청 파라미터:**

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| `file` | File | O | WAV 음성 파일 |
| `reference_text` | String | X | 참조 텍스트 (발음 평가용) |
| `language_code` | String | X | 언어 코드 (기본값: `ko-KR`) |
| `gender` | String | X | 성별 (기본값: `F`) |

**cURL 예시:**

```bash
curl -X POST "http://localhost:8005/api/v1/asr/analyze" \
  -F "file=@test_audio.wav" \
  -F "reference_text=안녕하세요. 승무원 음성 분석 테스트입니다." \
  -F "language_code=ko-KR" \
  -F "gender=F"
```

**Python 예시:**

```python
import requests

url = "http://localhost:8005/api/v1/asr/analyze"

files = {
    'file': open('test_audio.wav', 'rb')
}

data = {
    'reference_text': '안녕하세요. 승무원 음성 분석 테스트입니다.',
    'language_code': 'ko-KR',
    'gender': 'F'
}

response = requests.post(url, files=files, data=data)
result = response.json()

print(f"전체 점수: {result['overall_score']}/100")
print(f"발음: {result['scores']['pronunciation']['score']}/100")
print(f"강조: {result['scores']['accent']['score']}/100")
```

**JavaScript (Axios) 예시:**

```javascript
const FormData = require('form-data');
const fs = require('fs');
const axios = require('axios');

const form = new FormData();
form.append('file', fs.createReadStream('test_audio.wav'));
form.append('reference_text', '안녕하세요. 승무원 음성 분석 테스트입니다.');
form.append('language_code', 'ko-KR');
form.append('gender', 'F');

axios.post('http://localhost:8005/api/v1/asr/analyze', form, {
  headers: form.getHeaders()
})
.then(response => {
  console.log('전체 점수:', response.data.overall_score);
  console.log('발음:', response.data.scores.pronunciation.score);
})
.catch(error => {
  console.error('Error:', error.response.data);
});
```

## 📋 응답 형식

### 성공 응답 (200 OK)

```json
{
  "overall_score": 85.5,
  "max_score": 100,
  "scores": {
    "pronunciation": {
      "score": 88.0,
      "max_score": 100,
      "feedback": [
        "종합 발음 점수: 88.00 / 100",
        "정확도: 90.00 / 100",
        "유창성: 85.00 / 100",
        "완전성: 89.00 / 100"
      ],
      "status": "success"
    },
    "accent": {
      "score": 82.0,
      "max_score": 100,
      "feedback": [
        "적절한 에너지 변화로 표현력이 좋습니다.",
        "자연스러운 음높이 변화를 잘 사용하고 있습니다."
      ],
      "status": "success"
    },
    "intonation": {
      "score": 85.0,
      "max_score": 100,
      "feedback": [
        "언어: 한국어",
        "억양 점수: 17.0 / 20.0점",
        "리듬 타입: syllable-timed",
        "문장 종결 패턴: falling"
      ],
      "status": "success"
    },
    "pause": {
      "score": 90.0,
      "max_score": 100,
      "feedback": [
        "유창성: 9.0/10.0점 (우수)",
        "Pause 위치: 4.5/5.0점",
        "Pause 길이: 4.0/5.0점"
      ],
      "status": "success"
    },
    "speed": {
      "score": 87.0,
      "max_score": 100,
      "feedback": [
        "매우 좋음 - 적절한 발화 속도를 유지하고 있습니다.",
        "전체 발화 속도: 4.25 음절/초",
        "최적 속도 범위: 3.8-4.8 음절/초"
      ],
      "status": "success"
    },
    "tone": {
      "score": 81.0,
      "max_score": 100,
      "feedback": [],
      "status": "success"
    }
  },
  "detailed_results": {
    "pronunciation": { /* 상세 분석 데이터 */ },
    "accent": { /* 상세 분석 데이터 */ },
    "intonation": { /* 상세 분석 데이터 */ },
    "pause": { /* 상세 분석 데이터 */ },
    "speed": { /* 상세 분석 데이터 */ },
    "tone": { /* 상세 분석 데이터 */ }
  },
  "analysis_summary": "전체 점수: 85.50/100 | Pronunciation: 88.00/100 | Accent: 82.00/100 | Intonation: 85.00/100 | Pause: 90.00/100 | Speed: 87.00/100 | Tone: 81.00/100"
}
```

### 에러 응답

#### 400 Bad Request - 잘못된 파일 형식
```json
{
  "detail": "WAV 파일만 업로드 가능합니다."
}
```

#### 500 Internal Server Error - 분석 실패
```json
{
  "detail": "음성 분석 중 오류 발생: [상세 오류 메시지]"
}
```

## 🏗️ 아키텍처

### AI Agent 구조

```
┌─────────────────────────────────────────┐
│         FastAPI Endpoint                │
│         POST /api/v1/asr/analyze        │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│         Agent Manager                   │
│   (Orchestrates all agents)             │
└──────┬──────────────────────────────────┘
       │
       ├─► Pronunciation Agent (Azure)
       ├─► Accent Agent
       ├─► Intonation Agent
       ├─► Pause Agent (uses Azure data)
       ├─► Speed Agent
       └─► Tone Agent
```

### 디렉토리 구조

```
app/
├── agents/
│   ├── __init__.py
│   └── agent_manager.py       # AI Agent 매니저
├── apis/
│   └── v1/
│       ├── router_asr.py      # ASR API 라우터
│       └── router_evaluate.py
├── schemas/
│   ├── asr_response.py        # ASR 응답 스키마
│   └── evaluation.py
└── main.py                     # FastAPI 애플리케이션

asr_module/                     # 음성 분석 모듈 (변경 금지)
├── accent.py
├── intonation.py
├── pause.py
├── pronunciation.py
├── speed.py
└── tone.py
```

## 🔧 주요 기능

### 1. 비동기 병렬 처리
- 6개 에이전트를 병렬로 실행하여 분석 속도 최적화
- `ThreadPoolExecutor`와 `asyncio` 활용

### 2. 모듈 독립성 유지
- `asr_module`의 코드를 변경하지 않고 래핑하는 구조
- Agent Manager가 각 분석기를 조율

### 3. 유연한 설정
- 언어별 분석 지원 (ko-KR, en-US)
- 성별별 톤 분석 (F, M)
- 참조 텍스트 선택적 제공

### 4. 견고한 에러 처리
- 각 에이전트별 독립적인 에러 처리
- 일부 에이전트 실패 시에도 다른 분석 결과 제공

## 📊 Swagger UI

서버 실행 후 브라우저에서 접속:
- Swagger UI: http://localhost:8005/docs
- ReDoc: http://localhost:8005/redoc

## 🐛 트러블슈팅

### 1. Azure Speech API 키 오류
**증상**: Pronunciation 분석이 실패함
**해결**: `.env` 파일에 올바른 Azure 키와 리전 설정

### 2. Speed Agent 초기화 실패
**증상**: "SpeedAnalyzer 초기화 실패"
**해결**: `sample/` 폴더에 기준 WAV 파일들이 있는지 확인

### 3. 파일 업로드 크기 제한
**증상**: 큰 파일 업로드 시 413 오류
**해결**: FastAPI 설정에서 `max_upload_size` 조정

## 📝 개발 노트

### asr_module 수정 금지
- `asr_module/` 내부의 파일들은 다른 저장소에서 관리됨
- 절대 직접 수정하지 말 것
- 기능 변경이 필요하면 `agent_manager.py`에서 래핑 로직 수정

### 의존성 관리
- `pyproject.toml`에 모든 필수 라이브러리 정의됨
- `uv sync`로 동기화

## 📞 문의

문제가 발생하면 Issue를 등록해주세요.
