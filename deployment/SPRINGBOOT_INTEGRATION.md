# Spring Boot ↔ FastAPI 통신 설정 가이드

## 📌 통신 흐름

```
[Spring Boot]                      [FastAPI]
server.crewvoice.cloud         ai.crewvoice.cloud
:8080                              :8000 (Nginx → 443)
    │                                  │
    │  1. POST /api/evaluate           │
    │──────────────────────────────────>│
    │     (taskId, audioUrl, script...) │
    │                                   │
    │  2. HTTP 200 OK (즉시 응답)       │
    │<──────────────────────────────────│
    │     {message, task_id}            │
    │                                   │
    │                                   │  3. 백그라운드 분석
    │                                   │     - S3에서 WAV 다운로드
    │                                   │     - 7개 에이전트 실행
    │                                   │     - AI 피드백 생성
    │                                   │
    │  4. POST /api/v1/evaluations/callback
    │<──────────────────────────────────│
    │     {scores, feedback_summary}    │
```

---

## 🔧 Spring Boot 설정 필요 사항

### 1. application.yml 설정

```yaml
# FastAPI 연동 설정
fastapi:
  # 옵션 1: 같은 EC2 내부 통신 (권장 - 빠름, 안전)
  base-url: http://localhost:8000

  # 옵션 2: 외부 도메인 통신 (필요시)
  # base-url: https://ai.crewvoice.cloud

  # 평가 요청 엔드포인트
  evaluate-url: ${fastapi.base-url}/api/evaluate

  # 콜백 인증 키 (FastAPI .env의 CALLBACK_API_KEY와 동일해야 함)
  callback-api-key: sk_callback_7f8e9d2a4b6c1e3f5a9b8c7d6e4f2a1b

# 콜백 수신 설정
server:
  # Spring Boot 포트
  port: 8080
```

### 2. RestTemplate/WebClient 설정

**RestTemplate 방식 (간단)**:
```java
@Configuration
public class RestTemplateConfig {

    @Bean
    public RestTemplate restTemplate() {
        RestTemplate restTemplate = new RestTemplate();

        // 타임아웃 설정 (연결: 5초, 읽기: 300초)
        // 음성 분석은 오래 걸릴 수 있지만, 즉시 응답이므로 짧게 설정
        HttpComponentsClientHttpRequestFactory factory =
            new HttpComponentsClientHttpRequestFactory();
        factory.setConnectTimeout(5000);
        factory.setReadTimeout(10000);  // 즉시 응답이므로 10초면 충분

        restTemplate.setRequestFactory(factory);
        return restTemplate;
    }
}
```

**WebClient 방식 (권장 - 비동기)**:
```java
@Configuration
public class WebClientConfig {

    @Bean
    public WebClient fastApiWebClient(@Value("${fastapi.base-url}") String baseUrl) {
        return WebClient.builder()
            .baseUrl(baseUrl)
            .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
            .defaultHeader("X-API-Key", "${fastapi.callback-api-key}")
            .build();
    }
}
```

### 3. 평가 요청 서비스 (Service Layer)

```java
@Service
@RequiredArgsConstructor
public class EvaluationService {

    private final WebClient fastApiWebClient;

    @Value("${fastapi.evaluate-url}")
    private String evaluateUrl;

    public Mono<EvaluationAcceptedResponse> requestEvaluation(
        String taskId,
        String audioUrl,
        String script,
        String language,
        String callbackUrl
    ) {
        // 요청 DTO 생성 (camelCase 필드명)
        EvaluationRequest request = EvaluationRequest.builder()
            .taskId(taskId)
            .audioUrl(audioUrl)
            .script(script)
            .language(language)
            .callbackUrl(callbackUrl)
            .build();

        return fastApiWebClient
            .post()
            .uri("/api/evaluate")
            .bodyValue(request)
            .retrieve()
            .onStatus(
                HttpStatus::is4xxClientError,
                response -> response.bodyToMono(String.class)
                    .flatMap(body -> Mono.error(
                        new RuntimeException("FastAPI 4xx 에러: " + body)))
            )
            .onStatus(
                HttpStatus::is5xxServerError,
                response -> response.bodyToMono(String.class)
                    .flatMap(body -> Mono.error(
                        new RuntimeException("FastAPI 5xx 에러: " + body)))
            )
            .bodyToMono(EvaluationAcceptedResponse.class)
            .doOnSuccess(res -> log.info("FastAPI 요청 성공: {}", res))
            .doOnError(err -> log.error("FastAPI 요청 실패", err));
    }
}
```

