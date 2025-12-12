# app/agents 폴더 구조

## 📁 전체 구조 (2025-12-10)

```
app/agents/
│
├── 📄 __init__.py
├── 📄 .gitignore                    # Git 관리 규칙
├── 📄 PAUSE_REFERENCE_DESIGN.md     # Pause reference 설계 문서
├── 📄 STRUCTURE.md                  # 이 파일
│
├── 📂 analyzers/                    # 🎯 7개 분석기 (Validate + 6개)
│   ├── 📄 __init__.py
│   ├── 📄 validate.py               # 1. 검증 에이전트 (Azure API)
│   ├── 📄 accent.py                 # 2. 강조 분석
│   ├── 📄 pronunciation.py          # 3. 발음 분석
│   ├── 📄 pause.py                  # 4. 휴지 분석
│   ├── 📄 intonation.py             # 5. 억양 분석
│   ├── 📄 speed.py                  # 6. 속도 분석
│   └── 📄 tone.py                   # 7. 톤 분석
│
├── 📂 managers/                     # 🎛️ 매니저 (통합 관리)
│   ├── 📄 __init__.py
│   ├── 📄 analyzer_manager.py       # 에이전트 실행 관리
│   └── 📄 baseline_manager.py       # Baseline 생성/관리
│
├── 📂 utils/                        # 🛠️ 유틸리티
│   ├── 📄 __init__.py
│   └── 📄 comment_generator.py      # AI 코멘트 생성 (OpenAI)
│
├── 📂 baselines/                    # 📊 Baseline 데이터 저장소
│   ├── 📄 tone_default.json         # Tone baseline
│   ├── 📄 speed_default.json        # Speed baseline
│   ├── 📄 pause_default.json        # Pause baseline (생성됨)
│   ├── 📄 intonation_default.json   # Intonation baseline
│   │
│   └── 📂 pause_reference/          # 🆕 Pause baseline 전처리 데이터
│       ├── 📄 .gitkeep
│       ├── 📄 README.md             # 사용 가이드
│       ├── 📄 *.txt                 # 원본 스크립트 (수동 작성)
│       └── 📄 *.json                # Azure 분석 결과 (자동 생성)
│
└── 📂 sample/                       # 🎤 샘플 음성 파일
    ├── 📄 .gitkeep
    └── 📄 *.wav                     # 샘플 WAV 파일들
```

---

## 🔄 데이터 플로우

### 1️⃣ 평가 플로우 (analyzer_manager.py)
```
사용자 음성 (WAV)
    ↓
┌─────────────────────────────────────┐
│ 1. Validate Agent (순차 실행)      │
│    - Azure Pronunciation Assessment │
│    - 스크립트 검증                  │
└─────────────────────────────────────┘
    ↓
    ├─ 검증 실패 → 모든 에이전트 0점 처리
    └─ 검증 통과 → 다음 단계
    ↓
┌─────────────────────────────────────┐
│ 2. 6개 Agent 병렬 실행              │
│    (ThreadPoolExecutor, max=5)      │
│    ├─ Accent                        │
│    ├─ Pronunciation                 │
│    ├─ Pause                         │
│    ├─ Intonation                    │
│    ├─ Speed                         │
│    └─ Tone                          │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 3. 결과 통합                        │
│    - 총점 계산                      │
│    - 평균 점수 계산                 │
│    - JSON 저장 (log/)               │
│    - AI 코멘트 생성 (OpenAI)        │
└─────────────────────────────────────┘
    ↓
최종 평가 결과
```

### 2️⃣ Baseline 생성 플로우 (baseline_manager.py)

#### Pause Baseline 생성
```
sample/*.wav + pause_reference/*.txt
    ↓
┌─────────────────────────────────────┐
│ 1. Azure 전처리                     │
│    preprocess_samples_for_pause()   │
│    - Azure Speech API 호출          │
│    - JSON 파일 생성                 │
└─────────────────────────────────────┘
    ↓
pause_reference/*.json (생성됨)
    ↓
┌─────────────────────────────────────┐
│ 2. Baseline 생성                    │
│    generate_pause_baseline_...()    │
│    - JSON 데이터 분석               │
│    - 통계 계산 (mean, std)          │
└─────────────────────────────────────┘
    ↓
baselines/pause_default.json
```

