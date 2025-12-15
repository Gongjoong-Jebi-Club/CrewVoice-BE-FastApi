# 1. 베이스 이미지 설정 (Python 3.12 슬림 버전)
FROM python:3.12-slim

# 2. 시스템 패키지 설치 (curl)
# python:slim 이미지는 매우 가벼워서 curl이 기본 포함되어 있지 않습니다.
# apt-get을 사용하여 curl을 먼저 설치합니다.
RUN apt-get update && apt-get install -y \
    curl \
    libasound2 \
    libsndfile1 \
    ffmpeg && \
    # apt 캐시를 정리하여 이미지 크기를 줄입니다.
    rm -rf /var/lib/apt/lists/*

# 3. 작업 디렉토리 설정
WORKDIR /app

# 4. 의존성 파일 복사 (이 부분은 변경 없음)
# 먼저 의존성 파일만 복사하여 Docker 빌드 캐시를 활용합니다.
# pyproject.toml이나 uv.lock이 변경될 때만 아래 레이어가 재실행됩니다.
COPY pyproject.toml uv.lock ./

# 5. uv 설치 및 Python 의존성 동기화 (수정된 부분)
# uv 설치와 의존성 설치를 하나의 RUN 레이어에서 실행하여 PATH 문제를 해결합니다.
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    export PATH="/root/.local/bin:${PATH}" && \
    # 1. pyproject.toml을 기반으로 requirements.txt 파일을 생성합니다.
    # 이 방법은 uv.lock을 직접 다루는 것보다 훨씬 안정적입니다.
    uv pip compile pyproject.toml --output-file=requirements.txt && \
    # 2. 생성된 requirements.txt를 사용하여 시스템에 의존성을 설치합니다.
    uv pip sync --system requirements.txt

# 6. 애플리케이션 소스 코드 복사 (이 부분은 변경 없음)
COPY ./app ./app

# 7. 서버 실행 포트 노출 (이 부분은 변경 없음)
EXPOSE 8000

# 8. 애플리케이션 실행
# --host 0.0.0.0 옵션은 컨테이너 외부에서 접근 가능하도록 합니다.
# 환경변수는 docker run -e 옵션 또는 --env-file로 주입됩니다.

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