### 4. 콜백 수신 컨트롤러 (Controller Layer)

```java
@RestController
@RequestMapping("/api/v1/evaluations")
@RequiredArgsConstructor
@Slf4j
public class EvaluationCallbackController {

    private final EvaluationResultService evaluationResultService;

    @Value("${fastapi.callback-api-key}")
    private String expectedApiKey;

    /**
     * FastAPI로부터 분석 결과 콜백 수신
     */
    @PostMapping("/callback")
    public ResponseEntity<Void> receiveCallback(
        @RequestHeader(value = "X-API-Key", required = false) String apiKey,
        @RequestBody CallbackPayload payload
    ) {
        // 1. API Key 검증
        if (!expectedApiKey.equals(apiKey)) {
            log.warn("잘못된 API Key로 콜백 시도: {}", apiKey);
            return ResponseEntity.status(HttpStatus.FORBIDDEN).build();
        }

        // 2. 상태에 따라 처리
        if ("completed".equals(payload.getStatus())) {
            // 성공 케이스
            log.info("[{}] 평가 완료 콜백 수신", payload.getTaskId());
            evaluationResultService.saveSuccessResult(payload);

        } else if ("failed".equals(payload.getStatus())) {
            // 실패 케이스
            log.error("[{}] 평가 실패 콜백 수신: {}",
                payload.getTaskId(), payload.getErrorMessage());
            evaluationResultService.saveFailureResult(payload);

        } else {
            log.warn("[{}] 알 수 없는 상태: {}",
                payload.getTaskId(), payload.getStatus());
            return ResponseEntity.badRequest().build();
        }

        return ResponseEntity.ok().build();
    }
}
```

### 5. DTO 클래스 (camelCase 필드명)

**EvaluationRequest.java**:
```java
@Data
@Builder
public class EvaluationRequest {
    private String taskId;      // camelCase
    private String audioUrl;    // camelCase
    private String script;
    private String language;
    private String callbackUrl; // camelCase
}
```

**CallbackPayload.java**:
```java
@Data
public class CallbackPayload {
    private String taskId;
    private String status;  // "completed" or "failed"

    // 성공 시 (status == "completed")
    private ScoresPayload scores;
    private String feedbackSummary;

    // 실패 시 (status == "failed")
    private String errorMessage;
}

@Data
public class ScoresPayload {
    private Double scorePronunciation;
    private Double scorePause;
    private Double scoreIntonation;
    private Double scoreTone;
    private Double scoreSpeed;
    private Double scoreAccent;
    private Double overallScore;
}
```

---

## 🔐 보안 설정

### 1. API Key 인증

**FastAPI → Spring Boot 콜백 시**:
```
POST /api/v1/evaluations/callback
Headers:
  X-API-Key: sk_callback_7f8e9d2a4b6c1e3f5a9b8c7d6e4f2a1b
```

**Spring Boot 검증 코드**:
```java
if (!expectedApiKey.equals(apiKey)) {
    return ResponseEntity.status(HttpStatus.FORBIDDEN).build();
}
```

### 2. 콜백 URL 보안

**HTTPS 사용 권장**:
```yaml
# application.yml
server:
  ssl:
    enabled: true
    key-store: classpath:keystore.p12
    key-store-password: ${SSL_KEYSTORE_PASSWORD}
    key-store-type: PKCS12
```

**콜백 URL**:
```
https://server.crewvoice.cloud/api/v1/evaluations/callback
```

---

## 🧪 통신 테스트

### 1. 로컬 테스트 (개발 환경)

**Spring Boot**: `http://localhost:8080`
**FastAPI**: `http://localhost:8000`

