"""
Source control management utilities (assumes git).
"""
import os
from typing import Optional

import git
import unidiff


def get_repo(repo_path: Optional[str] = None) -> Optional[git.Repo]:
    """
    Returns the git.Repo object for the current working directory, or None if the current
    """
    # TODO: Cache
    try:
        return git.Repo(repo_path or os.getcwd(), search_parent_directories=True)
    except (git.InvalidGitRepositoryError, git.NoSuchPathError):
        return None


def maybe_commit_rev(
    commit_hash: str, repo_path: Optional[str]
) -> Optional[git.Commit]:
    """
    Returns True if the given string is a valid Git commit revision (commit hash, tag, branch).
    """
    try:
        repo = get_repo(repo_path)
        if repo is None:
            return
        return repo.commit(commit_hash)
    except git.BadName:
        return


def patch_set(
    repo: git.Repo, head_commit_rev: str, base_commit_rev: Optional[str]
) -> unidiff.PatchSet:
    """Returns the PatchSet for the given commit range."""
    if base_commit_rev is None:
        base_commit_rev = head_commit_rev + "^"
    full_patch = repo.git.diff(base_commit_rev, head_commit_rev)
    return unidiff.PatchSet(full_patch)


def file_is_binary(file_path, check_bytes=8000):
    """
    Same as git is_binary check
    https://git.kernel.org/pub/scm/git/git.git/tree/xdiff-interface.c?h=v2.30.0#n187
    """
    with open(file_path, "rb") as file:
        data = file.read(check_bytes)
        return b"\0" in data
