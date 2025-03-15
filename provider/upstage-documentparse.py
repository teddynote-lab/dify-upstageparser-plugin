from typing import Any

from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError
from tools.upstage_client import UpstageDocumentParseClient


class UpstageDocumentparseProvider(ToolProvider):
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        try:
            api_key = credentials.get("upstage_api_key", None)
            # API Checking is needed: Future work
            if api_key is not None:
                client = UpstageDocumentParseClient(
                    api_key=api_key,
                    debug=True,
                    output_dir="test_output",
                    model="document-parse-250305",
                )
            else:
                raise ToolProviderCredentialValidationError(
                    "Upstage API key is not found"
                )
        except Exception as e:
            raise ToolProviderCredentialValidationError(str(e))
