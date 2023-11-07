"""
Main CLI entrypoint
"""
import os
import webbrowser
from pathlib import Path
from typing import Any, List, Optional, Tuple

import typer
from rich import print as rich_print
from rich.table import Table
from typing_extensions import Annotated

from sparrow import WELCOME, init_app
from sparrow.assistant import review, run
from sparrow.libs import config, html, scm


def _init_and_run():
    rich_print(WELCOME)
    cfg = config.AppConfig.instance()
    if cfg.openai_token is None:
        # Check environment
        if "OPENAI_API_KEY" in os.environ:
            rich_print("Using OpenAI API key from environment")
            token = os.environ["OPENAI_API_KEY"]
        else:
            token = typer.prompt(
                "Enter your OpenAI API token (https://platform.openai.com/api-keys)",
                hide_input=True,
            )
        if token is None or not token.startswith("sk-"):
            raise typer.Abort("Invalid OpenAI API token, aborting...")
        cfg.openai_token = token.strip()
        cfg.save()
    init_app()


app = typer.Typer(callback=_init_and_run)


def _tabulate_key_values(values: List[Tuple[str, Any]]) -> Table:
    table = Table(show_header=False, title_justify="left")
    table.add_column("Property")
    table.add_column("Value", justify="right")
    for key, value in values:
        value_str = "{:.3f}".format(value) if isinstance(value, float) else str(value)
        table.add_row(key, str(value_str))
    return table


@app.command("review")
def cmd_review(
    path_or_commit: Annotated[
        str,
        typer.Argument(
            help="Path to a file or commit reference (commit hashes, revs, tags, etc.))",
        ),
    ] = "HEAD",
    base_commit: Annotated[
        Optional[str], typer.Argument(help="Base commit to compare against")
    ] = None,
    repo_path: Annotated[
        Optional[str],
        typer.Option(help="Path to the git repository containing the commit"),
    ] = None,
    yes: Annotated[
        bool,
        typer.Option(
            help="Automatically approve the review without prompting for confirmation",
        ),
    ] = False,
):
    """
    Review specified file or commit.
    """
    commit = scm.maybe_commit_rev(path_or_commit, repo_path)
    path = None
    if commit is None:
        path = Path(path_or_commit)
        if not path.is_file():
            raise typer.BadParameter(f"Invalid commit: {path}")
        new_review = review.FileReview(str(path))
    else:
        repo = scm.get_repo(repo_path)
        if repo is None:
            raise typer.BadParameter(
                f"No git repository found with commit: {commit}, path: {repo_path or os.getcwd()}"
            )
        new_review = review.SCMReview(
            head_commit=path_or_commit,
            base_commit=base_commit,
            repo_path=str(repo.working_dir),
        )
    plan = run.plan_code_review(new_review)
    est_cost, review_tokens, out_tokens = run.cost(plan)
    rich_print("Code Review Plan:")
    rich_print(
        _tabulate_key_values(
            [
                ("Files", len(plan.files)),
                ("Input Tokens", review_tokens),
                ("Output Tokens (Estimate)", out_tokens),
                ("Cost (USD, Estimate)", est_cost),
            ]
        )
    )

    if yes or typer.confirm("Continue with review?"):
        review_comments = run.execute_code_review(plan)
        review_page = html.new_page(new_review, plan, review_comments)
        print("Saved review to: " + review_page)
        webbrowser.open(review_page)


if __name__ == "__main__":
    app()
