import os
import logging
import hashlib
import json
from typing import Any, Tuple, Generator
import requests

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from tools.upstage_client import UpstageDocumentParseClient


class UpstageDocumentparseTool(Tool):
    """
    A Dify Tool for document parsing using the Upstage Document Parse API.

    This tool processes document files and converts them to various formats (markdown, HTML, or text).
    It implements caching to avoid reprocessing the same files.

    Supported file formats: PDF, DOCX, and various image formats.

    Key features:
    - File caching based on content hash
    - Result caching for different output formats
    - Support for markdown, HTML, and text output
    - Configurable output format (text message or file)
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize the UpstageDocumentparseTool with caching and logging capabilities.

        Args:
            *args: Variable length argument list passed to the parent Tool class
            **kwargs: Arbitrary keyword arguments passed to the parent Tool class
        """
        super().__init__(*args, **kwargs)
        self.client = None
        # Temporary output directory
        self.output_dir = "temp_output"
        # Upstage Document Parse Model
        # https://console.upstage.ai/docs/capabilities/document-parse/asynchronous
        self.model = "document-parse-250305"
        # Debug mode
        self.debug = False
        # Set up cache directory
        self.cache_dir = os.path.join(self.output_dir, "cache")
        self.cache_index_file = os.path.join(self.cache_dir, "cache_index.json")
        # Create directory
        os.makedirs(self.cache_dir, exist_ok=True)
        # Load cache index
        self.conversion_cache = self._load_cache_index()
        # Initialize logging
        self._setup_logging()

    def _setup_logging(self) -> None:
        """
        Initialize the logging system for the tool.

        Sets up both console and file logging with detailed formatting.
        Log file is saved as upstage_documentparse.log.
        """
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        logging.basicConfig(
            level=logging.DEBUG,
            format=log_format,
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler("upstage_documentparse.log"),
            ],
        )
        self.logger = logging.getLogger("UpstageDocumentparseTool")
        self.logger.info("Logging system initialized")

    def _load_cache_index(self) -> dict:
        """
        Load the cache index from the file system.

        The cache index is a dictionary that maps cache keys to boolean values
        indicating whether corresponding cached results exist.

        Returns:
            dict: The loaded cache index, or an empty dict if no index exists or loading fails
        """
        if os.path.exists(self.cache_index_file):
            try:
                with open(self.cache_index_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                # Return empty dictionary if loading fails
                return {}
        return {}

    def _save_cache_index(self) -> None:
        """
        Save the current cache index to the file system.

        The cache index is saved as a JSON file with UTF-8 encoding and
        human-readable formatting (with indentation).
        """
        try:
            with open(self.cache_index_file, "w", encoding="utf-8") as f:
                json.dump(self.conversion_cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            if hasattr(self, "logger"):
                self.logger.error(f"Error occurred while saving cache index: {e}")

    def _get_cache_filepath(self, cache_key: str, result_type: str) -> str:
        """
        Generate the filepath for a cached result.

        Args:
            cache_key (str): The unique identifier for the cached content (typically file hash)
            result_type (str): The format of the result (md, html, or text)

        Returns:
            str: The full path to the cache file
        """
        return os.path.join(self.cache_dir, f"{cache_key}_{result_type}.txt")

    def _download_file(
        self, file, base_url: str, timeout: int = 300
    ) -> Tuple[bytes, str]:
        """
        Download a file from the provided URL.

        Args:
            file: The file object containing URL and filename
            base_url (str): The base URL to prepend to the file URL
            timeout (int, optional): Request timeout in seconds. Defaults to 300.

        Returns:
            Tuple[bytes, str]: A tuple containing the file content as bytes and the file extension

        Raises:
            Exception: If download fails due to HTTP error or other issues
        """
        url = f"{base_url}{file.url}"
        self.logger.debug(f"Starting file download: {url}")
        try:
            response = requests.get(url, timeout=timeout)
            if response.status_code != 200:
                error_msg = f"File download failed: Status code {response.status_code}, Response: {response.text}"
                self.logger.error(error_msg)
                raise Exception(error_msg)
            file_in_bytes = response.content
        except requests.RequestException as e:
            self.logger.exception(
                "Requests client error occurred during file download."
            )
            raise Exception(f"Error during file download: {str(e)}")
        except Exception as e:
            self.logger.exception("Unexpected error occurred during file download.")
            raise Exception(f"Error during file download: {str(e)}")

        self.logger.info(f"Downloaded file size: {len(file_in_bytes)} bytes")
        ext = (
            os.path.splitext(file.filename)[1]
            if hasattr(file, "filename") and file.filename
            else ""
        )
        self.logger.debug(f"File extension: {ext}")
        return file_in_bytes, ext

    def _return_result(
        self,
        result: str,
        return_type: str,
        as_file: bool,
        original_filename: str = "output",
    ) -> Generator[ToolInvokeMessage, None, None]:
        """
        Return the processing result in the appropriate format.

        Args:
            result (str): The conversion result as a string
            return_type (str): The format of the result (md, html, or text)
            as_file (bool): Whether to return as a file (True) or as text (False)
            original_filename (str, optional): The original filename to use as a base. Defaults to "output".

        Yields:
            ToolInvokeMessage: A message containing the result, either as a blob or text
        """
        self.logger.info(
            f"Starting result return: type={return_type}, file_format={as_file}, original_filename={original_filename}"
        )

        # Extract base filename without extension from original filename
        base_filename = os.path.splitext(original_filename)[0]
        # Use default value if filename is empty
        if not base_filename:
            base_filename = "output"

        if as_file:
            if return_type == "md":
                result_bytes = result.encode("utf-8")
                output_filename = f"{base_filename}.md"
                self.logger.debug(
                    f"Returning result as markdown file: {output_filename}"
                )
                yield self.create_blob_message(
                    result_bytes,
                    meta={
                        "filename": output_filename,
                        "mime_type": "text/markdown",
                    },
                )
            elif return_type == "html":
                result_bytes = result.encode("utf-8")
                output_filename = f"{base_filename}.html"
                self.logger.debug(f"Returning result as HTML file: {output_filename}")
                yield self.create_blob_message(
                    result_bytes,
                    meta={
                        "filename": output_filename,
                        "mime_type": "text/html",
                    },
                )
            elif return_type == "text":
                result_bytes = result.encode("utf-8")
                output_filename = f"{base_filename}.txt"
                self.logger.debug(f"Returning result as text file: {output_filename}")
                yield self.create_blob_message(
                    result_bytes,
                    meta={
                        "filename": output_filename,
                        "mime_type": "text/plain",
                    },
                )
        else:
            self.logger.debug("Returning result as text message")
            yield self.create_text_message(result)

    def _invoke(
        self, tool_parameters: dict[str, Any]
    ) -> Generator[ToolInvokeMessage, None, None]:
        """
        Main entry point for tool invocation. Processes a document file and returns its content
        in the requested format.

        The tool supports caching to avoid reprocessing the same document multiple times.

        Args:
            tool_parameters (dict[str, Any]): Parameters for the tool invocation, including:
                - files: List of file objects to process (only the first one is used)
                - result_type: Output format (md, html, or text)
                - as_file: Whether to return as file ("file") or text ("text")

        Yields:
            ToolInvokeMessage: Messages containing the processing result or error messages

        API Parameters:
            The tool internally uses the Upstage Document Parse API with these parameters:

            - document: The document file to be processed. Supported formats include PDF, DOCX,
              and various image formats.

            - ocr (string): Controls OCR behavior. Options:
              * "auto" (default): OCR is applied only to image documents. For non-image files
                (PDF, DOCX), layout and text detection only work if the document is digital-born.
              * "force": The file is always converted to images, and OCR is performed before
                layout detection.

            - coordinates (boolean): Whether to return coordinates of bounding boxes for each
              layout element. Default: true.

            - chart_recognition (boolean): Whether to use chart recognition. Default: true.

            - output_formats (string): Format for layout elements. Possible values are "text",
              "html", and "markdown". Default: ["html"].

            - model (string): Model used for inference. Default: "document-parse-250305".

            - base64_encoding (string): Which layout categories should be provided as base64
              encoded strings. This is useful for extracting images of specific elements
              (e.g., tables or figures) from the document. Default: [].
        """
        self.logger.info("Tool invocation started")
        self.logger.debug(f"Tool parameters: {tool_parameters}")

        files = tool_parameters.get("files", [])
        if not files:
            self.logger.warning("No files provided")
            yield self.create_text_message("No files provided.")
            return

        # Process only the first file
        file_obj = files[0]
        self.logger.info(f"File to process: {getattr(file_obj, 'filename', 'unknown')}")
        result_type = tool_parameters.get("result_type", "md")
        as_file = tool_parameters.get("as_file", "text")
        as_file = as_file == "file"
        self.logger.debug(f"Result type: {result_type}, File format: {as_file}")

        base_url = self.runtime.credentials.get("base_url", "https://cloud.dify.ai")
        api_key = self.runtime.credentials.get("upstage_api_key")
        if not api_key:
            self.logger.error("API key not provided")
            yield self.create_text_message("Missing upstage_api_key in credentials.")
            return

        # Initialize client
        if self.client is None:
            self.logger.info("Initializing Upstage client")
            self.client = UpstageDocumentParseClient(
                api_key=api_key,
                debug=self.debug,
                output_dir=self.output_dir,
                model=self.model,
            )

        try:
            # Download file: get file content and extension
            self.logger.info("Starting file download")
            file_content, ext = self._download_file(file_obj, base_url)
            self.logger.info(f"File info: {file_obj}")

            filename = file_obj.filename
            self.logger.info(f"File name: {filename}")

            # Calculate file hash (used as cache key)
            file_hash = hashlib.md5(file_content).hexdigest()

            # Create cache key - using file hash, result type, and output format
            cache_key = f"{file_hash}_{result_type}_{as_file}"

            # Save original file to cache (if needed)
            original_cache_path = os.path.join(self.cache_dir, f"{file_hash}{ext}")
            if not os.path.exists(original_cache_path):
                with open(original_cache_path, "wb") as f:
                    f.write(file_content)
                self.logger.debug(
                    f"Original file saved to cache: {original_cache_path}"
                )

            # Cache result file path
            result_cache_path = self._get_cache_filepath(file_hash, result_type)

            # Check cache
            if cache_key in self.conversion_cache and os.path.exists(result_cache_path):
                self.logger.info(f"Returning result from cache: {cache_key}")
                try:
                    with open(result_cache_path, "r", encoding="utf-8") as f:
                        cached_result = f.read()
                    yield from self._return_result(
                        cached_result, result_type, as_file, filename
                    )
                    return
                except Exception as e:
                    self.logger.warning(
                        f"Failed to read cache file, converting again: {e}"
                    )
                    # Continue processing if cache fails

            self.logger.info(f"Starting conversion to {result_type} format")
            if result_type == "md":
                results = self.client.convert_to_markdown(original_cache_path)
            elif result_type == "html":
                results = self.client.convert_to_html(original_cache_path)
            elif result_type == "text":
                results = self.client.convert_to_text(original_cache_path)
            else:
                error_msg = f"Unsupported result type: {result_type}"
                self.logger.error(error_msg)
                yield self.create_text_message(error_msg)
                return

            # Save conversion result to file-based cache
            try:
                with open(result_cache_path, "w", encoding="utf-8") as f:
                    f.write(results)
                # Update cache index
                self.conversion_cache[cache_key] = True
                self._save_cache_index()
                self.logger.info(f"Conversion result saved to cache: {cache_key}")
            except Exception as e:
                self.logger.error(f"Cache save failed: {e}")

            self.logger.info("Conversion complete, returning result")
            yield from self._return_result(
                results, result_type, as_file=as_file, original_filename=filename
            )
        except Exception as e:
            self.logger.exception(f"Error occurred during file processing: {e}")
            yield self.create_text_message(
                f"Error occurred during file processing: {str(e)}"
            )