```java
// Spring Boot에서 FastAPI 호출
EvaluationRequest request = EvaluationRequest.builder()
    .taskId(UUID.randomUUID().toString())
    .audioUrl("http://localhost:8000/test.wav")  // 로컬 파일
    .script("안녕하세요 승객 여러분")
    .language("ko-KR")
    .callbackUrl("http://localhost:8080/api/v1/evaluations/callback")
    .build();
```

### 2. EC2 테스트 (프로덕션 환경)

**옵션 1: 내부 통신 (권장)**
```java
// Spring Boot → FastAPI
POST http://localhost:8000/api/evaluate

// FastAPI → Spring Boot
POST http://localhost:8080/api/v1/evaluations/callback
```

**옵션 2: 외부 도메인 통신**
```java
// Spring Boot → FastAPI
POST https://ai.crewvoice.cloud/api/evaluate

// FastAPI → Spring Boot
POST https://server.crewvoice.cloud/api/v1/evaluations/callback
```

### 3. Swagger UI 테스트

**FastAPI API 문서**:
```
https://ai.crewvoice.cloud/docs
```

**Spring Boot API 문서** (Swagger 설정 시):
```
https://server.crewvoice.cloud/swagger-ui/index.html
```

---

## 🐛 트러블슈팅

### 1. Connection Refused

**증상**:
```
java.net.ConnectException: Connection refused
```

**원인**:
- FastAPI 서비스가 실행되지 않음
- 포트가 잘못됨 (8000 대신 다른 포트)
- 방화벽 차단

**해결**:
```bash
# EC2에서 FastAPI 상태 확인
sudo systemctl status fastapi

# 포트 확인
sudo lsof -i :8000

# 방화벽 확인 (UFW 사용 시)
sudo ufw status
```

### 2. 403 Forbidden (콜백)

**증상**:
```
HTTP 403: Forbidden
```

**원인**:
- `X-API-Key` 헤더 누락
- API Key 불일치

**해결**:
1. FastAPI `.env` 확인
2. Spring Boot `application.yml` 확인
3. 두 값이 동일한지 확인

### 3. Read Timeout

**증상**:
```
java.net.SocketTimeoutException: Read timed out
```

**원인**:
- FastAPI가 응답하지 않음 (분석 중 크래시)
- 타임아웃 설정이 너무 짧음 (즉시 응답이므로 문제 없어야 함)

**해결**:
```java
// 타임아웃 늘리기 (하지만 즉시 응답이므로 10초면 충분)
factory.setReadTimeout(10000);  // 10초
```

### 4. 콜백 미수신

**증상**:
- FastAPI는 성공했다고 로그에 표시
- Spring Boot는 콜백을 받지 못함

**원인**:
- 콜백 URL이 잘못됨 (localhost vs 외부 도메인)
- 방화벽 차단
- Spring Boot 서버가 다운됨

**해결**:
```bash
# FastAPI 로그 확인
sudo journalctl -u fastapi -n 100 | grep "콜백"

# Spring Boot 로그 확인
tail -f /var/log/spring-boot/application.log
```

---

## ✅ 체크리스트

### Spring Boot 설정
- [ ] `application.yml`에 FastAPI URL 설정
- [ ] `CALLBACK_API_KEY` 설정 (FastAPI와 동일)
- [ ] RestTemplate/WebClient 설정
- [ ] 콜백 수신 컨트롤러 작성
- [ ] API Key 검증 로직 추가

### FastAPI 설정
- [ ] `.env`에 `CALLBACK_API_KEY` 설정 (.env.production 복사)
- [ ] CORS에 Spring Boot 도메인 추가 ✅ (이미 완료)
- [ ] Systemd 서비스 등록
- [ ] Nginx 리버스 프록시 설정

### 통신 테스트
- [ ] Spring Boot → FastAPI 요청 테스트
- [ ] FastAPI → Spring Boot 콜백 테스트
- [ ] 전체 프로세스 (요청 → 분석 → 콜백) 테스트
- [ ] 실패 케이스 테스트 (잘못된 audio_url 등)

---

## 📞 참고 자료

- FastAPI 공식 문서: https://fastapi.tiangolo.com/
- Spring WebClient: https://docs.spring.io/spring-framework/docs/current/reference/html/web-reactive.html#webflux-client
- CORS 설정: https://fastapi.tiangolo.com/tutorial/cors/
