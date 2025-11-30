# 음성 분석 피드백 필터링 가이드

## 🎯 개요

음성 분석 결과가 너무 길어 사용자가 부담스러울 수 있습니다.
이를 해결하기 위해 **음성학적 임계값을 기반으로 개선이 필요한 항목만 표시**하는 필터링 기능을 제공합니다.

## 📊 음성학적 임계값 기준

| 점수 범위 | 등급 | 피드백 표시 | 설명 |
|----------|------|-------------|------|
| 90~100점 | 우수 (Excellent) | ❌ 표시 안 함 | 매우 우수한 수준, 개선 불필요 |
| 80~89점 | 양호 (Good) | ❌ 표시 안 함 | 우수한 수준, 경미한 개선만 필요 |
| 70~79점 | 보통 (Fair) | ✅ 개선 사항 표시 | 개선이 필요한 수준 |
| 60~69점 | 미흡 (Poor) | ✅ 상세 개선 사항 표시 | 많은 개선이 필요한 수준 |
| 60점 미만 | 불량 (Very Poor) | ✅ 매우 상세한 개선 사항 표시 | 집중적인 연습이 필요한 수준 |

**핵심 원칙**: **80점 미만 항목만 피드백 표시**

## 🎨 응답 형식 (3가지)

### 1. `compact` (추천 ⭐ - 기본값)

**가장 간결한 응답**: 전체 점수 + 개선 필요 항목만

```bash
curl -X POST "http://localhost:8005/api/v1/asr/analyze" \
  -F "file=@test.wav" \
  -F "response_format=compact"
```

**응답 예시**:
```json
{
  "overall_score": 82.5,
  "max_score": 100,
  "improvements": [
    {
      "category": "accent",
      "category_kr": "강조",
      "score": 72.0,
      "performance_level": "fair",
      "feedback": [
        "목소리 크기 변화가 적어 단조롭게 들릴 수 있습니다. 중요한 단어는 조금 더 힘주어 말해보세요."
      ]
    },
    {
      "category": "speed",
      "category_kr": "속도",
      "score": 75.0,
      "performance_level": "fair",
      "feedback": [
        "💡 조언: 발화 속도를 높이세요. 문장 간 불필요한 쉼을 줄이고, 더 자연스럽게 말하는 연습이 필요합니다."
      ]
    }
  ],
  "summary": "전체 점수: 82.50/100 | Pronunciation: 88.00/100 | Accent: 72.00/100"
}
```

### 2. `filtered`

**개선 필요 항목 + 전체 점수 정보**

```bash
curl -X POST "http://localhost:8005/api/v1/asr/analyze" \
  -F "file=@test.wav" \
  -F "response_format=filtered"
```

**응답 예시**:
```json
{
  "overall_score": 82.5,
  "max_score": 100,
  "improvements": [
    {
      "category": "accent",
      "category_kr": "강조",
      "score": 72.0,
      "performance_level": "fair",
      "feedback": [...]
    }
  ],
  "scores": {
    "pronunciation": {
      "score": 88.0,
      "max_score": 100,
      "feedback": [],
      "status": "success"
    },
    "accent": {
      "score": 72.0,
      "max_score": 100,
      "feedback": [...],
      "status": "success"
    }
    // ... 나머지 항목들
  },
  "analysis_summary": "전체 점수: 82.50/100 | ..."
}
```

### 3. `full`

**전체 상세 결과** (기존 방식)

```bash
curl -X POST "http://localhost:8005/api/v1/asr/analyze" \
  -F "file=@test.wav" \
  -F "response_format=full"
```

모든 분석 결과와 상세 데이터를 포함합니다.

## 🔍 에이전트별 피드백 필터링 규칙

### 1. Pronunciation (발음)
- **제외**: 점수 표시 ("종합 발음 점수: XX / 100")
- **포함**: 구체적인 개선 조언만

### 2. Accent (강조)
- **제외**:
  - 긍정적 피드백 ("좋습니다", "자연스러운")
  - 디버그 정보 ("Stds(...)")
- **포함**:
  - 개선 필요 사항 ("부족", "개선 필요", "너무", "단조", "불안정")

### 3. Intonation (억양)
- **제외**:
  - 기본 정보 ("언어: 한국어", "리듬 타입: ...")
  - 긍정적 평가 ("A등급", "S등급")
- **포함**:
  - 개선 필요 ("C등급", "D등급", "부자연", "부족")

### 4. Pause (휴지)
- **제외**: 점수 표시
- **포함**:
  - 문제점 ("부적절", "문제", "미흡", "불량")

