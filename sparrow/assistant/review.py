"""
Review Types
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Iterator, List, Literal, Optional, Protocol, Tuple

import git
import unidiff

from sparrow.libs import config, scm


class BaseReview(Protocol):
    """
    Base Review Protocol
    """

    def current_file_contents(self, path: str) -> Optional[str]:
        """Read the current file contents which includes the changes made by this review"""
        ...

    def previous_file_contents(self, path: str) -> Optional[str]:
        """Read a file contents before the changes made by this review"""
        ...

    @property
    def diff_by_file(
        self,
    ) -> Iterator[Tuple[str, Optional[str], List[Tuple[int, int]]]]:
        """
        Returns a generator of (file_path, unified_diff, list of (hunk_start_line and hunk_end_line)) tuples
        """
        ...

    @property
    def root_dir(self) -> str:
        """Returns the root directory of the review"""
        ...


class FileReview(BaseReview):
    def __init__(self, path: str) -> None:
        self.path = path
        with open(path) as f:
            self.file_contents = f.read()

    def current_file_contents(self, path: str) -> Optional[str]:
        """Read a file at the head commit"""
        assert path == self.path
        return self.file_contents

    def previous_file_contents(self, path: str) -> Optional[str]:
        """Read a file contents before the changes made by this review"""
        return None

    @property
    def diff_by_file(
        self,
    ) -> Iterator[Tuple[str, Optional[str], List[Tuple[int, int]]]]:
        """
        Returns a generator of (file_path, unified_diff, list of (hunk_start_line and hunk_end_line)) tuples
        """
        yield self.path, self.file_contents, [(1, len(self.file_contents.splitlines()))]

    @property
    def root_dir(self) -> str:
        return ""


class SCMReview(BaseReview):
    """
    SCM based review
    """

    head_commit: str
    base_commit: Optional[str]
    repo: git.Repo
    patch_set: unidiff.PatchSet

    def __init__(
        self, head_commit: str, base_commit: Optional[str], repo_path: Optional[str]
    ) -> None:
        self.head_commit = head_commit
        self.base_commit = base_commit if base_commit else head_commit + "^"
        self.repo_root = repo_path or os.getcwd()
        repo = scm.get_repo(self.repo_root)
        if repo is None:
            raise ValueError(
                f"No git repository found with commit: {head_commit}, path: {self.repo_root}"
            )
        self.repo = repo
        self.patch_set = scm.patch_set(self.repo, self.head_commit, self.base_commit)

    def current_file_contents(self, path: str) -> Optional[str]:
        """Read a file at the head commit"""
        try:
            return (
                self.repo.commit(self.head_commit)
                .tree[path]
                .data_stream.read()
                .decode("utf-8")
            )
        except:  # pylint: disable=bare-except
            logging.exception("Error reading %s at commit: %s", path, self.head_commit)

    def previous_file_contents(self, path: str) -> Optional[str]:
        """Read a file contents before the changes made by this review"""
        try:
            return (
                self.repo.commit(self.base_commit)
                .tree[path]
                .data_stream.read()
                .decode("utf-8")
            )
        except:  # pylint: disable=bare-except
            # This could be the first commit
            pass

    @property
    def diff_by_file(
        self,
    ) -> Iterator[Tuple[str, Optional[str], List[Tuple[int, int]]]]:
        """
        Returns a generator of (file_path, unified_diff, list of (hunk_start_line and hunk_end_line)) tuples
        """
        for single_file_patch in self.patch_set:
            proceed, reason = can_review(single_file_patch)
            if not proceed:
                logging.info("Skipping %s: %s", single_file_patch.path, reason)
                yield single_file_patch.path, None, []
                continue
            unified_diff = "\n".join(str(patch) for patch in single_file_patch)
            hunk_lines = [
                (hunk.target_start, hunk.target_start + hunk.target_length)
                for hunk in single_file_patch
            ]
            yield single_file_patch.path, unified_diff, hunk_lines

    @property
    def root_dir(self) -> str:
        """Returns the root directory of the review"""
        return self.repo_root


@dataclass
class ReviewFile:
    """
    Wrapper for a single LLM call
    """

    file_path: str
    message: str
    status: Literal["needs_review", "skipped"]
    input_tokens: int
    skipped_reason: Optional[str] = None


@dataclass
class ReviewPlan:
    """
    Review broken down into individual review steps.

    Includes other metrics like estimated cost and input/output token counts computed during
    `plan` in case user confirmation is needed.
    """

    files: List[ReviewFile] = field(default_factory=list)
    estimated_cost: float = 0
    input_tokens: int = 0
    estimated_output_tokens: int = 0

    def add_file(self, file: ReviewFile, in_tokens: int, est_out_tokens: int) -> None:
        """
        Add a review step to the plan.
        """
        self.files.append(file)
        self.input_tokens += in_tokens
        self.estimated_output_tokens += est_out_tokens


def can_review(single_file: unidiff.PatchedFile) -> Tuple[bool, str]:
    """
    Returns True if the given file can be reviewed.
    """
    if single_file.is_binary_file:
        return False, "binary file"

    if single_file.is_removed_file:
        return False, "removed file"

    if config.is_excluded(single_file.path):
        return False, "excluded file extension"

    return True, ""
