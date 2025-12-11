# Streamlit 없이 음성 분석 로직 테스트 가이드

## 📊 분석 요약

**결론**: ✅ **Streamlit 없이 완벽하게 작동 가능합니다!**

app/agents의 음성 분석 로직은 **이미 FastAPI로 통합**되어 있으며, 다양한 방법으로 테스트할 수 있습니다.

---

## 🔍 기존 구조 비교

### asr_python_test (Streamlit 기반)

```
asr_python_test/
├── app.py                    # 🌐 Streamlit UI (웹 인터페이스)
├── api_server.py             # 🚀 FastAPI 서버
├── analyzer_manager.py       # 🎯 분석 매니저
├── comment_generator.py      # 💬 AI 코멘트
└── new_agent/                # 📁 7개 분석기
    ├── validate.py
    ├── accent.py
    └── ...
```

**실행 방법**:
```bash
# Streamlit UI
streamlit run app.py

# FastAPI 서버
uvicorn api_server:app --reload
```

---

### app/agents (FastAPI 통합)

```
app/
├── main.py                   # 🚀 FastAPI 메인 앱
├── apis/v1/
│   ├── router_evaluate.py    # ✅ 평가 엔드포인트 (이미 구현됨!)
│   └── router_submission.py  # ✅ 제출 엔드포인트
├── schemas/
│   └── evaluation.py         # 📋 응답 스키마
└── agents/
    ├── managers/
    │   ├── analyzer_manager.py    # 🎯 분석 매니저
    │   └── baseline_manager.py
    ├── utils/
    │   └── comment_generator.py   # 💬 AI 코멘트
    └── analyzers/                 # 📁 7개 분석기
        ├── validate.py
        ├── accent.py
        └── ...
```

**실행 방법**:
```bash
# FastAPI 서버
uvicorn app.main:app --reload --port 8000
```

---

## ✅ 이미 구현된 FastAPI 엔드포인트

### 1️⃣ `/api/v1/evaluate` 엔드포인트

**파일**: [app/apis/v1/router_evaluate.py](apis/v1/router_evaluate.py)

```python
@router.post("/evaluate", response_model=EvaluationResponse)
async def evaluate_speech(
    audio_file: UploadFile,           # 음성 파일
    script_id: int = Form(...),       # 스크립트 ID
    user_id: str = Form(...),         # 사용자 ID
    reference_text: str = Form(...),  # 참조 텍스트
    background_tasks: BackgroundTasks = None
):
    # 1. 파일 검증
    # 2. 임시 파일 저장
    # 3. 음성 분석 실행 (analyzer_manager 사용!)
    result = analyzer_manager.analyze_parallel(
        wav_path=tmp_path,
        reference_text=reference_text,
        language_code="ko-KR"
    )

    # 4. AI 코멘트 생성 (comment_generator 사용!)
    agent_outputs = analyzer_manager.get_agent_outputs(result)
    ai_comment_data = comment_generator.generate_comment(agent_outputs)

    # 5. 응답 반환
    return EvaluationResponse(...)
```

**특징**:
- ✅ `SpeechAnalysisManager` 사용 (app/agents/managers/)
- ✅ `AICommentGenerator` 사용 (app/agents/utils/)
- ✅ 6가지 점수 반환 (pronunciation, pause, intonation, tone, speed, accent)
- ✅ AI 피드백 생성
- ✅ 임시 파일 자동 삭제

---

## 🚀 Streamlit 없이 테스트하는 5가지 방법

### 방법 1: FastAPI Swagger UI (가장 쉬움) ⭐

**단계**:
1. FastAPI 서버 실행
```bash
cd "c:\Users\yco11\Desktop\SKALA\final project\FastApi"
uvicorn app.main:app --reload --port 8000
```

2. 브라우저에서 Swagger UI 열기
```
http://localhost:8000/docs
```

3. `/api/v1/evaluate` 엔드포인트 테스트
   - "Try it out" 클릭
   - `audio_file`: WAV/MP3 파일 업로드
   - `script_id`: 1
   - `user_id`: "test_user"
   - `reference_text`: "안녕하세요. 오늘은 날씨가 좋습니다."
   - "Execute" 클릭

