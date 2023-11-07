"""
App Constants
"""
from collections import namedtuple
from typing import Dict

PACKAGE_NAME = "stack-sparrow"

ModelCost = namedtuple(
    "ModelCost", ["block_size", "input_cost_per_block", "output_cost_per_block"]
)

MODEL_COSTS: Dict[str, ModelCost] = {
    "gpt-4-1106-preview": ModelCost(
        block_size=1000, input_cost_per_block=0.01, output_cost_per_block=0.03
    ),
}

MAX_TOKENS_PER_REVIEW = 20 * 1000  # 20K for high signal
# pylint: disable=line-too-long
SENTRY_DSN = "https://d57c1dcbafc96c6c28e233af853ac991@o4506171527266304.ingest.sentry.io/4506171531132928"
