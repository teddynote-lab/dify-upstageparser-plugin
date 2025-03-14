"""
Upstage Document Parser API를 사용하기 위한 클라이언트 클래스 구현
"""

import os
import json
import time
from typing import Dict, List, Union, Optional, Any
from urllib.parse import urlparse
import requests


class DocumentParser:
    """Upstage Document Parser API를 위한 클라이언트 클래스

    이 클래스는 Upstage의 Document Parser API를 사용하여 문서를 분석하고
    구조화된 데이터로 변환하는 기능을 제공합니다.

    Attributes:
        api_key (str): Upstage API 키
        base_url (str): API 기본 URL
    """

    def __init__(
        self, api_key: Optional[str] = None, base_url: str = "https://api.upstage.ai/v1"
    ):
        """
        DocumentParser 클라이언트를 초기화합니다.

        Args:
            api_key: Upstage API 키. 없으면 환경 변수 UPSTAGE_API_KEY에서 가져옵니다.
            base_url: API 기본 URL

        Raises:
            ValueError: API 키가 제공되지 않았거나 환경 변수에 설정되지 않은 경우
        """
        self.api_key = api_key or os.environ.get("UPSTAGE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "API 키가 필요합니다. 매개변수로 전달하거나 UPSTAGE_API_KEY 환경 변수를 설정하세요."
            )
        self.base_url = base_url
        self.headers = {"Authorization": f"Bearer {self.api_key}"}

    def parse_document(
        self,
        filename: str,
        ocr: str = "auto",
        coordinates: bool = False,
        base64_encoding: List[str] = None,
        model: str = "document-parse",
    ) -> str:
        """
        문서 파싱 요청을 전송합니다.

        Args:
            filename: 파싱할 PDF 파일 경로
            ocr: OCR 처리 방식 ('auto', 'always', 'never')
            coordinates: 요소 좌표 정보 포함 여부
            base64_encoding: base64로 인코딩할 요소 유형 리스트 (예: ['table', 'figure', 'chart'])
            model: 사용할 모델 이름

        Returns:
            request_id: 요청 ID (파싱 진행 상황을 추적하는 데 사용)

        Raises:
            FileNotFoundError: 파일을 찾을 수 없는 경우
            Exception: API 요청 중 오류가 발생한 경우
        """
        # 파라미터 기본값 설정
        if base64_encoding is None:
            base64_encoding = ["table", "figure", "chart"]

        url = f"{self.base_url}/document-ai/async/document-parse"

        # 파일이 존재하는지 확인
        if not os.path.exists(filename):
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {filename}")

        # 파일과 데이터 준비
        with open(filename, "rb") as file:
            files = {"document": file}
            data = {
                "ocr": ocr,
                "coordinates": str(coordinates).lower(),
                "base64_encoding": str(base64_encoding),
                "model": model,
            }

            # API 요청 전송
            response = requests.post(url, headers=self.headers, files=files, data=data)

            # 응답 확인
            if response.status_code != 200:
                raise Exception(
                    f"API 요청 실패: {response.status_code} {response.text}"
                )

            # 요청 ID 반환
            result = response.json()
            return result.get("request_id")

    def check_status(self, request_id: str) -> Dict[str, Any]:
        """
        문서 파싱 요청의 상태를 확인합니다.

        Args:
            request_id: 파싱 요청의 ID

        Returns:
            Dict: 요청 상태 정보가 포함된 딕셔너리

        Raises:
            Exception: API 요청 중 오류가 발생한 경우
        """
        url = f"{self.base_url}/document-ai/requests/{request_id}"
        response = requests.get(url, headers=self.headers)

        if response.status_code != 200:
            raise Exception(f"상태 확인 실패: {response.status_code} {response.text}")

        return response.json()

    def list_requests(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        모든 문서 파싱 요청 목록을 가져옵니다.

        Returns:
            Dict: 요청 목록이 포함된 딕셔너리

        Raises:
            Exception: API 요청 중 오류가 발생한 경우
        """
        url = f"{self.base_url}/document-ai/requests"
        response = requests.get(url, headers=self.headers)

        if response.status_code != 200:
            raise Exception(
                f"요청 목록 가져오기 실패: {response.status_code} {response.text}"
            )

        return response.json()

    def wait_for_completion(
        self, request_id: str, polling_interval: int = 5, timeout: int = 600
    ) -> Dict[str, Any]:
        """
        문서 파싱이 완료될 때까지 대기합니다.

        Args:
            request_id: 파싱 요청의 ID
            polling_interval: 상태 확인 간격(초)
            timeout: 최대 대기 시간(초)

        Returns:
            Dict: 파싱 완료 상태 정보

        Raises:
            TimeoutError: 지정된 시간 내에 파싱이 완료되지 않은 경우
            Exception: 파싱 과정에서 오류가 발생한 경우
        """
        start_time = time.time()

        while True:
            # 시간 초과 확인
            if time.time() - start_time > timeout:
                raise TimeoutError(f"파싱 대기 시간 초과: {timeout}초")

            # 상태 확인
            status = self.check_status(request_id)

            # 파싱 완료 확인
            if status.get("status") == "completed":
                return status

            # 파싱 실패 확인
            if status.get("status") == "failed":
                raise Exception(
                    f"파싱 실패: {status.get('failure_message', '알 수 없는 오류')}"
                )

            # 대기
            time.sleep(polling_interval)

    def download_batch_results(self, batch: Dict[str, Any]) -> Dict[str, Any]:
        """
        배치 결과를 다운로드합니다.

        Args:
            batch: 배치 정보 딕셔너리

        Returns:
            Dict: 다운로드한 배치 결과

        Raises:
            Exception: 다운로드 중 오류가 발생한 경우
        """
        download_url = batch.get("download_url")
        if not download_url:
            raise ValueError("배치에 다운로드 URL이 없습니다")

        response = requests.get(download_url)

        if response.status_code != 200:
            raise Exception(
                f"결과 다운로드 실패: {response.status_code} {response.text}"
            )

        return response.json()

    def download_results(self, status: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        모든 배치 결과를 다운로드합니다.

        Args:
            status: 문서 파싱 상태 정보

        Returns:
            List[Dict]: 다운로드한 모든 배치 결과의 리스트

        Raises:
            ValueError: 상태 정보가 올바르지 않은 경우
        """
        batches = status.get("batches", [])
        if not batches:
            raise ValueError("상태 정보에 배치가 없습니다")

        results = []
        for batch in batches:
            if batch.get("status") == "completed":
                batch_result = self.download_batch_results(batch)
                results.append(batch_result)

        return results

    def save_results(self, results: List[Dict[str, Any]], output_dir: str) -> List[str]:
        """
        파싱 결과를 JSON 파일로 저장합니다.

        Args:
            results: 다운로드한 결과 리스트
            output_dir: 결과를 저장할 디렉토리 경로

        Returns:
            List[str]: 저장된 파일 경로 리스트

        Raises:
            FileNotFoundError: 출력 디렉토리가 없는 경우
        """
        # 디렉토리 존재 확인 및 생성
        os.makedirs(output_dir, exist_ok=True)

        saved_files = []
        for i, result in enumerate(results):
            filename = os.path.join(output_dir, f"batch_{i}.json")
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            saved_files.append(filename)

        return saved_files
