from dataclasses import dataclass
from google import genai
from google.genai import types
from context import CONTEXT

@dataclass
class ChatbotManager:
    api_key: str
    client: genai.Client = genai.Client(api_key=api_key)

    def scan_image(self, image_bytes, mime_type)->str:
        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type=mime_type
                ),
                CONTEXT
            ]
        )
        return response.text
        