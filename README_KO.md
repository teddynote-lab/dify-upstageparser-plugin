# Dify를 위한 Upstage 문서 파싱 플러그인

[![dify 커스텀 도구 제작하기 (upstage 파서) 튜토리얼](https://img.youtube.com/vi/xWG4nYBZTsE/0.jpg)](https://youtu.be/xWG4nYBZTsE)

[dify 커스텀 도구 제작하기 (upstage 파서) 튜토리얼](https://youtu.be/xWG4nYBZTsE)을 확인하여 플러그인 사용법을 확인하세요!

**바로 사용하기** 

[Dify 플러그인 패키지 다운로드](https://www.dropbox.com/scl/fi/ehbl0zmd409njmq2tmya3/upstage-documentparse.difypkg?rlkey=my8l73m70emtnc9fi1mo0tvg7&st=a10wvxty&dl=0)를 받아 Dify 인스턴스에 직접 업로드하세요.

[Dify](https://dify.ai) 플랫폼을 위한 강력한 문서 파싱 플러그인으로, Upstage Document Parse API를 활용하여 다양한 문서 형식을 구조화된 마크다운, HTML 또는 텍스트로 변환합니다.


## 기능

- **다양한 형식 지원**: PDF, DOCX 파일 및 다양한 이미지 형식 처리
- **지능형 문서 이해**: 원본 구조를 유지하며 텍스트, 표, 차트, 그림 추출
- **다양한 출력 형식**: 문서를 마크다운, HTML 또는 일반 텍스트로 변환
- **효율적인 캐싱**: 콘텐츠 기반 캐싱으로 동일한 파일의 재처리 방지
- **OCR 기능**: 스캔된 문서와 이미지에서 텍스트 추출
- **차트 인식**: 문서에서 차트 식별 및 추출
- **배치 처리**: 다중 페이지 문서를 효율적으로 처리
- **좌표 추출**: 문서 요소의 경계 상자 좌표 획득

## 설치

필요한 의존성을 설치합니다:

```bash
pip install -r requirements.txt
```

Dify 플랫폼에서 플러그인을 구성합니다.

## 구성

### 필수 자격 증명

플러그인에는 다음 자격 증명이 필요합니다:

- `upstage_api_key`: Upstage API 키 ([Upstage Console](https://console.upstage.ai)에서 획득)
- `base_url`: Dify 인스턴스 기본 URL (기본값: "https://cloud.dify.ai")

### 매개변수 옵션

도구 사용 시 다음 매개변수를 구성할 수 있습니다:

- `result_type`: 출력 형식 (옵션: "md", "html", "text")
- `as_file`: 결과를 파일 또는 텍스트로 반환할지 여부 (옵션: "file", "text")

## 사용법

### Dify 애플리케이션에서

1. Upstage Document Parse 도구를 애플리케이션에 추가합니다.
2. 필요한 자격 증명을 구성합니다.
3. 애플리케이션 흐름에서 도구를 사용하여 문서를 처리합니다.

### Python에서 직접 사용

Python 코드에서 클라이언트를 직접 사용할 수도 있습니다:

```python
from tools.upstage_client import UpstageDocumentParseClient

# 클라이언트 초기화
client = UpstageDocumentParseClient(
    api_key="your_upstage_api_key",
    output_dir="exported_documents"
)

# 문서를 마크다운으로 변환
markdown_content = client.convert_to_markdown("path/to/your/document.pdf")

# 문서를 HTML로 변환
html_content = client.convert_to_html("path/to/your/document.docx")

# 문서를 일반 텍스트로 변환
text_content = client.convert_to_text("path/to/your/image.jpg")
```

## API 매개변수

플러그인은 Upstage Document Parse API를 호출할 때 다음 매개변수를 사용합니다:

| 매개변수 | 유형 | 설명 | 기본값 |
|-----------|------|-------------|---------|
| `document` | 파일 | 처리할 문서 파일 | 필수 |
| `ocr` | 문자열 | OCR 동작 제어: "auto" (이미지에만 적용) 또는 "force" (모두 이미지로 먼저 변환) | "auto" |
| `coordinates` | 불리언 | 경계 상자 좌표를 반환할지 여부 | false |
| `chart_recognition` | 불리언 | 차트 인식을 사용할지 여부 | true |
| `output_formats` | List[String] | 레이아웃 요소의 형식: "text", "html", "markdown" | ["html", "markdown", "text"] |
| `model` | 문자열 | 추론에 사용되는 모델 | "document-parse-250305" |
| `base64_encoding` | List[String] | base64 인코딩된 문자열로 제공할 레이아웃 카테고리 | ["table", "figure", "chart"] |

## 캐싱 메커니즘

플러그인은 효율적인 캐싱 시스템을 구현합니다:

1. 중복 문서를 식별하기 위한 파일 내용 해싱
2. 내용 해시 및 출력 형식 기반 결과 캐싱
3. TTL 기반 캐시 만료 (기본값: 1시간)

## 예제

### PDF를 마크다운으로 변환

```python
client = UpstageDocumentParseClient(api_key="your_api_key")
markdown = client.convert_to_markdown("sample.pdf")
print(markdown)
```

### 대용량 문서 처리

```python
client = UpstageDocumentParseClient(api_key="your_api_key")
exported_files = client.process_document(
    "large_document.pdf",
    wait=True,
    poll_interval=2,
    max_wait=600
)
print(f"내보낸 파일: {exported_files}")
```

## 개발

### 프로젝트 구조

- `upstage-documentparse.py`: 메인 Dify 플러그인 통합
- `upstage_client.py`: Upstage API와 상호 작용하는 핵심 클라이언트
- `requirements.txt`: Python 의존성

### 기여

기여는 언제나 환영합니다! Pull Request를 제출해 주세요.

## 라이선스

[MIT 라이선스](LICENSE.md)

## 문의

**문의사항이 있으시다면 다음 이메일로 문의해 주세요:**  
dev@brain-crew.com