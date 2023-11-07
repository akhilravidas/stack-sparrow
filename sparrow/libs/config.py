"""
App and Run Configuration parameters
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

from sparrow.libs import constants

EXCLUDED_EXTENSIONS = (".lock", ".yaml", ".toml", ".json", ".md", ".txt")


def is_excluded(path: str):
    """
    Returns True if the given path is excluded from review.
    """
    return Path(path).suffix in EXCLUDED_EXTENSIONS


def app_data_root() -> Path:
    """Directory storing application data"""
    sys_data_root = Path.home() / ".cache"
    return Path(os.getenv("XDG_CACHE_HOME", sys_data_root)) / constants.PACKAGE_NAME


def config_path() -> Path:
    """Path to configuration file (within app data root)"""
    return app_data_root() / "config.yaml"


@dataclass
class AppConfig:
    """
    App Configuration parameters
    """

    openai_token: Optional[str] = None
    assistant_id: Optional[str] = None
    model_id: str = "openai/gpt-4-1106-preview"
    llm_seed: int = 42
    llm_temperature: float = 0
    llm_request_timeout_seconds: float = 10
    max_retries: int = 3
    config_file_version: int = 1

    @classmethod
    def instance(cls) -> AppConfig:
        """Returns the singleton instance of AppConfig"""
        if hasattr(cls, "_config"):
            return cls._config

        cfg_path = config_path()

        if not cfg_path.exists():
            cls._config = cls()
            return cls._config
        else:
            logging.debug("Loading sparrow cli config from %s", cfg_path)
            with cfg_path.open() as f:
                data = yaml.safe_load(f)
                cls._config = cls(**data) if data else cls()
                return cls._config

    def save(self):
        """Save config to config_path"""
        if not os.path.exists(app_data_root()):
            os.makedirs(app_data_root())
        with config_path().open("w") as f:
            yaml.safe_dump(self.__dict__, f)

    @property
    def model_name(self) -> str:
        """Returns the model name"""
        return self.model_id.rsplit("/", maxsplit=1)[-1]


def get() -> AppConfig:
    """
    Returns the singleton instance of AppConfig
    """
    return AppConfig.instance()
