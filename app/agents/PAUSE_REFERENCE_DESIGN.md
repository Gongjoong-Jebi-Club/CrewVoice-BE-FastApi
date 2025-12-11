# Pause Reference 폴더 설계 문서

## 📋 개요

Pause baseline 생성을 위한 reference 데이터 저장 및 관리 설계

---

## 📁 폴더 구조 설계

### ✅ 권장 구조 (Option 1): baselines 폴더 내부 통합

```
app/agents/
├── analyzers/           # 7개 분석기
├── managers/            # analyzer_manager, baseline_manager
├── utils/               # comment_generator
├── baselines/           # 🎯 Baseline 관련 모든 데이터 집중 관리
│   ├── pause_reference/ # 🆕 Pause baseline 생성용 reference 데이터
│   │   ├── .gitkeep
│   │   ├── README.md    # 사용 가이드
│   │   ├── F_ko-KR_track1.txt    # 원본 스크립트 (수동 작성)
│   │   ├── F_ko-KR_track1.json   # Azure 분석 결과 (자동 생성)
│   │   ├── F_en-US_track1.txt
│   │   ├── F_en-US_track1.json
│   │   └── ...
│   ├── tone_default.json          # Tone baseline
│   ├── speed_default.json         # Speed baseline
│   ├── pause_default.json         # Pause baseline (pause_reference로부터 생성)
│   └── intonation_default.json    # Intonation baseline
└── sample/              # 샘플 음성 파일
    ├── F_ko-KR_track1.wav
    ├── F_en-US_track1.wav
    └── ...
```

**장점**:
- ✅ Baseline 관련 모든 데이터를 `baselines/` 폴더에 집중
- ✅ pause_reference가 pause_default.json과 같은 폴더에 위치 (논리적 연관성)
- ✅ 모듈 구조가 명확: analyzers(로직) / baselines(데이터) / sample(원본)

**단점**:
- ⚠️ asr_python_test와 구조가 다름 (asr는 최상위에 pause_reference)

---

### Alternative (Option 2): 최상위 폴더 분리

```
app/agents/
├── analyzers/
├── managers/
├── utils/
├── baselines/
│   ├── tone_default.json
│   ├── speed_default.json
│   ├── pause_default.json
│   └── intonation_default.json
├── pause_reference/     # 🆕 최상위에 별도 폴더
│   ├── F_ko-KR_track1.txt
│   ├── F_ko-KR_track1.json
│   └── ...
└── sample/
```

**장점**:
- ✅ asr_python_test와 동일한 구조 유지

**단점**:
- ⚠️ baseline 관련 데이터가 분산됨 (baselines/, pause_reference/)

---

## 🎯 최종 권장: Option 1 (baselines/pause_reference/)

### 이유
1. **논리적 일관성**: Pause baseline 생성을 위한 전처리 데이터이므로 baselines 폴더 내부가 적합
2. **데이터 집중화**: Baseline 관련 모든 파일을 한 곳에서 관리
3. **확장성**: 향후 다른 baseline에도 reference 데이터가 필요하면 동일한 패턴 적용 가능

---

## 📝 파일 네이밍 규칙

### 파일명 패턴
```
{Gender}_{Language}_{TrackID}.{extension}
```

### 예시
- `F_ko-KR_track1.wav` (sample 폴더)
- `F_ko-KR_track1.txt` (pause_reference 폴더, 원본 스크립트)
- `F_ko-KR_track1.json` (pause_reference 폴더, Azure 분석 결과)

### 필드 설명
| 필드 | 값 | 설명 |
|------|-----|------|
| Gender | `F` / `M` | 성별 (Female/Male) |
| Language | `ko-KR` / `en-US` | 언어 코드 |
| TrackID | `track1`, `track2`, ... | 트랙 번호 |

---

## 🔄 사용 플로우

### 1단계: 샘플 준비
```bash
# sample 폴더에 WAV 파일 준비
app/agents/sample/
├── F_ko-KR_track1.wav
├── F_ko-KR_track2.wav
└── F_en-US_track1.wav
```

### 2단계: 원본 스크립트 작성
```bash
# pause_reference 폴더에 TXT 파일 수동 작성
app/agents/baselines/pause_reference/
├── F_ko-KR_track1.txt  # 내용: "안녕하세요. 오늘은 날씨가 좋습니다."
├── F_ko-KR_track2.txt
└── F_en-US_track1.txt  # 내용: "Hello. It's a beautiful day today."
```

### 3단계: Azure 전처리 실행
```python
from app.agents.managers.baseline_manager import BaselineManager

manager = BaselineManager()

# Azure API 호출하여 JSON 파일 생성
manager.preprocess_samples_for_pause(
    sample_dir=None,  # 기본값: app/agents/sample
    pause_reference_dir=None  # 기본값: app/agents/baselines/pause_reference
)
```

**결과**:
```bash
app/agents/baselines/pause_reference/
├── F_ko-KR_track1.txt   # 원본
├── F_ko-KR_track1.json  # 🆕 생성됨 (Azure 분석 결과)
├── F_ko-KR_track2.txt
├── F_ko-KR_track2.json  # 🆕 생성됨
└── ...
```

