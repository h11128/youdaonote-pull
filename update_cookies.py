#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
有道云笔记Cookie更新工具
用于更新cookies.json文件中的cookie值
"""

import json
import os
import sys
from datetime import datetime


def backup_cookies(cookies_path):
    """备份现有的cookies.json文件"""
    if os.path.exists(cookies_path):
        backup_path = f"{cookies_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        try:
            with open(cookies_path, 'r', encoding='utf-8') as f:
                content = f.read()
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ 已备份原cookies文件到: {backup_path}")
            return True
        except Exception as e:
            print(f"❌ 备份失败: {e}")
            return False
    return True


def update_cookies_interactive():
    """交互式更新cookies"""
    cookies_path = "cookies.json"
    
    print("🔧 有道云笔记Cookie更新工具")
    print("=" * 50)
    
    # 备份现有文件
    backup_cookies(cookies_path)
    
    # 获取用户输入的cookie值
    cookies_data = {
        "cookies": []
    }
    
    required_cookies = [
        ("YNOTE_CSTK", "CSTK令牌"),
        ("YNOTE_LOGIN", "登录信息"),
        ("YNOTE_SESS", "会话信息")
    ]
    
    print("\n请输入以下cookie值（从浏览器开发者工具中获取）:")
    print("提示：可以运行 extract_cookies.js 脚本自动提取\n")
    
    for cookie_name, description in required_cookies:
        while True:
            value = input(f"请输入 {cookie_name} ({description}): ").strip()
            if value and value != "**":
                cookies_data["cookies"].append([
                    cookie_name,
                    value,
                    ".note.youdao.com",
                    "/"
                ])
                print(f"✅ {cookie_name} 已设置")
                break
            else:
                print("❌ 请输入有效的cookie值")
    
    # 保存到文件
    try:
        with open(cookies_path, 'w', encoding='utf-8') as f:
            json.dump(cookies_data, f, indent=4, ensure_ascii=False)
        print(f"\n🎉 Cookie已成功保存到 {cookies_path}")
        
        # 显示保存的内容
        print("\n📄 保存的内容:")
        print(json.dumps(cookies_data, indent=4, ensure_ascii=False))
        
    except Exception as e:
        print(f"❌ 保存失败: {e}")
        return False
    
    return True


def update_cookies_from_json(json_string):
    """从JSON字符串更新cookies"""
    cookies_path = "cookies.json"
    
    try:
        # 解析JSON
        cookies_data = json.loads(json_string)
        
        # 验证格式
        if "cookies" not in cookies_data:
            raise ValueError("JSON格式错误：缺少'cookies'字段")
        
        if len(cookies_data["cookies"]) != 3:
            raise ValueError("Cookie数量错误：应该有3个cookie")
        
        # 备份现有文件
        backup_cookies(cookies_path)
        
        # 保存新的cookies
        with open(cookies_path, 'w', encoding='utf-8') as f:
            json.dump(cookies_data, f, indent=4, ensure_ascii=False)
        
        print("🎉 Cookie已成功更新！")
        return True
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON解析错误: {e}")
        return False
    except Exception as e:
        print(f"❌ 更新失败: {e}")
        return False


def main():
    """主函数"""
    if len(sys.argv) > 1:
        # 如果提供了命令行参数，尝试作为JSON解析
        json_string = " ".join(sys.argv[1:])
        update_cookies_from_json(json_string)
    else:
        # 交互式模式
        update_cookies_interactive()


if __name__ == "__main__":
    main()
