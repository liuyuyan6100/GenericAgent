import argparse
import subprocess
import sys
from datetime import datetime


def _run_git(args, repo_root='.', check=False, capture_output=True):
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=check,
        capture_output=capture_output,
        text=True,
    )


def _git_output(args, repo_root='.'):
    result = _run_git(args, repo_root=repo_root)
    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode,
            ["git", *args],
            output=result.stdout,
            stderr=result.stderr,
        )
    return result.stdout.strip()


def _remote_exists(name, repo_root='.'):
    return _run_git(["remote", "get-url", name], repo_root=repo_root).returncode == 0


def _branch_exists(name, repo_root='.'):
    return _run_git(["show-ref", "--verify", "--quiet", f"refs/heads/{name}"], repo_root=repo_root).returncode == 0


def _remote_ref_exists(name, repo_root='.'):
    return _run_git(["show-ref", "--verify", "--quiet", f"refs/remotes/{name}"], repo_root=repo_root).returncode == 0


def _preferred_main_remote(repo_root='.'):
    for remote in ("upstream", "origin"):
        if _remote_exists(remote, repo_root=repo_root):
            return remote
    return None


def get_current_branch(repo_root='.'):
    return _git_output(["rev-parse", "--abbrev-ref", "HEAD"], repo_root=repo_root)


def is_worktree_clean(repo_root='.'):
    result = _run_git(["status", "--porcelain"], repo_root=repo_root)
    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode,
            ["git", "status", "--porcelain"],
            output=result.stdout,
            stderr=result.stderr,
        )
    return not result.stdout.strip()


def auto_create_usage_branch(repo_root='.'):
    """GA 启动时检查：若在 develop 分支且工作区干净，自动创建 feat/session-{时间戳} 分支。"""
    try:
        current_branch = get_current_branch(repo_root=repo_root)
        if current_branch != "develop":
            return
        if not is_worktree_clean(repo_root=repo_root):
            print("[GA] develop 分支有未提交改动，留在当前分支。")
            return
        timestamp = datetime.now().strftime("%m%d-%H%M%S")
        branch_name = f"feat/session-{timestamp}"
        _run_git(["checkout", "-b", branch_name], repo_root=repo_root, check=True)
        print(f"[GA] 已自动创建并切换到使用分支: {branch_name}")
    except subprocess.CalledProcessError as e:
        print(f"[GA] 分支检查失败: {e}", file=sys.stderr)
    except FileNotFoundError:
        pass


def sync_main_if_safe(repo_root='.'):
    result = {"ok": True, "notes": []}
    notes = result["notes"]
    try:
        current_branch = get_current_branch(repo_root=repo_root)
        clean = is_worktree_clean(repo_root=repo_root)
        notes.append(f"current_branch={current_branch}")
        notes.append(f"worktree_clean={'yes' if clean else 'no'}")

        remote = _preferred_main_remote(repo_root=repo_root)
        if not remote:
            notes.append("sync_main=skip reason=no_upstream_or_origin")
            return result
        notes.append(f"main_remote={remote}")

        fetch = _run_git(["fetch", "--all", "--prune"], repo_root=repo_root)
        if fetch.returncode != 0:
            result["ok"] = False
            notes.append(f"sync_main=warn reason=fetch_failed code={fetch.returncode}")
            stderr = (fetch.stderr or "").strip()
            if stderr:
                notes.append(f"fetch_stderr={stderr}")
            return result

        if not clean:
            notes.append("sync_main=skip reason=dirty_worktree")
            return result

        if not _branch_exists("main", repo_root=repo_root):
            notes.append("sync_main=skip reason=no_local_main")
            return result

        remote_ref = f"{remote}/main"
        if not _remote_ref_exists(remote_ref, repo_root=repo_root):
            notes.append(f"sync_main=skip reason=no_remote_ref target={remote_ref}")
            return result

        switched = False
        if current_branch != "main":
            checkout_main = _run_git(["checkout", "main"], repo_root=repo_root)
            if checkout_main.returncode != 0:
                result["ok"] = False
                notes.append(f"sync_main=warn reason=checkout_main_failed code={checkout_main.returncode}")
                stderr = (checkout_main.stderr or "").strip()
                if stderr:
                    notes.append(f"checkout_main_stderr={stderr}")
                return result
            switched = True

        try:
            merge = _run_git(["merge", "--ff-only", remote_ref], repo_root=repo_root)
            if merge.returncode == 0:
                notes.append(f"sync_main=ok target={remote_ref}")
            else:
                result["ok"] = False
                notes.append(f"sync_main=warn reason=ff_only_failed target={remote_ref} code={merge.returncode}")
                stderr = (merge.stderr or "").strip()
                if stderr:
                    notes.append(f"merge_stderr={stderr}")
        finally:
            if switched:
                checkout_back = _run_git(["checkout", current_branch], repo_root=repo_root)
                if checkout_back.returncode == 0:
                    notes.append(f"restored_branch={current_branch}")
                else:
                    result["ok"] = False
                    notes.append(f"restore_branch=warn target={current_branch} code={checkout_back.returncode}")
                    stderr = (checkout_back.stderr or "").strip()
                    if stderr:
                        notes.append(f"restore_branch_stderr={stderr}")
    except subprocess.CalledProcessError as e:
        result["ok"] = False
        notes.append(f"sync_main=warn reason=git_error code={e.returncode}")
        if e.stderr:
            notes.append(f"git_stderr={e.stderr.strip()}")
    except FileNotFoundError:
        result["ok"] = False
        notes.append("sync_main=warn reason=git_not_found")
    return result


