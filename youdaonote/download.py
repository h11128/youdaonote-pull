#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
有道云笔记下载引擎
统一的下载逻辑，供 CLI 和 GUI 使用
"""

import json
import logging
import os
import platform
import re
import xml.etree.ElementTree as ET
from enum import Enum
from typing import Dict, Optional, Tuple

from youdaonote.api import YoudaoNoteApi
from youdaonote.covert import YoudaoNoteConvert
from youdaonote.image import ImagePull
from youdaonote.common import get_config_directory, get_script_directory

# 尝试导入 Windows 特定模块
try:
    from win32_setctime import setctime
    HAS_WIN32_SETCTIME = True
except ImportError:
    HAS_WIN32_SETCTIME = False


MARKDOWN_SUFFIX = ".md"


class FileType(Enum):
    """文件类型枚举"""
    OTHER = 0
    MARKDOWN = 1
    XML = 2
    JSON = 3


class FileAction(Enum):
    """文件操作枚举"""
    SKIP = "跳过"
    ADD = "新增"
    UPDATE = "更新"


class YoudaoNoteDownload:
    """
    有道云笔记下载引擎
    提供统一的文件和文件夹下载功能
    """

    def __init__(self, api: YoudaoNoteApi, smms_secret_token: str = "", 
                 is_relative_path: bool = True):
        """
        初始化下载引擎
        :param api: 已登录的 YoudaoNoteApi 实例
        :param smms_secret_token: SM.MS 图床 token（可选）
        :param is_relative_path: 是否使用相对路径
        """
        self.api = api
        self.smms_secret_token = smms_secret_token
        self.is_relative_path = is_relative_path
        
        # 文件名中需要替换的特殊字符
        self._regex_symbol = re.compile(r"[<]")
        self._del_regex_symbol = re.compile(r'[\\/":\|\*\?#>]')

    def download_file(self, file_id: str, file_name: str, local_dir: str,
                      modify_time: int = 0, create_time: int = 0,
                      convert_to_md: bool = True) -> bool:
        """
        下载单个文件
        :param file_id: 文件 ID
        :param file_name: 文件名
        :param local_dir: 本地目录
        :param modify_time: 修改时间（毫秒时间戳）
        :param create_time: 创建时间（毫秒时间戳）
        :param convert_to_md: 是否转换为 Markdown
        :return: 是否成功
        """
        try:
            # 优化文件名
            file_name = self._optimize_file_name(file_name)
            youdao_file_suffix = os.path.splitext(file_name)[1]
            original_file_path = os.path.join(local_dir, file_name).replace("\\", "/")

            # 判断文件类型
            file_type = self._judge_file_type(file_id, youdao_file_suffix)

            # 确定本地文件路径
            if file_type != FileType.OTHER and convert_to_md:
                local_file_path = os.path.join(
                    local_dir, 
                    os.path.splitext(file_name)[0] + MARKDOWN_SUFFIX
                ).replace("\\", "/")
            else:
                local_file_path = original_file_path

            # 判断文件操作
            file_action = self._get_file_action(local_file_path, modify_time / 1000 if modify_time else 0)
            
            if file_action == FileAction.SKIP:
                logging.debug(f"跳过文件: {local_file_path}")
                return True

            if file_action == FileAction.UPDATE:
                # 删除旧文件
                if os.path.exists(local_file_path):
                    os.remove(local_file_path)

            # 下载文件
            self._download_and_convert(file_id, original_file_path, local_file_path, 
                                       file_type, youdao_file_suffix, convert_to_md)

            # 设置文件时间
            self._set_file_time(local_file_path, create_time / 1000 if create_time else 0,
                               modify_time / 1000 if modify_time else 0)

            tip = f"，原格式为 {file_type.name}" if file_type != FileType.OTHER else ""
            logging.info(f"{file_action.value}「{local_file_path}」{tip}")
            
            return True

        except Exception as e:
            logging.error(f"下载文件 {file_name} 失败: {e}")
            return False

    def download_folder(self, folder_id: str, folder_name: str, 
                        local_dir: str) -> bool:
        """
        下载整个文件夹（递归）
        :param folder_id: 文件夹 ID
        :param folder_name: 文件夹名
        :param local_dir: 本地目录
        :return: 是否成功
        """
        try:
            # 创建本地文件夹
            local_folder_path = os.path.join(local_dir, folder_name).replace("\\", "/")
            if not os.path.exists(local_folder_path):
                os.makedirs(local_folder_path, exist_ok=True)

            logging.info(f"📁 下载文件夹: {folder_name} -> {local_folder_path}")

            # 递归下载
            self._download_dir_recursively(folder_id, local_folder_path)
            
            logging.info(f"✅ 文件夹下载完成: {folder_name}")
            return True

        except Exception as e:
            logging.error(f"下载文件夹 {folder_name} 失败: {e}")
            return False

    def _download_dir_recursively(self, dir_id: str, local_dir: str):
        """
        递归下载目录
        :param dir_id: 目录 ID
        :param local_dir: 本地目录
        """
        dir_info = self.api.get_dir_info_by_id(dir_id)
        entries = dir_info.get('entries', [])

        for entry in entries:
            file_entry = entry.get('fileEntry', {})
            entry_id = file_entry.get('id', '')
            name = file_entry.get('name', '')
            is_dir = file_entry.get('dir', False)

            if is_dir:
                # 递归下载子目录
                sub_dir = os.path.join(local_dir, name).replace("\\", "/")
                if not os.path.exists(sub_dir):
                    os.makedirs(sub_dir, exist_ok=True)
                self._download_dir_recursively(entry_id, sub_dir)
            else:
                # 下载文件
                modify_time = file_entry.get('modifyTimeForSort', 0)
                create_time = file_entry.get('createTimeForSort', 0)
                self.download_file(entry_id, name, local_dir, modify_time, create_time)

    def _optimize_file_name(self, name: str) -> str:
        """
        优化文件名，移除特殊字符
        :param name: 原文件名
        :return: 优化后的文件名
        """
        # 去除换行符
        name = name.replace("\n", "")
        # 去除首尾空格
        name = name.strip()
        # 替换特殊字符
        name = self._regex_symbol.sub("_", name)
        name = self._del_regex_symbol.sub("", name)
        return name

    def _judge_file_type(self, file_id: str, youdao_file_suffix: str) -> FileType:
        """
        判断文件类型
        :param file_id: 文件 ID
        :param youdao_file_suffix: 文件后缀
        :return: 文件类型
        """
        if youdao_file_suffix == MARKDOWN_SUFFIX:
            return FileType.MARKDOWN
        
        if youdao_file_suffix in [".note", ".clip", ""]:
            response = self.api.get_file_by_id(file_id)
            content = response.content
            
            if content[:5] == b"<?xml":
                return FileType.XML
            elif content.startswith(b'{"'):
                return FileType.JSON
        
        return FileType.OTHER

    def _get_file_action(self, local_file_path: str, modify_time: float) -> FileAction:
        """
        判断文件操作类型
        :param local_file_path: 本地文件路径
        :param modify_time: 修改时间（秒）
        :return: 文件操作类型
        """
        if not os.path.exists(local_file_path):
            return FileAction.ADD

        # 如果云端修改时间小于等于本地文件时间，跳过
        if modify_time and modify_time <= os.path.getmtime(local_file_path):
            return FileAction.SKIP

        return FileAction.UPDATE

    def _download_and_convert(self, file_id: str, original_file_path: str,
                              local_file_path: str, file_type: FileType,
                              youdao_file_suffix: str, convert_to_md: bool):
        """
        下载并转换文件
        :param file_id: 文件 ID
        :param original_file_path: 原始文件路径
        :param local_file_path: 本地文件路径
        :param file_type: 文件类型
        :param youdao_file_suffix: 原始后缀
        :param convert_to_md: 是否转换为 Markdown
        """
        # 下载文件
        response = self.api.get_file_by_id(file_id)
        with open(original_file_path, "wb") as f:
            f.write(response.content)

        # 转换为 Markdown
        if convert_to_md:
            if file_type == FileType.XML:
                try:
                    YoudaoNoteConvert.covert_xml_to_markdown(original_file_path)
                except ET.ParseError:
                    logging.info("此 note 笔记为旧格式 HTML，转换为 Markdown...")
                    YoudaoNoteConvert.covert_html_to_markdown(original_file_path)
                except Exception as e:
                    logging.warning(f"XML 转换失败，跳过: {e}")
            elif file_type == FileType.JSON:
                YoudaoNoteConvert.covert_json_to_markdown(original_file_path)

        # 处理图片链接
        if file_type != FileType.OTHER or youdao_file_suffix == MARKDOWN_SUFFIX:
            image_pull = ImagePull(self.api, self.smms_secret_token, self.is_relative_path)
            image_pull.migration_ydnote_url(local_file_path)

    def _set_file_time(self, file_path: str, create_time: float, modify_time: float):
        """
        设置文件时间
        :param file_path: 文件路径
        :param create_time: 创建时间（秒）
        :param modify_time: 修改时间（秒）
        """
        if not create_time and not modify_time:
            return

        try:
            if platform.system() == "Windows" and HAS_WIN32_SETCTIME:
                if create_time:
                    setctime(file_path, create_time)
            
            if modify_time:
                os.utime(file_path, (create_time or modify_time, modify_time))
        except Exception as e:
            logging.warning(f"设置文件时间失败: {e}")

    def download_by_search_result(self, result: Dict, local_dir: str) -> bool:
        """
        根据搜索结果下载
        :param result: 搜索结果字典，包含 id, name, is_dir, entry 等
        :param local_dir: 本地目录
        :return: 是否成功
        """
        if result.get('is_dir'):
            return self.download_folder(
                result['id'], 
                result['name'], 
                local_dir
            )
        else:
            entry = result.get('entry', {})
            return self.download_file(
                result['id'],
                result['name'],
                local_dir,
                entry.get('modifyTimeForSort', 0),
                entry.get('createTimeForSort', 0)
            )

    def pull_all(self, local_dir: str = None, ydnote_dir: str = None) -> bool:
        """
        全量导出所有笔记
        :param local_dir: 本地目录，为空则使用默认目录
        :param ydnote_dir: 只导出指定的有道云目录，为空则导出全部
        :return: 是否成功
        """
        try:
            # 确定本地目录
            if not local_dir:
                local_dir = os.path.join(get_script_directory(), "youdaonote")
            
            if not os.path.exists(local_dir):
                os.makedirs(local_dir, exist_ok=True)
            
            # 获取根目录 ID
            root_info = self.api.get_root_dir_info_id()
            root_id = root_info.get('fileEntry', {}).get('id')
            
            if not root_id:
                logging.error("无法获取根目录 ID")
                return False
            
            # 如果指定了目录，找到该目录
            if ydnote_dir:
                dir_info = self.api.get_dir_info_by_id(root_id)
                found = False
                for entry in dir_info.get('entries', []):
                    file_entry = entry.get('fileEntry', {})
                    if file_entry.get('name') == ydnote_dir:
                        root_id = file_entry.get('id')
                        found = True
                        break
                if not found:
                    logging.error(f"未找到指定目录: {ydnote_dir}")
                    return False
            
            logging.info(f"开始全量导出到: {local_dir}")
            self._download_dir_recursively(root_id, local_dir)
            logging.info("全量导出完成!")
            return True
            
        except Exception as e:
            logging.error(f"全量导出失败: {e}")
            return False


def load_config() -> Tuple[Dict, str]:
    """
    加载配置文件
    :return: (config_dict, error_msg)
    """
    config_path = os.path.join(get_config_directory(), "config.json")
    
    if not os.path.exists(config_path):
        # 返回默认配置
        return {
            "local_dir": "",
            "ydnote_dir": "",
            "smms_secret_token": "",
            "is_relative_path": True
        }, ""
    
    try:
        with open(config_path, "rb") as f:
            config_str = f.read().decode("utf-8")
        config_dict = json.loads(config_str)
        return config_dict, ""
    except json.JSONDecodeError as e:
        return {}, f"config.json 格式错误: {e}"
    except Exception as e:
        return {}, f"读取配置失败: {e}"
