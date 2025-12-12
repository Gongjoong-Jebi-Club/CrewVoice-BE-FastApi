# 음성 파일 라이프사이클 - EC2 환경

## 📌 전체 플로우 다이어그램

```
┌─────────────────┐                    ┌──────────────┐                    ┌─────────────┐
│   Spring Boot   │                    │   FastAPI    │                    │  AWS S3     │
│ server.crew...  │                    │ ai.crew...   │                    │  버킷       │
└────────┬────────┘                    └──────┬───────┘                    └──────┬──────┘
         │                                     │                                   │
         │  1. POST /api/evaluate              │                                   │
         │     {taskId, audioUrl, script...}   │                                   │
         │────────────────────────────────────>│                                   │
         │                                     │                                   │
         │  2. HTTP 200 OK (즉시 응답)          │                                   │
         │<────────────────────────────────────│                                   │
         │     {message, task_id}              │                                   │
         │                                     │                                   │
         │                                     │  3. GET pre-signed URL           │
         │                                     │  (WAV 파일 다운로드)              │
         │                                     │─────────────────────────────────>│
         │                                     │                                   │
         │                                     │<─────────────────────────────────│
         │                                     │  WAV 파일 바이너리 (11.2 MB)      │
         │                                     │                                   │
         │                                     │  4. 임시 저장                     │
         │                                     │  /tmp/tmp1mb0_m64.wav            │
         │                                     │                                   │
         │                                     │  5. 7개 에이전트 분석             │
         │                                     │  (2-3분 소요)                     │
         │                                     │                                   │
         │                                     │  6. 임시 파일 삭제               │
         │                                     │  os.remove(tmp_path)             │
         │                                     │                                   │
         │  7. POST /api/v1/evaluations/callback                                 │
         │     {scores, feedback_summary}      │                                   │
         │<────────────────────────────────────│                                   │
         │                                     │                                   │
         │  8. HTTP 200 OK                     │                                   │
         │────────────────────────────────────>│                                   │
         │                                     │                                   │
```

---

## 🔄 상세 라이프사이클

### Phase 1: 요청 수신 (0초)

**Location**: `app/apis/router_springboot.py:43-103`

```python
@router.post("/evaluate")
async def start_evaluation(
    request: EvaluationRequest,
    background_tasks: BackgroundTasks
):
    # 1. 즉시 200 OK 응답 반환
    background_tasks.add_task(process_evaluation_async, request)
    return {"message": "Request received", "task_id": request.task_id}
```

**파일 상태**:
```
S3: ✅ 존재 (Pre-signed URL 유효)
EC2: ❌ 아직 없음
```

---

### Phase 2: S3 다운로드 (1-5초)

**Location**: `app/apis/router_springboot.py:240-300`

```python
async def download_from_s3(url: str, task_id: str, timeout: int = 30) -> str:
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url)

        # 임시 파일 생성 (Python tempfile 모듈)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp.write(response.content)
            tmp_path = tmp.name  # 예: /tmp/tmp1mb0_m64.wav

        return tmp_path
```

**저장 위치 (EC2 Linux)**:
```bash
/tmp/tmp1mb0_m64.wav  # NamedTemporaryFile이 자동 생성
```

**파일 정보**:
- **위치**: `/tmp/` (시스템 임시 디렉토리)
- **권한**: `-rw------- ubuntu ubuntu` (소유자만 읽기/쓰기)
- **크기**: 11.2 MB (예시)
- **포맷**: WAV (2채널 스테레오, 16bit, 44.1kHz)

**파일 상태**:
```
S3: ✅ 존재 (원본 유지)
EC2: ✅ /tmp/tmp1mb0_m64.wav (11.2 MB)
```

**로그**:
```
[54507242-4e79-4434-a3f0-69d46b9fc72e] 다운로드 완료: 11489.00KB
[54507242-4e79-4434-a3f0-69d46b9fc72e] WAV 검증 완료: {'channels': 2, 'sample_rate': 44100, ...}
```

---

### Phase 3: WAV 검증 및 디버그 저장 (선택)

**Location**: `app/apis/router_springboot.py:280-287`

```python
# WAV 파일 헤더 검증
wav_info = validate_wav_file(tmp_path, task_id)

# 디버그 모드일 경우 영구 저장
if DEBUG_SAVE_AUDIO:  # .env에서 설정
    save_debug_audio(tmp_path, task_id)
```

