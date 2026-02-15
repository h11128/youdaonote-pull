#!/usr/bin/env python3
"""
使用 Playwright 捕获有道云笔记的 API 请求

用法：
1. 运行此脚本，会打开浏览器
2. 在浏览器中编辑一篇笔记并保存
3. 脚本会捕获并打印所有相关的 API 请求
"""

import json
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright


def get_browser_data_dir() -> str:
    """获取浏览器数据目录"""
    from youdaonote.common import get_config_directory
    return os.path.join(get_config_directory(), "browser_data")


def capture_requests():
    """捕获有道云笔记的 API 请求"""
    
    captured_requests = []
    
    def handle_request(request):
        """处理请求"""
        url = request.url
        # 只关注有道云笔记的 API 请求
        if "note.youdao.com" in url and "/yws/" in url:
            # 过滤掉静态资源
            if any(ext in url for ext in ['.js', '.css', '.png', '.jpg', '.gif', '.ico']):
                return
            
            req_info = {
                "method": request.method,
                "url": url,
                "headers": dict(request.headers),
                "post_data": None
            }
            
            # 尝试获取 POST 数据
            if request.method == "POST":
                try:
                    req_info["post_data"] = request.post_data
                except:
                    pass
            
            captured_requests.append(req_info)
            print(f"\n{'='*60}")
            print(f"🔍 捕获请求: {request.method} {url[:80]}...")
            if req_info["post_data"]:
                print(f"   POST 数据: {req_info['post_data'][:200]}...")
    
    def handle_response(response):
        """处理响应"""
        url = response.url
        if "note.youdao.com" in url and "/yws/" in url:
            # 过滤掉静态资源
            if any(ext in url for ext in ['.js', '.css', '.png', '.jpg', '.gif', '.ico']):
                return
            
            # 只关注写操作相关的 API
            write_keywords = ['create', 'update', 'save', 'upload', 'sync', 'push', 'modify', 'edit']
            if any(kw in url.lower() for kw in write_keywords):
                print(f"✅ 响应: {response.status} {url[:60]}...")
                try:
                    body = response.text()
                    if body:
                        print(f"   响应体: {body[:300]}...")
                except:
                    pass

    browser_data_dir = get_browser_data_dir()
    
    print("="*60)
    print("  有道云笔记 API 捕获工具")
    print("="*60)
    print()
    print("📌 操作说明：")
    print("   1. 浏览器打开后，进入有道云笔记")
    print("   2. 选择一篇笔记进行编辑")
    print("   3. 修改内容后保存")
    print("   4. 观察终端输出的 API 请求")
    print("   5. 完成后关闭浏览器窗口")
    print()
    print("🔍 重点关注包含以下关键词的请求：")
    print("   create, update, save, upload, sync, push")
    print()
    
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            browser_data_dir,
            headless=False,
            viewport={'width': 1400, 'height': 900},
            locale='zh-CN',
        )
        
        # 注册请求/响应监听器
        context.on("request", handle_request)
        context.on("response", handle_response)
        
        page = context.pages[0] if context.pages else context.new_page()
        
        print("🚀 正在打开有道云笔记...")
        page.goto("https://note.youdao.com/web/")
        
        print("\n⏳ 请在浏览器中操作，完成后关闭浏览器窗口...")
        print("   （程序会持续监听所有 API 请求）\n")
        
        # 等待用户关闭浏览器
        try:
            page.wait_for_event("close", timeout=600000)  # 10分钟超时
        except:
            pass
        
        context.close()
    
    # 保存捕获的请求
    if captured_requests:
        output_file = "captured_api_requests.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(captured_requests, f, ensure_ascii=False, indent=2)
        
        print(f"\n{'='*60}")
        print(f"📁 已保存 {len(captured_requests)} 个 API 请求到: {output_file}")
        print("="*60)
        
        # 打印写操作相关的 API 摘要
        print("\n📋 写操作相关 API 摘要：")
        write_keywords = ['create', 'update', 'save', 'upload', 'sync', 'push', 'modify', 'edit']
        for req in captured_requests:
            if any(kw in req['url'].lower() for kw in write_keywords):
                print(f"\n  {req['method']} {req['url']}")
                if req['post_data']:
                    print(f"  POST: {req['post_data'][:100]}...")
    else:
        print("\n⚠️ 未捕获到任何 API 请求")


if __name__ == "__main__":
    capture_requests()
