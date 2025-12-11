"""
음성 분석 로직 간단 테스트 스크립트
Streamlit 없이 직접 analyzer_manager 호출

사용 방법:
    python test_analyzer_simple.py
"""
from app.agents.managers.analyzer_manager import SpeechAnalysisManager
from app.agents.utils.comment_generator import AICommentGenerator
from pathlib import Path
import json

def test_analysis(wav_path: str, reference_text: str, language_code: str = "ko-KR", gender: str = "F"):
    """
    음성 분석 테스트

    Args:
        wav_path: WAV 파일 경로
        reference_text: 참조 텍스트
        language_code: 언어 코드 (ko-KR, en-US)
        gender: 성별 (F, M)
    """
    print("=" * 80)
    print("🎤 음성 분석 테스트 시작")
    print("=" * 80)
    print(f"📁 파일: {wav_path}")
    print(f"📝 참조 텍스트: {reference_text}")
    print(f"🌐 언어: {language_code}")
    print(f"👤 성별: {gender}")
    print("=" * 80)
    print()

    # 1. 매니저 초기화
    print("📦 매니저 초기화 중...")
    analyzer = SpeechAnalysisManager(log_dir="test_logs")
    comment_gen = AICommentGenerator()
    print("✅ 초기화 완료")
    print()

    # 2. 음성 분석 실행
    print("🔄 음성 분석 실행 중...")
    result = analyzer.analyze_parallel(
        wav_path=wav_path,
        reference_text=reference_text,
        language_code=language_code,
        gender=gender
    )
    print("✅ 분석 완료")
    print()

    # 3. 결과 출력
    print("=" * 80)
    print("📊 분석 결과")
    print("=" * 80)
    summary = result['summary']
    print(f"총점: {summary['total_score']:.2f} / {summary['max_total_score']}")
    print(f"평균: {summary['average_score']:.2f}%")
    print(f"소요 시간: {result['elapsed_time']:.2f}초")
    print()

    print("📈 에이전트별 점수:")
    for agent, score in summary['individual_scores'].items():
        if agent != 'validate':  # validate는 점수가 없음
            print(f"  • {agent:15s}: {score:6.2f} / 100")
    print()

    # 4. AI 코멘트 생성
    print("💬 AI 코멘트 생성 중...")
    agent_outputs = analyzer.get_agent_outputs(result)
    validation_result = result['detailed_results'].get('validate', {})

    comment_data = comment_gen.generate_comment(agent_outputs, validation_result)
    print("✅ 코멘트 생성 완료")
    print()

    print("=" * 80)
    print("📝 AI 피드백")
    print("=" * 80)
    print(comment_data['comment'])
    print()

    # 5. 결과 저장
    output_file = Path("test_result.json")
    print(f"💾 결과 저장 중: {output_file}")

    save_data = {
        "input": {
            "wav_path": wav_path,
            "reference_text": reference_text,
            "language_code": language_code,
            "gender": gender
        },
        "analysis_result": result,
        "ai_comment": comment_data
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)

    print(f"✅ 저장 완료: {output_file}")
    print()

    # 6. 요약
    print("=" * 80)
    print("✅ 테스트 완료!")
    print("=" * 80)
    print(f"📊 평균 점수: {summary['average_score']:.2f}%")
    print(f"⏱️  소요 시간: {result['elapsed_time']:.2f}초")
    print(f"💾 결과 파일: {output_file}")
    print(f"📋 로그 파일: test_logs/")
    print("=" * 80)

    return result


def main():
    """메인 함수"""
    print()
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "음성 분석 로직 테스트 스크립트" + " " * 28 + "║")
    print("╚" + "=" * 78 + "╝")
    print()

    # 테스트 파일 경로 설정
    # ⚠️ 실제 테스트할 파일 경로로 수정하세요!
    wav_path = input("📁 WAV 파일 경로를 입력하세요 (예: sample/test.wav): ").strip()

    if not wav_path:
        print("❌ 파일 경로가 입력되지 않았습니다.")
        print("예시 경로 사용: sample/test.wav")
        wav_path = "sample/test.wav"

    # 파일 존재 확인
    if not Path(wav_path).exists():
        print(f"❌ 파일을 찾을 수 없습니다: {wav_path}")
        print()
        print("💡 해결 방법:")
        print("  1. 파일 경로를 확인하세요")
        print("  2. 상대 경로 또는 절대 경로를 사용하세요")
        print("  3. 예시: app/agents/sample/F_ko-KR_track1.wav")
        return

    # 참조 텍스트 입력
    reference_text = input("📝 참조 텍스트를 입력하세요 (예: 안녕하세요. 오늘은 날씨가 좋습니다.): ").strip()

    if not reference_text:
        print("❌ 참조 텍스트가 입력되지 않았습니다.")
        print("기본 텍스트 사용: 안녕하세요. 오늘은 날씨가 좋습니다.")
        reference_text = "안녕하세요. 오늘은 날씨가 좋습니다."

    # 언어 선택
    language = input("🌐 언어를 선택하세요 (ko-KR / en-US) [기본: ko-KR]: ").strip()
    language_code = language if language in ["ko-KR", "en-US"] else "ko-KR"

    # 성별 선택
    gender_input = input("👤 성별을 선택하세요 (F / M) [기본: F]: ").strip().upper()
    gender = gender_input if gender_input in ["F", "M"] else "F"

    print()

    # 테스트 실행
    try:
        result = test_analysis(wav_path, reference_text, language_code, gender)
    except Exception as e:
        print()
        print("=" * 80)
        print("❌ 오류 발생!")
        print("=" * 80)
        print(f"오류 메시지: {str(e)}")
        print()
        print("💡 확인 사항:")
        print("  1. Azure Speech API 키가 .env에 설정되어 있는지 확인")
        print("  2. 필요한 패키지가 모두 설치되어 있는지 확인")
        print("  3. 오디오 파일이 올바른 형식(WAV)인지 확인")
        print()
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        print("⚠️  사용자가 중단했습니다.")
    except Exception as e:
        print()
        print(f"❌ 예상치 못한 오류: {str(e)}")
        import traceback
        traceback.print_exc()
