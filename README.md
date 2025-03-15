# Upstage Document Parse Plugin for Dify

**Ready to use?**

[Download the Dify plugin package](https://www.dropbox.com/scl/fi/ehbl0zmd409njmq2tmya3/upstage-documentparse.difypkg?rlkey=my8l73m70emtnc9fi1mo0tvg7&st=a10wvxty&dl=0) and upload it directly to your Dify instance.

A powerful document parsing plugin for the [Dify](https://dify.ai) platform that leverages the Upstage Document Parse API to convert various document formats into structured markdown, HTML, or text.

## Features

- **Multi-format Support**: Process PDFs, DOCX files, and various image formats
- **Intelligent Document Understanding**: Extract text, tables, charts, and figures with their original structure
- **Multiple Output Formats**: Convert documents to markdown, HTML, or plain text
- **Efficient Caching**: Avoid reprocessing identical files with content-based caching
- **OCR Capabilities**: Extract text from scanned documents and images
- **Chart Recognition**: Identify and extract charts from documents
- **Batch Processing**: Process multi-page documents efficiently
- **Coordinate Extraction**: Obtain bounding box coordinates for document elements

## Installation

Install the required dependencies:

```bash
pip install -r requirements.txt
```

Configure the plugin in your Dify platform.

## Configuration

### Required Credentials

The plugin requires the following credentials:

- `upstage_api_key`: Your Upstage API key (obtain from [Upstage Console](https://console.upstage.ai))
- `base_url`: Your Dify instance base URL (default: "https://cloud.dify.ai")

### Parameter Options

When using the tool, you can configure the following parameters:

- `result_type`: Output format (options: "md", "html", "text")
- `as_file`: Whether to return results as a file or text (options: "file", "text")

## Usage

### In Dify Application

1. Add the Upstage Document Parse tool to your application.
2. Configure the required credentials.
3. Use the tool in your application flows to process documents.

### Direct Python Usage

You can also use the client directly in your Python code:

```python
from tools.upstage_client import UpstageDocumentParseClient

# Initialize the client
client = UpstageDocumentParseClient(
    api_key="your_upstage_api_key",
    output_dir="exported_documents"
)

# Convert a document to markdown
markdown_content = client.convert_to_markdown("path/to/your/document.pdf")

# Convert a document to HTML
html_content = client.convert_to_html("path/to/your/document.docx")

# Convert a document to plain text
text_content = client.convert_to_text("path/to/your/image.jpg")
```

## API Parameters

The plugin uses the following parameters when calling the Upstage Document Parse API:

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `document` | File | The document file to be processed | Required |
| `ocr` | String | Controls OCR behavior: "auto" (apply to images only) or "force" (convert all to images first) | "auto" |
| `coordinates` | Boolean | Whether to return bounding box coordinates | false |
| `chart_recognition` | Boolean | Whether to use chart recognition | true |
| `output_formats` | List[String] | Format for layout elements: "text", "html", "markdown" | ["html", "markdown", "text"] |
| `model` | String | Model used for inference | "document-parse-250305" |
| `base64_encoding` | List[String] | Layout categories to provide as base64 encoded strings | ["table", "figure", "chart"] |

## Caching Mechanism

The plugin implements an efficient caching system:

1. File content hashing to identify duplicate documents
2. Result caching based on content hash and output format
3. TTL-based cache expiration (default: 1 hour)

## Examples

### Converting a PDF to Markdown

```python
client = UpstageDocumentParseClient(api_key="your_api_key")
markdown = client.convert_to_markdown("sample.pdf")
print(markdown)
```

### Processing a Large Document

```python
client = UpstageDocumentParseClient(api_key="your_api_key")
exported_files = client.process_document(
    "large_document.pdf",
    wait=True,
    poll_interval=2,
    max_wait=600
)
print(f"Files exported: {exported_files}")
```

## Development

### Project Structure

- `upstage-documentparse.py`: Main Dify plugin integration
- `upstage_client.py`: Core client for interacting with the Upstage API
- `requirements.txt`: Python dependencies

### Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

[MIT License](LICENSE.md)

## Contact

**For any inquiries, please contact:**  
dev@brain-crew.com




