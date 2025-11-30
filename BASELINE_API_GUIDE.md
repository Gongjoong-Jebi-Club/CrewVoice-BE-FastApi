# Baseline 관리 API 가이드

## 🎯 개요

**Baseline**은 음성 분석의 기준점이 되는 데이터입니다.
다수의 샘플 음성 파일을 분석하여 평균값, 표준편차 등의 통계를 계산하고, 이를 바탕으로 개인의 음성을 평가합니다.

## 📊 Baseline이 필요한 이유

### 문제상황
- **Speed Analyzer**: sample 폴더의 파일로 매번 baseline 계산 (비효율적)
- **Intonation/Tone**: baseline 없으면 기본 점수만 제공
- **불안정성**: 파일 없으면 오류 발생

### 해결방법
- 샘플 파일 업로드 → Baseline JSON 생성 → 저장
- 이후 분석 시 저장된 Baseline 사용
- 안정적이고 빠른 분석

## 🛠️ Baseline 생성 대상

| 에이전트 | Baseline 내용 | 필수 여부 |
|---------|--------------|----------|
| **Speed** | 평균 속도, 표준편차, 임계값 | ✅ 필수 |
| **Intonation** | 억양 특징 통계 (20개 항목) | ⚠️ 권장 |
| **Tone** | 톤 특징 통계 (성별/언어별) | ⚠️ 권장 |
| **Accent** | 향후 확장용 | ❌ 선택 |
| **Pronunciation** | Azure API 사용 (불필요) | ❌ 불필요 |
| **Pause** | Azure 데이터 활용 (불필요) | ❌ 불필요 |

## 📡 API 엔드포인트

### 1. Baseline 생성

```bash
POST /api/v1/baseline/generate
```

**요청 파라미터:**

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `files` | File[] | O | - | 샘플 WAV 파일들 (최소 2개, 3개 이상 권장) |
| `baseline_name` | String | X | `default` | Baseline 이름 |
| `language_code` | String | X | `ko-KR` | 언어 코드 |
| `gender` | String | X | `F` | 성별 (F, M) |

**cURL 예시:**

```bash
curl -X POST "http://localhost:8005/api/v1/baseline/generate" \
  -F "files=@sample1.wav" \
  -F "files=@sample2.wav" \
  -F "files=@sample3.wav" \
  -F "baseline_name=female_korean" \
  -F "language_code=ko-KR" \
  -F "gender=F"
```

**응답 예시:**

```json
{
  "message": "Baseline 생성 완료: 성공 4개, 실패 0개",
  "baseline_name": "female_korean",
  "language_code": "ko-KR",
  "gender": "F",
  "sample_count": 3,
  "results": {
    "speed": {
      "baseline_name": "female_korean",
      "sample_count": 3,
      "statistics": {
        "mean": 4.25,
        "std": 0.35,
        "median": 4.20,
        "min": 3.95,
        "max": 4.65
      },
      "thresholds": {
        "optimal_min": 3.90,
        "optimal_max": 4.60,
        "slow_threshold": 3.72,
        "fast_threshold": 4.78
      }
    },
    "intonation": {
      "baseline_name": "female_korean",
      "language_code": "ko-KR",
      "sample_count": 3,
      "reference_features": { /* 억양 특징 통계 */ }
    },
    "tone": {
      "baseline_name": "female_korean",
      "genders": {
        "F": {
          "languages": {
            "ko-KR": {
              "sample_count": 3,
              "features": { /* 톤 특징 통계 */ }
            }
          }
        }
      }
    },
    "accent": {
      "baseline_name": "female_korean",
      "sample_count": 3,
      "note": "Accent analyzer currently uses dynamic analysis"
    }
  }
}
```

### 2. Baseline 목록 조회

```bash
GET /api/v1/baseline/list
```

**cURL 예시:**

```bash
curl -X GET "http://localhost:8005/api/v1/baseline/list"
```

**응답 예시:**

```json
{
  "baselines": {
    "speed": ["default", "female_korean", "male_english"],
    "intonation": ["default", "female_korean"],
    "tone": ["default", "female_korean"],
    "accent": ["default"]
  },
  "total_count": 9
}
```

