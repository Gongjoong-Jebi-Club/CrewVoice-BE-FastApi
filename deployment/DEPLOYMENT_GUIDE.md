# FastAPI EC2 배포 가이드

## 📋 목차

1. [사전 요구사항](#사전-요구사항)
2. [EC2 초기 설정](#ec2-초기-설정)
3. [FastAPI 배포](#fastapi-배포)
4. [Nginx 설정](#nginx-설정)
5. [SSL 인증서 설정](#ssl-인증서-설정)
6. [서비스 관리](#서비스-관리)
7. [트러블슈팅](#트러블슈팅)

---

## 🔧 사전 요구사항

### 1. EC2 인스턴스 스펙
- **OS**: Ubuntu 22.04 LTS (권장)
- **인스턴스 타입**: t3.medium 이상 (음성 분석 CPU 사용량 높음)
- **스토리지**: 30GB 이상
- **보안 그룹**:
  - 22 (SSH)
  - 80 (HTTP)
  - 443 (HTTPS)
  - 8080 (Spring Boot, 내부용)
  - 8000 (FastAPI, 내부용 - 선택)

### 2. 도메인 설정
- **Spring Boot**: `server.crewvoice.cloud` → EC2 IP
- **FastAPI**: `ai.crewvoice.cloud` → EC2 IP (동일 IP)

Route 53 또는 도메인 제공자에서 A 레코드 설정:
```
server.crewvoice.cloud  →  EC2_PUBLIC_IP
ai.crewvoice.cloud     →  EC2_PUBLIC_IP
```

---

## 🚀 EC2 초기 설정

### 1. SSH 접속
```bash
ssh -i your-key.pem ubuntu@EC2_PUBLIC_IP
```

### 2. 시스템 업데이트
```bash
sudo apt update && sudo apt upgrade -y
```

### 3. 필수 패키지 설치
```bash
# Python 3.11
sudo apt install -y python3.11 python3.11-venv python3-pip

# Nginx
sudo apt install -y nginx

# Git
sudo apt install -y git

# 기타 유틸리티
sudo apt install -y curl wget vim htop
```

### 4. Python 버전 확인
```bash
python3 --version  # Python 3.11.x 확인
```

---

## 📦 FastAPI 배포

### 1. 프로젝트 클론
```bash
cd /home/ubuntu
git clone https://github.com/YOUR_ORG/FastApi.git
cd FastApi
```

### 2. 브랜치 체크아웃
```bash
# dev 브랜치 사용 (또는 main)
git checkout dev
```

### 3. 가상 환경 생성
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 4. 의존성 설치
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 5. 환경 변수 설정
```bash
# .env.production을 .env로 복사
cp .env.production .env

# 필요시 환경 변수 편집
vim .env
```

**중요**: .env 파일에 다음 값들이 설정되어 있는지 확인:
- `AZURE_SPEECH_KEY`: Azure Speech API 키
- `OPENAI_API_KEY`: OpenAI API 키
- `CALLBACK_API_KEY`: Spring Boot와 동일한 값
- `DEBUG_SAVE_AUDIO=false`: 프로덕션에서는 false (이미 설정됨)

### 6. 로컬 테스트 (선택)
```bash
# 테스트 실행
uvicorn app.main:app --host 127.0.0.1 --port 8000

# 다른 터미널에서 확인
curl http://localhost:8000/docs
```

**Ctrl+C로 중단**

---

## ⚙️ Systemd 서비스 설정

### 1. 서비스 파일 복사
```bash
sudo cp deployment/fastapi.service /etc/systemd/system/fastapi.service
```

### 2. 서비스 파일 편집 (필요시)
```bash
sudo vim /etc/systemd/system/fastapi.service
```

**확인 사항**:
- `User=ubuntu`
- `Group=ubuntu`
- `WorkingDirectory=/home/ubuntu/FastApi`
- `EnvironmentFile=/home/ubuntu/FastApi/.env`

### 3. 로그 디렉토리 생성
```bash
sudo mkdir -p /var/log/fastapi
sudo chown ubuntu:ubuntu /var/log/fastapi
```

### 4. 서비스 등록 및 시작
```bash
# Systemd 리로드
sudo systemctl daemon-reload

# 서비스 시작
sudo systemctl start fastapi

# 자동 시작 활성화
sudo systemctl enable fastapi

# 상태 확인
sudo systemctl status fastapi
```

---

## 🌐 Nginx 설정

### 1. Nginx 설정 파일 복사
```bash
sudo cp deployment/nginx-fastapi.conf /etc/nginx/sites-available/ai.crewvoice.cloud
```

### 2. 심볼릭 링크 생성
```bash
sudo ln -s /etc/nginx/sites-available/ai.crewvoice.cloud /etc/nginx/sites-enabled/
```

### 3. Nginx 설정 테스트
```bash
sudo nginx -t
```

### 4. Nginx 재시작
```bash
sudo systemctl restart nginx
sudo systemctl status nginx
```

---

## 🔒 SSL 인증서 설정 (Let's Encrypt)

### 1. Certbot 설치
```bash
sudo apt install -y certbot python3-certbot-nginx
```

### 2. SSL 인증서 발급
```bash
sudo certbot --nginx -d ai.crewvoice.cloud
```

**프롬프트에 따라 진행**:
- 이메일 입력
- 약관 동의
- HTTP → HTTPS 리다이렉트: Yes (2 선택)

### 3. 자동 갱신 확인
```bash
# 갱신 테스트 (실제로 갱신하지는 않음)
sudo certbot renew --dry-run
```

Certbot은 자동으로 cron job을 설정하여 인증서를 갱신합니다.

---

## 🛠️ 서비스 관리

### 서비스 상태 확인
```bash
sudo systemctl status fastapi
```

### 서비스 재시작
```bash
sudo systemctl restart fastapi
```

### 로그 확인
```bash
# 실시간 로그
sudo journalctl -u fastapi -f

# 마지막 100줄
sudo journalctl -u fastapi -n 100

# 오늘 로그만
sudo journalctl -u fastapi --since today
```

### 애플리케이션 로그
```bash
# Access 로그
tail -f /var/log/fastapi/access.log

# Error 로그
tail -f /var/log/fastapi/error.log
```

### 배포 업데이트
```bash
cd /home/ubuntu/FastApi
chmod +x deployment/deploy.sh
./deployment/deploy.sh
```

---

## 🔍 트러블슈팅

### 1. 서비스가 시작되지 않는 경우

**로그 확인**:
```bash
sudo journalctl -u fastapi -n 50
```

**가능한 원인**:
- `.env` 파일 누락
- Python 의존성 미설치
- 포트 8000 이미 사용 중

**해결**:
```bash
# 포트 사용 확인
sudo lsof -i :8000

# 프로세스 종료
sudo kill -9 <PID>

# 서비스 재시작
sudo systemctl restart fastapi
```

### 2. 502 Bad Gateway (Nginx)

**원인**: FastAPI 서비스가 실행되지 않음

**해결**:
```bash
# FastAPI 상태 확인
sudo systemctl status fastapi

# 재시작
sudo systemctl restart fastapi
```

### 3. Spring Boot 콜백 실패 (403 Forbidden)

**원인**: `CALLBACK_API_KEY` 불일치

**해결**:
1. FastAPI `.env` 확인
2. Spring Boot `application.yml` 확인
3. 두 값이 동일한지 확인
4. 서비스 재시작

### 4. Azure STT 타임아웃

**원인**: 네트워크 지연 또는 Azure API 키 문제

**해결**:
```bash
# 환경 변수 확인
cat /home/ubuntu/FastApi/.env | grep AZURE

# 로그 확인
sudo journalctl -u fastapi -n 100 | grep AZURE
```

### 5. 디스크 공간 부족

**로그 파일이 너무 큰 경우**:
```bash
# 로그 파일 크기 확인
du -sh /var/log/fastapi/*

# 오래된 로그 삭제
sudo find /var/log/fastapi -name "*.log" -mtime +7 -delete
```

---

## ✅ 배포 체크리스트

### 배포 전
- [ ] EC2 인스턴스 준비 (t3.medium 이상)
- [ ] 도메인 DNS 설정 완료 (ai.crewvoice.cloud)
- [ ] Spring Boot 배포 완료
- [ ] 보안 그룹 설정 (80, 443 포트)
- [ ] `.env` 파일 준비 (.env.production 복사)

### 배포 중
- [ ] Git 클론
- [ ] 가상 환경 생성
- [ ] 의존성 설치
- [ ] 환경 변수 설정
- [ ] Systemd 서비스 등록
- [ ] Nginx 설정
- [ ] SSL 인증서 발급

### 배포 후
- [ ] FastAPI 서비스 정상 작동 확인
- [ ] API 문서 접근 가능 (`https://ai.crewvoice.cloud/docs`)
- [ ] Spring Boot → FastAPI 통신 테스트
- [ ] FastAPI → Spring Boot 콜백 테스트
- [ ] 음성 분석 전체 프로세스 테스트
- [ ] 로그 모니터링 설정

---

## 📞 지원 및 문의

문제가 발생하면:
1. 로그 확인: `sudo journalctl -u fastapi -n 100`
2. 서비스 상태: `sudo systemctl status fastapi`
3. Nginx 로그: `sudo tail -f /var/log/nginx/fastapi-error.log`

---

## 🔗 유용한 명령어 모음

```bash
# FastAPI 서비스 상태
sudo systemctl status fastapi

# FastAPI 재시작
sudo systemctl restart fastapi

# Nginx 재시작
sudo systemctl restart nginx

# 실시간 로그
sudo journalctl -u fastapi -f

# CPU/메모리 사용량
htop

# 디스크 사용량
df -h

# 포트 사용 확인
sudo netstat -tulpn | grep LISTEN
```
