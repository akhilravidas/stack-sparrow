import logging

import openai
import sentry_sdk

from sparrow.libs import config, constants

WELCOME = """
[bold]Sparrow CLI
"""


def init_app():
    """
    Setup the app
    """
    logging.basicConfig(
        format="%(asctime)s %(levelname)8s %(filename)15s: %(message)s",
        level=logging.DEBUG,
    )

    sentry_sdk.init(
        dsn=constants.SENTRY_DSN,
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
    )
    cfg = config.AppConfig.instance()
    openai.api_key = cfg.openai_token
