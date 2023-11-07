"""
LLM utility functions.
"""

import tiktoken

from sparrow.libs import config, constants


def num_tokens(prompt: str) -> int:
    """
    Calculate the number of tokens based on the currently configured model.
    """
    cfg = config.AppConfig.instance()
    enc = tiktoken.encoding_for_model(cfg.model_name)
    return len(enc.encode(prompt))


def cost(input_tokens: int, estimated_output_tokens: int) -> float:
    """
    Calculate the cost of the prompt based on the currently configured model.
    """
    cfg = config.AppConfig.instance()
    model = cfg.model_name
    if model not in constants.MODEL_COSTS:
        raise ValueError(f"Unknown model {model}")

    pricing = constants.MODEL_COSTS[model]
    return (
        pricing.input_cost_per_block * float(input_tokens)
        + pricing.output_cost_per_block * float(estimated_output_tokens)
    ) / pricing.block_size
