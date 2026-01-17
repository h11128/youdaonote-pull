#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import queue
import os
import logging
import sys
import time
from typing import Dict, List

# 添加父目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 使用现有实现，避免重复代码
from core.api import YoudaoNoteApi
from download_notes import YoudaoNoteDownloader
from list_notes import YoudaoNoteLister


class YoudaoNoteGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("有道云笔记管理工具")
        self.root.geometry("1000x700")
        
        # 设置编码
        self.root.option_add('*TCombobox*Listbox.selectBackground', '#0078d4')
        
        # API实例和工具类
        self.youdaonote_api = None
        self.lister = None
        self.downloader = None
        
        # 数据存储
        self.current_dir_id = None
        self.current_path = ""
        self.download_queue = queue.Queue()
        # Tree项元数据存储
        self.item_meta: Dict[str, Dict] = {}

        # 搜索结果存储
        self.search_results = []
        self.is_search_mode = False
        
        # 创建界面
        self.create_widgets()
        
        # 启动时自动登录
        self.login()
    
    def create_widgets(self):
        """创建界面组件"""
        # 主框架
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 顶部工具栏（路径 + 导航）
        toolbar_frame = ttk.Frame(main_frame)
        toolbar_frame.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(toolbar_frame, text="当前路径:").pack(side=tk.LEFT)
        self.path_var = tk.StringVar(value="/")
        self.path_label = ttk.Label(toolbar_frame, textvariable=self.path_var, relief=tk.SUNKEN, width=50)
        self.path_label.pack(side=tk.LEFT, padx=(5, 10))

        ttk.Button(toolbar_frame, text="刷新", command=self.refresh_current_dir).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar_frame, text="返回上级", command=self.go_back).pack(side=tk.LEFT, padx=5)

        # 搜索行（在路径下方）
        search_frame = ttk.Frame(main_frame)
        search_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(search_frame, text="搜索:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=30)
        self.search_entry.pack(side=tk.LEFT, padx=6)
        self.search_entry.bind("<Return>", lambda e: self.search_items())
        ttk.Button(search_frame, text="搜索", command=self.search_items).pack(side=tk.LEFT)

        # 垂直分割面板（可拖动）
        paned = ttk.PanedWindow(main_frame, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # 上半部分：文件/文件夹列表
        top_pane = ttk.Frame(paned)
        paned.add(top_pane, weight=3)
        self.create_file_list(top_pane)

        # 下半部分：操作行 + 状态/进度
        bottom_container = ttk.Frame(paned)
        paned.add(bottom_container, weight=1)

        # 操作行（在状态和进度上方）
        actions_frame = ttk.Frame(bottom_container)
        actions_frame.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(actions_frame, text="批量下载", command=self.batch_download).pack(side=tk.RIGHT, padx=5)
        ttk.Button(actions_frame, text="选择下载目录", command=self.select_download_dir).pack(side=tk.RIGHT, padx=5)

        # 状态和进度区域
        self.create_status_area(bottom_container)
    
    def create_file_list(self, parent):
        """创建文件列表"""
        # 文件列表框架
        list_frame = ttk.LabelFrame(parent, text="文件和文件夹")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # 创建Treeview
        columns = ("name", "type", "size", "modified", "id")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="tree headings", height=15)
        
        # 设置列标题
        self.tree.heading("#0", text="名称")
        self.tree.heading("name", text="完整名称")
        self.tree.heading("type", text="类型")
        self.tree.heading("size", text="大小")
        self.tree.heading("modified", text="修改时间")
        self.tree.heading("id", text="ID")
        
        # 设置列宽
        self.tree.column("#0", width=300)
        self.tree.column("name", width=200)
        self.tree.column("type", width=80)
        self.tree.column("size", width=100)
        self.tree.column("modified", width=150)
        self.tree.column("id", width=100)
        
        # 滚动条
        scrollbar_y = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        scrollbar_x = ttk.Scrollbar(list_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
        
        # 布局
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 绑定事件
        self.tree.bind("<Double-1>", self.on_item_double_click)
        self.tree.bind("<Button-3>", self.on_right_click)
        
        # 右键菜单
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="下载", command=self.download_selected)
        self.context_menu.add_command(label="进入文件夹", command=self.enter_folder)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="复制ID", command=self.copy_id)
        self.context_menu.add_command(label="复制路径", command=self.copy_path)
    
    def create_status_area(self, parent):
        """创建状态和进度区域"""
        status_frame = ttk.LabelFrame(parent, text="状态和进度")
        status_frame.pack(fill=tk.X, pady=(10, 0))
        
        # 状态标签
        self.status_var = tk.StringVar(value="就绪")
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var)
        self.status_label.pack(anchor=tk.W, padx=5, pady=2)
        
        # 进度条
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(status_frame, variable=self.progress_var, 
                                          maximum=100, length=400)
        self.progress_bar.pack(anchor=tk.W, padx=5, pady=2)
        
        # 下载目录显示
        self.download_dir_var = tk.StringVar(value=f"下载目录: {os.path.abspath('./youdaonote')}")
        self.download_dir_label = ttk.Label(status_frame, textvariable=self.download_dir_var)
        self.download_dir_label.pack(anchor=tk.W, padx=5, pady=2)
        
        # 当前下载目录
        self.download_dir = "./youdaonote"
    
    def safe_set_status(self, message):
        """安全地设置状态消息"""
        try:
            # 确保消息是安全的字符串
            safe_message = str(message).encode('utf-8', errors='ignore').decode('utf-8')
            self.status_var.set(safe_message)
        except Exception:
            self.status_var.set("状态更新失败")
    
    def login(self):
        """登录有道云笔记"""
        try:
            self.safe_set_status("正在登录...")
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            cookies_path = os.path.join(base_dir, "cookies.json")
            self.youdaonote_api = YoudaoNoteApi(cookies_path=cookies_path)
            error_msg = self.youdaonote_api.login_by_cookies()

            if error_msg:
                messagebox.showerror("登录失败", f"Cookie登录失败: {error_msg}")
                self.safe_set_status("登录失败")
                return False

            # 初始化工具类，传递cookies_path
            self.lister = YoudaoNoteLister(cookies_path=cookies_path)
            self.downloader = YoudaoNoteDownloader(cookies_path=cookies_path)
            # 复用已登录的 API
            self.lister.youdaonote_api = self.youdaonote_api
            self.downloader.youdaonote_api = self.youdaonote_api

            self.safe_set_status("登录成功")

            # 加载根目录
            self.load_root_directory()
            return True
            
        except Exception as e:
            error_msg = f"登录时出错: {e}"
            messagebox.showerror("错误", error_msg)
            self.safe_set_status("登录失败")
            return False
    
    def load_root_directory(self):
        """加载根目录"""
        try:
            root_info = self.youdaonote_api.get_root_dir_info_id()

            # 调试：打印返回的数据结构
            logging.info(f"根目录API返回: {root_info}")

            # 检查返回数据的有效性
            if not root_info:
                raise Exception("API返回空数据")

            # 检查是否是错误响应
            if 'error' in root_info:
                error_code = root_info.get('error', '未知')
                error_msg = root_info.get('message', '未知错误')
                scope = root_info.get('scope', '')

                if error_code == '207' or 'AUTHENTICATION' in error_msg:
                    raise Exception(
                        f"认证失败！Cookies已过期或无效。\n\n"
                        f"错误代码: {error_code}\n"
                        f"错误信息: {error_msg}\n\n"
                        f"请重新获取cookies.json文件：\n"
                        f"1. 在浏览器中登录 note.youdao.com\n"
                        f"2. 按F12打开开发者工具\n"
                        f"3. 导出cookies并保存为cookies.json"
                    )
                else:
                    raise Exception(f"API错误 [{error_code}]: {error_msg}")

            # 尝试多种可能的数据结构
            if 'fileEntry' in root_info:
                self.current_dir_id = root_info['fileEntry']['id']
            elif 'id' in root_info:
                # 有些API可能直接返回id
                self.current_dir_id = root_info['id']
            else:
                # 打印完整的返回数据以便调试
                raise Exception(f"无法从API返回中找到ID。返回数据: {list(root_info.keys())}")

            self.current_path = "/"
            self.path_var.set(self.current_path)
            self.load_directory_contents(self.current_dir_id)
        except KeyError as e:
            error_msg = f"加载根目录失败: 缺少字段 {e}\n返回数据: {root_info if 'root_info' in locals() else '无'}"
            logging.error(error_msg)
            messagebox.showerror("错误", error_msg)
        except Exception as e:
            error_msg = f"加载根目录失败: {e}"
            logging.error(error_msg)
            messagebox.showerror("错误", error_msg)
    
    def load_directory_contents(self, dir_id: str):
        """加载目录内容"""
        def load_in_thread():
            try:
                self.safe_set_status("正在加载目录内容...")
                
                # 清空当前列表
                for item in self.tree.get_children():
                    self.tree.delete(item)
                # 重置元数据存储
                self.item_meta = {}

                # 获取目录信息
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
                
                # 先添加文件夹
                for folder in folders:
                    self.add_tree_item(folder, True)
                
                # 再添加文件
                for file in files:
                    self.add_tree_item(file, False)
                
                self.safe_set_status(f"加载完成 - {len(folders)} 个文件夹, {len(files)} 个文件")
                
            except Exception as e:
                error_msg = f"加载失败: {e}"
                self.safe_set_status(error_msg)
                messagebox.showerror("错误", f"加载目录内容失败: {e}")
        
        # 在后台线程中加载
        threading.Thread(target=load_in_thread, daemon=True).start()

    def add_tree_item(self, file_entry: Dict, is_dir: bool):
        """添加树形列表项"""
        name = file_entry.get('name', '无名称')
        file_id = file_entry.get('id', '')
        size = file_entry.get('size', 0)
        modify_time = file_entry.get('modifyTimeForSort', 0)

        # 确保名称安全
        safe_name = self.get_safe_text(name)

        # 格式化大小
        if size > 1024 * 1024:
            size_str = f"{size / (1024 * 1024):.1f}MB"
        elif size > 1024:
            size_str = f"{size / 1024:.1f}KB"
        else:
            size_str = f"{size}B" if size > 0 else "-"

        # 格式化时间
        if modify_time > 0:
            time_str = time.strftime('%Y-%m-%d %H:%M', time.localtime(modify_time / 1000))
        else:
            time_str = "-"

        # 设置图标和类型
        if is_dir:
            item_type = "文件夹"
        else:
            item_type = "文件"

        # 添加到树形列表
        try:
            item_id = self.tree.insert("", tk.END,
                                      text=f"{safe_name}",
                                      values=(safe_name, item_type, size_str, time_str, file_id))

            # 存储额外信息（使用内存字典）
            self.item_meta[item_id] = {
                'is_dir': is_dir,
                'entry_data': file_entry,
                'full_path': None
            }
        except Exception as e:
            print(f"添加树项失败: {e}")

    def get_safe_text(self, text):
        """安全地处理文本"""
        if not text:
            return ""
        try:
            return str(text).encode('utf-8', errors='ignore').decode('utf-8')
        except Exception:
            return str(text).encode('ascii', errors='ignore').decode('ascii')

    def on_item_double_click(self, event):
        """双击事件处理"""
        item = self.tree.selection()[0] if self.tree.selection() else None
        if not item:
            return

        meta = self.item_meta.get(item, {})
        is_dir = bool(meta.get('is_dir'))
        if is_dir:
            self.enter_folder()

    def on_right_click(self, event):
        """右键点击事件"""
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)

    def enter_folder(self):
        """进入选中的文件夹"""
        item = self.tree.selection()[0] if self.tree.selection() else None
        if not item:
            return

        meta = self.item_meta.get(item, {})
        is_dir = bool(meta.get('is_dir'))
        if not is_dir:
            messagebox.showwarning("警告", "请选择一个文件夹")
            return

        folder_name = self.tree.item(item)["values"][0]
        folder_id = self.tree.item(item)["values"][4]

        # 更新路径
        if self.current_path == "/":
            self.current_path = f"/{folder_name}"
        else:
            self.current_path = f"{self.current_path}/{folder_name}"

        self.path_var.set(self.current_path)
        self.current_dir_id = folder_id

        # 重置搜索模式
        self.is_search_mode = False

        # 加载新目录
        self.load_directory_contents(folder_id)

    def go_back(self):
        """返回上级目录"""
        if self.current_path == "/" and not self.is_search_mode:
            return

        # 如果在搜索模式，返回到正常浏览模式
        if self.is_search_mode:
            self.is_search_mode = False
            self.search_var.set("")
            self.load_directory_contents(self.current_dir_id)
            return

        # 简化处理：重新加载根目录
        self.current_path = "/"
        self.path_var.set(self.current_path)
        self.load_root_directory()

    def refresh_current_dir(self):
        """刷新当前目录"""
        if self.is_search_mode:
            self.search_items()
        elif self.current_dir_id:
            self.load_directory_contents(self.current_dir_id)

    def select_download_dir(self):
        """选择下载目录"""
        dir_path = filedialog.askdirectory(title="选择下载目录")
        if dir_path:
            self.download_dir = dir_path
            self.download_dir_var.set(f"下载目录: {dir_path}")

    def search_items(self):
        """搜索功能"""
        search_term = self.search_var.get().strip()
        if not search_term:
            messagebox.showwarning("警告", "请输入搜索关键词")
            return

        if not self.youdaonote_api:
            messagebox.showerror("错误", "请先登录")
            return

        def search_in_thread():
            try:
                self.safe_set_status(f"正在搜索: {search_term}")
                self.is_search_mode = True

                # 清空当前列表
                for item in self.tree.get_children():
                    self.tree.delete(item)
                # 重置元数据存储
                self.item_meta = {}

                # 执行搜索
                results = self._search_by_name(search_term, "all", False)

                # 显示搜索结果
                for result in results:
                    self.add_search_result_item(result)

                self.safe_set_status(f"搜索完成 - 找到 {len(results)} 个结果")

            except Exception as e:
                error_msg = f"搜索失败: {e}"
                self.safe_set_status(error_msg)
                messagebox.showerror("错误", error_msg)

        threading.Thread(target=search_in_thread, daemon=True).start()

    def _search_by_name(self, name: str, search_type: str = "all", exact_match: bool = False):
        """搜索方法"""
        root_info = self.youdaonote_api.get_root_dir_info_id()

        # 兼容不同的API返回格式
        if 'fileEntry' in root_info:
            root_id = root_info['fileEntry']['id']
        elif 'id' in root_info:
            root_id = root_info['id']
        else:
            raise Exception(f"无法从API返回中找到根目录ID")

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

                # 安全处理名称
                safe_entry_name = self.get_safe_text(entry_name)
                current_entry_path = f"{current_path}/{safe_entry_name}" if current_path else safe_entry_name

                # 检查是否匹配
                if exact_match:
                    is_match = safe_entry_name == target_name
                else:
                    is_match = target_name.lower() in safe_entry_name.lower()

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
                        'entry': file_entry,
                        'path': current_entry_path,
                        'is_dir': is_dir
                    })

                # 如果是文件夹，继续递归搜索
                if is_dir:
                    self._search_recursively(entry_id, target_name, search_type, exact_match,
                                           results, current_entry_path)

        except Exception as e:
            print(f"搜索目录 {current_path} 时出错: {e}")

    def add_search_result_item(self, result):
        """添加搜索结果项"""
        file_entry = result['entry']
        path = result['path']
        is_dir = result['is_dir']

        name = file_entry.get('name', '无名称')
        file_id = file_entry.get('id', '')
        size = file_entry.get('size', 0)
        modify_time = file_entry.get('modifyTimeForSort', 0)

        # 安全处理名称和路径
        safe_name = self.get_safe_text(name)
        safe_path = self.get_safe_text(path)

        # 格式化大小
        if size > 1024 * 1024:
            size_str = f"{size / (1024 * 1024):.1f}MB"
        elif size > 1024:
            size_str = f"{size / 1024:.1f}KB"
        else:
            size_str = f"{size}B" if size > 0 else "-"

        # 格式化时间
        if modify_time > 0:
            time_str = time.strftime('%Y-%m-%d %H:%M', time.localtime(modify_time / 1000))
        else:
            time_str = "-"

        # 类型
        if is_dir:
            item_type = "文件夹"
        else:
            item_type = "文件"

        # 添加到树形列表，显示完整路径
        try:
            item_id = self.tree.insert("", tk.END,
                                      text=f"{safe_path}",
                                      values=(safe_name, item_type, size_str, time_str, file_id))

            # 存储额外信息（使用内存字典）
            self.item_meta[item_id] = {
                'is_dir': is_dir,
                'entry_data': file_entry,
                'full_path': safe_path
            }
        except Exception as e:
            print(f"添加搜索结果失败: {e}")

    def download_selected(self):
        """下载选中的项目"""
        item = self.tree.selection()[0] if self.tree.selection() else None
        if not item:
            messagebox.showwarning("警告", "请选择要下载的项目")
            return

        # 在后台线程中下载
        threading.Thread(target=self._download_item, args=(item,), daemon=True).start()

    def _download_item(self, item):
        """下载项目的后台方法"""
        try:
            name = self.tree.item(item)["values"][0]
            safe_name = self.get_safe_text(name)
            self.safe_set_status(f"正在下载: {safe_name}")
            self.progress_var.set(0)

            self._download_single_item(item)

            self.progress_var.set(100)
            self.safe_set_status(f"下载完成: {safe_name}")
            messagebox.showinfo("成功", f"'{safe_name}' 下载完成!")

        except Exception as e:
            error_msg = f"下载失败: {e}"
            self.safe_set_status(error_msg)
            messagebox.showerror("错误", error_msg)

    def _download_single_item(self, item):
        """下载单个项目"""
        name = self.tree.item(item)["values"][0]
        item_id = self.tree.item(item)["values"][4]
        meta = self.item_meta.get(item, {})
        is_dir = bool(meta.get('is_dir'))
        entry_data = meta.get('entry_data', {})

        # 安全处理名称
        safe_name = self.get_safe_text(name)

        if is_dir:
            folder_info = {
                'id': item_id,
                'name': safe_name,
                'path': safe_name,
                'is_dir': True
            }
            self.downloader._download_folder(folder_info, self.download_dir)
        else:
            file_info = {
                'id': item_id,
                'name': safe_name,
                'path': safe_name,
                'entry': {}
            }
            self.downloader._download_file(file_info, self.download_dir)

    def batch_download(self):
        """批量下载选中的项目"""
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("警告", "请选择要下载的项目")
            return

        if len(selected_items) == 1:
            self.download_selected()
            return

        # 确认批量下载
        result = messagebox.askyesno("确认", f"确定要下载选中的 {len(selected_items)} 个项目吗？")
        if not result:
            return

        # 在后台线程中批量下载
        threading.Thread(target=self._batch_download_items, args=(selected_items,), daemon=True).start()

    def _batch_download_items(self, items):
        """批量下载的后台方法"""
        try:
            total_items = len(items)
            success_count = 0

            for i, item in enumerate(items):
                name = self.tree.item(item)["values"][0]
                safe_name = self.get_safe_text(name)
                self.safe_set_status(f"正在下载 ({i+1}/{total_items}): {safe_name}")
                self.progress_var.set((i / total_items) * 100)

                try:
                    self._download_single_item(item)
                    success_count += 1
                except Exception as e:
                    print(f"下载 {safe_name} 失败: {e}")

            self.progress_var.set(100)
            self.safe_set_status(f"批量下载完成 - 成功: {success_count}/{total_items}")
            messagebox.showinfo("完成", f"批量下载完成！\n成功: {success_count}/{total_items}")

        except Exception as e:
            error_msg = f"批量下载失败: {e}"
            self.safe_set_status(error_msg)
            messagebox.showerror("错误", error_msg)

    def copy_id(self):
        """复制选中项目的ID"""
        item = self.tree.selection()[0] if self.tree.selection() else None
        if not item:
            return

        item_id = self.tree.item(item)["values"][4]
        self.root.clipboard_clear()
        self.root.clipboard_append(item_id)
        self.safe_set_status(f"已复制ID: {item_id}")

    def copy_path(self):
        """复制选中项目的路径"""
        item = self.tree.selection()[0] if self.tree.selection() else None
        if not item:
            return

        if self.is_search_mode:
            # 搜索模式下使用完整路径
            full_path = self.item_meta.get(item, {}).get('full_path')
            if full_path:
                path = full_path
            else:
                name = self.tree.item(item)["values"][0]
                path = name
        else:
            # 正常浏览模式
            name = self.tree.item(item)["values"][0]
            if self.current_path == "/":
                path = f"/{name}"
            else:
                path = f"{self.current_path}/{name}"

        safe_path = self.get_safe_text(path)
        self.root.clipboard_clear()
        self.root.clipboard_append(safe_path)
        self.safe_set_status(f"已复制路径: {safe_path}")


def main():
    """主函数"""
    # 配置日志
    logging.basicConfig(level=logging.INFO,
                       format='%(asctime)s - %(levelname)s - %(message)s',
                       handlers=[logging.StreamHandler()])

    # 创建主窗口
    root = tk.Tk()

    # 设置窗口图标（如果有的话）
    try:
        # 可以在这里设置图标
        pass
    except Exception:
        pass

    # 创建应用
    app = YoudaoNoteGUI(root)

    # 运行应用
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("应用被用户中断")
    except Exception as e:
        print(f"应用运行时出错: {e}")


if __name__ == "__main__":
    main()
