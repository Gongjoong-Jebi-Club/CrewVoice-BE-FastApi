# API 엔드포인트 비교 분석

## 📊 개요

현재 FastAPI 프로젝트에는 **2개의 음성 분석 API**가 존재합니다:

1. **POST `/api/v1/evaluate`** - Spring Boot 연동용 (동기 방식)
2. **POST `/api/v1/analysis/submit`** - React 클라이언트 직접 호출용 (비동기 방식)

---

## 🔍 상세 비교

### 1️⃣ POST `/api/v1/evaluate` (Spring Boot 연동용)

**파일**: [app/apis/v1/router_evaluate.py](router_evaluate.py)

#### 📋 기본 정보
| 항목 | 내용 |
|------|------|
| **엔드포인트** | `/api/v1/evaluate` |
| **메소드** | POST |
| **호출 주체** | Spring Boot 백엔드 서버 |
| **처리 방식** | **동기 (Synchronous)** |
| **응답 시간** | 15-30초 (분석 완료 후 응답) |

#### 📥 요청 파라미터 (Form Data)
```python
{
    "audio_file": UploadFile,          # 음성 파일 (.wav, .mp3, .m4a)
    "script_id": int,                  # 스크립트 ID
    "user_id": str,                    # 사용자 ID
    "reference_text": str              # 참조 텍스트 (필수)
}
```

#### 📤 응답 형식
```json
{
  "score_pronunciation": 85.5,        // 발음 점수 (0-100)
  "score_pause": 90.2,                // 휴지 점수
  "score_intonation": 88.0,           // 억양 점수
  "score_tone": 92.3,                 // 톤 점수
  "score_speed": 87.8,                // 속도 점수
  "score_accent": 84.1,               // 강조 점수
  "overall_score": 88.0,              // 전체 평균 점수
  "feedback_summary": "## 1. 강조 (Accent) 평가\n...",  // AI 피드백 (Markdown)
  "eval_id": "eval-test_user-1"       // 평가 ID
}
```

#### 🔄 처리 플로우
```
1. 파일 검증 (.wav, .mp3, .m4a만 허용)
   ↓
2. 임시 파일 저장 (tempfile.NamedTemporaryFile)
   ↓
3. 음성 분석 실행 (analyzer_manager.analyze_parallel) ⏱️ 15-30초
   ├─ Validate (스크립트 검증)
   ├─ Pronunciation (발음)
   ├─ Accent (강조)
   ├─ Pause (휴지)
   ├─ Intonation (억양)
   ├─ Speed (속도)
   └─ Tone (톤)
   ↓
4. AI 코멘트 생성 (comment_generator) ⏱️ 2-5초
   ↓
5. 응답 반환 (EvaluationResponse)
   ↓
6. 임시 파일 즉시 삭제 (finally 블록)
```

#### ⚙️ 주요 특징
- ✅ **즉시 분석 결과 반환** (분석 완료까지 대기)
- ✅ **AI 피드백 포함** (OpenAI API 사용)
- ✅ **6가지 점수 + 종합 점수** 반환
- ✅ **임시 파일 자동 삭제** (메모리 관리)
- ⚠️ **응답 시간 길음** (15-30초, Azure + OpenAI API 호출)
- ⚠️ **클라이언트 대기 필요** (동기 방식)

#### 🎯 사용 시나리오
```
[ Spring Boot ] ──HTTP POST──> [ FastAPI /evaluate ] ──분석 완료 대기──> [ 결과 반환 ]
                                        ↓
                                   15-30초 소요
                                   (분석 + AI 코멘트)
```

**예시 사용처**:
- Spring Boot가 사용자 요청을 받아 FastAPI에 전달
- FastAPI가 분석 완료 후 결과를 Spring Boot로 반환
- Spring Boot가 DB에 저장 후 프론트엔드에 전달

---

### 2️⃣ POST `/api/v1/analysis/submit` (React 직접 호출용)

**파일**: [app/apis/v1/router_submission.py](router_submission.py)

#### 📋 기본 정보
| 항목 | 내용 |
|------|------|
| **엔드포인트** | `/api/v1/analysis/submit` |
| **메소드** | POST |
| **호출 주체** | React/Vue 프론트엔드 (직접 호출) |
| **처리 방식** | **비동기 (Asynchronous)** |
| **응답 시간** | 1초 이하 (즉시 응답) |