**디버그 저장 위치** (DEBUG_SAVE_AUDIO=true):
```bash
/home/ubuntu/FastApi/debug_audio/54507242_20251212_135110.wav
```

**파일 상태**:
```
S3: ✅ 존재
EC2 /tmp/: ✅ tmp1mb0_m64.wav (분석용)
EC2 debug_audio/: ✅ 54507242_20251212_135110.wav (디버그용, 선택)
```

**⚠️ 프로덕션 환경**:
- `DEBUG_SAVE_AUDIO=false` 권장
- 디버그 파일 저장하지 않음 (디스크 공간 절약)

---

### Phase 4: 음성 분석 (120-180초)

**Location**: `app/apis/router_springboot.py:136-144`

```python
result = await asyncio.wait_for(
    asyncio.to_thread(
        analyzer_manager.analyze_parallel,
        wav_path=tmp_path,  # /tmp/tmp1mb0_m64.wav
        reference_text=request.script,
        language_code=request.language
    ),
    timeout=300  # 5분 타임아웃
)
```

**분석 중 파일 접근**:
```
Validate 에이전트:   Azure STT API 접근 (30-60초)
Accent 에이전트:     librosa 로드 + Azure STT (30-60초)
Pronunciation:       Azure 데이터 재사용 (1초)
Pause:               Azure 데이터 재사용 (1초)
Intonation:          librosa 로드 + 분석 (60-90초)
Speed:               librosa 로드 + 분석 (1초)
Tone:                librosa 로드 + 분석 (20초)
```

**파일 핸들 관리**:
- Azure SDK: 파일 읽기 후 자동으로 핸들 해제
- librosa: 메모리에 로드 후 파일 핸들 해제
- 여러 에이전트가 동시에 접근해도 문제 없음 (읽기 전용)

**파일 상태**:
```
S3: ✅ 존재
EC2 /tmp/: ✅ tmp1mb0_m64.wav (분석 중... 7개 에이전트가 읽기)
```

**로그**:
```
[VALIDATE] 분석 시작...
[VALIDATE] Azure STT 시작 - 파일: /tmp/tmp1mb0_m64.wav
[VALIDATE] 검증 통과 - 나머지 에이전트 분석을 진행합니다.
[ACCENT] 분석 시작...
[PRONUNCIATION] 분석 시작...
... (병렬 실행)
분석 완료 - 총점: 497.97/600 (82.99%)
소요 시간: 166.25초
```

---

### Phase 5: 파일 삭제 (분석 완료 직후)

**Location**: `app/apis/router_springboot.py:229-237`

```python
finally:
    # 임시 파일 삭제 (자동 리소스 정리)
    if tmp_path and os.path.exists(tmp_path) and tmp_path != request.audio_url:
        try:
            os.remove(tmp_path)
            logger.info(f"[{request.task_id}] 임시 파일 삭제 완료")
        except Exception as e:
            logger.warning(f"[{request.task_id}] 임시 파일 삭제 실패: {e}")
```

**파일 상태**:
```
S3: ✅ 존재 (원본 유지)
EC2 /tmp/: ❌ 삭제됨 (os.remove)
EC2 debug_audio/: ✅ 유지 (DEBUG_SAVE_AUDIO=true인 경우만)
```

**로그**:
```
[54507242-4e79-4434-a3f0-69d46b9fc72e] 임시 파일 삭제 완료
```

**삭제 실패 케이스**:
- 파일이 다른 프로세스에 의해 잠김 (WinError 32)
  - **해결**: validate.py에서 Azure SDK 객체 명시적 삭제 (`del speech_recognizer`)
  - 코드: `app/agents/analyzers/validate.py:166-168`

---

### Phase 6: 콜백 전송 (1-2초)

**Location**: `app/apis/router_springboot.py:397-440`

```python
async def send_callback(callback_url: str, payload: dict, task_id: str):
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": os.getenv("CALLBACK_API_KEY")
    }

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(callback_url, json=payload, headers=headers)
        logger.info(f"[{task_id}] 콜백 전송 완료: HTTP {response.status_code}")
```

**파일 상태**:
```
S3: ✅ 존재 (원본 유지 - Spring Boot가 관리)
EC2: ❌ 모두 삭제됨
```