#### Tone/Speed Baseline 생성
```
sample/*.wav
    ↓
┌─────────────────────────────────────┐
│ generate_tone_baseline_...()        │
│ generate_speed_baseline_...()       │
│    - 음성 특징 추출                 │
│    - 통계 계산                      │
└─────────────────────────────────────┘
    ↓
baselines/tone_default.json
baselines/speed_default.json
```

---

## 📦 주요 모듈별 역할

### analyzers/ (분석기)
| 모듈 | 역할 | Azure API 사용 |
|------|------|----------------|
| `validate.py` | 스크립트 검증, Azure 데이터 생성 | ✅ |
| `accent.py` | 강조(Pitch, Energy) 분석 | ✅ (STT) |
| `pronunciation.py` | 발음 정확도 분석 | ❌ (Validate 데이터 재사용) |
| `pause.py` | 휴지 분석 | ❌ (Validate 데이터 재사용) |
| `intonation.py` | 억양(Rhythm, Ending) 분석 | ✅ (STT) |
| `speed.py` | 발화 속도 분석 | ❌ |
| `tone.py` | 톤(Clarity, Stability) 분석 | ❌ |

### managers/ (관리자)
| 모듈 | 역할 |
|------|------|
| `analyzer_manager.py` | 7개 에이전트 실행 및 결과 통합 |
| `baseline_manager.py` | Baseline 생성/로드/관리 |

### utils/ (유틸리티)
| 모듈 | 역할 |
|------|------|
| `comment_generator.py` | OpenAI API를 사용한 AI 코멘트 생성 |

---

## 🔧 환경 변수 (.env)

```bash
# Azure Speech API
AZURE_SPEECH_KEY=your_azure_key
AZURE_SPEECH_REGION=koreacentral

# OpenAI API (AI 코멘트 생성)
OPENAI_API_KEY=your_openai_key
```

---

## 📊 파일 네이밍 규칙

### 샘플 음성 파일 (sample/)
```
{Gender}_{Language}_{TrackID}.wav
```
예시: `F_ko-KR_track1.wav`

### Reference 스크립트 (baselines/pause_reference/)
```
{Gender}_{Language}_{TrackID}.txt  # 원본 스크립트
{Gender}_{Language}_{TrackID}.json # Azure 분석 결과
```
예시:
- `F_ko-KR_track1.txt` (수동 작성)
- `F_ko-KR_track1.json` (자동 생성)

---

## 🚀 사용 예시

### 1. 음성 평가
```python
from app.agents.managers.analyzer_manager import SpeechAnalysisManager

manager = SpeechAnalysisManager()
result = manager.analyze_parallel(
    wav_path="path/to/audio.wav",
    reference_text="안녕하세요. 오늘은 날씨가 좋습니다.",
    language_code="ko-KR",
    gender="F"
)
```

### 2. Baseline 생성
```python
from app.agents.managers.baseline_manager import BaselineManager

manager = BaselineManager()

# 모든 baseline 생성
manager.generate_all_baselines_from_samples()

# 또는 개별 생성
manager.generate_pause_baseline_from_samples()
```

### 3. AI 코멘트 생성
```python
from app.agents.utils.comment_generator import AICommentGenerator

generator = AICommentGenerator()
agent_outputs = manager.get_agent_outputs(result)
comment = generator.generate_comment(agent_outputs)
```

---

## 📋 Git 관리 전략

### ✅ 커밋 대상
- `analyzers/*.py` (분석기 코드)
- `managers/*.py` (매니저 코드)
- `utils/*.py` (유틸리티 코드)
- `baselines/pause_reference/*.txt` (원본 스크립트)
- `baselines/pause_reference/README.md`
- `.gitignore`

### ❌ 커밋 제외 (.gitignore)
- `baselines/*.json` (Baseline 파일, 재생성 가능)
- `baselines/pause_reference/*.json` (Azure 결과, 재생성 가능)
- `sample/*.wav` (샘플 음성, 파일 크기 큼)
- `log/` (로그 파일)
- `__pycache__/` (Python 캐시)

---

## 🔗 관련 문서
- **Pause Reference 설계**: [PAUSE_REFERENCE_DESIGN.md](PAUSE_REFERENCE_DESIGN.md)
- **Pause Reference 사용 가이드**: [baselines/pause_reference/README.md](baselines/pause_reference/README.md)

---

## 📈 버전 히스토리
- **2025-12-10**: 초기 구조 설계 및 pause_reference 폴더 추가
- **2025-12-10**: baseline_manager.py 버그 수정 (script_word_idx → i)
