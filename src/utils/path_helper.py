from pathlib import Path
import os


def _get_script_dir() -> Path:
    """获取当前这个path_helper.py文件所在目录"""
    return Path(__file__).resolve().parent


def get_cwd() -> Path:
    """获取命令行执行脚本时的终端工作目录 os.getcwd()"""
    return Path(os.getcwd()).resolve()


def get_project_root(marker: str = ".git") -> Path:
    """
    自动向上查找标记文件，返回项目根目录
    :param marker: 识别项目根的标记，默认.git，可选 requirements.txt / pyproject.toml
    """
    current = _get_script_dir()
    while True:
        # 判断当前目录是否存在标记文件/文件夹
        if (current / marker).exists():
            return current
        parent = current.parent
        # 到达磁盘根目录，停止循环，防止死循环
        if parent == current:
            return current
        current = parent
