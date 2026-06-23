from pathlib import Path
import os


def get_cwd() -> Path:
    """获取命令行执行脚本时的终端工作目录 os.getcwd()"""
    return Path(os.getcwd()).resolve()


def get_project_root(marker: str = ".git") -> Path:
    """从当前文件向上查找项目根目录（含 marker 标记）"""
    current = Path(__file__).resolve().parent
    while True:
        if (current / marker).exists():
            return current
        parent = current.parent
        if parent == current:
            return current
        current = parent
