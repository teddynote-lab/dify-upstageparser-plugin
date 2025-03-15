import os
import time
import json
import logging
import hashlib
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

import requests


@dataclass
class BatchResult:
    """Represents the result of a batch document processing job."""

    id: int
    status: str
    download_url: Optional[str] = None
    start_page: Optional[int] = None
    end_page: Optional[int] = None


class UpstageDocumentParseClient:
    """Client for interacting with the Upstage Document Parse API.

    This client handles the entire document parsing workflow:
    1. Submitting document processing requests
    2. Polling for status updates
    3. Downloading and merging results
    4. Exporting results in various formats (markdown, HTML, text)

    The client implements caching to avoid reprocessing the same documents.

    Supported file formats include PDF, DOCX, and various image formats.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.upstage.ai/v1/document-ai",
        ocr: str = "auto",
        coordinates: str = "false",
        output_formats: Optional[List[str]] = None,
        chart_recognition: str = "true",
        base64_encoding: Optional[List[str]] = None,
        model: str = "document-parse",
        output_dir: str = "upstage_export",
        debug: bool = False,
    ):
        """
        Initialize the Upstage Document Parse API client.

        Args:
            api_key (Optional[str]): API key for authentication. If not provided, will try to use UPSTAGE_API_KEY environment variable.
            base_url (str): Base URL for the API. Defaults to "https://api.upstage.ai/v1/document-ai".
            ocr (str): OCR mode - "auto" or "force". In "auto" mode, OCR is applied only to image documents.
                In "force" mode, all documents are converted to images before OCR. Defaults to "auto".
            coordinates (str): Whether to return coordinates of bounding boxes. Defaults to "false".
            output_formats (Optional[List[str]]): List of output formats to generate, such as ["html", "markdown", "text"]. Defaults to all formats.
            chart_recognition (str): Whether to use chart recognition. Defaults to "true".
            base64_encoding (Optional[List[str]]): List of layout categories to provide as base64 encoded strings (e.g., ["table"]). Defaults to ["table", "figure", "chart"].
            model (str): Model to use for inference. Defaults to "document-parse".
            output_dir (str): Directory to save output files. Defaults to "upstage_export".
            debug (bool): Whether to enable debug logging. Defaults to False.

        Raises:
            ValueError: If no API key is provided and UPSTAGE_API_KEY environment variable is not set.
        """
        self.api_key = api_key or os.environ.get("UPSTAGE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "No API key provided. Either pass it directly or set the UPSTAGE_API_KEY environment variable."
            )

        self.base_url = base_url.rstrip("/")
        self.ocr = ocr
        self.coordinates = coordinates
        self.output_formats = output_formats or ["html", "markdown", "text"]
        self.chart_recognition = chart_recognition
        self.base64_encoding = base64_encoding or ["table", "figure", "chart"]
        self.model = model
        self.debug = debug
        self.output_dir = output_dir
        self.request_id: Optional[str] = None
        self.batch_results: List[BatchResult] = []

        # Create reusable HTTP session
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})

        # Configure logging
        self.logger = logging.getLogger("upstage_client")
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        if not debug:
            self.logger.setLevel(logging.CRITICAL)
        else:
            self.logger.setLevel(logging.DEBUG)
            self.logger.debug("Debug mode activated.")

        # Instance variables for caching (TTL: 3600 seconds, i.e., 1 hour)
        self._cache: Dict[str, (Dict[str, str], float)] = {}
        self._cache_ttl: int = 3600

        # Cache to reduce API request calls for identical files (file content hash -> request_id)
        self._request_id_cache: Dict[str, str] = {}

    def _generate_cache_key(
        self, file_path: str, export_formats: Optional[List[str]]
    ) -> str:
        """
        Generate a cache key based on file content and export formats.

        Args:
            file_path (str): Path to the file
            export_formats (Optional[List[str]]): List of export formats

        Returns:
            str: A unique cache key combining file hash and export formats

        Raises:
            Exception: If file cannot be read
        """
        try:
            with open(file_path, "rb") as f:
                content = f.read()
        except Exception as e:
            self.logger.error(
                f"Error reading file while generating cache key ({file_path}): {e}"
            )
            raise

        # Calculate hash of file content
        file_hash = hashlib.sha256(content).hexdigest()

        # Convert export_formats to a JSON string (sorted for consistency)
        export_formats_str = (
            json.dumps(export_formats, sort_keys=True)
            if export_formats is not None
            else "None"
        )
        export_formats_hash = hashlib.sha256(
            export_formats_str.encode("utf-8")
        ).hexdigest()

        return f"{file_hash}_{export_formats_hash}"

    def _generate_request_cache_key(self, file_path: str) -> str:
        """
        Generate an API request cache key based only on file content.

        Args:
            file_path (str): Path to the file

        Returns:
            str: A hash of the file content

        Raises:
            Exception: If file cannot be read
        """
        try:
            with open(file_path, "rb") as f:
                content = f.read()
        except Exception as e:
            self.logger.error(
                f"Error reading file while generating request cache key ({file_path}): {e}"
            )
            raise
        return hashlib.sha256(content).hexdigest()

    def request(
        self,
        file_path: str,
        wait: bool = False,
        poll_interval: int = 1,
        max_wait: int = 300,
    ) -> str:
        """
        Submit a document parsing request to the Upstage API.

        Args:
            file_path (str): Path to the document file to process
            wait (bool): Whether to wait for processing to complete. Defaults to False.
            poll_interval (int): Number of seconds between status checks when waiting. Defaults to 1.
            max_wait (int): Maximum number of seconds to wait for completion. Defaults to 300.

        Returns:
            str: The request ID assigned by the API

        Raises:
            FileNotFoundError: If the specified file does not exist
            requests.RequestException: If the API request fails
            ValueError: If the API response is invalid
        """
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Check cache for previously processed identical file
        req_cache_key = self._generate_request_cache_key(file_path)
        if req_cache_key in self._request_id_cache:
            self.logger.info(
                "Found previous request for identical file. Using cached request_id."
            )
            self.request_id = self._request_id_cache[req_cache_key]
            if wait:
                self.check_status(
                    wait=True, poll_interval=poll_interval, max_wait=max_wait
                )
            return self.request_id

        url = f"{self.base_url}/async/document-parse"
        self.logger.debug(f"API request URL: {url}")

        with open(file_path, "rb") as f:
            files = {"document": (file_path_obj.name, f)}
            data = {
                "ocr": self.ocr,
                "coordinates": self.coordinates,
                "output_formats": str(self.output_formats),
                "chart_recognition": self.chart_recognition,
                "base64_encoding": str(self.base64_encoding),
                "model": self.model,
            }
            self.logger.info(
                f"Starting document parsing request for file '{file_path}'."
            )
            self.logger.debug(f"Request data: {data}")

            try:
                response = self.session.post(url, files=files, data=data)
                self.logger.debug(f"Response status code: {response.status_code}")

                if self.debug:
                    try:
                        self.logger.debug(f"Response content: {response.json()}")
                    except Exception as e:
                        self.logger.debug(f"JSON parsing failed: {e}")
                        self.logger.debug(f"Response text: {response.text[:1000]}")

                if response.status_code not in (200, 202):
                    self.logger.error(
                        f"API request failed: {response.status_code} - {response.text}"
                    )
                    response.raise_for_status()

                response_data = response.json()
                if "request_id" not in response_data:
                    raise ValueError(
                        f"API response missing request_id: {response_data}"
                    )

                self.request_id = response_data["request_id"]
                self.logger.info(
                    f"Document parsing request successfully submitted. Request ID: {self.request_id}"
                )

                # Cache the request_id for this file
                self._request_id_cache[req_cache_key] = self.request_id

                if wait:
                    self.logger.info("Waiting for document processing to complete...")
                    self.check_status(
                        wait=True, poll_interval=poll_interval, max_wait=max_wait
                    )

                return self.request_id

            except requests.RequestException as e:
                self.logger.error(f"Error during API request: {e}")
                raise

    def check_status(
        self,
        request_id: Optional[str] = None,
        wait: bool = False,
        poll_interval: int = 1,
        max_wait: int = 300,
    ) -> List[BatchResult]:
        """
        Check the status of a document parsing request.

        Args:
            request_id (Optional[str]): The request ID to check. If None, uses the last request_id.
            wait (bool): Whether to wait for processing to complete. Defaults to False.
            poll_interval (int): Number of seconds between status checks when waiting. Defaults to 1.
            max_wait (int): Maximum number of seconds to wait for completion. Defaults to 300.

        Returns:
            List[BatchResult]: A list of batch processing results

        Raises:
            ValueError: If no request ID is available
            requests.RequestException: If the API request fails
            TimeoutError: If waiting times out
        """
        request_id = request_id or self.request_id
        if not request_id:
            raise ValueError(
                "No request ID available. Call request() first or provide a request ID."
            )

        url = f"{self.base_url}/requests/{request_id}"
        self.logger.debug(f"Status check URL: {url}")

        start_time = time.time()
        try:
            response = self.session.get(url)
            self.logger.debug(f"Status check response code: {response.status_code}")

            if self.debug:
                try:
                    self.logger.debug(f"Status check response: {response.json()}")
                except Exception as e:
                    self.logger.debug(f"JSON parsing failed: {e}")
                    self.logger.debug(f"Response text: {response.text[:1000]}")

            if response.status_code != 200:
                self.logger.error(
                    f"Status check failed: {response.status_code} - {response.text}"
                )
                response.raise_for_status()

            response_data = response.json()

            while wait and response_data.get("status") == "submitted":
                elapsed = time.time() - start_time
                if elapsed > max_wait:
                    raise TimeoutError(
                        "Request is still in 'submitted' state. Maximum wait time exceeded."
                    )
                self.logger.info(
                    "Request submitted but processing has not started yet. Waiting..."
                )
                time.sleep(poll_interval)
                response = self.session.get(url)
                response.raise_for_status()
                response_data = response.json()
                self.logger.debug(
                    f"Current request status: {response_data.get('status')}"
                )

            if "batches" not in response_data:
                raise ValueError(
                    f"API response missing batch information: {response_data}"
                )

            self.batch_results = []
            for batch in response_data["batches"]:
                result = BatchResult(
                    id=batch["id"],
                    status=batch["status"],
                    start_page=batch.get("start_page"),
                    end_page=batch.get("end_page"),
                    download_url=batch.get("download_url"),
                )
                if result.status == "completed":
                    self.logger.info(
                        f"Batch {result.id} completed: Pages {result.start_page}-{result.end_page}"
                    )
                    self.logger.debug(f"Download URL: {result.download_url}")
                self.batch_results.append(result)

            while wait and not all(
                result.status == "completed" for result in self.batch_results
            ):
                elapsed = time.time() - start_time
                if elapsed > max_wait:
                    raise TimeoutError(
                        "Not all batches have completed processing. Maximum wait time exceeded."
                    )
                incomplete_count = sum(
                    1 for result in self.batch_results if result.status != "completed"
                )
                self.logger.info(
                    f"{incomplete_count} batches still processing. Checking again in {poll_interval} seconds..."
                )
                time.sleep(poll_interval)
                response = self.session.get(url)
                response.raise_for_status()
                updated_batches = response.json().get("batches", [])
                for updated_batch in updated_batches:
                    for result in self.batch_results:
                        if result.id == updated_batch["id"]:
                            previous_status = result.status
                            result.status = updated_batch["status"]
                            if previous_status != result.status:
                                self.logger.debug(
                                    f"Batch {result.id} status changed: {previous_status} -> {result.status}"
                                )
                            if (
                                result.status == "completed"
                                and "download_url" in updated_batch
                            ):
                                result.download_url = updated_batch["download_url"]
                                self.logger.info(
                                    f"Batch {result.id} completed: Pages {updated_batch.get('start_page')}-{updated_batch.get('end_page')}"
                                )
                                self.logger.debug(
                                    f"Download URL: {result.download_url}"
                                )
            self.logger.info("All batches have completed processing.")

            # Filter batches to remove duplicates
            # If multiple batches have the same (start_page, end_page),
            # keep only the one with the highest batch ID
            unique_batches = {}
            for batch in self.batch_results:
                key = (batch.start_page, batch.end_page)
                if key in unique_batches:
                    if batch.id > unique_batches[key].id:
                        unique_batches[key] = batch
                else:
                    unique_batches[key] = batch

            self.batch_results = sorted(unique_batches.values(), key=lambda x: x.id)
            return self.batch_results

        except requests.RequestException as e:
            self.logger.error(f"Error during status check: {e}")
            raise

    def download(
        self,
        request_id: Optional[str] = None,
        batch_results: Optional[List[BatchResult]] = None,
        temp_dir: str = "temp",
    ) -> List[Dict[str, Any]]:
        """
        Download the results of a document parsing request.

        Args:
            request_id (Optional[str]): The request ID to download results for. If None, uses the last request_id.
            batch_results (Optional[List[BatchResult]]): Batch results to download. If None, uses the last batch_results.
            temp_dir (str): Directory for temporary files. Defaults to "temp".

        Returns:
            List[Dict[str, Any]]: A list of downloaded batch data

        Raises:
            ValueError: If no request ID is available
            requests.RequestException: If the download fails
            json.JSONDecodeError: If the downloaded data is not valid JSON
        """
        request_id = request_id or self.request_id
        if not request_id:
            raise ValueError(
                "No request ID available. Call request() first or provide a request ID."
            )

        batch_results = batch_results or self.batch_results
        if not batch_results:
            self.logger.info("No batch results available. Checking status.")
            batch_results = self.check_status(request_id)

        incomplete_batches = [
            result
            for result in batch_results
            if result.status != "completed" or not result.download_url
        ]
        if incomplete_batches:
            self.logger.warning(
                f"{len(incomplete_batches)} batches are not completed or missing download URL."
            )
            for batch in incomplete_batches:
                self.logger.debug(
                    f"Incomplete batch ID: {batch.id}, Status: {batch.status}, URL: {batch.download_url}"
                )

        temp_path = Path(temp_dir)
        temp_path.mkdir(parents=True, exist_ok=True)
        self.logger.debug(f"Created temporary directory: {temp_path.absolute()}")

        downloaded_data = []
        temp_files = []

        for result in batch_results:
            if result.status == "completed" and result.download_url:
                try:
                    self.logger.info(f"Downloading batch {result.id}...")
                    self.logger.debug(f"Download URL: {result.download_url}")
                    download_response = self.session.get(result.download_url)
                    download_response.raise_for_status()
                    content_type = download_response.headers.get("Content-Type", "")
                    self.logger.debug(f"Content type: {content_type}")

                    if "application/json" in content_type:
                        parsed_data = download_response.json()
                    else:
                        parsed_data = json.loads(download_response.text)

                    if self.debug:
                        temp_filename = (
                            temp_path / f"batch_{result.id}_{request_id}.json"
                        )
                        with open(temp_filename, "w", encoding="utf-8") as f:
                            f.write(
                                json.dumps(parsed_data, ensure_ascii=False, indent=2)
                            )
                        temp_files.append(temp_filename)
                        self.logger.debug(
                            f"Debug mode: Saved temporary file: {temp_filename}"
                        )

                    downloaded_data.append(parsed_data)
                    self.logger.info(f"Successfully downloaded batch {result.id}")
                except requests.RequestException as e:
                    self.logger.error(f"Failed to download batch {result.id}: {e}")
                    raise
                except json.JSONDecodeError as e:
                    self.logger.error(f"JSON parsing failed: {e}")
                    raise
                except Exception as e:
                    self.logger.error(
                        f"Error processing batch {result.id}: {type(e).__name__}: {e}"
                    )
                    raise

        if not self.debug:
            for temp_file in temp_files:
                try:
                    os.remove(temp_file)
                    self.logger.debug(f"Deleted temporary file: {temp_file}")
                except Exception as e:
                    self.logger.warning(
                        f"Failed to delete temporary file: {temp_file} - {e}"
                    )
        else:
            self.logger.debug(
                f"Debug mode: Preserving temporary files: {', '.join(str(f) for f in temp_files)}"
            )

        return downloaded_data

    def merge_results(
        self, downloaded_data: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Dict[str, str]]:
        """
        Merge downloaded batch results into a single result.

        Args:
            downloaded_data (Optional[List[Dict[str, Any]]]): List of downloaded batch data.
                If None, automatically downloads the data.

        Returns:
            Dict[str, Dict[str, str]]: Merged results by format type (e.g., 'html', 'markdown', 'text')
        """
        if not downloaded_data:
            self.logger.info("No downloaded data provided. Downloading automatically.")
            downloaded_data = self.download()

        if not downloaded_data:
            self.logger.warning("No data to merge.")
            return {}

        self.logger.debug(f"Merging {len(downloaded_data)} data items")
        result_formats = set()
        for data in downloaded_data:
            if "content" in data:
                result_formats.update(data["content"].keys())

        self.logger.debug(f"Available formats: {result_formats}")
        merged_results = {fmt: [] for fmt in result_formats}

        for i, data in enumerate(downloaded_data):
            self.logger.debug(f"Processing data {i+1}/{len(downloaded_data)}")
            if "content" in data:
                for fmt in result_formats:
                    if fmt in data["content"]:
                        self.logger.debug(
                            f"{fmt} content size: {len(data['content'][fmt])} characters"
                        )
                        merged_results[fmt].append(data["content"][fmt])
            else:
                self.logger.warning(f"Data missing 'content' key: {list(data.keys())}")

        result = {}
        for fmt, contents in merged_results.items():
            if contents:
                merged_content = "\n\n".join(contents)
                result[fmt] = {"content": merged_content}
                self.logger.debug(
                    f"{fmt} merged result size: {len(merged_content)} characters"
                )
            else:
                self.logger.warning(f"No content for format {fmt}.")
        return result

    def export(
        self,
        filename: Optional[str] = None,
        merged_results: Optional[Dict[str, Dict[str, str]]] = None,
        formats: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """
        Export merged results to files.

        Args:
            filename (Optional[str]): Base filename for output files.
                If None, uses the request ID or a timestamp.
            merged_results (Optional[Dict[str, Dict[str, str]]]): Merged results to export.
                If None, automatically merges the results.
            formats (Optional[List[str]]): List of formats to export.
                If None, exports all available formats.

        Returns:
            Dict[str, str]: Dictionary mapping format names to exported file paths
        """
        output_path = Path(self.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        self.logger.debug(f"Created output directory: {output_path.absolute()}")

        if not filename:
            filename = self.request_id or f"parsed_document_{int(time.time())}"
        filename = Path(filename).stem
        self.logger.debug(f"Output filename: {filename}")

        if not merged_results:
            self.logger.info("No merged results provided. Merging automatically.")
            merged_results = self.merge_results()

        if not merged_results:
            self.logger.warning("No merged results to export.")
            return {}

        available_formats = set(merged_results.keys())
        self.logger.debug(f"Available formats: {available_formats}")

        export_formats = (
            set(formats) & available_formats if formats else available_formats
        )
        if not export_formats:
            self.logger.warning(
                f"Requested formats do not match available formats. Available formats: {available_formats}"
            )
            return {}

        self.logger.debug(f"Formats to export: {export_formats}")
        exported_files = {}

        for fmt in export_formats:
            ext = (
                "md"
                if fmt == "markdown"
                else "html" if fmt == "html" else "txt" if fmt == "text" else fmt
            )
            output_file = output_path / f"{filename}.{ext}"
            try:
                with open(output_file, "w", encoding="utf-8") as f:
                    content = merged_results[fmt]["content"]
                    f.write(content)
                    self.logger.debug(f"{fmt} content size: {len(content)} characters")
                self.logger.info(f"{fmt.capitalize()} file created: {output_file}")
                exported_files[fmt] = str(output_file)
            except Exception as e:
                self.logger.error(f"Error creating {fmt} file: {e}")
        return exported_files

    def process_document(
        self,
        file_path: str,
        wait: bool = True,
        poll_interval: int = 1,
        export_formats: Optional[List[str]] = None,
        max_wait: int = 300,
    ) -> Dict[str, str]:
        """
        Process a document through the entire pipeline (request → status check → download → merge → export).

        Uses caching to return cached results for identical inputs and options.
        If any exported file has been deleted, invalidates the cache and regenerates.

        Args:
            file_path (str): Path to the document file to process
            wait (bool): Whether to wait for processing to complete. Defaults to True.
            poll_interval (int): Number of seconds between status checks when waiting. Defaults to 1.
            export_formats (Optional[List[str]]): List of formats to export.
                If None, exports all available formats.
            max_wait (int): Maximum number of seconds to wait for completion. Defaults to 300.

        Returns:
            Dict[str, str]: Dictionary mapping format names to exported file paths
        """
        print(f"process_document: {file_path}")
        cache_key = self._generate_cache_key(file_path, export_formats)
        self.logger.info(f"cache_key: {cache_key}")
        self.logger.info(f"self._cache: {self._cache}")

        if cache_key in self._cache:
            cached_result, timestamp = self._cache[cache_key]
            files_exist = all(os.path.exists(path) for path in cached_result.values())
            if not files_exist:
                self.logger.info(
                    "Some cached files have been deleted. Invalidating cache."
                )
                del self._cache[cache_key]
            elif time.time() - timestamp < self._cache_ttl:
                self.logger.info("Returning cached results.")
                return cached_result
            else:
                self.logger.info(f"Cache expired: {cache_key}")
                del self._cache[cache_key]

        try:
            self.request(
                file_path, wait=wait, poll_interval=poll_interval, max_wait=max_wait
            )
            if not wait:
                self.check_status(
                    wait=True, poll_interval=poll_interval, max_wait=max_wait
                )
            downloaded_data = self.download()
            merged_results = self.merge_results(downloaded_data)
            filename = Path(file_path).name
            exported_files = self.export(
                filename=filename,
                merged_results=merged_results,
                formats=export_formats,
            )
        except Exception as e:
            self.logger.error(f"Error processing document: {e}")
            raise

        # Cache the results
        self._cache[cache_key] = (exported_files, time.time())
        return exported_files

    def convert_to_markdown(self, file_path: str) -> str:
        """
        Convert a document to markdown format.

        Calls process_document() and returns the content of the markdown file if successful.

        Args:
            file_path (str): Path to the document file to process

        Returns:
            str: Markdown content, or None if conversion fails
        """
        try:
            logging.info(f"convert_to_markdown: {file_path}")
            exported_files = self.process_document(
                file_path, export_formats=["markdown"], poll_interval=1
            )
            if "markdown" in exported_files:
                md_file = exported_files["markdown"]
                with open(md_file, "r", encoding="utf-8") as f:
                    content = f.read()
                return content
            else:
                self.logger.warning("No 'markdown' key in document processing results.")
                return None
        except Exception as e:
            self.logger.error(f"Error in convert_to_markdown: {e}")
            return None

    def convert_to_html(self, file_path: str) -> str:
        """
        Convert a document to HTML format.

        Calls process_document() and returns the content of the HTML file if successful.

        Args:
            file_path (str): Path to the document file to process

        Returns:
            str: HTML content, or None if conversion fails
        """
        try:
            exported_files = self.process_document(file_path, export_formats=["html"])
            if "html" in exported_files:
                html_file = exported_files["html"]
                with open(html_file, "r", encoding="utf-8") as f:
                    content = f.read()
                return content
            else:
                self.logger.warning("No 'html' key in document processing results.")
                return None
        except Exception as e:
            self.logger.error(f"Error in convert_to_html: {e}")
            return None

    def convert_to_text(self, file_path: str) -> str:
        """
        Convert a document to plain text format.

        Calls process_document() and returns the content of the text file if successful.

        Args:
            file_path (str): Path to the document file to process

        Returns:
            str: Plain text content, or None if conversion fails
        """
        try:
            exported_files = self.process_document(file_path, export_formats=["text"])
            if "text" in exported_files:
                text_file = exported_files["text"]
                with open(text_file, "r", encoding="utf-8") as f:
                    content = f.read()
                return content
            else:
                self.logger.warning("No 'text' key in document processing results.")
                return None
        except Exception as e:
            self.logger.error(f"Error in convert_to_text: {e}")
            return None
