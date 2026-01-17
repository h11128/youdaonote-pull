#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
import os
import sys
from typing import List, Dict, Optional

from core import log
from core.api import YoudaoNoteApi


class YoudaoNoteLister:
    """
    有道云笔记文件夹和文件列表工具
    """

    def __init__(self, cookies_path=None):
        self.youdaonote_api = None
        self.cookies_path = cookies_path

    def init_api(self):
        """初始化API"""
        self.youdaonote_api = YoudaoNoteApi(cookies_path=self.cookies_path)
        error_msg = self.youdaonote_api.login_by_cookies()
        if error_msg:
            logging.error(f"Cookie登录失败: {error_msg}")
            return False
        logging.info("Cookie登录成功!")
        return True
    
    def list_root_contents(self):
        """列出根目录内容"""
        if not self.youdaonote_api:
            if not self.init_api():
                return
        
        root_info = self.youdaonote_api.get_root_dir_info_id()
        root_id = root_info['fileEntry']['id']
        
        print("📁 根目录内容:")
        self._list_directory_contents(root_id, "")
    
    def list_directory_by_path(self, path: str):
        """根据路径列出目录内容"""
        if not self.youdaonote_api:
            if not self.init_api():
                return
        
        folder_id = self._find_folder_by_path(path)
        if not folder_id:
            print(f"❌ 未找到路径: {path}")
            return
        
        print(f"📁 目录内容 ({path}):")
        self._list_directory_contents(folder_id, path)
    
    def _find_folder_by_path(self, path: str) -> Optional[str]:
        """根据路径查找文件夹ID"""
        if not path or path == "/":
            root_info = self.youdaonote_api.get_root_dir_info_id()
            return root_info['fileEntry']['id']
        
        # 分割路径
        path_parts = [part for part in path.split('/') if part]
        
        # 从根目录开始查找
        root_info = self.youdaonote_api.get_root_dir_info_id()
        current_id = root_info['fileEntry']['id']
        
        for part in path_parts:
            dir_info = self.youdaonote_api.get_dir_info_by_id(current_id)
            found = False
            
            for entry in dir_info.get('entries', []):
                file_entry = entry['fileEntry']
                if file_entry.get('dir', False) and file_entry.get('name') == part:
                    current_id = file_entry['id']
                    found = True
                    break
            
            if not found:
                return None
        
        return current_id
    
    def _list_directory_contents(self, dir_id: str, current_path: str, max_depth: int = 2, current_depth: int = 0):
        """列出目录内容"""
        if current_depth >= max_depth:
            return
        
        try:
            dir_info = self.youdaonote_api.get_dir_info_by_id(dir_id)
            entries = dir_info.get('entries', [])
            
            # 分离文件夹和文件
            folders = []
            files = []
            
            for entry in entries:
                file_entry = entry['fileEntry']
                if file_entry.get('dir', False):
                    folders.append(file_entry)
                else:
                    files.append(file_entry)
            
            # 显示文件夹
            indent = "  " * current_depth
            for folder in folders:
                folder_name = folder.get('name', '无名称')
                folder_id = folder.get('id', '')
                print(f"{indent}📁 {folder_name} (ID: {folder_id})")
                
                # 递归显示子文件夹（限制深度）
                if current_depth < max_depth - 1:
                    self._list_directory_contents(folder_id, f"{current_path}/{folder_name}", max_depth, current_depth + 1)
            
            # 显示文件
            for file in files:
                file_name = file.get('name', '无名称')
                file_id = file.get('id', '')
                file_size = file.get('size', 0)
                modify_time = file.get('modifyTimeForSort', 0)
                
                # 格式化文件大小
                if file_size > 1024 * 1024:
                    size_str = f"{file_size / (1024 * 1024):.1f}MB"
                elif file_size > 1024:
                    size_str = f"{file_size / 1024:.1f}KB"
                else:
                    size_str = f"{file_size}B"
                
                # 格式化修改时间
                import time
                time_str = time.strftime('%Y-%m-%d %H:%M', time.localtime(modify_time / 1000))
                
                print(f"{indent}📄 {file_name} ({size_str}, {time_str}) (ID: {file_id})")
                
        except Exception as e:
            logging.error(f"列出目录内容时出错: {e}")
    
    def search_by_name(self, name: str, search_type: str = "all", exact_match: bool = False):
        """
        根据名称搜索文件或文件夹
        :param name: 搜索的名称
        :param search_type: 搜索类型 ("all", "folder", "file")
        :param exact_match: 是否精确匹配
        """
        if not self.youdaonote_api:
            if not self.init_api():
                return

        root_info = self.youdaonote_api.get_root_dir_info_id()
        root_id = root_info['fileEntry']['id']

        results = []
        print(f"🔍 搜索 '{name}' (类型: {search_type}, 精确匹配: {exact_match})")
        self._search_recursively(root_id, name, search_type, exact_match, results)

        if not results:
            print("❌ 未找到匹配的项目")
            return

        print(f"✅ 找到 {len(results)} 个匹配项:")
        for i, item in enumerate(results, 1):
            item_type = "📁" if item['is_dir'] else "📄"
            print(f"  {i}. {item_type} {item['path']} (ID: {item['id']})")

    def _search_by_name(self, name: str, search_type: str = "all", exact_match: bool = False):
        """
        根据名称搜索文件或文件夹（返回结果列表，供GUI使用）
        :param name: 搜索的名称
        :param search_type: 搜索类型 ("all", "folder", "file")
        :param exact_match: 是否精确匹配
        :return: 搜索结果列表
        """
        if not self.youdaonote_api:
            if not self.init_api():
                return []

        root_info = self.youdaonote_api.get_root_dir_info_id()
        root_id = root_info['fileEntry']['id']

        results = []
        self._search_recursively(root_id, name, search_type, exact_match, results)

        return results
    
    def _search_recursively(self, dir_id: str, target_name: str, search_type: str, 
                           exact_match: bool, results: List[Dict], current_path: str = ""):
        """递归搜索"""
        try:
            dir_info = self.youdaonote_api.get_dir_info_by_id(dir_id)
            
            for entry in dir_info.get('entries', []):
                file_entry = entry['fileEntry']
                entry_name = file_entry.get('name', '')
                entry_id = file_entry.get('id', '')
                is_dir = file_entry.get('dir', False)
                
                current_entry_path = f"{current_path}/{entry_name}" if current_path else entry_name
                
                # 检查是否匹配
                if exact_match:
                    is_match = entry_name == target_name
                else:
                    is_match = target_name.lower() in entry_name.lower()
                
                # 根据搜索类型过滤
                should_include = False
                if search_type == "all":
                    should_include = True
                elif search_type == "folder" and is_dir:
                    should_include = True
                elif search_type == "file" and not is_dir:
                    should_include = True
                
                if is_match and should_include:
                    results.append({
                        'id': entry_id,
                        'name': entry_name,
                        'path': current_entry_path,
                        'is_dir': is_dir,
                        'entry': file_entry
                    })
                
                # 如果是文件夹，继续递归搜索
                if is_dir:
                    self._search_recursively(entry_id, target_name, search_type, exact_match, 
                                           results, current_entry_path)
                    
        except Exception as e:
            logging.error(f"搜索时出错: {e}")


