#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
有道云笔记GUI管理工具启动脚本
"""

import os
import sys

def main():
    """主启动函数"""
    print("🚀 启动有道云笔记GUI管理工具...")
    
    # 检查cookies文件
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cookies_file = os.path.join(parent_dir, "cookies.json")
    
    if not os.path.exists(cookies_file):
        print("❌ 未找到cookies.json文件")
        print("请确保在父目录中有有效的cookies.json文件")
        input("按回车键退出...")
        return
    
    print("✅ 找到cookies.json文件")
    
    # 导入并启动GUI
    try:
        from youdao_gui import main as gui_main
        print("✅ 正在启动GUI界面...")
        gui_main()
    except ImportError as e:
        print(f"❌ 导入GUI模块失败: {e}")
        print("请确保所有依赖都已正确安装")
        input("按回车键退出...")
    except Exception as e:
        print(f"❌ 启动GUI失败: {e}")
        input("按回车键退出...")


if __name__ == "__main__":
    main()
