import os
import platform
import sys


def get_script_directory():
    """获取脚本所在的目录"""

    if getattr(sys, "frozen", False):
        # 如果是打包后的可执行文件
        return os.path.dirname(sys.executable)
    else:
        # 如果是普通脚本
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_config_directory():
    """获取配置文件目录"""
    return os.path.join(get_script_directory(), "config")


def safe_long_path(path: str) -> str:
    """
    处理 Windows 长路径问题。
    
    Windows 默认最大路径长度 260 字符（MAX_PATH），超过后文件操作会报错。
    对于超长路径，添加 ``\\\\?\\`` 前缀来突破限制。
    非 Windows 系统或短路径原样返回。
    
    :param path: 文件路径
    :return: 可能添加了长路径前缀的路径
    """
    if platform.system() != "Windows":
        return path
    # 已有前缀则跳过
    if path.startswith("\\\\?\\"):
        return path
    # 路径足够短则不处理（留一些余量给文件名拼接）
    if len(path) < 240:
        return path
    # \\?\ 前缀要求绝对路径且使用反斜杠
    abs_path = os.path.abspath(path)
    return "\\\\?\\" + abs_path
