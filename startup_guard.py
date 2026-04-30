import subprocess
import sys
from datetime import datetime

def auto_create_usage_branch(repo_root='.'):
    """GA 启动时检查：若在 develop 分支且工作区干净，自动创建 feat/session-{时间戳} 分支。"""
    try:
        current_branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root, text=True, stderr=subprocess.DEVNULL
        ).strip()
        if current_branch != "develop":
            return
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_root, capture_output=True, text=True
        )
        if result.stdout.strip():
            print("[GA] develop 分支有未提交改动，留在当前分支。")
            return
        timestamp = datetime.now().strftime("%m%d-%H%M%S")
        branch_name = f"feat/session-{timestamp}"
        subprocess.run(
            ["git", "checkout", "-b", branch_name],
            cwd=repo_root, check=True
        )
        print(f"[GA] 已自动创建并切换到使用分支: {branch_name}")
    except subprocess.CalledProcessError as e:
        print(f"[GA] 分支检查失败: {e}", file=sys.stderr)
    except FileNotFoundError:
        pass