# Upstage Document Parser

Upstage Document Parser는 PDF 문서를 분석하고 구조화된 데이터로 변환하는 API 클라이언트입니다.

## 기능

- PDF 문서 파싱
- OCR 자동 처리
- 테이블, 그림, 차트 등의 요소 추출
- 비동기 문서 처리 지원

## 사용법

```python
import os
from upstage_parser import DocumentParser

# API 키 설정
api_key = "your_api_key"
# 또는 환경 변수로 설정
# os.environ["UPSTAGE_API_KEY"] = "your_api_key"

# 파서 초기화
parser = DocumentParser(api_key=api_key)

# 문서 파싱 요청
request_id = parser.parse_document(
    filename="your_document.pdf", 
    ocr="auto",
    coordinates=False,
    base64_encoding=["table", "figure", "chart"]
)

# 파싱 상태 확인
status = parser.check_status(request_id)

# 결과 다운로드
if status["status"] == "completed":
    results = parser.download_results(status)
```

## 설치

```bash
pip install -r requirements.txt
```

## 환경 설정

`.env` 파일을 생성하고 다음 내용을 추가하세요:

```
UPSTAGE_API_KEY=your_api_key
```

## upstage-documentparse

**Author:** teddynote
**Version:** 0.0.1
**Type:** tool

### Description