4. 응답 확인
```json
{
  "score_pronunciation": 85.5,
  "score_pause": 90.2,
  "score_intonation": 88.0,
  "score_tone": 92.3,
  "score_speed": 87.8,
  "score_accent": 84.1,
  "overall_score": 88.0,
  "feedback_summary": "## 1. 강조 (Accent) 평가\n...",
  "eval_id": "eval-test_user-1"
}
```

**장점**:
- ✅ 웹 브라우저만 있으면 됨
- ✅ GUI로 파일 업로드 가능
- ✅ 실시간 응답 확인
- ✅ 설치 불필요

---

### 방법 2: Python 스크립트 테스트

**파일 생성**: `test_analyzer.py`

```python
"""
음성 분석 로직 테스트 스크립트
Streamlit 없이 직접 analyzer_manager 호출
"""
from app.agents.managers.analyzer_manager import SpeechAnalysisManager
from app.agents.utils.comment_generator import AICommentGenerator
from pathlib import Path
import json

def test_analysis(wav_path: str, reference_text: str):
    """음성 분석 테스트"""
    print("🎤 음성 분석 시작...")
    print(f"파일: {wav_path}")
    print(f"참조 텍스트: {reference_text}")
    print("=" * 80)

    # 1. 매니저 초기화
    analyzer = SpeechAnalysisManager(log_dir="test_logs")
    comment_gen = AICommentGenerator()

    # 2. 음성 분석 실행
    result = analyzer.analyze_parallel(
        wav_path=wav_path,
        reference_text=reference_text,
        language_code="ko-KR",
        gender="F"
    )

    # 3. 결과 출력
    print("\n📊 분석 결과:")
    print(f"총점: {result['summary']['total_score']:.2f} / {result['summary']['max_total_score']}")
    print(f"평균: {result['summary']['average_score']:.2f}%")
    print(f"소요 시간: {result['elapsed_time']:.2f}초")

    print("\n📈 에이전트별 점수:")
    for agent, score in result['summary']['individual_scores'].items():
        print(f"  {agent}: {score:.2f}")

    # 4. AI 코멘트 생성
    print("\n💬 AI 코멘트 생성 중...")
    agent_outputs = analyzer.get_agent_outputs(result)
    validation_result = result['detailed_results'].get('validate', {})

    comment_data = comment_gen.generate_comment(agent_outputs, validation_result)

    print("\n📝 AI 피드백:")
    print(comment_data['comment'])

    # 5. 결과 저장
    output_file = Path("test_result.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "analysis_result": result,
            "ai_comment": comment_data
        }, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 결과 저장 완료: {output_file}")
    return result

if __name__ == "__main__":
    # 테스트 파일 경로 (실제 경로로 수정 필요)
    wav_path = "path/to/test_audio.wav"
    reference_text = "안녕하세요. 오늘은 날씨가 좋습니다."

    # 테스트 실행
    test_analysis(wav_path, reference_text)
```

**실행**:
```bash
python test_analyzer.py
```

**출력 예시**:
```
🎤 음성 분석 시작...
파일: path/to/test_audio.wav
참조 텍스트: 안녕하세요. 오늘은 날씨가 좋습니다.
================================================================================
2025-12-10 10:30:45 | INFO     | 음성 분석 매니저 초기화 완료
2025-12-10 10:30:45 | INFO     | [VALIDATE] 분석 시작...
2025-12-10 10:30:47 | INFO     | [VALIDATE] 검증 완료 - is_valid: True
...

📊 분석 결과:
총점: 528.50 / 600
평균: 88.08%
소요 시간: 12.34초

📈 에이전트별 점수:
  pronunciation: 85.5
  accent: 84.1
  pause: 90.2
  intonation: 88.0
  speed: 87.8
  tone: 92.3

💬 AI 코멘트 생성 중...

📝 AI 피드백:
## 1. 강조 (Accent) 평가
...

✅ 결과 저장 완료: test_result.json
```

---

### 방법 3: curl 명령어 (CLI)

```bash
# 서버 실행 (다른 터미널)
uvicorn app.main:app --reload --port 8000

# curl로 API 호출
curl -X POST "http://localhost:8000/api/v1/evaluate" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "audio_file=@test_audio.wav" \
  -F "script_id=1" \
  -F "user_id=test_user" \
  -F "reference_text=안녕하세요. 오늘은 날씨가 좋습니다."
```

