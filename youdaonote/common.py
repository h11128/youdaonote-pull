import os
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
