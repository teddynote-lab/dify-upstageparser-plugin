#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Upstage Document Parser 사용 예제
"""
import os
import argparse
from dotenv import load_dotenv
from upstage_parser import DocumentParser


def main():
    """
    Upstage Document Parser를 사용하여 PDF 문서를 파싱하는 예제
    """
    # 환경 변수 로드
    load_dotenv()

    # 명령행 인자 파싱
    parser = argparse.ArgumentParser(description="Upstage Document Parser 예제")
    parser.add_argument("--file", "-f", required=True, help="파싱할 PDF 파일 경로")
    parser.add_argument(
        "--output",
        "-o",
        default="output",
        help="결과를 저장할 디렉토리 (기본값: output)",
    )
    parser.add_argument(
        "--api-key", help="Upstage API 키 (환경 변수로 설정하지 않은 경우)"
    )
    parser.add_argument("--wait", action="store_true", help="파싱 완료까지 대기")
    args = parser.parse_args()

    # API 키 설정
    api_key = args.api_key or os.environ.get("UPSTAGE_API_KEY")
    if not api_key:
        print(
            "API 키가 필요합니다. --api-key 옵션을 사용하거나 환경 변수 UPSTAGE_API_KEY를 설정하세요."
        )
        return

    # 파서 초기화
    parser = DocumentParser(api_key=api_key)

    try:
        # 문서 파싱 요청
        print(f"'{args.file}' 파싱 요청 중...")
        request_id = parser.parse_document(
            filename=args.file,
            ocr="auto",
            coordinates=False,
            base64_encoding=["table", "figure", "chart"],
        )
        print(f"요청 ID: {request_id}")

        if args.wait:
            # 파싱 완료까지 대기
            print("파싱 완료까지 대기 중...")
            status = parser.wait_for_completion(request_id)
            print(f"파싱 완료: {status['total_pages']} 페이지")

            # 결과 다운로드
            print("결과 다운로드 중...")
            results = parser.download_results(status)

            # 결과 저장
            print(f"결과 저장 중 ({len(results)} 배치)...")
            saved_files = parser.save_results(results, args.output)
            print(f"결과가 다음 위치에 저장되었습니다: {', '.join(saved_files)}")
        else:
            print("비동기 요청이 제출되었습니다. 나중에 결과를 확인하세요.")

    except Exception as e:
        print(f"오류 발생: {e}")


if __name__ == "__main__":
    main()