**PowerShell 버전** (Windows):
```powershell
$uri = "http://localhost:8000/api/v1/evaluate"
$filePath = "C:\path\to\test_audio.wav"

$form = @{
    audio_file = Get-Item -Path $filePath
    script_id = 1
    user_id = "test_user"
    reference_text = "안녕하세요. 오늘은 날씨가 좋습니다."
}

Invoke-RestMethod -Uri $uri -Method Post -Form $form
```

---

### 방법 4: Postman / Insomnia (GUI 도구)

**Postman 설정**:

1. **Request Type**: POST
2. **URL**: `http://localhost:8000/api/v1/evaluate`
3. **Body**: form-data
   - `audio_file`: [File] test_audio.wav
   - `script_id`: [Text] 1
   - `user_id`: [Text] test_user
   - `reference_text`: [Text] 안녕하세요. 오늘은 날씨가 좋습니다.
4. **Send** 클릭

**응답 예시**:
```json
{
  "score_pronunciation": 85.5,
  "score_pause": 90.2,
  "score_intonation": 88.0,
  "score_tone": 92.3,
  "score_speed": 87.8,
  "score_accent": 84.1,
  "overall_score": 88.0,
  "feedback_summary": "## 1. 강조 (Accent) 평가\n음높이 변화와 에너지 조절이 우수합니다...",
  "eval_id": "eval-test_user-1"
}
```

---

### 방법 5: Jupyter Notebook / IPython

```python
# Jupyter Notebook 셀

# 1. 매니저 임포트
from app.agents.managers.analyzer_manager import SpeechAnalysisManager
from app.agents.utils.comment_generator import AICommentGenerator

# 2. 초기화
analyzer = SpeechAnalysisManager()
comment_gen = AICommentGenerator()

# 3. 분석 실행
result = analyzer.analyze_parallel(
    wav_path="path/to/audio.wav",
    reference_text="안녕하세요. 오늘은 날씨가 좋습니다.",
    language_code="ko-KR"
)

# 4. 결과 확인
print(f"평균 점수: {result['summary']['average_score']:.2f}%")

# 5. 시각화
import matplotlib.pyplot as plt

scores = result['summary']['individual_scores']
plt.figure(figsize=(10, 6))
plt.bar(scores.keys(), scores.values())
plt.title('Agent Scores')
plt.ylabel('Score')
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()

# 6. AI 코멘트
agent_outputs = analyzer.get_agent_outputs(result)
comment = comment_gen.generate_comment(agent_outputs)
print(comment['comment'])
```

---

## 🔧 테스트 환경 설정

### 1. 환경 변수 (.env)

```bash
# Azure Speech API
AZURE_SPEECH_KEY=your_azure_key
AZURE_SPEECH_REGION=koreacentral

# OpenAI API (AI 코멘트 생성)
OPENAI_API_KEY=your_openai_key
```

### 2. 필요한 패키지 설치

```bash
pip install fastapi uvicorn python-multipart
pip install librosa soundfile parselmouth
pip install azure-cognitiveservices-speech
pip install openai python-dotenv
```

---

## 📊 API 응답 스키마

### EvaluationResponse

```python
{
  "score_pronunciation": float,   # 발음 점수 (0-100)
  "score_pause": float,           # 휴지 점수 (0-100)
  "score_intonation": float,      # 억양 점수 (0-100)
  "score_tone": float,            # 톤 점수 (0-100)
  "score_speed": float,           # 속도 점수 (0-100)
  "score_accent": float,          # 강조 점수 (0-100)
  "overall_score": float,         # 전체 평균 점수 (0-100)
  "feedback_summary": str,        # AI 피드백 (Markdown)
  "eval_id": str                  # 평가 ID
}
```

### 상세 분석 결과 (analyzer_manager.analyze_parallel)

```python
{
  "file_path": str,
  "timestamp": str,
  "elapsed_time": float,
  "summary": {
    "total_score": float,
    "max_total_score": int,
    "average_score": float,
    "individual_scores": {
      "validate": float,
      "pronunciation": float,
      "accent": float,
      "pause": float,
      "intonation": float,
      "speed": float,
      "tone": float
    }
  },
  "detailed_results": {
    "validate": { ... },
    "pronunciation": { ... },
    "accent": { ... },
    "pause": { ... },
    "intonation": { ... },
    "speed": { ... },
    "tone": { ... }
  }
}
```