#### 📥 요청 파라미터 (Form Data)
```python
{
    "file": UploadFile,                # 음성 파일 (.webm, .wav, .mp3, .ogg, .m4a)
    "user_id": int,                    # 사용자 ID
    "evaluation_id": int,              # 평가 세션 ID
    "step": str,                       # 평가 단계 (STEP2, STEP3 등)
    "question_index": int,             # 문제 번호 (0부터 시작)
    "language": str                    # 언어 코드 (kor, eng)
}
```

#### 📤 응답 형식
```json
{
  "code": 200,
  "message": "제출 성공",
  "data": {
    "submission_id": 1234             // 제출 ID (백그라운드 작업 추적용)
  }
}
```

#### 🔄 처리 플로우
```
1. 파일 검증 (.webm, .wav, .mp3, .ogg, .m4a 허용)
   ↓
2. 파일 저장 (temp/ 폴더에 영구 저장) 💾
   └─ 파일명: {user_id}_{evaluation_id}_{step}_Q{question_index}_{timestamp}.ext
   ↓
3. DB 기록 생성 (현재는 Mock)
   └─ submission_id 발급
   ↓
4. 백그라운드 작업 등록 (BackgroundTasks) 🔄
   └─ run_ai_analysis() 함수 등록 (비동기 실행)
   ↓
5. 즉시 응답 반환 (submission_id만) ⚡ < 1초
   ↓
6. [백그라운드에서 실행]
   ├─ STT 변환
   ├─ 발음 평가
   ├─ 억양 분석
   ├─ 속도 분석
   ├─ 톤 분석
   └─ DB 결과 저장 (TODO)
```

#### ⚙️ 주요 특징
- ✅ **즉시 응답 반환** (< 1초, submission_id만)
- ✅ **파일 영구 저장** (temp/ 폴더)
- ✅ **백그라운드 분석** (클라이언트 대기 불필요)
- ✅ **확장 가능한 파일 형식** (.webm 포함)
- ⚠️ **분석 결과 별도 조회 필요** (조회 API 미구현)
- ⚠️ **현재 Mock 구현** (run_ai_analysis는 실제 분석 안 함)

#### 🎯 사용 시나리오
```
[ React 클라이언트 ] ──HTTP POST──> [ FastAPI /analysis/submit ]
                                           ↓
                                      즉시 응답 (< 1초)
                                      submission_id 반환
                                           ↓
                        [백그라운드에서 분석 진행 15-30초]
                                           ↓
                        [별도 조회 API로 결과 확인] (TODO)
```

**예시 사용처**:
- 프론트엔드가 직접 FastAPI에 음성 파일 업로드
- 즉시 submission_id를 받아서 사용자에게 "제출 완료" 표시
- 백그라운드에서 분석 진행
- 나중에 조회 API로 결과 확인 (또는 웹소켓으로 실시간 알림)

---

## 📊 핵심 차이점 요약

| 항목 | `/evaluate` | `/analysis/submit` |
|------|-------------|-------------------|
| **호출 주체** | Spring Boot | React/Vue 클라이언트 |
| **처리 방식** | 동기 (Sync) | 비동기 (Async) |
| **응답 시간** | 15-30초 | < 1초 |
| **응답 내용** | 분석 결과 + AI 피드백 | submission_id만 |
| **파일 처리** | 임시 저장 → 즉시 삭제 | temp/ 폴더에 영구 저장 |
| **AI 코멘트** | ✅ 포함 | ❌ 없음 |
| **6가지 점수** | ✅ 반환 | ❌ 없음 (백그라운드 처리) |
| **구현 상태** | ✅ 완전 구현 | ⚠️ Mock (분석 미구현) |
| **파일 형식** | .wav, .mp3, .m4a | .webm, .wav, .mp3, .ogg, .m4a |
| **reference_text** | 필수 | 없음 |

---

## 🔗 아키텍처 다이어그램

