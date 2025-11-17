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

# 尝试导入pull模块，如果失败则使用简化版本
try:
    from pull import YoudaoNotePull
except ImportError:
    # 如果无法导入pull模块，创建一个简化的下载类
    class YoudaoNotePull:
        def __init__(self):
            self.youdaonote_api = None
            self.root_local_dir = "./youdaonote"
            self.smms_secret_token = ""
            self.is_relative_path = True

        def _add_or_update_file(self, file_id, file_name, local_dir, modify_time, create_time):
            """简化的文件下载方法"""
            import os
            response = self.youdaonote_api.get_file_by_id(file_id)
            file_path = os.path.join(local_dir, file_name)

            with open(file_path, 'wb') as f:
                f.write(response.content)

        def pull_dir_by_id_recursively(self, dir_id, local_dir):
            """简化的递归下载方法"""
            import os
            dir_info = self.youdaonote_api.get_dir_info_by_id(dir_id)

            for entry in dir_info.get("entries", []):
                file_entry = entry["fileEntry"]
                entry_id = file_entry["id"]
                name = file_entry["name"]

                if file_entry["dir"]:
                    sub_dir = os.path.join(local_dir, name)
                    if not os.path.exists(sub_dir):
                        os.makedirs(sub_dir)
                    self.pull_dir_by_id_recursively(entry_id, sub_dir)
                else:
                    modify_time = file_entry["modifyTimeForSort"]
                    create_time = file_entry["createTimeForSort"]
                    self._add_or_update_file(entry_id, name, local_dir, modify_time, create_time)


