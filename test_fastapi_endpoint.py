"""
FastAPI 엔드포인트 테스트 스크립트
/api/v1/evaluate 엔드포인트를 직접 호출하여 테스트

사용 방법:
    1. 서버 실행: uvicorn app.main:app --reload --port 8000
    2. 다른 터미널에서: python test_fastapi_endpoint.py
"""
import requests
from pathlib import Path
import json
import sys

def test_evaluate_endpoint(
    audio_file_path: str,
    reference_text: str,
    script_id: int = 1,
    user_id: str = "test_user",
    base_url: str = "http://localhost:8000"
):
    """
    /api/v1/evaluate 엔드포인트 테스트

    Args:
        audio_file_path: 오디오 파일 경로
        reference_text: 참조 텍스트
        script_id: 스크립트 ID
        user_id: 사용자 ID
        base_url: API 서버 주소
    """
    print("=" * 80)
    print("🚀 FastAPI 엔드포인트 테스트")
    print("=" * 80)
    print(f"🌐 서버: {base_url}")
    print(f"📁 파일: {audio_file_path}")
    print(f"📝 참조 텍스트: {reference_text}")
    print(f"📋 스크립트 ID: {script_id}")
    print(f"👤 사용자 ID: {user_id}")
    print("=" * 80)
    print()

    # 1. 파일 존재 확인
    file_path = Path(audio_file_path)
    if not file_path.exists():
        print(f"❌ 파일을 찾을 수 없습니다: {audio_file_path}")
        return None

    print(f"✅ 파일 확인 완료: {file_path.name} ({file_path.stat().st_size} bytes)")
    print()

    # 2. 서버 연결 확인
    print("🔍 서버 연결 확인 중...")
    try:
        health_response = requests.get(f"{base_url}/health", timeout=5)
        if health_response.status_code == 200:
            print(f"✅ 서버 연결 성공: {health_response.json()}")
        else:
            print(f"⚠️  서버 응답 이상: {health_response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"❌ 서버 연결 실패: {str(e)}")
        print()
        print("💡 해결 방법:")
        print("  1. 서버가 실행 중인지 확인: uvicorn app.main:app --reload --port 8000")
        print("  2. 포트 번호가 맞는지 확인 (기본: 8000)")
        print("  3. 방화벽 설정 확인")
        return None
    print()

    # 3. API 요청 준비
    url = f"{base_url}/api/v1/evaluate"

    # multipart/form-data 형식
    files = {
        'audio_file': (file_path.name, open(file_path, 'rb'), 'audio/wav')
    }

    data = {
        'script_id': script_id,
        'user_id': user_id,
        'reference_text': reference_text
    }

    # 4. API 요청 전송
    print("📤 API 요청 전송 중...")
    print(f"   URL: {url}")
    print(f"   Method: POST")
    print(f"   Files: {file_path.name}")
    print()

    try:
        response = requests.post(url, files=files, data=data, timeout=300)  # 5분 타임아웃

        # 파일 닫기
        files['audio_file'][1].close()

        # 5. 응답 처리
        if response.status_code == 200:
            print("=" * 80)
            print("✅ 분석 성공!")
            print("=" * 80)
            result = response.json()

            # 점수 출력
            print()
            print("📊 분석 결과:")
            print(f"  • 전체 점수:     {result['overall_score']:.2f}%")
            print()
            print("📈 세부 점수:")
            print(f"  • 발음 (Pronunciation): {result['score_pronunciation']:.2f}")
            print(f"  • 휴지 (Pause):         {result['score_pause']:.2f}")
            print(f"  • 억양 (Intonation):    {result['score_intonation']:.2f}")
            print(f"  • 톤 (Tone):            {result['score_tone']:.2f}")
            print(f"  • 속도 (Speed):         {result['score_speed']:.2f}")
            print(f"  • 강조 (Accent):        {result['score_accent']:.2f}")
            print()

            # AI 피드백 출력 (처음 500자만)
            feedback = result['feedback_summary']
            print("=" * 80)
            print("💬 AI 피드백 (미리보기)")
            print("=" * 80)
            if len(feedback) > 500:
                print(feedback[:500] + "...")
                print(f"\n[전체 {len(feedback)}자 중 500자만 표시]")
            else:
                print(feedback)
            print()

            # 결과 저장
            output_file = Path("test_api_result.json")
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            print("=" * 80)
            print(f"💾 전체 결과 저장: {output_file}")
            print("=" * 80)

            return result

        else:
            print("=" * 80)
            print(f"❌ API 요청 실패: {response.status_code}")
            print("=" * 80)
            print("응답 내용:")
            try:
                error_detail = response.json()
                print(json.dumps(error_detail, indent=2, ensure_ascii=False))
            except:
                print(response.text)
            return None

    except requests.exceptions.Timeout:
        print("❌ 요청 타임아웃 (5분 초과)")
        print("   분석 시간이 오래 걸릴 수 있습니다. 잠시 후 다시 시도하세요.")
        return None
    except requests.exceptions.RequestException as e:
        print(f"❌ 요청 실패: {str(e)}")
        return None


def main():
    """메인 함수"""
    print()
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 22 + "FastAPI 엔드포인트 테스트" + " " * 32 + "║")
    print("╚" + "=" * 78 + "╝")
    print()

    # 사용자 입력
    audio_path = input("📁 오디오 파일 경로 (예: sample/test.wav): ").strip()
    if not audio_path:
        print("⚠️  경로 미입력. 예시 경로 사용: sample/test.wav")
        audio_path = "sample/test.wav"

    reference_text = input("📝 참조 텍스트 (예: 안녕하세요): ").strip()
    if not reference_text:
        print("⚠️  텍스트 미입력. 예시 텍스트 사용")
        reference_text = "안녕하세요. 오늘은 날씨가 좋습니다."

    # 서버 주소 (선택)
    server_input = input("🌐 서버 주소 [기본: http://localhost:8000]: ").strip()
    base_url = server_input if server_input else "http://localhost:8000"

    print()

    # 테스트 실행
    try:
        result = test_evaluate_endpoint(
            audio_file_path=audio_path,
            reference_text=reference_text,
            base_url=base_url
        )

        if result:
            print()
            print("=" * 80)
            print("✅ 테스트 완료!")
            print("=" * 80)
        else:
            print()
            print("=" * 80)
            print("❌ 테스트 실패")
            print("=" * 80)

    except Exception as e:
        print()
        print("=" * 80)
        print("❌ 예상치 못한 오류")
        print("=" * 80)
        print(f"오류: {str(e)}")
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
        print(f"❌ 오류: {str(e)}")
        import traceback
        traceback.print_exc()