### 5. Speed (속도)
- **제외**: 평가 등급
- **포함**:
  - 조언 ("💡 조언:", "개선 필요")

### 6. Tone (톤)
- 원본 피드백 그대로 (기본적으로 간결함)

## 💡 사용 권장 사항

### 일반 사용자용
```bash
# compact 형식 사용 (기본값)
response_format=compact
```
- **장점**: 가장 간결, 필요한 정보만
- **단점**: 전체 점수 확인 어려움

### 개발자/상세 분석용
```bash
# filtered 형식 사용
response_format=filtered
```
- **장점**: 개선 사항 + 전체 점수 확인 가능
- **단점**: 응답 크기 중간

### 디버깅/연구용
```bash
# full 형식 사용
response_format=full
```
- **장점**: 모든 상세 데이터 포함
- **단점**: 응답 매우 큼

## 📋 실전 예시

### Python 예시

```python
import requests

url = "http://localhost:8005/api/v1/asr/analyze"

files = {'file': open('test_audio.wav', 'rb')}
data = {
    'reference_text': '안녕하세요. 승무원 음성 분석 테스트입니다.',
    'language_code': 'ko-KR',
    'gender': 'F',
    'response_format': 'compact'  # 간결한 응답
}

response = requests.post(url, files=files, data=data)
result = response.json()

print(f"전체 점수: {result['overall_score']}/100")
print(f"\n개선 필요 항목 ({len(result['improvements'])}개):")

for improvement in result['improvements']:
    print(f"\n[{improvement['category_kr']}] - {improvement['score']}점")
    for feedback in improvement['feedback']:
        print(f"  • {feedback}")
```

### JavaScript 예시

```javascript
const FormData = require('form-data');
const fs = require('fs');
const axios = require('axios');

const form = new FormData();
form.append('file', fs.createReadStream('test_audio.wav'));
form.append('reference_text', '안녕하세요. 승무원 음성 분석 테스트입니다.');
form.append('language_code', 'ko-KR');
form.append('gender', 'F');
form.append('response_format', 'compact'); // 간결한 응답

axios.post('http://localhost:8005/api/v1/asr/analyze', form, {
  headers: form.getHeaders()
})
.then(response => {
  const result = response.data;

  console.log(`전체 점수: ${result.overall_score}/100`);
  console.log(`\n개선 필요 항목 (${result.improvements.length}개):`);

  result.improvements.forEach(improvement => {
    console.log(`\n[${improvement.category_kr}] - ${improvement.score}점`);
    improvement.feedback.forEach(fb => {
      console.log(`  • ${fb}`);
    });
  });
})
.catch(error => {
  console.error('Error:', error.response?.data || error.message);
});
```

## 🎯 실제 출력 예시

### 우수한 발화 (85점)

```json
{
  "overall_score": 85.0,
  "max_score": 100,
  "improvements": [],  // 개선 필요 항목 없음
  "summary": "전체 점수: 85.00/100 | 모든 항목 우수"
}
```

### 개선이 필요한 발화 (70점)

```json
{
  "overall_score": 70.0,
  "max_score": 100,
  "improvements": [
    {
      "category": "accent",
      "category_kr": "강조",
      "score": 62.0,
      "performance_level": "poor",
      "feedback": [
        "전반적으로 목소리 크기 변화가 적어 단조롭게 들릴 수 있습니다.",
        "음높이 변화가 거의 없어 로봇처럼 들릴 수 있습니다."
      ]
    },
    {
      "category": "speed",
      "category_kr": "속도",
      "score": 68.0,
      "performance_level": "poor",
      "feedback": [
        "💡 조언: 발화 속도를 높이세요."
      ]
    },
    {
      "category": "pause",
      "category_kr": "휴지",
      "score": 75.0,
      "performance_level": "fair",
      "feedback": [
        "부적절한 위치 pause: 3개",
        "주요 문제: 2개"
      ]
    }
  ],
  "summary": "전체 점수: 70.00/100 | 3개 항목 개선 필요"
}
```

## 🔧 커스터마이징

임계값을 조정하려면 [app/agents/feedback_filter.py](app/agents/feedback_filter.py) 수정:

```python
class FeedbackFilter:
    # 음성학적 임계값 설정
    EXCELLENT_THRESHOLD = 90  # 우수
    GOOD_THRESHOLD = 80       # 양호
    FAIR_THRESHOLD = 70       # 보통
    POOR_THRESHOLD = 60       # 미흡
```

## 📞 문의

필터링 기준이나 임계값 조정이 필요하면 Issue를 등록해주세요.