### 4단계: Pause Baseline 생성
```python
# pause_reference 데이터로부터 pause_default.json 생성
manager.generate_pause_baseline_from_samples(
    sample_dir=None,
    pause_reference_dir=None,
    output_filename="pause_default.json"
)
```

**결과**:
```bash
app/agents/baselines/
├── pause_default.json  # 🆕 생성됨
├── pause_reference/
│   ├── F_ko-KR_track1.txt
│   ├── F_ko-KR_track1.json
│   └── ...
└── ...
```

---

## 🛠️ 코드 수정 사항

### baseline_manager.py 수정 (이미 반영됨)

```python
class BaselineManager:
    def __init__(self, baseline_dir: str = "baselines"):
        # app/agents/baselines
        self.baseline_dir = Path(__file__).parent.parent / "baselines"
        self.baseline_dir.mkdir(exist_ok=True, parents=True)

        # app/agents/sample
        self.sample_dir = Path(__file__).parent.parent / "sample"
        self.sample_dir.mkdir(exist_ok=True, parents=True)

    def preprocess_samples_for_pause(
        self,
        sample_dir: Path | None = None,
        pause_reference_dir: Path | None = None,
    ) -> int:
        if sample_dir is None:
            sample_dir = self.sample_dir
        if pause_reference_dir is None:
            # 🎯 기본값: baselines/pause_reference
            pause_reference_dir = self.baseline_dir / "pause_reference"

        pause_reference_dir.mkdir(exist_ok=True)
        # ... 나머지 로직
```

---

## 📂 Git 관리 전략

### .gitignore 설정 권장

```gitignore
# app/agents/.gitignore

# Baseline 데이터 (파일 크기가 큰 경우)
baselines/*.json

# Pause reference 데이터
baselines/pause_reference/*.json  # Azure 결과는 제외 (재생성 가능)

# 단, TXT 파일은 커밋 (수동 작성이므로 버전 관리 필요)
!baselines/pause_reference/*.txt
!baselines/pause_reference/README.md

# 샘플 음성 파일 (파일 크기 큰 경우)
sample/*.wav
sample/*.mp3
```

### 커밋 대상
- ✅ `baselines/pause_reference/README.md` (가이드)
- ✅ `baselines/pause_reference/.gitkeep` (폴더 유지)
- ✅ `baselines/pause_reference/*.txt` (원본 스크립트, 수동 작성)

### 커밋 제외 대상
- ❌ `baselines/pause_reference/*.json` (Azure API 결과, 재생성 가능)
- ❌ `baselines/*.json` (Baseline 파일들, 재생성 가능)
- ❌ `sample/*.wav` (파일 크기가 큰 경우)

---

## 📚 Reference 데이터 관리 가이드

### pause_reference/README.md 내용 예시

```markdown
# Pause Reference 데이터

## 개요
Pause baseline 생성을 위한 reference 데이터 폴더

## 파일 구성
- `*.txt`: 원본 스크립트 (수동 작성, Git 커밋)
- `*.json`: Azure 분석 결과 (자동 생성, Git 제외)

## 사용 방법

### 1. TXT 파일 작성
파일명: `{Gender}_{Language}_{TrackID}.txt`
예시: `F_ko-KR_track1.txt`

내용 예시:
```
안녕하세요. 오늘은 날씨가 좋습니다. 산책하기 좋은 날입니다.
```

### 2. Azure 전처리 실행
```python
from app.agents.managers.baseline_manager import BaselineManager
manager = BaselineManager()
manager.preprocess_samples_for_pause()
```

### 3. Baseline 생성
```python
manager.generate_pause_baseline_from_samples()
```

## 주의사항
- WAV 파일과 TXT 파일명은 확장자를 제외하고 동일해야 함
- TXT 파일은 UTF-8 인코딩 사용
- 문장부호(. , !)를 정확히 사용 (Pause context 분류에 사용됨)
```

---

## 🔍 검증 체크리스트

- [ ] `app/agents/baselines/pause_reference/` 폴더 생성
- [ ] `.gitkeep` 파일 추가
- [ ] `README.md` 작성
- [ ] baseline_manager.py의 경로 설정 확인
- [ ] 샘플 TXT 파일 작성 및 테스트
- [ ] Azure 전처리 정상 동작 확인
- [ ] Baseline 생성 정상 동작 확인
- [ ] .gitignore 설정 확인

---

## 📌 요약

| 항목 | 경로 |
|------|------|
| **Pause reference 폴더** | `app/agents/baselines/pause_reference/` |
| **원본 스크립트 (TXT)** | `app/agents/baselines/pause_reference/{파일명}.txt` |
| **Azure 결과 (JSON)** | `app/agents/baselines/pause_reference/{파일명}.json` |
| **생성된 Baseline** | `app/agents/baselines/pause_default.json` |
| **샘플 WAV 파일** | `app/agents/sample/{파일명}.wav` |

**핵심 원칙**: Baseline 관련 모든 데이터를 `baselines/` 폴더에 집중하여 관리 📁