def repo_status(repo_root='.'):
    result = {"ok": True, "notes": []}
    notes = result["notes"]
    try:
        current_branch = get_current_branch(repo_root=repo_root)
        clean = is_worktree_clean(repo_root=repo_root)
        notes.append(f"repo_root={repo_root}")
        notes.append(f"repo_current_branch={current_branch}")
        notes.append(f"repo_worktree_clean={'yes' if clean else 'no'}")

        remote = _preferred_main_remote(repo_root=repo_root)
        if not remote:
            notes.append("repo_main_remote=none")
            notes.append("repo_main_sync=unknown")
            return result

        notes.append(f"repo_main_remote={remote}")
        remote_ref = f"{remote}/main"
        if not _branch_exists("main", repo_root=repo_root):
            result["ok"] = False
            notes.append("repo_main_sync=no_local_main")
            return result
        if not _remote_ref_exists(remote_ref, repo_root=repo_root):
            result["ok"] = False
            notes.append(f"repo_main_sync=no_remote_ref target={remote_ref}")
            return result

        local_main = _git_output(["rev-parse", "main"], repo_root=repo_root)
        remote_main = _git_output(["rev-parse", remote_ref], repo_root=repo_root)
        notes.append(f"repo_main_local={local_main}")
        notes.append(f"repo_main_remote_sha={remote_main}")
        if local_main == remote_main:
            notes.append("repo_main_sync=up_to_date")
            return result

        behind = _run_git(["merge-base", "--is-ancestor", "main", remote_ref], repo_root=repo_root, capture_output=False)
        ahead = _run_git(["merge-base", "--is-ancestor", remote_ref, "main"], repo_root=repo_root, capture_output=False)
        if behind.returncode == 0:
            result["ok"] = False
            notes.append(f"repo_main_sync=behind target={remote_ref}")
        elif ahead.returncode == 0:
            result["ok"] = False
            notes.append(f"repo_main_sync=ahead_of_remote target={remote_ref}")
        else:
            result["ok"] = False
            notes.append(f"repo_main_sync=diverged target={remote_ref}")
    except subprocess.CalledProcessError as e:
        result["ok"] = False
        notes.append(f"repo_status_error=git code={e.returncode}")
        if e.stderr:
            notes.append(f"repo_status_stderr={e.stderr.strip()}")
    except FileNotFoundError:
        result["ok"] = False
        notes.append("repo_status_error=git_not_found")
    return result


def print_repo_status(repo_root='.'):
    result = repo_status(repo_root=repo_root)
    print("repo_status_begin")
    for note in result["notes"]:
        print(note)
    print(f"repo_ok={'yes' if result['ok'] else 'no'}")
    print("repo_status_end")


def _main(argv=None):
    parser = argparse.ArgumentParser(description="GenericAgent startup repo guard")
    parser.add_argument("command", nargs="?", choices=["preflight-main", "repo-status"])
    parser.add_argument("--repo-root", default='.')
    args = parser.parse_args(argv)

    if args.command == "preflight-main":
        result = sync_main_if_safe(repo_root=args.repo_root)
        prefix = '[GA] main 同步完成' if result.get('ok') else '[GA] main 同步跳过/告警'
        print(prefix)
        for note in result.get('notes', []):
            print(f"[GA] {note}")
        return 0

    if args.command == 'repo-status':
        print_repo_status(args.repo_root)
        return 0

    parser.print_help()
    return 0


if __name__ == '__main__':
    raise SystemExit(_main())
