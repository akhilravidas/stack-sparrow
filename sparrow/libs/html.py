"""
HTML generation helpers
"""
import difflib
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Literal, Optional
from urllib.parse import quote as urlquote

from jinja2 import Template

from sparrow.assistant import actions
from sparrow.assistant.review import BaseReview, ReviewPlan

COLUMN_WIDTH = 80

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Code Review Results</title>
    <style type="text/css">
        table.diff {
            width: 100%;
            font-family: Courier;
            border: medium;
        }

        td[id^="from"]+td,
        td[id^="to"]+td {
            width: 50%;
            white-space: nowrap;
        }

        .diff_header {
            background-color: #e0e0e0
        }

        td.diff_header {
            text-align: right
        }

        .diff_next {
            background-color: #c0c0c0
        }

        .diff_add {
            background-color: #aaffaa
        }

        .diff_chg {
            background-color: #ffff77
        }

        .diff_sub {
            background-color: #ffaaaa
        }
    </style>
</head>

<body>

    <h1>Code Review Results</h1>

    {% for fragment in fragments %}
    <div class="review-section">
        <h2>
            {{ fragment.file_path }}
            [
            {% if fragment.status == "accepted" %}
            ✅️ lgtm
            {% elif fragment.status == "rejected" %}
            🤔 Review Suggestions
            {% else %}
            ⏩ Skipped
            {% endif %}
            ]
        </h2>
        <div class="diff-content">
            {{ fragment.diff_html | safe }}
        </div>
        {% if fragment.comments %}
        <h3>Review Comments:</h3>
        <ul class="suggestions-list">
            {% for comment in fragment.comments %}
            <li>
                <strong>Status:</strong> {{ comment.accepted and "Accepted" or "Rejected" }}<br>
                {% for review_comment in comment.review_comments %}
                <strong>Explanation:</strong> {{ review_comment.explanation }} <br>
                <strong>Start Line:</strong> {{ review_comment.start_line }} <br>
                {% if review_comment.old_code_block or review_comment.new_code_block %}
                <pre><code>Old Code Block: {{ review_comment.old_code_block }}</code></pre>
                <pre><code>New Code Block: {{ review_comment.new_code_block }}</code></pre>
                {% endif %}
                {% endfor %}
            </li>
            {% endfor %}
        </ul>
        {% elif fragment.status == "skipped" %}
        <p>No review comments because this file was skipped.</p>
        {% endif %}
    </div>
    {% endfor %}

</body>

</html>
"""


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
    # TODO: Fix issue with load templates from the templates directory
    template = Template(HTML_TEMPLATE)
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
