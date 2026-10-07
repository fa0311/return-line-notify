from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environ(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    works_id: str = Field(alias="WORKS_ID")
    password: str = Field(alias="PASSWORD")

    log_path: Path = Field(default=Path(".log/debug.log"), alias="LOG_PATH")

    # LINE WORKS への HTTP リクエストの (接続, 読み取り) タイムアウト秒
    http_connect_timeout: float = Field(
        default=10, alias="HTTP_CONNECT_TIMEOUT_SEC", gt=0
    )
    http_read_timeout: float = Field(default=30, alias="HTTP_READ_TIMEOUT_SEC", gt=0)

    # MQTT でこの秒数なにも受信できなければ切断して繋ぎ直す。
    # LINE WORKS は通知以外なにも送ってこない (keepalive にも応答しない) ので
    # 既定は 0 (無効)
    mqtt_idle_timeout: float = Field(default=0, alias="MQTT_IDLE_TIMEOUT_SEC", ge=0)

    # この秒数ごとにセッションを張り直す (cookie が有効なら再ログインなし)。
    # サーバからの死活応答がないため、静かに死んだ接続の保険として短めにする
    relogin_interval: float = Field(default=21600, alias="RELOGIN_INTERVAL_SEC", gt=0)

    # 再接続の指数バックオフの上限秒
    reconnect_backoff_max: float = Field(
        default=300, alias="RECONNECT_BACKOFF_MAX_SEC", gt=0
    )

    # この秒数つづけて MQTT 未接続 (またはイベントループ停止) なら
    # プロセスを終了して Docker に再起動させる。0 で無効
    unhealthy_exit: float = Field(default=600, alias="UNHEALTHY_EXIT_SEC", ge=0)

    def __init__(self, **values: Any) -> None:
        super().__init__(**values)

    @property
    def http_timeout(self) -> tuple[float, float]:
        return (self.http_connect_timeout, self.http_read_timeout)