---

## 🎯 테스트 시나리오

### 시나리오 1: 정상 음성 분석

**입력**:
- 음성 파일: 명확한 발음, 적절한 속도
- 참조 텍스트: "안녕하세요. 오늘은 날씨가 좋습니다."

**기대 결과**:
- ✅ 모든 에이전트 점수 > 70
- ✅ AI 피드백 생성 성공
- ✅ 6가지 측면 모두 평가됨

### 시나리오 2: Validation 실패

**입력**:
- 음성 파일: 참조 텍스트와 다른 내용
- 참조 텍스트: "안녕하세요."
- 실제 음성: "반갑습니다."

**기대 결과**:
- ❌ Validation 실패
- ✅ 나머지 에이전트 모두 0점
- ✅ "분석 부적합" 메시지

### 시나리오 3: 부분 에이전트 실패

**입력**:
- 음성 파일: 매우 짧은 오디오 (< 1초)

**기대 결과**:
- ⚠️ 일부 에이전트 실패 가능
- ✅ 성공한 에이전트만 점수 반영
- ✅ "분석 불완전" 메시지

---

## 🔍 디버깅 & 로깅

### 로그 위치

```
log/
├── analysis_20251210_103045.log    # 분석 로그
└── result_20251210_103045.json     # 분석 결과 JSON
```

### 로그 레벨 조정

```python
# app/agents/managers/analyzer_manager.py
import logging

# INFO → DEBUG로 변경
logger.setLevel(logging.DEBUG)
```

### FastAPI 로그 확인

```bash
# 서버 실행 시 --log-level 옵션
uvicorn app.main:app --reload --log-level debug
```

---

## ⚡ 성능 최적화

### 1. 매니저 재사용

❌ **나쁜 예**:
```python
# 매번 새로 생성 (느림)
for audio in audio_files:
    analyzer = SpeechAnalysisManager()  # 매번 초기화
    result = analyzer.analyze_parallel(audio)
```

✅ **좋은 예**:
```python
# 한 번만 생성 후 재사용 (빠름)
analyzer = SpeechAnalysisManager()
for audio in audio_files:
    result = analyzer.analyze_parallel(audio)  # 재사용
```

### 2. 병렬 처리 활용

이미 구현됨:
- `analyze_parallel()` 내부에서 ThreadPoolExecutor 사용
- Validate 후 6개 에이전트 병렬 실행 (max_workers=5)

---

## 📚 비교 요약

| 항목 | asr_python_test (Streamlit) | app (FastAPI) |
|------|----------------------------|---------------|
| **UI** | Streamlit 웹 인터페이스 | Swagger UI / API |
| **실행 방식** | `streamlit run app.py` | `uvicorn app.main:app` |
| **테스트** | 웹 브라우저 필요 | 5가지 방법 가능 |
| **통합** | 독립 실행형 | 백엔드 API 통합 |
| **자동화** | 어려움 | 쉬움 (API 호출) |
| **배포** | Streamlit Cloud | Docker / 클라우드 |

---

## ✅ 최종 결론

### 🎉 Streamlit 없이 완벽하게 작동합니다!

**이유**:
1. ✅ **FastAPI 엔드포인트 이미 구현됨** (`/api/v1/evaluate`)
2. ✅ **analyzer_manager 통합 완료** (app/agents/managers/)
3. ✅ **5가지 테스트 방법 제공** (Swagger UI, Python, curl, Postman, Jupyter)
4. ✅ **로직 100% 동일** (asr_python_test와 동일한 결과)

**권장 테스트 방법**:
1. **가장 쉬움**: Swagger UI (`http://localhost:8000/docs`)
2. **자동화**: Python 스크립트
3. **개발 중**: Postman / Insomnia
4. **탐색적 분석**: Jupyter Notebook
5. **CI/CD**: curl / API 호출

**다음 단계**:
1. FastAPI 서버 실행: `uvicorn app.main:app --reload`
2. Swagger UI 접속: `http://localhost:8000/docs`
3. `/api/v1/evaluate` 엔드포인트 테스트
4. 응답 확인 및 검증

**Streamlit은 더 이상 필요하지 않습니다!** 🎉
