#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动从浏览器提取有道云笔记 Cookies
支持 Chrome, Edge, Firefox 等主流浏览器

需要安装: pip install browser-cookie3
"""

import os
import sys

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from youdaonote.cookies import CookieManager


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("  有道云笔记 Cookies 自动提取工具")
    print("=" * 60 + "\n")
    
    print("🔍 正在尝试从浏览器中提取有道云笔记 Cookies...")
    
    # 使用 CookieManager 提取
    cookies_data, error = CookieManager.extract_from_browser()
    
    if error:
        if "browser-cookie3" in error:
            print("❌ 缺少 browser_cookie3 库")
            print("\n请先安装依赖:")
            print("  pip install browser-cookie3")
        else:
            print(f"❌ 提取失败: {error}")
            print("\n可能的原因:")
            print("  1. 浏览器中未登录有道云笔记")
            print("  2. 浏览器 cookies 已过期")
            print("  3. 浏览器数据库被锁定（请关闭浏览器后重试）")
        
        print("\n💡 推荐使用浏览器登录方式:")
        print("  python -m youdaonote login")
        return 1
    
    print("🎉 成功提取到所有必需的 cookies!")
    
    # 保存 cookies
    success, error = CookieManager.save(cookies_data)
    
    if success:
        print(f"\n✅ Cookies 已保存到: {CookieManager.get_default_path()}")
        print("\n现在可以使用:")
        print("  python -m youdaonote pull   # 全量导出")
        print("  python -m youdaonote gui    # 图形界面")
        return 0
    else:
        print(f"\n❌ 保存失败: {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
