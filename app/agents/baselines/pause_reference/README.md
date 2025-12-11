# Pause Reference 데이터

## 📋 개요
Pause baseline 생성을 위한 reference 데이터 폴더입니다.

## 📂 파일 구성
- `*.txt`: 원본 스크립트 (수동 작성, Git 커밋 대상)
- `*.json`: Azure 분석 결과 (자동 생성, Git 제외)

---

## 🚀 사용 방법

### 1단계: WAV 파일 준비
먼저 `app/agents/sample/` 폴더에 샘플 음성 파일을 준비합니다.

```bash
app/agents/sample/
├── F_ko-KR_track1.wav
├── F_ko-KR_track2.wav
└── F_en-US_track1.wav
```

### 2단계: TXT 파일 작성
이 폴더(`app/agents/baselines/pause_reference/`)에 원본 스크립트를 작성합니다.

**파일명 규칙**: `{Gender}_{Language}_{TrackID}.txt`

**예시 파일명**:
- `F_ko-KR_track1.txt` (한국어 여성)
- `M_ko-KR_track1.txt` (한국어 남성)
- `F_en-US_track1.txt` (영어 여성)

**내용 예시** (`F_ko-KR_track1.txt`):
```
안녕하세요. 오늘은 날씨가 좋습니다. 산책하기 좋은 날입니다.
```

**⚠️ 중요**:
- WAV 파일과 TXT 파일명은 **확장자를 제외하고 동일**해야 합니다
- 문장부호(마침표, 쉼표)를 정확히 사용하세요 (Pause context 분류에 사용됨)
- UTF-8 인코딩으로 저장하세요

### 3단계: Azure 전처리 실행
Azure Speech API를 호출하여 JSON 분석 결과를 생성합니다.

```python
from app.agents.managers.baseline_manager import BaselineManager

manager = BaselineManager()

# Azure API 호출 (TXT 파일에 대응하는 JSON 생성)
manager.preprocess_samples_for_pause()
```

**실행 결과**:
```bash
app/agents/baselines/pause_reference/
├── F_ko-KR_track1.txt   # 기존 (수동 작성)
├── F_ko-KR_track1.json  # 🆕 생성됨 (Azure 분석 결과)
├── F_ko-KR_track2.txt
├── F_ko-KR_track2.json  # 🆕 생성됨
└── ...
```

### 4단계: Pause Baseline 생성
JSON 데이터를 분석하여 pause_default.json을 생성합니다.

```python
# Pause baseline 생성
manager.generate_pause_baseline_from_samples()
```

**실행 결과**:
```bash
app/agents/baselines/
├── pause_default.json  # 🆕 생성됨
└── pause_reference/
    ├── *.txt
    ├── *.json
    └── ...
```

---

## 📝 파일명 규칙 상세

### 형식
```
{Gender}_{Language}_{TrackID}.{extension}
```

### 필드 설명

| 필드 | 가능한 값 | 설명 |
|------|----------|------|
| **Gender** | `F`, `M` | 화자 성별 (Female/Male) |
| **Language** | `ko-KR`, `en-US` | 언어 코드 (Azure Speech API 형식) |
| **TrackID** | `track1`, `track2`, ... | 트랙 식별자 |
| **extension** | `.wav`, `.txt`, `.json` | 파일 유형 |

### 예시

| WAV 파일 | TXT 파일 | JSON 파일 | 설명 |
|----------|----------|-----------|------|
| `F_ko-KR_track1.wav` | `F_ko-KR_track1.txt` | `F_ko-KR_track1.json` | 한국어 여성 화자 1 |
| `M_ko-KR_track1.wav` | `M_ko-KR_track1.txt` | `M_ko-KR_track1.json` | 한국어 남성 화자 1 |
| `F_en-US_track1.wav` | `F_en-US_track1.txt` | `F_en-US_track1.json` | 영어 여성 화자 1 |

---

## 🔍 TXT 파일 작성 가이드