class YoudaoNoteDownloader:
    """
    有道云笔记下载工具
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
    
    def search_and_download(self, name: str, search_type: str = "all", exact_match: bool = False, 
                           local_base_dir: str = "./youdaonote"):
        """
        搜索并下载文件或文件夹
        :param name: 搜索的名称
        :param search_type: 搜索类型 ("all", "folder", "file")
        :param exact_match: 是否精确匹配
        :param local_base_dir: 本地保存目录
        """
        if not self.youdaonote_api:
            if not self.init_api():
                return False
        
        # 搜索匹配项
        results = self._search_by_name(name, search_type, exact_match)
        
        if not results:
            logging.info("❌ 未找到匹配的项目")
            return False
        
        # 显示找到的项目
        logging.info(f"✅ 找到 {len(results)} 个匹配项:")
        for i, item in enumerate(results, 1):
            item_type = "📁" if item['is_dir'] else "📄"
            logging.info(f"  {i}. {item_type} {item['path']} (ID: {item['id']})")
        
        # 如果找到多个项目，让用户选择
        if len(results) > 1:
            print("\n请选择要下载的项目:")
            for i, item in enumerate(results, 1):
                item_type = "📁" if item['is_dir'] else "📄"
                print(f"  {i}. {item_type} {item['path']}")
            print(f"  0. 下载全部")
            
            try:
                choice = input(f"请输入序号 (0-{len(results)}): ").strip()
                if choice == "0":
                    selected_items = results
                else:
                    choice_num = int(choice)
                    if 1 <= choice_num <= len(results):
                        selected_items = [results[choice_num - 1]]
                    else:
                        logging.error("无效的选择")
                        return False
            except ValueError:
                logging.error("请输入有效的数字")
                return False
        else:
            selected_items = results
        
        # 下载选中的项目
        success_count = 0
        for item in selected_items:
            if item['is_dir']:
                success = self._download_folder(item, local_base_dir)
            else:
                success = self._download_file(item, local_base_dir)
            
            if success:
                success_count += 1
        
        logging.info(f"🎉 下载完成! 成功: {success_count}/{len(selected_items)}")
        return success_count > 0
    
    def _search_by_name(self, name: str, search_type: str = "all", exact_match: bool = False) -> List[Dict]:
        """根据名称搜索"""
        root_info = self.youdaonote_api.get_root_dir_info_id()
        root_id = root_info['fileEntry']['id']
        
        results = []
        logging.info(f"🔍 搜索 '{name}' (类型: {search_type}, 精确匹配: {exact_match})")
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
    
    def _download_folder(self, folder_info: Dict, local_base_dir: str) -> bool:
        """下载文件夹"""
        if not self.youdaonote_pull:
            if not self.init_api():
                return False
        
        folder_name = folder_info['name']
        folder_id = folder_info['id']
        
        # 创建本地目录
        local_folder_path = os.path.join(local_base_dir, folder_name).replace("\\", "/")
        if not os.path.exists(local_folder_path):
            os.makedirs(local_folder_path, exist_ok=True)
        
        logging.info(f"📥 开始下载文件夹: {folder_info['path']} -> {local_folder_path}")
        
        try:
            # 配置pull实例
            self.youdaonote_pull.youdaonote_api = self.youdaonote_api
            self.youdaonote_pull.root_local_dir = local_base_dir
            self.youdaonote_pull.smms_secret_token = ""
            self.youdaonote_pull.is_relative_path = True
            
            # 使用pull.py中的递归下载方法
            self.youdaonote_pull.pull_dir_by_id_recursively(folder_id, local_folder_path)
            logging.info(f"✅ 文件夹下载完成: {folder_name}")
            return True
            
        except Exception as e:
            logging.error(f"下载文件夹时出错: {e}")
            return False
    
    def _download_file(self, file_info: Dict, local_base_dir: str) -> bool:
        """下载单个文件"""
        if not self.youdaonote_pull:
            if not self.init_api():
                return False
        
        file_name = file_info['name']
        file_id = file_info['id']
        file_entry = file_info['entry']
        
        # 确保本地目录存在
        if not os.path.exists(local_base_dir):
            os.makedirs(local_base_dir, exist_ok=True)
        
        logging.info(f"📄 开始下载文件: {file_info['path']} -> {local_base_dir}")
        
        try:
            # 配置pull实例
            self.youdaonote_pull.youdaonote_api = self.youdaonote_api
            self.youdaonote_pull.root_local_dir = local_base_dir
            self.youdaonote_pull.smms_secret_token = ""
            self.youdaonote_pull.is_relative_path = True
            
            # 下载单个文件
            modify_time = file_entry.get('modifyTimeForSort', 0)
            create_time = file_entry.get('createTimeForSort', 0)
            
            self.youdaonote_pull._add_or_update_file(
                file_id, file_name, local_base_dir, modify_time, create_time
            )
            
            logging.info(f"✅ 文件下载完成: {file_name}")
            return True
            
        except Exception as e:
            logging.error(f"下载文件时出错: {e}")
            return False
    
    def download_by_id(self, item_id: str, item_type: str, local_base_dir: str = "./youdaonote"):
        """
        根据ID直接下载
        :param item_id: 文件或文件夹ID
        :param item_type: 类型 ("folder" 或 "file")
        :param local_base_dir: 本地保存目录
        """
        if not self.youdaonote_api:
            if not self.init_api():
                return False
        
        if item_type == "folder":
            # 获取文件夹信息
            try:
                dir_info = self.youdaonote_api.get_dir_info_by_id(item_id)
                # 这里需要从父目录获取文件夹名称，暂时使用ID作为名称
                folder_name = f"folder_{item_id}"
                
                folder_info = {
                    'id': item_id,
                    'name': folder_name,
                    'path': folder_name,
                    'is_dir': True
                }
                
                return self._download_folder(folder_info, local_base_dir)
                
            except Exception as e:
                logging.error(f"获取文件夹信息时出错: {e}")
                return False
        
        elif item_type == "file":
            logging.error("暂不支持根据ID直接下载单个文件，请使用搜索功能")
            return False
        
        else:
            logging.error(f"未知的项目类型: {item_type}")
            return False


def main():
    """主函数"""
    log.init_logging()
    
    if len(sys.argv) < 2:
        print("有道云笔记下载工具")
        print("")
        print("使用方法:")
        print("  python download_notes.py search <名称> [选项]  # 搜索并下载")
        print("  python download_notes.py id <ID> <类型>       # 根据ID下载")
        print("")
        print("搜索选项:")
        print("  --type folder    只搜索文件夹")
        print("  --type file      只搜索文件")
        print("  --exact          精确匹配名称")
        print("  --dir <目录>     指定本地保存目录 (默认: ./youdaonote)")
        print("")
        print("ID下载:")
        print("  类型: folder 或 file")
        print("")
        print("示例:")
        print("  python download_notes.py search 内在世界")
        print("  python download_notes.py search 内在世界 --type folder --exact")
        print("  python download_notes.py search 笔记 --dir ./my_notes")
        print("  python download_notes.py id ABC123 folder")
        sys.exit(1)
    
    command = sys.argv[1]
    downloader = YoudaoNoteDownloader()
    
    # 解析本地目录选项
    local_dir = "./youdaonote"
    if "--dir" in sys.argv:
        dir_index = sys.argv.index("--dir")
        if dir_index + 1 < len(sys.argv):
            local_dir = sys.argv[dir_index + 1]
    
    if command == "search":
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
        
        downloader.search_and_download(search_name, search_type, exact_match, local_dir)
    
    elif command == "id":
        if len(sys.argv) < 4:
            print("❌ 请提供ID和类型")
            sys.exit(1)
        
        item_id = sys.argv[2]
        item_type = sys.argv[3]
        
        downloader.download_by_id(item_id, item_type, local_dir)
    
    else:
        print(f"❌ 未知命令: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
