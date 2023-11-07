"""
HTML generation helpers
"""
import difflib
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Literal, Optional
from urllib.parse import quote as urlquote

from jinja2 import Environment, FileSystemLoader

from sparrow.assistant import actions
from sparrow.assistant.review import BaseReview, ReviewPlan

COLUMN_WIDTH = 80


def diff_table(
    file_path: str, new_content: Optional[str], old_content: Optional[str]
) -> str:
    """Get HTML for a diff fragment"""
    old_file_path = file_path if old_content is not None else "New File"
    new_file_path = file_path if new_content is not None else "Deleted File"

    old_content = old_content or ""
    new_content = new_content or ""

    return difflib.HtmlDiff(wrapcolumn=COLUMN_WIDTH).make_table(
        old_content.splitlines(), new_content.splitlines(), old_file_path, new_file_path
    )


@dataclass
class _ReviewFragment:
    file_path: str
    diff_html: str
    status: Literal["accepted", "rejected", "skipped"]
    comments: List[actions.FileReviewResult]


def _render_review_page(fragments: List[_ReviewFragment]) -> str:
    # Load templates from the templates directory
    env = Environment(loader=FileSystemLoader("sparrow/templates"))
    template = env.get_template("code-review.html")
    return template.render(fragments=fragments)


def new_page(
    review: BaseReview, plan: ReviewPlan, comments: List[actions.FileReviewResult]
) -> str:
    """
    Generate and save a new review page.
    """

    all_comments = defaultdict(list)
    for comment in comments:
        all_comments[comment.file_path].append(comment)

    reviewed_fragments = []
    skipped_fragments = []
    for file in plan.files:
        if file.file_path in all_comments:
            comments = all_comments[file.file_path]
            reviewed_fragments.append(
                _ReviewFragment(
                    file_path=file.file_path,
                    diff_html=diff_table(
                        file.file_path,
                        review.current_file_contents(file.file_path),
                        review.previous_file_contents(file.file_path),
                    ),
                    status="accepted"
                    if all(c.accepted for c in comments)
                    else "rejected",
                    comments=comments,
                )
            )
        else:
            skipped_fragments.append(
                _ReviewFragment(
                    file_path=file.file_path,
                    diff_html=diff_table(
                        file.file_path,
                        "<skipped>",
                        "<skipped>",
                    ),
                    status="skipped",
                    comments=[],
                )
            )

    page_html = _render_review_page(reviewed_fragments + skipped_fragments)
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as temp_file:
        temp_file.write(page_html.encode("utf-8"))
        return "file://" + urlquote(temp_file.name)