### 기본 원칙
1. **정확한 스크립트 작성**: WAV 파일의 음성 내용과 정확히 일치해야 함
2. **문장부호 사용**: 마침표(.), 쉼표(,)를 정확히 표시
3. **자연스러운 문장**: Pause context 분류에 사용되므로 자연스러운 문장 구조 유지

### 예시 1: 한국어 (ko-KR)
```
안녕하세요. 오늘은 날씨가 좋습니다. 산책하기 좋은 날입니다.
```

**Pause context 분류**:
- `좋습니다.` 뒤 pause → `after_period`
- `날입니다.` 뒤 pause → `after_period`

### 예시 2: 영어 (en-US)
```
Hello. It's a beautiful day today. Perfect for a walk.
```

**Pause context 분류**:
- `Hello.` 뒤 pause → `after_period`
- `today.` 뒤 pause → `after_period`

### 예시 3: 쉼표 포함
```
사과, 배, 바나나, 그리고 오렌지를 샀습니다.
```

**Pause context 분류**:
- `사과,` 뒤 pause → `after_comma`
- `배,` 뒤 pause → `after_comma`
- `바나나,` 뒤 pause → `after_comma`

---

## ⚙️ 고급 사용법

### 특정 폴더 지정
```python
from pathlib import Path

manager = BaselineManager()

# 커스텀 경로 사용
manager.preprocess_samples_for_pause(
    sample_dir=Path("custom/sample/path"),
    pause_reference_dir=Path("custom/reference/path")
)
```

### 기존 JSON 파일 건너뛰기
전처리 함수는 이미 존재하는 JSON 파일을 자동으로 건너뜁니다.

```bash
⏭️  건너뜀: F_ko-KR_track1.wav
처리 중: F_ko-KR_track2.wav
```

---

## 🐛 문제 해결

### Azure API 인증 오류
```
Azure Speech credentials not found. Check .env file.
```

**해결 방법**:
1. 프로젝트 루트의 `.env` 파일 확인
2. 다음 환경변수 설정:
   ```
   AZURE_SPEECH_KEY=your_key_here
   AZURE_SPEECH_REGION=your_region_here
   ```

### WAV 파일을 찾을 수 없음
```
sample/에 WAV 파일이 없습니다.
```

**해결 방법**:
- `app/agents/sample/` 폴더에 WAV 파일이 있는지 확인
- 파일명이 규칙에 맞는지 확인

### TXT 파일 없음 경고
```
⚠️  원본 스크립트 없음: F_ko-KR_track1.txt
baseline 생성 시 context 분류가 부정확할 수 있습니다.
```

**해결 방법**:
- pause_reference 폴더에 대응하는 TXT 파일 작성
- 파일명이 WAV 파일과 동일한지 확인 (확장자 제외)

---

## 📊 생성되는 데이터 형식

### JSON 파일 구조 (Azure 결과)
```json
{
  "NBest": [
    {
      "Words": [
        {
          "Word": "안녕하세요",
          "Offset": 0,
          "Duration": 1000000
        }
      ]
    }
  ]
}
```

### Pause Baseline 구조
```json
{
  "agent": "pause",
  "created_at": "2025-12-10T...",
  "languages": {
    "ko-KR": {
      "min_pause_threshold": 0.15,
      "contexts": {
        "after_period": {
          "features": {
            "pause_sec": {"mean": 0.5, "std": 0.1}
          }
        }
      }
    }
  }
}
```

---

## 📌 체크리스트

준비 단계:
- [ ] WAV 파일을 `app/agents/sample/`에 준비
- [ ] TXT 파일을 이 폴더에 작성
- [ ] 파일명 규칙 확인 (Gender_Language_TrackID)
- [ ] Azure 환경변수 설정 (.env)

실행 단계:
- [ ] `preprocess_samples_for_pause()` 실행
- [ ] JSON 파일 생성 확인
- [ ] `generate_pause_baseline_from_samples()` 실행
- [ ] `pause_default.json` 생성 확인

---

## 📚 참고 문서
- 상위 설계 문서: `app/agents/PAUSE_REFERENCE_DESIGN.md`
- Baseline Manager: `app/agents/managers/baseline_manager.py`
- Pause Analyzer: `app/agents/analyzers/pause.py`
