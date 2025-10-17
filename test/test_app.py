import os
import subprocess
import sys


def test_app_query_generates_markdown():
    env = os.environ.copy()
    out = "output/test_app.md"
    # 使用简单问题触发查询与Markdown写入
    result = subprocess.run(
        [sys.executable, "src/app.py", "--q", "测试查询", "--out", out, "--top-k", "1"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0
    assert f"已生成Markdown：{out}" in result.stdout
    assert os.path.exists(out)