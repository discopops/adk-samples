import os
from functools import cached_property
from google.adk.models import Gemini
from google.genai import Client, types

class GeminiPreview(Gemini):
    @cached_property
    def api_client(self) -> Client:
        project = os.getenv("GOOGLE_CLOUD_PROJECT")
        location = "global"
        return Client(
            project=project,
            location=location,
            http_options=types.HttpOptions(
                headers=self._tracking_headers(),
                retry_options=self.retry_options,
            )
        )
