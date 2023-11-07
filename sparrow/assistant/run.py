"""
OpenAI assistant
"""
import json
import logging
import os
import time
from functools import lru_cache
from typing import List, Optional, Tuple

import pydantic
from openai import OpenAI
from openai.types.beta.threads import Run
from rich import print  # pylint: disable=redefined-builtin
from rich.progress import Progress, SpinnerColumn, TextColumn

from sparrow.assistant import actions
from sparrow.assistant.review import BaseReview, ReviewFile, ReviewPlan
from sparrow.libs import config, constants, llm, scm, strings

ASSISTANT_INSTRUCTIONS = """
You an an assistant that helps with DevOps tasks. You review code, help with adding documentation etc..
""".strip()

REVIEW_THREAD_INSTRUCTIONS = """
Each message in this thread represents changes made to a file in the patch set.
The first line is the file path. The subsequent lines contains the file contents annotated with line numbers.
Only the lines that start with an asterisk were updated.
IMPORTANT:
- Review code and flag substantive issues for updated code (lines marked with an asterisk).
- Only reject if you are sure that there is an underlying issue with the code.
- Do not flag formatting or style issues.
""".strip()


@lru_cache(maxsize=None)
def _client() -> OpenAI:
    return OpenAI(api_key=config.AppConfig.instance().openai_token)


@lru_cache(maxsize=None)
def _assistant_id() -> str:
    cfg = config.AppConfig.instance()
    if not cfg.assistant_id:
        client = _client()
        # TODO: Should this be a different assistant / repo?
        # (11/6): No - use threads / review request instead.
        assistant = client.beta.assistants.create(
            name="Stack Sparrow",
            model=config.AppConfig.instance().model_name,
            instructions=ASSISTANT_INSTRUCTIONS,
            tools=[actions.review_tool],
        )
        cfg.assistant_id = assistant.id
        cfg.save()
    return cfg.assistant_id


SINGLE_MESSAGE = """
File Path: {file_path}

File Contents (annotated):
```
{file_contents_with_line_numbers}
```
"""


MAX_WAIT_SECONDS = 120
SLEEP_DURATION_SECONDS = 5
MAX_RETRIES = int(MAX_WAIT_SECONDS / SLEEP_DURATION_SECONDS)  # approx


def wait_for_run_completion(client: OpenAI, run: Run) -> Optional[Run]:
    """
    Wait for a single review thread to complete.
    """
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task(description="Reviewing...", total=None)
        for _ in range(0, MAX_RETRIES):
            time.sleep(SLEEP_DURATION_SECONDS)
            run = client.beta.threads.runs.retrieve(
                thread_id=run.thread_id, run_id=run.id
            )
            if run.status not in ("queued", "in_progress"):
                return run
    print("Timed out waiting for review chunk to complete")


def execute_code_review(plan: ReviewPlan) -> List[actions.FileReviewResult]:
    """
    Run code review
    """
    client = _client()
    review_chunks = []
    current_chunk = []
    review_tokens = 0
    for step in plan.files:
        if step.status == "skipped":
            continue
        if review_tokens + step.input_tokens > constants.MAX_TOKENS_PER_REVIEW:
            review_chunks.append(current_chunk)
            current_chunk = []
            review_tokens = 0
        else:
            review_tokens += step.input_tokens
            current_chunk.append(step.message)

    if current_chunk:
        review_chunks.append(current_chunk)

    total_chunks = len(review_chunks)
    results = []
    for idx, chunk in enumerate(review_chunks):
        print(f"Starting review... [{idx + 1}/{total_chunks}]")
        run = client.beta.threads.create_and_run(
            assistant_id=_assistant_id(),
            thread={
                "messages": [
                    {
                        "role": "user",
                        "content": REVIEW_THREAD_INSTRUCTIONS,
                        "file_ids": [],
                    },
                    *[{"role": "user", "content": msg} for msg in chunk],
                ],
            },
        )
        chunk_result = wait_for_run_completion(client, run)
        if chunk_result:
            results.extend(_deserialize_review_response(chunk_result))
    return results


def _deserialize_review_response(response: Run) -> List[actions.FileReviewResult]:
    res = []
    if response.status in ("requires_action", "completed") and response.required_action:
        tool_calls = response.required_action.submit_tool_outputs.tool_calls
        for call in tool_calls:
            try:
                res.append(
                    actions.FileReviewResult.model_validate_json(
                        call.function.arguments
                    )
                )
            except (json.JSONDecodeError, pydantic.ValidationError):
                print("Failed to deserialize response")
                print(response)

    return res


def plan_code_review(revu: BaseReview) -> ReviewPlan:
    """Plan a review"""
    ret = ReviewPlan()
    for file_path, unified_diff, changed_hunks in revu.diff_by_file:
        # file_ctx = gather_context(revu, file_path)
        # Ideas:
        # 1. Include global context (ex: python version, dependencies etc..)
        # 2. Rerank and filter out less relevant snippets
        # ctx_for_upload = [file_ctx] if file_ctx else []
        # 3. Use 3.5-turbo to gather context based on the diff

        full_file_path = os.path.join(revu.root_dir, file_path)
        msg = ""
        num_input_tokens = 0
        approx_output_tokens = 0
        skipped_reason = None
        if scm.file_is_binary(full_file_path) or unified_diff is None:
            status = "skipped"
            skipped_reason = "binary or generated file"
        else:
            status = "needs_review"
            file_contents = revu.current_file_contents(file_path)
            annotated_file_contents = strings.annotated_file_contents(
                file_contents or "", changed_hunks
            )
            msg = SINGLE_MESSAGE.format(
                file_path=file_path,
                file_contents_with_line_numbers=annotated_file_contents,
            )
            # Approximate output tokens = the patch size
            approx_output_tokens = llm.num_tokens(str(unified_diff))
            num_input_tokens = llm.num_tokens(msg)
            if num_input_tokens > constants.MAX_TOKENS_PER_REVIEW:
                logging.warning(
                    "Skipping %s: File too large to review [num tokens=(%d)]",
                    file_path,
                    num_input_tokens,
                )
                num_input_tokens = 0
                approx_output_tokens = 0
                status = "skipped"
                skipped_reason = "file too large"

        ret.add_file(
            ReviewFile(
                file_path=file_path,
                status=status,
                message=msg,
                input_tokens=num_input_tokens,
                skipped_reason=skipped_reason,
            ),
            num_input_tokens,
            approx_output_tokens,
        )
    return ret


def cost(plan: ReviewPlan) -> Tuple[float, int, int]:
    """
    Calculate cost of running the review plan
    """
    input_tokens = sum(
        map(
            llm.num_tokens,
            [
                ASSISTANT_INSTRUCTIONS,
                REVIEW_THREAD_INSTRUCTIONS,
                json.dumps(actions.mark_file_reviewed),
            ],
        )
    )

    input_tokens += plan.input_tokens
    return (
        llm.cost(input_tokens, plan.estimated_output_tokens),
        input_tokens,
        plan.estimated_output_tokens,
    )
