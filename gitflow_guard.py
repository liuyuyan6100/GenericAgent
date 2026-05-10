#!/usr/bin/env python3
"""Guarded GenericAgent gitflow helpers.

Primary use case: merge the current/session branch into local develop using
`git merge --no-ff`, with explicit blocker checks before any write action.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


PROTECTED_SOURCE_BRANCHES = {"main", "develop"}


def _run_git(args: list[str], repo_root: str = ".", check: bool = False, capture_output: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=check,
        capture_output=capture_output,
        text=True,
    )


def _git_output(args: list[str], repo_root: str = ".") -> str:
    result = _run_git(args, repo_root=repo_root)
    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode,
            ["git", *args],
            output=result.stdout,
            stderr=result.stderr,
        )
    return result.stdout.strip()


def _append_stderr(notes: list[str], key: str, completed: subprocess.CompletedProcess[str]) -> None:
    stderr = (completed.stderr or "").strip()
    if stderr:
        notes.append(f"{key}={stderr}")


def _branch_exists(name: str, repo_root: str = ".") -> bool:
    return _run_git(["show-ref", "--verify", "--quiet", f"refs/heads/{name}"], repo_root=repo_root).returncode == 0


def _remote_exists(name: str, repo_root: str = ".") -> bool:
    return _run_git(["remote", "get-url", name], repo_root=repo_root).returncode == 0


def _merge_in_progress(repo_root: str = ".") -> bool:
    result = _run_git(["rev-parse", "--git-path", "MERGE_HEAD"], repo_root=repo_root)
    if result.returncode != 0:
        return False
    return Path(repo_root, result.stdout.strip()).exists()


def _current_branch(repo_root: str = ".") -> str:
    return _git_output(["rev-parse", "--abbrev-ref", "HEAD"], repo_root=repo_root)


def _is_clean(repo_root: str = ".") -> bool:
    return _git_output(["status", "--porcelain"], repo_root=repo_root) == ""


def _short_commit(ref: str, repo_root: str = ".") -> str:
    return _git_output(["log", "-1", "--format=%h %ci %s", ref], repo_root=repo_root)


def _count_commits(left: str, right: str, repo_root: str = ".") -> int:
    return int(_git_output(["rev-list", "--count", f"{left}..{right}"], repo_root=repo_root) or "0")


def _is_ancestor(left: str, right: str, repo_root: str = ".") -> bool:
    return _run_git(["merge-base", "--is-ancestor", left, right], repo_root=repo_root, capture_output=False).returncode == 0


def _normalize_source(source: str | None, repo_root: str) -> str:
    return source or _current_branch(repo_root=repo_root)


def build_plan(repo_root: str = ".", source: str | None = None, target: str = "develop") -> dict[str, Any]:
    result: dict[str, Any] = {"ok": True, "blockers": [], "warnings": [], "notes": []}
    blockers: list[str] = result["blockers"]
    warnings: list[str] = result["warnings"]
    notes: list[str] = result["notes"]

    try:
        repo_root_abs = str(Path(repo_root).resolve())
        current = _current_branch(repo_root=repo_root)
        clean = _is_clean(repo_root=repo_root)
        merge_busy = _merge_in_progress(repo_root=repo_root)
        src = _normalize_source(source, repo_root=repo_root)

        result.update(
            {
                "repo_root": repo_root_abs,
                "current_branch": current,
                "source_branch": src,
                "target_branch": target,
                "worktree_clean": clean,
                "merge_in_progress": merge_busy,
            }
        )
        notes.append(f"repo_root={repo_root_abs}")
        notes.append(f"current_branch={current}")
        notes.append(f"source_branch={src}")
        notes.append(f"target_branch={target}")
        notes.append(f"worktree_clean={'yes' if clean else 'no'}")

        if current == "HEAD":
            blockers.append("detached_head")
        if not clean:
            blockers.append("dirty_worktree")
        if merge_busy:
            blockers.append("merge_in_progress")
        if src == target:
            blockers.append("source_is_target")
        if src in PROTECTED_SOURCE_BRANCHES:
            blockers.append(f"protected_source_branch:{src}")
        if not _branch_exists(src, repo_root=repo_root):
            blockers.append(f"missing_source_branch:{src}")
        if not _branch_exists(target, repo_root=repo_root):
            blockers.append(f"missing_target_branch:{target}")

        if blockers:
            result["ok"] = False
            return result

        source_tip = _short_commit(src, repo_root=repo_root)
        target_tip = _short_commit(target, repo_root=repo_root)
        ahead = _count_commits(target, src, repo_root=repo_root)
        behind = _count_commits(src, target, repo_root=repo_root)
        already_merged = _is_ancestor(src, target, repo_root=repo_root)
        target_ancestor = _is_ancestor(target, src, repo_root=repo_root)
        merge_base = _git_output(["merge-base", target, src], repo_root=repo_root)

        result.update(
            {
                "source_tip": source_tip,
                "target_tip": target_tip,
                "source_ahead_of_target": ahead,
                "source_behind_target": behind,
                "source_already_merged": already_merged,
                "target_is_ancestor_of_source": target_ancestor,
                "merge_base": merge_base,
            }
        )
        notes.append(f"source_tip={source_tip}")
        notes.append(f"target_tip={target_tip}")
        notes.append(f"source_vs_target=ahead:{ahead} behind:{behind}")
        notes.append(f"merge_base={merge_base}")

        if ahead <= 0 or already_merged:
            blockers.append("no_unique_source_commits")
        if behind > 0:
            warnings.append(f"source_behind_target:{behind}")
            notes.append("warning=source_behind_target merge_may_need_conflict_resolution")
        if target_ancestor:
            notes.append("merge_shape=target_is_ancestor_of_source no_ff_merge_will_create_merge_commit")
        else:
            notes.append("merge_shape=diverged_or_target_ahead no_ff_merge_may_conflict")

        result["ok"] = not blockers
        return result
    except subprocess.CalledProcessError as e:
        result["ok"] = False
        blockers.append(f"git_error:{e.returncode}")
        if e.stderr:
            notes.append(f"git_stderr={e.stderr.strip()}")
        if e.output:
            notes.append(f"git_stdout={str(e.output).strip()}")
        return result
    except FileNotFoundError:
        result["ok"] = False
        blockers.append("git_not_found")
        return result


def print_result(result: dict[str, Any], as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return
    print("gitflow_begin")
    for note in result.get("notes", []):
        print(note)
    blockers = result.get("blockers", [])
    warnings = result.get("warnings", [])
    if warnings:
        print("warnings=" + ",".join(warnings))
    if blockers:
        print("blockers=" + ",".join(blockers))
    print(f"gitflow_ok={'yes' if result.get('ok') else 'no'}")
    print("gitflow_end")


def run_merge(
    repo_root: str,
    source: str | None,
    target: str,
    push: bool,
    yes: bool,
    stay_on_target: bool,
    message: str | None,
) -> dict[str, Any]:
    result = build_plan(repo_root=repo_root, source=source, target=target)
    notes: list[str] = result.setdefault("notes", [])
    blockers: list[str] = result.setdefault("blockers", [])

    if not result.get("ok"):
        return result
    if not yes:
        result["ok"] = False
        blockers.append("confirmation_required:rerun_with_--yes")
        notes.append("run=skip reason=confirmation_required")
        return result

    src = str(result["source_branch"])
    original = str(result["current_branch"])
    switched = False
    merge_succeeded = False
    try:
        if original != target:
            checkout = _run_git(["checkout", target], repo_root=repo_root)
            if checkout.returncode != 0:
                result["ok"] = False
                blockers.append(f"checkout_target_failed:{target}")
                _append_stderr(notes, "checkout_target_stderr", checkout)
                return result
            switched = True
            notes.append(f"checkout_target=ok branch={target}")

        merge_args = ["merge", "--no-ff", "--no-edit"]
        if message:
            merge_args = ["merge", "--no-ff", "-m", message]
        merge_args.append(src)
        merge = _run_git(merge_args, repo_root=repo_root)
        if merge.returncode != 0:
            result["ok"] = False
            blockers.append(f"merge_failed:{src}_to_{target}")
            _append_stderr(notes, "merge_stderr", merge)
            stdout = (merge.stdout or "").strip()
            if stdout:
                notes.append(f"merge_stdout={stdout}")
            if _merge_in_progress(repo_root=repo_root):
                abort = _run_git(["merge", "--abort"], repo_root=repo_root)
                if abort.returncode == 0:
                    notes.append("merge_abort=ok")
                else:
                    notes.append(f"merge_abort=warn code={abort.returncode}")
                    _append_stderr(notes, "merge_abort_stderr", abort)
            return result
        merge_succeeded = True
        notes.append(f"merge_no_ff=ok source={src} target={target}")
        stdout = (merge.stdout or "").strip()
        if stdout:
            notes.append(f"merge_stdout={stdout}")

        if push:
            if not _remote_exists("origin", repo_root=repo_root):
                notes.append("push_target=skip reason=no_origin")
            else:
                push_result = _run_git(["push", "origin", target], repo_root=repo_root)
                if push_result.returncode == 0:
                    notes.append(f"push_target=ok remote=origin branch={target}")
                else:
                    result["ok"] = False
                    blockers.append(f"push_failed:origin/{target}")
                    _append_stderr(notes, "push_stderr", push_result)
        else:
            notes.append("push_target=skip reason=not_requested")
        return result
    except subprocess.CalledProcessError as e:
        result["ok"] = False
        blockers.append(f"git_error:{e.returncode}")
        if e.stderr:
            notes.append(f"git_stderr={e.stderr.strip()}")
        return result
    finally:
        if switched and not stay_on_target:
            restore = _run_git(["checkout", original], repo_root=repo_root)
            if restore.returncode == 0:
                notes.append(f"restored_branch={original}")
            else:
                result["ok"] = False
                blockers.append(f"restore_original_failed:{original}")
                _append_stderr(notes, "restore_stderr", restore)
        elif merge_succeeded and stay_on_target:
            notes.append(f"current_branch_after_run={target}")


def cleanup_branch(repo_root: str, source: str | None, target: str, yes: bool) -> dict[str, Any]:
    result = build_plan(repo_root=repo_root, source=source, target=target)
    notes: list[str] = result.setdefault("notes", [])
    blockers: list[str] = result.setdefault("blockers", [])
    src = result.get("source_branch") or source
    current = result.get("current_branch")

    if not src:
        result["ok"] = False
        blockers.append("missing_source_branch")
        return result
    if src == current:
        result["ok"] = False
        blockers.append("cannot_delete_current_branch")
        return result
    if src in PROTECTED_SOURCE_BRANCHES:
        result["ok"] = False
        blockers.append(f"protected_source_branch:{src}")
        return result
    # Cleanup is normally run after the source commits are already integrated;
    # that condition is a blocker for a new merge plan, but not for safe branch deletion.
    if "no_unique_source_commits" in blockers:
        blockers[:] = [blocker for blocker in blockers if blocker != "no_unique_source_commits"]
    if blockers:
        result["ok"] = False
        return result
    if _branch_exists(str(src), repo_root=repo_root) and _branch_exists(target, repo_root=repo_root):
        if not _is_ancestor(str(src), target, repo_root=repo_root):
            result["ok"] = False
            blockers.append(f"source_not_merged_to_target:{src}->{target}")
            return result
    if not yes:
        result["ok"] = False
        blockers.append("confirmation_required:rerun_with_--yes")
        notes.append("cleanup=skip reason=confirmation_required")
        return result
    delete = _run_git(["branch", "-d", str(src)], repo_root=repo_root)
    if delete.returncode == 0:
        result["ok"] = True
        notes.append(f"cleanup_delete_branch=ok branch={src}")
    else:
        result["ok"] = False
        blockers.append(f"delete_branch_failed:{src}")
        _append_stderr(notes, "delete_branch_stderr", delete)
    return result


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Guarded gitflow operations for GenericAgent")
    parser.add_argument("command", nargs="?", default="status", choices=["status", "plan", "run", "cleanup"])
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--source", help="source branch to merge; default: current branch")
    parser.add_argument("--target", default="develop", help="target integration branch; default: develop")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--yes", action="store_true", help="confirm write actions for run/cleanup")
    parser.add_argument("--push", action="store_true", help="after a successful run, push origin/TARGET")
    parser.add_argument("--stay-on-target", action="store_true", help="after run, remain on TARGET instead of restoring the original branch")
    parser.add_argument("-m", "--message", help="custom merge commit message")
    args = parser.parse_args(argv)

    if args.command in {"status", "plan"}:
        result = build_plan(repo_root=args.repo_root, source=args.source, target=args.target)
    elif args.command == "run":
        result = run_merge(
            repo_root=args.repo_root,
            source=args.source,
            target=args.target,
            push=args.push,
            yes=args.yes,
            stay_on_target=args.stay_on_target,
            message=args.message,
        )
    elif args.command == "cleanup":
        result = cleanup_branch(repo_root=args.repo_root, source=args.source, target=args.target, yes=args.yes)
    else:  # argparse choices keep this unreachable.
        parser.print_help()
        return 2

    print_result(result, as_json=args.json)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(_main())
