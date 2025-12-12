#!/bin/bash

# ========================================
# FastAPI EC2 배포 스크립트
# ========================================

set -e  # 에러 발생 시 중단

echo "========================================="
echo "FastAPI 배포 시작"
echo "========================================="

# 색상 정의
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 프로젝트 경로
PROJECT_DIR="/home/ubuntu/FastApi"
VENV_DIR="$PROJECT_DIR/.venv"
BACKUP_DIR="$PROJECT_DIR/.backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_PATH="$BACKUP_DIR/backup_$TIMESTAMP"

# 롤백 함수
rollback() {
    echo -e "${RED}=========================================${NC}"
    echo -e "${RED}배포 실패! 롤백 시작...${NC}"
    echo -e "${RED}=========================================${NC}"

    if [ -d "$BACKUP_PATH" ]; then
        echo "백업에서 코드 복원 중..."
        cp -r $BACKUP_PATH/* $PROJECT_DIR/

        echo "서비스 재시작 중..."
        sudo systemctl restart fastapi

        echo -e "${YELLOW}✓ 이전 버전으로 롤백 완료${NC}"
    else
        echo -e "${YELLOW}백업이 없습니다. 수동 복구가 필요합니다.${NC}"
    fi

    exit 1
}

# 에러 발생 시 롤백 실행
trap rollback ERR

# 1. 프로젝트 디렉토리로 이동
echo -e "${YELLOW}[1/9] 프로젝트 디렉토리로 이동${NC}"
cd $PROJECT_DIR

# 2. 백업 생성
echo -e "${YELLOW}[2/9] 현재 버전 백업${NC}"
mkdir -p $BACKUP_DIR
cp -r $PROJECT_DIR $BACKUP_PATH
echo -e "${GREEN}✓ 백업 생성: $BACKUP_PATH${NC}"

# 오래된 백업 정리 (7일 이상)
find $BACKUP_DIR -type d -name "backup_*" -mtime +7 -exec rm -rf {} + 2>/dev/null || true

# 3. Git Pull
echo -e "${YELLOW}[3/9] 최신 코드 가져오기 (Git Pull)${NC}"
git pull origin dev

# 4. 가상 환경 활성화
echo -e "${YELLOW}[4/9] Python 가상 환경 활성화${NC}"
if [ ! -d "$VENV_DIR" ]; then
    echo "가상 환경이 존재하지 않습니다. 생성 중..."
    python3 -m venv .venv
fi
source .venv/bin/activate

# 5. 의존성 설치
echo -e "${YELLOW}[5/9] 의존성 설치 (pip install)${NC}"
pip install -r requirements.txt --upgrade

# 6. .env.production 파일 확인
echo -e "${YELLOW}[6/9] 환경 변수 파일 확인${NC}"
if [ ! -f ".env.production" ]; then
    echo -e "${RED}오류: .env.production 파일이 없습니다!${NC}"
    echo "배포 전에 .env.production 파일을 생성하세요."
    exit 1
fi
cp .env.production .env
echo -e "${GREEN}✓ .env.production → .env 복사 완료${NC}"

# 7. 로그 디렉토리 생성
echo -e "${YELLOW}[7/9] 로그 디렉토리 생성${NC}"
sudo mkdir -p /var/log/fastapi
sudo chown ubuntu:ubuntu /var/log/fastapi

# 8. Systemd 서비스 재시작
echo -e "${YELLOW}[8/9] FastAPI 서비스 재시작${NC}"
sudo systemctl daemon-reload
sudo systemctl restart fastapi
sudo systemctl enable fastapi

# 9. 상태 확인
echo -e "${YELLOW}[9/9] 서비스 상태 확인${NC}"
sleep 2
if sudo systemctl is-active --quiet fastapi; then
    echo -e "${GREEN}=========================================${NC}"
    echo -e "${GREEN}✓ FastAPI 배포 성공!${NC}"
    echo -e "${GREEN}=========================================${NC}"
    sudo systemctl status fastapi --no-pager
else
    echo -e "${RED}=========================================${NC}"
    echo -e "${RED}✗ FastAPI 서비스 시작 실패${NC}"
    echo -e "${RED}=========================================${NC}"
    echo "로그 확인:"
    sudo journalctl -u fastapi -n 50 --no-pager
    exit 1
fi

# 서비스 로그 확인 (마지막 20줄)
echo ""
echo "최근 로그 (마지막 20줄):"
sudo journalctl -u fastapi -n 20 --no-pager

echo ""
echo -e "${GREEN}배포가 완료되었습니다!${NC}"
echo "FastAPI URL: https://ai.crewvoice.cloud"
echo "API 문서: https://ai.crewvoice.cloud/docs"
