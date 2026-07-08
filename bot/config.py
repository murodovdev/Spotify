import base64
import hashlib
import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    bot_token: str
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    spotify_redirect_uri: str = ""
    admin_id: int = 0
    encryption_key: str = ""
    db_path: str = ""
    port: int = 8080
    lastfm_api_key: str = ""

    # Og'ir media ishlari qayerda bajariladi: "local" (jarayon ichida yt-dlp +
    # ffmpeg) yoki "remote" (VPS media serveri — Phase 1, hali tayyor emas).
    media_backend: str = "local"
    media_server_url: str = ""
    media_server_secret: str = ""

    @property
    def database_path(self) -> str:
        """DB fayl yo'li. Aniq DB_PATH berilmasa: Railway'da volume (/data),
        lokalda data/ papkasi. Bu yo'l bilan Railway'da sozlash unutilsa ham
        ma'lumot ephemeral konteynerga tushib qolmaydi."""
        if self.db_path:
            return self.db_path
        if os.getenv("RAILWAY_ENVIRONMENT"):
            return "/data/bot.db"
        return "data/bot.db"

    @property
    def redirect_uri(self) -> str:
        if self.spotify_redirect_uri:
            return self.spotify_redirect_uri
        domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "")
        if domain:
            return f"https://{domain}/callback"
        return f"http://127.0.0.1:{self.port}/callback"

    @property
    def fernet_key(self) -> bytes:
        if self.encryption_key:
            return self.encryption_key.encode()
        digest = hashlib.sha256(self.bot_token.encode()).digest()
        return base64.urlsafe_b64encode(digest)


settings = Settings()
