# 설치 가이드

## 의존성 설치 방법

### Option 1: uv 사용 (권장 - 빠름)

```bash
# 의존성 설치 및 가상환경 생성
uv sync

# 가상환경 활성화
source .venv/bin/activate
```

### Option 2: pip 사용

```bash
# 가상환경 생성
python3 -m venv .venv

# 가상환경 활성화
source .venv/bin/activate

# 의존성 설치
pip install -r requirements.txt
```

## 환경 변수 설정

`.env` 파일을 프로젝트 루트에 생성하고 다음 내용을 추가하세요:

```bash
SPEECH_KEY=your_azure_speech_key
SPEECH_REGION=your_azure_region
```

## 필수 시스템 패키지 (KoNLPy 사용 시)

KoNLPy를 사용하려면 Java가 필요합니다:

```bash
# Ubuntu/Debian
sudo apt-get install default-jdk

# macOS
brew install openjdk
```

## 설치 확인

```bash
python3 -c "import librosa, azure.cognitiveservices.speech, parselmouth; print('✓ All packages installed successfully!')"
```

## 실행 방법

```bash
# 개발 서버 실행
uvicorn app.main:app --reload

# 또는 uv 사용
uv run uvicorn app.main:app --reload
```
