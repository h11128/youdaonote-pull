#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动从浏览器提取有道云笔记Cookies
支持 Chrome, Edge, Firefox 等主流浏览器
"""

import json
import os
import sys
from datetime import datetime


def extract_cookies_from_browser():
    """从浏览器自动提取cookies"""
    print("🔍 正在尝试从浏览器中提取有道云笔记Cookies...")
    print("=" * 60)
    
    # 尝试导入 browser_cookie3
    try:
        import browser_cookie3
    except ImportError:
        print("❌ 缺少 browser_cookie3 库")
        print("\n请先安装依赖:")
        print("  pip install browser-cookie3")
        print("\n或者使用手动方式:")
        print("  1. 访问 https://note.youdao.com 并登录")
        print("  2. 按F12打开开发者工具，切换到Console")
        print("  3. 运行项目中的 extract_cookies.js 脚本")
        return None
    
    required_cookies = ['YNOTE_CSTK', 'YNOTE_SESS', 'YNOTE_LOGIN']
    found_cookies = {}
    
    # 支持的浏览器列表
    browsers = [
        ('Chrome', browser_cookie3.chrome),
        ('Edge', browser_cookie3.edge),
        ('Firefox', browser_cookie3.firefox),
        ('Chromium', browser_cookie3.chromium),
    ]
    
    # 尝试从各个浏览器提取
    for browser_name, browser_func in browsers:
        try:
            print(f"\n🔎 尝试从 {browser_name} 提取...")
            cj = browser_func(domain_name='youdao.com')
            
            for cookie in cj:
                if cookie.name in required_cookies:
                    found_cookies[cookie.name] = cookie.value
                    print(f"  ✅ 找到 {cookie.name}")
            
            # 如果找到了所有必需的cookies，就停止搜索
            if len(found_cookies) == 3:
                print(f"\n🎉 成功从 {browser_name} 提取到所有必需的cookies!")
                break
                
        except Exception as e:
            print(f"  ⚠️ {browser_name} 提取失败: {str(e)[:50]}")
            continue
    
    # 检查是否找到了所有必需的cookies
    if len(found_cookies) != 3:
        missing = set(required_cookies) - set(found_cookies.keys())
        print(f"\n❌ 未能提取到所有必需的cookies")
        print(f"缺少: {', '.join(missing)}")
        print("\n可能的原因:")
        print("  1. 浏览器中未登录有道云笔记")
        print("  2. 浏览器cookies已过期")
        print("  3. 浏览器数据库被锁定（请关闭浏览器后重试）")
        return None
    
    # 构建cookies.json格式
    cookies_data = {
        "cookies": [
            ["YNOTE_CSTK", found_cookies["YNOTE_CSTK"], ".note.youdao.com", "/"],
            ["YNOTE_LOGIN", found_cookies["YNOTE_LOGIN"], ".note.youdao.com", "/"],
            ["YNOTE_SESS", found_cookies["YNOTE_SESS"], ".note.youdao.com", "/"]
        ]
    }
    
    return cookies_data


def save_cookies(cookies_data, cookies_path="cookies.json"):
    """保存cookies到文件"""
    # 备份现有文件
    if os.path.exists(cookies_path):
        backup_path = f"{cookies_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        try:
            with open(cookies_path, 'r', encoding='utf-8') as f:
                content = f.read()
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"\n📦 已备份原cookies文件到: {backup_path}")
        except Exception as e:
            print(f"⚠️ 备份失败: {e}")
    
    # 保存新的cookies
    try:
        with open(cookies_path, 'w', encoding='utf-8') as f:
            json.dump(cookies_data, f, indent=4, ensure_ascii=False)
        print(f"✅ Cookies已保存到: {os.path.abspath(cookies_path)}")
        return True
    except Exception as e:
        print(f"❌ 保存失败: {e}")
        return False


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("  有道云笔记 Cookies 自动提取工具")
    print("=" * 60 + "\n")
    
    # 提取cookies
    cookies_data = extract_cookies_from_browser()
    
    if not cookies_data:
        print("\n" + "=" * 60)
        print("❌ 自动提取失败，请使用手动方式:")
        print("=" * 60)
        print("\n方法1: 使用浏览器控制台脚本")
        print("  1. 访问 https://note.youdao.com 并登录")
        print("  2. 按F12打开开发者工具，切换到Console")
        print("  3. 复制并运行 extract_cookies.js 中的代码")
        print("  4. 将输出的JSON保存到 cookies.json")
        print("\n方法2: 查看详细教程")
        print("  打开文件: gui/如何获取Cookies.md")
        return 1
    
    # 保存cookies
    if save_cookies(cookies_data):
        print("\n" + "=" * 60)
        print("🎉 成功！现在可以启动GUI了:")
        print("=" * 60)
        print("\n  cd gui")
        print("  python start_gui.py")
        print()
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())

