#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
import os
import sys
import time
from typing import List, Dict, Optional

from core import log
from core.api import YoudaoNoteApi
from pull import YoudaoNotePull


class YoudaoNoteSearch:
    """
    有道云笔记搜索和下载工具
    """
    
    def __init__(self):
        self.youdaonote_api = None
        self.youdaonote_pull = None
        
    def init_api(self):
        """初始化API"""
        self.youdaonote_api = YoudaoNoteApi()
        error_msg = self.youdaonote_api.login_by_cookies()
        if error_msg:
            logging.error(f"Cookie登录失败: {error_msg}")
            return False
        logging.info("Cookie登录成功!")
        
        # 初始化pull实例
        self.youdaonote_pull = YoudaoNotePull()
        return True
    
    def search_folders_by_name(self, folder_name: str, exact_match: bool = False) -> List[Dict]:
        """
        根据名称搜索文件夹
        :param folder_name: 要搜索的文件夹名称
        :param exact_match: 是否精确匹配
        :return: 匹配的文件夹列表
        """
        if not self.youdaonote_api:
            if not self.init_api():
                return []
        
        root_info = self.youdaonote_api.get_root_dir_info_id()
        root_id = root_info['fileEntry']['id']
        
        found_folders = []
        self._search_folders_recursively(root_id, folder_name, exact_match, found_folders)
        
        return found_folders
    
    def _search_folders_recursively(self, dir_id: str, target_name: str, exact_match: bool, 
                                   found_folders: List[Dict], current_path: str = ""):
        """
        递归搜索文件夹
        """
        try:
            dir_info = self.youdaonote_api.get_dir_info_by_id(dir_id)
            if 'entries' not in dir_info:
                return
            
            for entry in dir_info['entries']:
                file_entry = entry['fileEntry']
                entry_name = file_entry.get('name', '')
                entry_id = file_entry.get('id', '')
                is_dir = file_entry.get('dir', False)
                
                current_entry_path = f"{current_path}/{entry_name}" if current_path else entry_name
                
                if is_dir:
                    # 检查是否匹配
                    if exact_match:
                        is_match = entry_name == target_name
                    else:
                        is_match = target_name.lower() in entry_name.lower()
                    
                    if is_match:
                        folder_info = {
                            'id': entry_id,
                            'name': entry_name,
                            'path': current_entry_path,
                            'full_entry': file_entry
                        }
                        found_folders.append(folder_info)
                        logging.info(f"🎯 找到匹配文件夹: {current_entry_path}")
                    
                    # 继续递归搜索子文件夹
                    self._search_folders_recursively(entry_id, target_name, exact_match, 
                                                   found_folders, current_entry_path)
                    
        except Exception as e:
            logging.error(f"搜索文件夹时出错: {e}")
    
    def list_folder_contents(self, folder_id: str) -> Dict:
        """
        列出文件夹内容
        """
        if not self.youdaonote_api:
            if not self.init_api():
                return {}
        
        try:
            return self.youdaonote_api.get_dir_info_by_id(folder_id)
        except Exception as e:
            logging.error(f"获取文件夹内容时出错: {e}")
            return {}
    
    def pull_folder_by_id(self, folder_id: str, folder_name: str, local_base_dir: str = "./youdaonote"):
        """
        根据文件夹ID下载整个文件夹
        """
        if not self.youdaonote_pull:
            if not self.init_api():
                return False
        
        # 创建本地目录
        local_folder_path = os.path.join(local_base_dir, folder_name).replace("\\", "/")
        if not os.path.exists(local_folder_path):
            os.makedirs(local_folder_path, exist_ok=True)
        
        logging.info(f"开始下载文件夹: {folder_name} -> {local_folder_path}")
        
        try:
            # 使用pull.py中的递归下载方法
            self.youdaonote_pull.youdaonote_api = self.youdaonote_api
            self.youdaonote_pull.root_local_dir = local_base_dir
            self.youdaonote_pull.smms_secret_token = ""
            self.youdaonote_pull.is_relative_path = True
            
            self.youdaonote_pull.pull_dir_by_id_recursively(folder_id, local_folder_path)
            logging.info(f"✅ 文件夹下载完成: {folder_name}")
            return True
            
        except Exception as e:
            logging.error(f"下载文件夹时出错: {e}")
            return False


def main():
    """主函数"""
    log.init_logging()
    
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python search_and_pull.py <文件夹名称> [选项]")
        print("")
        print("选项:")
        print("  --exact     精确匹配文件夹名称")
        print("  --list-only 只列出匹配的文件夹，不下载")
        print("")
        print("示例:")
        print("  python search_and_pull.py 内在世界")
        print("  python search_and_pull.py 内在世界 --exact")
        print("  python search_and_pull.py 内在世界 --list-only")
        sys.exit(1)
    
    folder_name = sys.argv[1]
    exact_match = "--exact" in sys.argv
    list_only = "--list-only" in sys.argv
    
    searcher = YoudaoNoteSearch()
    
    # 搜索文件夹
    logging.info(f"🔍 正在搜索文件夹: {folder_name}")
    found_folders = searcher.search_folders_by_name(folder_name, exact_match)
    
    if not found_folders:
        logging.info("❌ 未找到匹配的文件夹")
        return
    
    # 显示找到的文件夹
    logging.info(f"✅ 找到 {len(found_folders)} 个匹配的文件夹:")
    for i, folder in enumerate(found_folders, 1):
        logging.info(f"  {i}. {folder['path']} (ID: {folder['id']})")
    
    if list_only:
        return
    
    # 如果找到多个文件夹，让用户选择
    if len(found_folders) > 1:
        print("\n请选择要下载的文件夹:")
        for i, folder in enumerate(found_folders, 1):
            print(f"  {i}. {folder['path']}")
        
        try:
            choice = int(input("请输入序号 (1-{}): ".format(len(found_folders))))
            if 1 <= choice <= len(found_folders):
                selected_folder = found_folders[choice - 1]
            else:
                logging.error("无效的选择")
                return
        except ValueError:
            logging.error("请输入有效的数字")
            return
    else:
        selected_folder = found_folders[0]
    
    # 下载选中的文件夹
    logging.info(f"📥 开始下载文件夹: {selected_folder['path']}")
    success = searcher.pull_folder_by_id(
        selected_folder['id'], 
        selected_folder['name']
    )
    
    if success:
        logging.info("🎉 下载完成!")
    else:
        logging.error("❌ 下载失败!")


if __name__ == "__main__":
    main()