### 3. Baseline 삭제

```bash
DELETE /api/v1/baseline/delete
```

**요청 파라미터:**

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| `agent` | String | O | 에이전트 이름 (speed, intonation, tone, accent) |
| `baseline_name` | String | O | 삭제할 baseline 이름 |

**cURL 예시:**

```bash
curl -X DELETE "http://localhost:8005/api/v1/baseline/delete" \
  -F "agent=speed" \
  -F "baseline_name=female_korean"
```

**응답 예시:**

```json
{
  "message": "Baseline 삭제 성공: speed_female_korean",
  "agent": "speed",
  "baseline_name": "female_korean"
}
```

### 4. Baseline 헬스체크

```bash
GET /api/v1/baseline/health
```

**cURL 예시:**

```bash
curl -X GET "http://localhost:8005/api/v1/baseline/health"
```

**응답 예시:**

```json
{
  "status": "ok",
  "module": "baseline_management",
  "baseline_directory": "baselines",
  "directory_exists": true,
  "supported_agents": ["speed", "intonation", "tone", "accent"]
}
```

## 📁 생성되는 파일 구조

Baseline 생성 시 `baselines/` 디렉토리에 JSON 파일로 저장됩니다:

```
baselines/
├── speed_default.json
├── speed_female_korean.json
├── intonation_default.json
├── intonation_female_korean.json
├── tone_default.json
├── tone_female_korean.json
├── accent_default.json
└── accent_female_korean.json
```

### Baseline JSON 예시

#### Speed Baseline (`speed_default.json`)

```json
{
  "baseline_name": "default",
  "sample_count": 5,
  "statistics": {
    "mean": 4.25,
    "std": 0.35,
    "median": 4.20,
    "min": 3.95,
    "max": 4.65
  },
  "thresholds": {
    "optimal_min": 3.90,
    "optimal_max": 4.60,
    "slow_threshold": 3.72,
    "fast_threshold": 4.78
  },
  "raw_rates": [3.95, 4.10, 4.20, 4.35, 4.65]
}
```

#### Tone Baseline (`tone_default.json`)

```json
{
  "baseline_name": "default",
  "genders": {
    "F": {
      "languages": {
        "ko-KR": {
          "sample_count": 5,
          "features": {
            "f0_mean": {
              "mean": 220.5,
              "std": 15.2,
              "median": 218.0,
              "min": 200.0,
              "max": 245.0
            },
            "hnr_like": {
              "mean": 15.3,
              "std": 2.1,
              "median": 15.0,
              "min": 12.5,
              "max": 18.5
            }
            // ... 기타 특징들
          }
        }
      }
    }
  }
}
```

## 💡 사용 권장사항

### 샘플 파일 준비

1. **최소 수량**: 2개 이상 (3개 이상 권장)
2. **품질**: 깨끗한 음성, 배경 소음 최소화
3. **다양성**: 여러 사람의 음성 또는 다양한 문장
4. **일관성**: 동일한 환경에서 녹음

### Baseline 이름 규칙

```bash
# 권장 명명 규칙
{gender}_{language}         # 예: female_korean, male_english
{purpose}_{gender}          # 예: crew_female, announcer_male
{custom_name}               # 예: training_v1, production
```

### 언어/성별 조합 예시

```bash
# 한국어 여성
baseline_name=female_korean
language_code=ko-KR
gender=F

# 영어 남성
baseline_name=male_english
language_code=en-US
gender=M

# 한국어 남성
baseline_name=male_korean
language_code=ko-KR
gender=M
```

## 🔄 Baseline 업데이트 워크플로우

### 1. 초기 Baseline 생성

```bash
# 샘플 파일 준비 (sample1.wav ~ sample5.wav)
curl -X POST "http://localhost:8005/api/v1/baseline/generate" \
  -F "files=@sample1.wav" \
  -F "files=@sample2.wav" \
  -F "files=@sample3.wav" \
  -F "files=@sample4.wav" \
  -F "files=@sample5.wav" \
  -F "baseline_name=production_v1"
```

