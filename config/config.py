from dataclasses import dataclass

from environs import Env


@dataclass
class TgBot:
    token: str


@dataclass
class LogSettings:
    level: str
    format: str


@dataclass
class WebSettings:
    python_base: str


@dataclass
class DbSettings:
    dsn: str


@dataclass
class Config:
    bot: TgBot
    log: LogSettings
    web: WebSettings
    db: DbSettings


def load_config(path: str | None = None) -> Config:
    env = Env()
    env.read_env(path)

    return Config(
        bot=TgBot(token=env("BOT_TOKEN")),
        log=LogSettings(
            level=env("LOG_LEVEL", "INFO"),
            format=env(
                "LOG_FORMAT",
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            ),
        ),
        web=WebSettings(
            python_base=env("PYTHON_BASE", "http://127.0.0.1:8001"),
        ),
        db=DbSettings(
            dsn=env("DATABASE_URL", ""),
        ),
    )
