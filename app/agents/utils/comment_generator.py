"""
AI Comment Generator
OpenAI API를 사용하여 음성 분석 결과에 대한 자세한 코멘트를 생성

주요 개선 사항:
- [2025-12-02] generate_detailed_feedback() 메서드 삭제 (Dead code 제거)
- [2025-12-02] OpenAI API 에러 핸들링 세분화 (RateLimitError, APITimeoutError, APIConnectionError, APIError)
- [2025-12-02] 각 예외 타입별로 사용자 친화적인 에러 메시지 제공
- [2025-12-02] error_detail 필드 추가로 디버깅 편의성 향상
"""
import os
import json
from typing import Dict, Any
from openai import OpenAI, APIError, RateLimitError, APIConnectionError, APITimeoutError
from dotenv import load_dotenv

load_dotenv()


class AICommentGenerator:
    """AI 코멘트 생성기"""

    def __init__(self):
        """OpenAI API 클라이언트 초기화"""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            # API 키가 없으면 None으로 초기화 (API 호출 시 에러 메시지 반환)
            self.client = None
            self.model = "gpt-4o-mini"
            print("⚠️  Warning: OPENAI_API_KEY가 설정되지 않았습니다. AI 코멘트 생성이 비활성화됩니다.")
        else:
            self.client = OpenAI(api_key=api_key)
            self.model = "gpt-4o-mini"  # 무료 테스트용

    def create_analysis_prompt(self, agent_outputs: Dict[str, Any]) -> str:
        """
        분석 결과를 기반으로 프롬프트 생성

        Args:
            agent_outputs: 각 에이전트의 부가적인 output

        Returns:
            프롬프트 문자열
        """
        prompt = """당신은 전문적인 음성 분석 코치입니다. 다음 6가지 측면에서 분석된 음성 평가 결과를 바탕으로,
사용자에게 구체적이고 실용적인 피드백을 제공해주세요.

평가 결과는 다음과 같습니다:

"""

        # Accent (강조)
        if "accent" in agent_outputs:
            accent = agent_outputs["accent"]
            prompt += f"""
### 1. 강조 (Accent) 분석
- 종합 점수: {accent.get('score', 0):.2f}점 / 100점
- 음높이 변화 점수: {accent.get('score_pitch', 0):.2f}점 / 100점
- 에너지(강약) 점수: {accent.get('score_energy', 0):.2f}점 / 100점
"""

        # Pronunciation (발음)
        if "pronunciation" in agent_outputs:
            pron = agent_outputs["pronunciation"]
            prompt += f"""
### 2. 발음 (Pronunciation) 분석
- 종합 점수: {pron.get('score', 0):.2f}점 / 100점
- 정확도: {pron.get('accuracy_score', 0):.2f}점 / 100점
- 유창성: {pron.get('fluency_score', 0):.2f}점 / 100점
- 완전성: {pron.get('completeness_score', 0):.2f}점 / 100점
- 인식된 텍스트: "{pron.get('recognized_text', '')}"
"""

        # Pause (휴지)
        if "pause" in agent_outputs:
            pause = agent_outputs["pause"]
            prompt += f"""
### 3. 휴지 (Pause) 분석
- 종합 점수: {pause.get('score', 0):.2f}점 / 100점
- 유창성 점수: {pause.get('fluency_score', 0):.2f}점 / 100점
- Pause 위치 점수: {pause.get('position_score', 0):.2f}점 / 10점
- Pause 길이 점수: {pause.get('length_score', 0):.2f}점 / 5점
- 총 Pause: {pause.get('total_pauses', 0)}개 (적절: {pause.get('good_pauses', 0)}개, 부적절: {pause.get('bad_pauses', 0)}개)
"""

        # Intonation (억양)
        if "intonation" in agent_outputs:
            inton = agent_outputs["intonation"]
            prompt += f"""
### 4. 억양 (Intonation) 분석
- 종합 점수: {inton.get('score', 0):.2f}점 / 100점
- 언어: {inton.get('language', '')}
- 리듬 타입: {inton.get('rhythm_type', '')}
- 문장 종결 패턴: {inton.get('ending_type', '')}
- 인식된 텍스트: "{inton.get('transcript', '')}"
"""

        # Speed (속도)
        if "speed" in agent_outputs:
            speed = agent_outputs["speed"]
            prompt += f"""
### 5. 속도 (Speed) 분석
- 종합 점수: {speed.get('score', 0):.2f}점 / 100점
- 전체 발화 속도: {speed.get('overall_rate', 0):.2f} 음절/초
- 총 음절 수: {speed.get('total_syllables', 0)}개
- 총 발화 시간: {speed.get('total_speech_duration', 0):.2f}초
- 최적 속도 범위: {speed.get('optimal_range', '')} 음절/초
"""

        # Tone (톤)
        if "tone" in agent_outputs:
            tone = agent_outputs["tone"]
            prompt += f"""
### 6. 톤 (Tone) 분석
- 종합 점수: {tone.get('score', 0):.2f}점 / 100점
- 명료도: {tone.get('clarity_score', 0):.2f}점 / 10점
- 안정성: {tone.get('stability_score', 0):.2f}점 / 10점
- 밝기: {tone.get('brightness_score', 0):.2f}점 / 10점
- 음높이 위치: {tone.get('pitch_position_score', 0):.2f}점 / 10점
"""

        prompt += """

위 분석 결과를 바탕으로, **반드시 다음 형식을 따라** 6가지 측면을 모두 평가해주세요:

---

## 1. 강조 (Accent) 평가
[강조에 대한 평가를 작성]

## 2. 발음 (Pronunciation) 평가
[발음에 대한 평가를 작성]

## 3. 휴지 (Pause) 평가
[휴지에 대한 평가를 작성]

## 4. 억양 (Intonation) 평가
[억양에 대한 평가를 작성]

## 5. 속도 (Speed) 평가
[속도에 대한 평가를 작성]

## 6. 톤 (Tone) 평가
[톤에 대한 평가를 작성]

---

## 종합 평가 및 조언
- **전체 종합**: 6가지 측면을 종합한 전체 평가
- **주요 강점**: 잘 수행한 부분을 구체적으로 칭찬
- **개선 우선순위**: 개선이 필요한 부분을 우선순위와 함께 설명
- **실천 방법**: 각 개선점에 대한 구체적이고 실천 가능한 연습 방법

**필수 요구사항**:
1. 위 형식의 "## 1. ~ ## 6." 섹션 헤더를 **정확히 그대로** 사용해야 합니다.
2. 6가지 측면(강조, 발음, 휴지, 억양, 속도, 톤)을 **모두 빠짐없이** 평가해야 합니다.
3. 각 섹션은 최소 2-3문장 이상으로 구체적으로 작성해야 합니다.
4. 답변은 전문적이고 객관적인 톤으로, 한국어로 작성해주세요.
"""

        return prompt

    def generate_comment(self, agent_outputs: Dict[str, Any], validation_result: Dict[str, Any] = None) -> Dict[str, str]:
        """
        AI 코멘트 생성

        Args:
            agent_outputs: 각 에이전트의 부가적인 output
            validation_result: 검증 결과 (선택사항)

        Returns:
            생성된 코멘트 딕셔너리
        """
        try:
            # OpenAI 클라이언트가 없으면 기본 메시지 반환
            if not self.client:
                return {
                    "comment": "AI 코멘트 생성이 비활성화되었습니다. OPENAI_API_KEY를 설정해주세요.",
                    "status": "disabled"
                }

            # Validation 결과 확인 - 부적합이면 예외 처리
            if validation_result and not validation_result.get("is_valid", True):
                feedback_list = validation_result.get("feedback", [])
                feedback_text = "\n".join(f"• {item}" for item in feedback_list)

                error_msg = validation_result.get("error", "")
                warnings = validation_result.get("warnings", [])

                # 상세한 부적합 사유 생성
                reason_parts = []
                if "completeness" in warnings:
                    reason_parts.append("스크립트 재현율이 기준(90%) 미만입니다.")
                if "text_mismatch" in warnings:
                    reason_parts.append("스크립트와 내용 일치도가 기준(90%) 미만입니다.")
                if "no_speech" in warnings:
                    reason_parts.append("음성이 인식되지 않았습니다.")
                if error_msg:
                    reason_parts.append(f"오류: {error_msg}")

                reason_text = "\n".join(f"• {reason}" for reason in reason_parts) if reason_parts else "• 검증 기준을 충족하지 못했습니다."

                return {
                    "comment": f"""## 🚫 분석 부적합

스크립트 정확도가 낮아 **부적합**으로 판정되었습니다.

### 부적합 사유
{reason_text}

### 검증 결과
{feedback_text}

### 권장 사항
1. 스크립트 내용을 정확하게 읽어주세요.
2. 배경 소음이 없는 조용한 환경에서 녹음해주세요.
3. 명확한 발음으로 천천히 말씀해주세요.
4. 스크립트와 다른 내용을 말하지 않도록 주의해주세요.
""",
                    "status": "validation_failed",
                    "validation_result": validation_result
                }

            # 에이전트 데이터 누락 확인
            expected_agents = {"accent", "pronunciation", "pause", "intonation", "speed", "tone"}
            available_agents = set(agent_outputs.keys())
            missing_agents = expected_agents - available_agents

            if missing_agents:
                missing_names = {
                    "accent": "강조",
                    "pronunciation": "발음",
                    "pause": "휴지",
                    "intonation": "억양",
                    "speed": "속도",
                    "tone": "톤"
                }
                missing_list = ", ".join(missing_names.get(agent, agent) for agent in missing_agents)

                return {
                    "comment": f"""## ⚠️ 분석 불완전

일부 분석이 실패하여 완전한 피드백을 제공할 수 없습니다.

### 실패한 분석
• {missing_list}

### 성공한 분석
• {", ".join(missing_names.get(agent, agent) for agent in available_agents)}

다시 시도하거나 시스템 관리자에게 문의해주세요.
""",
                    "status": "incomplete_analysis",
                    "missing_agents": list(missing_agents)
                }

            # 프롬프트 생성
            prompt = self.create_analysis_prompt(agent_outputs)

            # OpenAI API 호출
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "당신은 전문적인 음성 분석 코치입니다. 음성 평가 결과를 바탕으로 구체적이고 실용적인 피드백을 제공합니다."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=2000
            )

            # 응답 추출
            comment = response.choices[0].message.content

            # 6가지 측면이 모두 포함되었는지 검증
            required_sections = [
                "강조 (Accent)",
                "발음 (Pronunciation)",
                "휴지 (Pause)",
                "억양 (Intonation)",
                "속도 (Speed)",
                "톤 (Tone)"
            ]

            missing_sections = [section for section in required_sections if section not in comment]

            validation_warning = ""
            if missing_sections:
                validation_warning = f"\n\n⚠️ 경고: 다음 측면이 응답에서 누락되었을 수 있습니다: {', '.join(missing_sections)}"

            return {
                "comment": comment + validation_warning,
                "model": self.model,
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
                "status": "success",
                "missing_sections": missing_sections if missing_sections else None
            }

        except RateLimitError as e:
            return {
                "comment": "API 사용량 한도 초과. 잠시 후 다시 시도해주세요.",
                "status": "rate_limit_error",
                "error_detail": str(e)
            }

        except APITimeoutError as e:
            return {
                "comment": "OpenAI API 응답 시간 초과. 네트워크 상태를 확인하거나 잠시 후 다시 시도해주세요.",
                "status": "timeout_error",
                "error_detail": str(e)
            }

        except APIConnectionError as e:
            return {
                "comment": "OpenAI API 연결 실패. 네트워크 연결을 확인해주세요.",
                "status": "connection_error",
                "error_detail": str(e)
            }

        except APIError as e:
            return {
                "comment": f"OpenAI API 오류가 발생했습니다: {str(e)}",
                "status": "api_error",
                "error_detail": str(e)
            }

        except Exception as e:
            return {
                "comment": f"예상치 못한 오류가 발생했습니다: {str(e)}",
                "status": "error",
                "error_detail": str(e)
            }


