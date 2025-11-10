# 1. 베이스 이미지 설정 (Python 3.12 슬림 버전)
FROM python:3.12-slim

# 2. uv (초고속 Python 패키지 관리자) 설치
# uv를 사용하면 pip보다 훨씬 빠르게 의존성을 설치할 수 있습니다.
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# 3. 작업 디렉토리 설정
WORKDIR /app

# 4. 의존성 파일 복사
# 먼저 의존성 파일만 복사하여 Docker 빌드 캐시를 활용합니다.
# pyproject.toml이나 uv.lock이 변경될 때만 아래 레이어가 재실행됩니다.
COPY pyproject.toml uv.lock ./

# 5. 의존성 설치
# uv sync를 사용하여 uv.lock에 명시된 버전으로 정확하고 빠르게 설치합니다.
# --system 옵션은 가상환경 대신 시스템 Python에 설치하여 컨테이너 환경에 적합합니다.
RUN uv sync --system

# 6. 애플리케이션 소스 코드 복사
COPY ./app ./app

# 7. 서버 실행 포트 노출
EXPOSE 8000

# 8. 애플리케이션 실행
# --host 0.0.0.0 옵션은 컨테이너 외부에서 접근 가능하도록 합니다.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]