---

## 📊 타임라인 요약

| 시간 | 단계 | 파일 상태 | 위치 |
|------|------|----------|------|
| **0초** | 요청 수신 | S3에만 존재 | S3 |
| **1-5초** | S3 다운로드 | 임시 파일 생성 | `/tmp/tmp*.wav` |
| **5-10초** | WAV 검증 | 임시 파일 유지 | `/tmp/tmp*.wav` |
| **10-180초** | 음성 분석 | 7개 에이전트가 읽기 | `/tmp/tmp*.wav` |
| **180초** | 분석 완료 | 임시 파일 삭제 | ❌ 삭제됨 |
| **181초** | 콜백 전송 | 파일 없음 | - |

---

## 💾 디스크 사용량 분석

### 프로덕션 환경 (DEBUG_SAVE_AUDIO=false)

**피크 디스크 사용량**:
```
1개 요청당: 11.2 MB (분석 중에만)
10개 동시 요청: 112 MB
분석 완료 후: 0 MB (자동 삭제)
```

**장기 축적**: ❌ 없음 (임시 파일 자동 삭제)

### 개발 환경 (DEBUG_SAVE_AUDIO=true)

**피크 디스크 사용량**:
```
1개 요청당: 11.2 MB (임시) + 11.2 MB (디버그) = 22.4 MB
10개 요청 누적: 112 MB (디버그 폴더에 영구 저장)
```

**장기 축적**: ✅ `debug_audio/` 폴더에 계속 쌓임

**정리 권장**:
```bash
# 7일 이상 된 디버그 파일 삭제
find /home/ubuntu/FastApi/debug_audio -name "*.wav" -mtime +7 -delete
```

---

## 🔒 보안 및 권한

### 임시 파일 권한
```bash
-rw------- ubuntu ubuntu  # 소유자만 읽기/쓰기 가능
```

### 파일 경로 검증
```python
# 로컬 파일 경로인 경우 다운로드 스킵 (개발용)
if os.path.exists(url):
    logger.info(f"로컬 파일 사용: {url}")
    return url

# 프로덕션: S3 Pre-signed URL만 허용
```

### 파일 크기 제한
```python
# 최대 50MB
if file_size > 50 * 1024 * 1024:
    os.remove(tmp_path)
    raise HTTPException(status_code=400, detail="파일 크기 초과")
```

---

## 🧪 실제 동작 예시 (로그 기반)

### 성공 케이스

```log
2025-12-12 13:51:10 | INFO | [54507242-4e79-4434-a3f0-69d46b9fc72e] 평가 요청 접수
2025-12-12 13:51:10 | INFO | [54507242-4e79-4434-a3f0-69d46b9fc72e] audio_url: https://s3.ap-northeast-2.amazonaws.com/bucket/...
2025-12-12 13:51:10 | INFO | [54507242-4e79-4434-a3f0-69d46b9fc72e] 백그라운드 처리 시작
2025-12-12 13:51:10 | INFO | [54507242-4e79-4434-a3f0-69d46b9fc72e] S3 다운로드 시작
2025-12-12 13:51:11 | INFO | [54507242-4e79-4434-a3f0-69d46b9fc72e] 다운로드 완료: 11489.00KB
2025-12-12 13:51:11 | INFO | [54507242-4e79-4434-a3f0-69d46b9fc72e] WAV 검증 완료: {'channels': 2, ...}
2025-12-12 13:51:11 | INFO | [54507242-4e79-4434-a3f0-69d46b9fc72e] 다운로드 완료: /tmp/tmp1mb0_m64.wav

2025-12-12 13:51:11 | INFO | [54507242-4e79-4434-a3f0-69d46b9fc72e] 음성 분석 시작...
2025-12-12 13:51:11 | INFO | ================================================================================
2025-12-12 13:51:11 | INFO | 음성 분석 시작: /tmp/tmp1mb0_m64.wav
2025-12-12 13:51:11 | INFO | ================================================================================
2025-12-12 13:51:11 | INFO | [VALIDATE] 분석 시작...
... (2-3분 분석)
2025-12-12 13:53:56 | INFO | 분석 완료 - 총점: 497.97/600 (82.99%)
2025-12-12 13:53:56 | INFO | 소요 시간: 166.25초

2025-12-12 13:53:56 | INFO | [54507242-4e79-4434-a3f0-69d46b9fc72e] 음성 분석 완료
2025-12-12 13:53:56 | INFO | [54507242-4e79-4434-a3f0-69d46b9fc72e] AI 피드백 생성 시작...
2025-12-12 13:53:57 | INFO | [54507242-4e79-4434-a3f0-69d46b9fc72e] AI 피드백 생성 완료
2025-12-12 13:53:57 | INFO | [54507242-4e79-4434-a3f0-69d46b9fc72e] 평가 완료 - overall_score: 82.99

2025-12-12 13:53:57 | INFO | [54507242-4e79-4434-a3f0-69d46b9fc72e] 콜백 전송 시작
2025-12-12 13:53:57 | INFO | [54507242-4e79-4434-a3f0-69d46b9fc72e] 콜백 전송 완료: HTTP 200

2025-12-12 13:53:57 | INFO | [54507242-4e79-4434-a3f0-69d46b9fc72e] 임시 파일 삭제 완료
```