def main():
    """主函数"""
    log.init_logging()
    
    if len(sys.argv) < 2:
        print("有道云笔记文件列表工具")
        print("")
        print("使用方法:")
        print("  python list_notes.py list [路径]           # 列出目录内容")
        print("  python list_notes.py search <名称> [选项]   # 搜索文件或文件夹")
        print("")
        print("列出选项:")
        print("  无路径参数时列出根目录")
        print("  路径格式: folder1/folder2")
        print("")
        print("搜索选项:")
        print("  --type folder    只搜索文件夹")
        print("  --type file      只搜索文件")
        print("  --exact          精确匹配名称")
        print("")
        print("示例:")
        print("  python list_notes.py list")
        print("  python list_notes.py list 存档记录/暂停项目")
        print("  python list_notes.py search 内在世界")
        print("  python list_notes.py search 内在世界 --type folder --exact")
        sys.exit(1)
    
    command = sys.argv[1]
    lister = YoudaoNoteLister()
    
    if command == "list":
        if len(sys.argv) > 2:
            path = sys.argv[2]
            lister.list_directory_by_path(path)
        else:
            lister.list_root_contents()
    
    elif command == "search":
        if len(sys.argv) < 3:
            print("❌ 请提供搜索名称")
            sys.exit(1)
        
        search_name = sys.argv[2]
        search_type = "all"
        exact_match = False
        
        # 解析选项
        if "--type" in sys.argv:
            type_index = sys.argv.index("--type")
            if type_index + 1 < len(sys.argv):
                search_type = sys.argv[type_index + 1]
        
        if "--exact" in sys.argv:
            exact_match = True
        
        lister.search_by_name(search_name, search_type, exact_match)
    
    else:
        print(f"❌ 未知命令: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
