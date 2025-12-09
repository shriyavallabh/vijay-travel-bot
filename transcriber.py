"""
Voice Transcription Module using OpenAI Whisper
Handles WhatsApp voice messages and converts them to text
For Travel Business RAG System
"""
import os
import tempfile
import httpx
from typing import Optional, Tuple
from openai import OpenAI


class WhisperTranscriber:
    """
    Transcribes audio files using OpenAI Whisper API.
    Supports WhatsApp voice messages (OGG/Opus format).
    """

    def __init__(self, openai_api_key: str, model: str = "whisper-1"):
        self.client = OpenAI(api_key=openai_api_key)
        self.model = model

    def transcribe_file(self, file_path: str, language: str = "en") -> Tuple[str, Optional[str]]:
        """
        Transcribe an audio file to text.

        Args:
            file_path: Path to the audio file
            language: Language code (e.g., 'en', 'hi' for Hindi)

        Returns:
            Tuple of (transcribed_text, error_message)
        """
        try:
            with open(file_path, "rb") as audio_file:
                response = self.client.audio.transcriptions.create(
                    model=self.model,
                    file=audio_file,
                    language=language,
                    response_format="text"
                )
            return response, None
        except Exception as e:
            return "", f"Transcription error: {str(e)}"

    def transcribe_bytes(self, audio_bytes: bytes, filename: str = "audio.ogg", language: str = "en") -> Tuple[str, Optional[str]]:
        """
        Transcribe audio bytes to text.

        Args:
            audio_bytes: Raw audio data
            filename: Filename with extension (for format detection)
            language: Language code

        Returns:
            Tuple of (transcribed_text, error_message)
        """
        try:
            # Create a temporary file
            suffix = os.path.splitext(filename)[1] or ".ogg"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp_file:
                temp_file.write(audio_bytes)
                temp_path = temp_file.name

            try:
                result, error = self.transcribe_file(temp_path, language)
                return result, error
            finally:
                # Clean up temp file
                if os.path.exists(temp_path):
                    os.remove(temp_path)

        except Exception as e:
            return "", f"Error processing audio: {str(e)}"


class WhatsAppAudioDownloader:
    """
    Downloads audio files from WhatsApp Cloud API.
    """

    def __init__(self, access_token: str, app_secret: str):
        self.access_token = access_token
        self.app_secret = app_secret

    def _generate_appsecret_proof(self) -> str:
        """Generate appsecret_proof for API authentication"""
        import hmac
        import hashlib
        return hmac.new(
            self.app_secret.encode('utf-8'),
            self.access_token.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    async def get_media_url(self, media_id: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Get the download URL for a WhatsApp media file.

        Args:
            media_id: WhatsApp media ID

        Returns:
            Tuple of (media_url, error_message)
        """
        url = f"https://graph.facebook.com/v18.0/{media_id}"
        proof = self._generate_appsecret_proof()

        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{url}?appsecret_proof={proof}",
                    headers=headers
                )

                if response.status_code == 200:
                    data = response.json()
                    return data.get("url"), None
                else:
                    return None, f"Failed to get media URL: {response.status_code} - {response.text}"

        except Exception as e:
            return None, f"Error getting media URL: {str(e)}"

    async def download_media(self, media_url: str) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Download media file from WhatsApp.

        Args:
            media_url: URL from get_media_url()

        Returns:
            Tuple of (audio_bytes, error_message)
        """
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    media_url,
                    headers=headers,
                    follow_redirects=True
                )

                if response.status_code == 200:
                    return response.content, None
                else:
                    return None, f"Failed to download media: {response.status_code}"

        except Exception as e:
            return None, f"Error downloading media: {str(e)}"

    async def download_audio(self, media_id: str) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Complete flow: get URL and download audio.

        Args:
            media_id: WhatsApp media ID from webhook

        Returns:
            Tuple of (audio_bytes, error_message)
        """
        # Step 1: Get media URL
        media_url, error = await self.get_media_url(media_id)
        if error:
            return None, error

        # Step 2: Download media
        return await self.download_media(media_url)


class VoiceMessageHandler:
    """
    Complete handler for WhatsApp voice messages.
    Downloads, transcribes, and returns text.
    """

    def __init__(
        self,
        openai_api_key: str,
        whatsapp_access_token: str,
        whatsapp_app_secret: str,
        default_language: str = "en"
    ):
        self.transcriber = WhisperTranscriber(openai_api_key)
        self.downloader = WhatsAppAudioDownloader(whatsapp_access_token, whatsapp_app_secret)
        self.default_language = default_language

    async def process_voice_message(
        self,
        media_id: str,
        language: Optional[str] = None
    ) -> Tuple[str, Optional[str]]:
        """
        Process a WhatsApp voice message end-to-end.

        Args:
            media_id: WhatsApp media ID from webhook
            language: Override default language

        Returns:
            Tuple of (transcribed_text, error_message)
        """
        lang = language or self.default_language

        print(f"[Voice] Downloading audio (media_id: {media_id})...")

        # Download audio
        audio_bytes, error = await self.downloader.download_audio(media_id)
        if error:
            print(f"[Voice] Download error: {error}")
            return "", error

        print(f"[Voice] Downloaded {len(audio_bytes)} bytes, transcribing...")

        # Transcribe
        text, error = self.transcriber.transcribe_bytes(audio_bytes, "voice.ogg", lang)
        if error:
            print(f"[Voice] Transcription error: {error}")
            return "", error

        print(f"[Voice] Transcribed: '{text[:100]}...'")
        return text, None


def create_voice_handler(
    openai_api_key: str,
    whatsapp_access_token: str,
    whatsapp_app_secret: str
) -> VoiceMessageHandler:
    """Factory function to create a voice handler"""
    return VoiceMessageHandler(
        openai_api_key=openai_api_key,
        whatsapp_access_token=whatsapp_access_token,
        whatsapp_app_secret=whatsapp_app_secret,
        default_language="en"  # Change to "hi" for Hindi default
    )


if __name__ == "__main__":
    # Test transcription with a local file
    import sys
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")
    transcriber = WhisperTranscriber(api_key)

    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        print(f"Transcribing: {file_path}")
        text, error = transcriber.transcribe_file(file_path)
        if error:
            print(f"Error: {error}")
        else:
            print(f"Transcription: {text}")
    else:
        print("Usage: python transcriber.py <audio_file>")