### 2. Baseline 확인

```bash
# 생성된 baseline 목록 조회
curl -X GET "http://localhost:8005/api/v1/baseline/list"
```

### 3. 음성 분석 시 자동 사용

```bash
# 분석 시 자동으로 'default' baseline 사용
# 또는 생성된 baseline 이름과 일치하면 해당 baseline 사용
curl -X POST "http://localhost:8005/api/v1/asr/analyze" \
  -F "file=@user_voice.wav"
```

### 4. 필요시 Baseline 업데이트

```bash
# 기존 baseline 삭제
curl -X DELETE "http://localhost:8005/api/v1/baseline/delete" \
  -F "agent=speed" \
  -F "baseline_name=production_v1"

# 새 샘플로 재생성
curl -X POST "http://localhost:8005/api/v1/baseline/generate" \
  -F "files=@new_sample1.wav" \
  -F "files=@new_sample2.wav" \
  -F "baseline_name=production_v2"
```

## 🎓 실전 예제

### Python 예제

```python
import requests
from pathlib import Path

url = "http://localhost:8005/api/v1/baseline/generate"

# 샘플 파일 준비
sample_dir = Path("samples")
sample_files = list(sample_dir.glob("*.wav"))

# 파일 업로드
files = [('files', open(f, 'rb')) for f in sample_files]

data = {
    'baseline_name': 'female_korean_crew',
    'language_code': 'ko-KR',
    'gender': 'F'
}

response = requests.post(url, files=files, data=data)
result = response.json()

print(f"✓ Baseline 생성 완료: {result['message']}")
print(f"  - Speed: {result['results']['speed']['statistics']['mean']:.2f} 음절/초")
print(f"  - 샘플 수: {result['sample_count']}개")

# 파일 닫기
for _, file in files:
    file.close()
```

### JavaScript 예제

```javascript
const FormData = require('form-data');
const fs = require('fs');
const axios = require('axios');
const path = require('path');

async function generateBaseline() {
  const form = new FormData();

  // 샘플 파일 추가
  const sampleFiles = [
    'sample1.wav',
    'sample2.wav',
    'sample3.wav'
  ];

  sampleFiles.forEach(file => {
    form.append('files', fs.createReadStream(path.join('samples', file)));
  });

  form.append('baseline_name', 'female_korean_crew');
  form.append('language_code', 'ko-KR');
  form.append('gender', 'F');

  try {
    const response = await axios.post(
      'http://localhost:8005/api/v1/baseline/generate',
      form,
      { headers: form.getHeaders() }
    );

    console.log('✓ Baseline 생성 완료:', response.data.message);
    console.log('  - 샘플 수:', response.data.sample_count);
    console.log('  - 결과:', response.data.results);
  } catch (error) {
    console.error('Error:', error.response?.data || error.message);
  }
}

generateBaseline();
```

## ⚠️ 주의사항

1. **파일 형식**: WAV 파일만 지원
2. **최소 수량**: 최소 2개, 3개 이상 권장 (통계의 신뢰성)
3. **일관성**: 동일한 언어/성별/환경의 샘플 사용
4. **덮어쓰기**: 동일한 이름의 baseline 생성 시 기존 파일 덮어쓰기
5. **Git 관리**: `baselines/` 디렉토리는 `.gitignore`에 포함하는 것을 권장

## 🐛 트러블슈팅

### "분석 가능한 파일이 없습니다"
- **원인**: 모든 샘플 파일의 분석이 실패함
- **해결**: WAV 파일 품질 확인, 소음 제거, 파일 형식 확인

### "Baseline 생성 실패"
- **원인**: 특정 에이전트의 분석 오류
- **해결**: 로그 확인, 샘플 파일 품질 개선

### Speed Analyzer 초기화 실패
- **원인**: `baselines/` 디렉토리 또는 `speed_default.json` 없음
- **해결**: Baseline 생성 API로 먼저 baseline 생성

## 📞 문의

Baseline 관련 문제가 발생하면 Issue를 등록해주세요.