### 실패 케이스 (파일 삭제 실패 → 수정됨)

**이전 (버그)**:
```log
WARNING: [ef5e42e7] 임시 파일 삭제 실패: [WinError 32] 다른 프로세스가 파일을 사용 중
```

**현재 (수정됨)**:
```python
# validate.py:166-168
del speech_recognizer  # 파일 핸들 명시적 해제
del audio_config

# router_springboot.py:234
os.remove(tmp_path)  # ✅ 성공
```

---

## 🔧 운영 및 모니터링

### 임시 파일 정리 (자동)

**정상 케이스**: `finally` 블록에서 자동 삭제
```python
finally:
    os.remove(tmp_path)  # 항상 실행됨
```

**비정상 케이스** (서버 크래시):
- Linux `/tmp/` 폴더는 시스템 재부팅 시 자동 정리
- Ubuntu cron: `/tmp/` 파일 10일 이상 미사용 시 자동 삭제

### 디버그 파일 정리 (수동)

**크론잡 설정** (선택):
```bash
# /etc/cron.daily/cleanup-debug-audio
#!/bin/bash
find /home/ubuntu/FastApi/debug_audio -name "*.wav" -mtime +7 -delete
```

### 디스크 사용량 모니터링

```bash
# 전체 디스크 사용량
df -h

# /tmp 폴더 사용량
du -sh /tmp

# debug_audio 폴더 사용량
du -sh /home/ubuntu/FastApi/debug_audio
```

---

## ⚠️ 주의사항

### 1. S3 Pre-signed URL 유효 시간
- **유효 시간**: 15분 (Spring Boot 설정)
- **다운로드 타임아웃**: 30초
- **전체 프로세스**: 3-5분 (충분함)

### 2. 동시 요청 처리
```
요청 1: /tmp/tmp1mb0_m64.wav  (11.2 MB)
요청 2: /tmp/tmp2abc_xyz.wav  (10.5 MB)
요청 3: /tmp/tmp3def_uvw.wav  (12.1 MB)
총 사용량: 33.8 MB (동시 처리 가능)
```

### 3. 파일명 충돌 방지
- `tempfile.NamedTemporaryFile`: 고유한 랜덤 파일명 자동 생성
- 충돌 가능성: 0% (시스템이 보장)

### 4. 원본 파일 보존
- **S3 원본**: FastAPI는 절대 삭제하지 않음
- **관리 주체**: Spring Boot (또는 별도 정책)

---

## 📋 체크리스트

### 개발 환경
- [ ] `DEBUG_SAVE_AUDIO=true` (디버그 파일 저장)
- [ ] `debug_audio/` 폴더 주기적 정리
- [ ] 로컬 파일 경로 테스트 지원

### 프로덕션 환경
- [ ] `DEBUG_SAVE_AUDIO=false` (디스크 절약)
- [ ] `/tmp` 자동 정리 확인
- [ ] S3 Pre-signed URL 15분 유효 확인
- [ ] 동시 요청 수 모니터링 (디스크 사용량)

---

## 🔗 관련 코드

- **다운로드**: `app/apis/router_springboot.py:240-300`
- **분석**: `app/apis/router_springboot.py:136-144`
- **삭제**: `app/apis/router_springboot.py:229-237`
- **파일 핸들 해제**: `app/agents/analyzers/validate.py:166-168`