### 현재 구조
```
┌─────────────────┐
│  Spring Boot    │
│   (Backend)     │
└────────┬────────┘
         │
         │ POST /api/v1/evaluate
         │ (동기, 15-30초 대기)
         ↓
┌─────────────────────────────┐
│     FastAPI (Python)        │
│  ┌─────────────────────┐    │
│  │ analyzer_manager    │    │
│  │ ├─ Validate         │    │
│  │ ├─ Pronunciation    │    │
│  │ ├─ Accent           │    │
│  │ ├─ Pause            │    │
│  │ ├─ Intonation       │    │
│  │ ├─ Speed            │    │
│  │ └─ Tone             │    │
│  └─────────────────────┘    │
│  ┌─────────────────────┐    │
│  │ comment_generator   │    │
│  │ (OpenAI API)        │    │
│  └─────────────────────┘    │
└─────────────────────────────┘
         │
         │ 분석 결과 + AI 피드백
         ↓
┌─────────────────┐
│  Spring Boot    │
│  (DB 저장)      │
└─────────────────┘


┌─────────────────┐
│ React/Vue       │
│ (Frontend)      │
└────────┬────────┘
         │
         │ POST /api/v1/analysis/submit
         │ (비동기, 즉시 응답)
         ↓
┌─────────────────────────────┐
│     FastAPI (Python)        │
│  ┌─────────────────────┐    │
│  │ submission_service  │    │
│  │ ├─ 파일 저장        │    │
│  │ └─ DB 기록 (Mock)   │    │
│  └─────────────────────┘    │
└─────────────────────────────┘
         │
         │ submission_id
         ↓
┌─────────────────┐
│ React/Vue       │
│ (제출 완료 표시) │
└─────────────────┘

[백그라운드에서]
┌─────────────────────────────┐
│ run_ai_analysis()           │
│ (TODO: 실제 분석 미구현)    │
└─────────────────────────────┘
```

---

## 🤔 제가 만든 건가요?

### ❌ 아닙니다. 두 API 모두 **이미 존재했던 코드**입니다.

**Git 히스토리 확인 결과**:
```
f589312 [ ✨ | #7 ] FastAPI 음성파일 업로드 API추가
```

두 API 모두 커밋 `f589312`에서 추가되었으며, **사용자 또는 팀원이 이미 만들어놓은 코드**입니다.

**제가 한 작업**:
- ✅ `/api/v1/evaluate`에서 사용하는 `analyzer_manager`와 `comment_generator`를 `asr_python_test`에서 `app/agents`로 통합
- ✅ `analyzer_manager`가 정상 작동하도록 import 경로 수정
- ✅ 누락된 패키지 설치 (`openai`)
- ✅ 버그 수정 (`comment_generator.py` f-string 오류, `run_ai_analysis` 주석 해제)
- ❌ API 엔드포인트 자체는 **수정하지 않음**

---

## 💡 권장 사항

### 1. `/api/v1/evaluate` 사용 (현재 완전 구현됨)
```python
# Spring Boot에서 호출
response = requests.post(
    "http://localhost:8000/api/v1/evaluate",
    files={"audio_file": open("audio.wav", "rb")},
    data={
        "script_id": 1,
        "user_id": "test_user",
        "reference_text": "안녕하세요. 오늘은 날씨가 좋습니다."
    }
)

# 즉시 분석 결과 획득
result = response.json()
print(f"평균 점수: {result['overall_score']}")
print(f"AI 피드백: {result['feedback_summary']}")
```

**장점**:
- ✅ 즉시 완전한 결과 획득
- ✅ AI 피드백 포함
- ✅ 추가 조회 API 불필요

**단점**:
- ⚠️ 응답 시간 15-30초 (클라이언트 대기)

---

### 2. `/api/v1/analysis/submit` 사용 (Mock, 개선 필요)
```python
# React에서 직접 호출
const response = await fetch("http://localhost:8000/api/v1/analysis/submit", {
    method: "POST",
    body: formData
});

const result = await response.json();
console.log(`제출 완료: ${result.data.submission_id}`);

// TODO: 별도 조회 API 필요
// await fetchAnalysisResult(result.data.submission_id);
```

**장점**:
- ✅ 즉시 응답 (< 1초)
- ✅ 사용자 경험 향상 (대기 시간 없음)

**단점**:
- ⚠️ 분석 결과 조회 API 미구현
- ⚠️ `run_ai_analysis`가 Mock (실제 분석 안 함)
- ⚠️ DB 연동 필요

**개선 필요 사항**:
1. `run_ai_analysis()`에서 실제 `analyzer_manager` 호출
2. DB 연동 (분석 결과 저장)
3. 조회 API 구현 (`GET /api/v1/analysis/status/{submission_id}`)

---

## 📝 결론

두 API는 **서로 다른 사용 사례**를 위해 설계되었습니다:

| 사용 케이스 | 권장 API |
|-------------|---------|
| **Spring Boot 통합** | `/api/v1/evaluate` ✅ |
| **즉시 결과 필요** | `/api/v1/evaluate` ✅ |
| **프론트엔드 직접 호출** | `/api/v1/analysis/submit` (개선 후) |
| **비동기 처리 필요** | `/api/v1/analysis/submit` (개선 후) |

**현재 상태**:
- `/api/v1/evaluate`: ✅ **완전히 작동** (바로 사용 가능)
- `/api/v1/analysis/submit`: ⚠️ **Mock 상태** (개선 필요)
