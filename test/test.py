# -*- coding:utf-8 -*-
"""
有道云笔记导出工具测试用例
"""

from __future__ import absolute_import

import os
import sys
import unittest
from unittest.mock import Mock, mock_open, patch

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from youdaonote.api import YoudaoNoteApi
from youdaonote.covert import YoudaoNoteConvert
from youdaonote.download import YoudaoNoteDownload, load_config


# 使用 test_cookies.json 作为 cookies 地址，避免 cookies.json 数据被错误覆盖
TEST_COOKIES_PATH = "test_cookies.json"


class MockResponse:
    def __init__(self, json_data, status_code):
        self.json_data = json_data
        self.status_code = status_code

    def json(self):
        return self.json_data


class YoudaoNoteApiTest(unittest.TestCase):
    """
    测试有道云笔记 API
    python -m pytest test/test.py::YoudaoNoteApiTest -v
    """

    TEST_COOKIES_PATH = "test_cookies.json"

    def test_cookies_login(self):
        """
        测试 cookies 登录
        python -m pytest test/test.py::YoudaoNoteApiTest::test_cookies_login -v
        """

        # 如果 cookies 文件不存在。期待：登录失败
        youdaonote_api = YoudaoNoteApi(cookies_path=self.TEST_COOKIES_PATH)
        message = youdaonote_api.login_by_cookies()
        self.assertTrue("No such file or directory" in message)

        # 如果 cookies 格式不对（少了一个 [）。期待：登录失败
        cookies_json_str = """{
                "cookies": 
                    ["YNOTE_CSTK", "fPk5IkDg", ".note.youdao.com", "/"],
                    ["YNOTE_LOGIN", "3||1591964671668", ".note.youdao.com", "/"],
                    ["YNOTE_SESS", "***", ".note.youdao.com", "/"],
                }"""

        youdaonote_api = YoudaoNoteApi(cookies_path=self.TEST_COOKIES_PATH)
        with patch(
            "builtins.open", mock_open(read_data=cookies_json_str.encode("utf-8"))
        ):
            message = youdaonote_api.login_by_cookies()
            self.assertEqual(message, "转换「{}」为字典时出现错误".format(self.TEST_COOKIES_PATH))

        # 如果 cookies 格式正确，但少了 YNOTE_CSTK。期待：登录失败
        cookies_json_str = """{"cookies": [
                                    ["YNOTE_LOGIN", "3||1591964671668", ".note.youdao.com", "/"],
                                    ["YNOTE_SESS", "***", ".note.youdao.com", "/"]
                                ]}"""
        youdaonote_api = YoudaoNoteApi(cookies_path=self.TEST_COOKIES_PATH)
        with patch(
            "builtins.open", mock_open(read_data=cookies_json_str.encode("utf-8"))
        ):
            message = youdaonote_api.login_by_cookies()
            self.assertEqual(message, "YNOTE_CSTK 字段为空")

        # 如果 cookies 格式正确，并包含 YNOTE_CSTK。期待：登录成功
        cookies_json_str = """{"cookies": [
                                    ["YNOTE_CSTK", "fPk5IkDg", ".note.youdao.com", "/"],
                                    ["YNOTE_LOGIN", "3||1591964671668", ".note.youdao.com", "/"],
                                    ["YNOTE_SESS", "***", ".note.youdao.com", "/"]
                                ]}"""
        youdaonote_api = YoudaoNoteApi(cookies_path=self.TEST_COOKIES_PATH)
        with patch(
            "builtins.open", mock_open(read_data=cookies_json_str.encode("utf-8"))
        ):
            message = youdaonote_api.login_by_cookies()
            self.assertFalse(message)
            self.assertEqual(youdaonote_api.cstk, "fPk5IkDg")

    def test_get_root_dir_info_id(self):
        """
        测试获取有道云笔记根目录信息
        python -m pytest test/test.py::YoudaoNoteApiTest::test_get_root_dir_info_id -v
        """

        # 先 mock 登录一下
        youdaonote_api = YoudaoNoteApi(cookies_path=TEST_COOKIES_PATH)
        with patch(
            "youdaonote.api.YoudaoNoteApi._covert_cookies",
            return_value=[["YNOTE_CSTK", "fPk5IkDg", ".note.youdao.com", "/"]],
        ):
            error_msg = youdaonote_api.login_by_cookies()
            self.assertFalse(error_msg)

        # 接口返回正常时。期待：根目录信息中有根目录 ID
        youdaonote_api.http_post = Mock(
            return_value=MockResponse(
                {"fileEntry": {"id": "test_root_id", "name": "ROOT"}}, 200
            )
        )
        root_dir_info = youdaonote_api.get_root_dir_info_id()
        self.assertEqual(root_dir_info["fileEntry"]["id"], "test_root_id")

    def test_get_dir_info_by_id(self):
        """
        测试根据目录 ID 获取目录下所有文件信息
        python -m pytest test/test.py::YoudaoNoteApiTest::test_get_dir_info_by_id -v
        """

        # 先 mock 登录一下
        youdaonote_api = YoudaoNoteApi(cookies_path=TEST_COOKIES_PATH)
        with patch(
            "youdaonote.api.YoudaoNoteApi._covert_cookies",
            return_value=[["YNOTE_CSTK", "fPk5IkDg", ".note.youdao.com", "/"]],
        ):
            error_msg = youdaonote_api.login_by_cookies()
            self.assertFalse(error_msg)

        # 当目录 ID 存在时。期待获取正常
        youdaonote_api.http_get = Mock(
            return_value=MockResponse(
                {
                    "count": 2,
                    "entries": [
                        {
                            "fileEntry": {
                                "id": "test_dir_id",
                                "name": "test_dir",
                                "dir": True,
                            }
                        },
                        {
                            "fileEntry": {
                                "id": "test_note_id",
                                "name": "test_note",
                                "dir": False,
                            }
                        },
                    ],
                },
                200,
            )
        )
        dir_info = youdaonote_api.get_dir_info_by_id(dir_id="test_dir_id")
        self.assertEqual(dir_info["count"], 2)
        self.assertTrue(dir_info["entries"][0]["fileEntry"]["dir"])
        self.assertFalse(dir_info["entries"][1]["fileEntry"]["dir"])

    def test_get_file_by_id(self):
        """
        测试根据文件 ID 获取文件内容
        python -m pytest test/test.py::YoudaoNoteApiTest::test_get_file_by_id -v
        """

        # 先 mock 登录一下
        youdaonote_api = YoudaoNoteApi(cookies_path=TEST_COOKIES_PATH)
        with patch(
            "youdaonote.api.YoudaoNoteApi._covert_cookies",
            return_value=[["YNOTE_CSTK", "fPk5IkDg", ".note.youdao.com", "/"]],
        ):
            error_msg = youdaonote_api.login_by_cookies()
            self.assertFalse(error_msg)

        # 当文件 ID 存在时。期待获取正常
        youdaonote_api.http_post = Mock(return_value=MockResponse({}, 200))
        file = youdaonote_api.get_file_by_id(file_id="test_note_id")
        self.assertTrue(file)


class YoudaoNoteCovertTest(unittest.TestCase):
    """
    测试格式转换
    python -m pytest test/test.py::YoudaoNoteCovertTest -v
    """

    def test_covert_xml_to_markdown_content(self):
        """
        测试 xml 转换 markdown
        python -m pytest test/test.py::YoudaoNoteCovertTest::test_covert_xml_to_markdown_content -v
        """
        content = YoudaoNoteConvert._covert_xml_to_markdown_content("test/test.note")
        with open("test/test.md", "rb") as f:
            content_target = f.read().decode()
        # 统一换行符为 \n 后再比较（fixture 文件可能是 CRLF 或 LF）
        self.assertEqual(content.replace("\r\n", "\n"), content_target.replace("\r\n", "\n"))

    def test_html_to_markdown(self):
        """
        测试 html 转换 markdown
        """
        from markdownify import markdownify as md

        new_content = md(
            f"""<div><span style='color: rgb(68, 68, 68); line-height: 1.5; font-family: "Monaco","Consolas","Lucida Console","Courier New","serif"; font-size: 12px; background-color: rgb(247, 247, 247);'><a href="http://bbs.pcbeta.com/viewthread-1095891-1-1.html">http://bbs.pcbeta.com/viewthread-1095891-1-1.html</a></span></div>"""
        )
        expected_content = """<http://bbs.pcbeta.com/viewthread-1095891-1-1.html>"""
        self.assertEqual(new_content, expected_content)

    def test_covert_json_to_markdown_content(self):
        """
        测试 json 转换 markdown
        python -m pytest test/test.py::YoudaoNoteCovertTest::test_covert_json_to_markdown_content -v
        """
        content = YoudaoNoteConvert._covert_json_to_markdown_content("test/test.json")
        with open("test/test-json.md", "rb") as f:
            content_target = f.read().decode()
        # 统一换行符为 \n 后再比较
        self.assertEqual(content.replace("\r\n", "\n"), content_target.replace("\r\n", "\n"))

    def test_covert_json_to_markdown_single_line(self):
        """
        测试 json 转换 markdown 单行富文本
        python -m pytest test/test.py::YoudaoNoteCovertTest::test_covert_json_to_markdown_single_line -v
        """
        line = YoudaoNoteConvert._covert_json_to_markdown_content("test/test-convert.json")
        with open("test/test-convert.md", "rb") as f:
            target = f.read().decode()
        # 统一换行符为 \n 后再比较
        self.assertEqual(line.replace("\r\n", "\n"), target.replace("\r\n", "\n"))


class YoudaoNoteDownloadTest(unittest.TestCase):
    """
    测试下载功能
    python -m pytest test/test.py::YoudaoNoteDownloadTest -v
    """

    TEST_CONFIG_PATH = "test_config.json"

    def test_load_config(self):
        """
        测试加载配置文件
        python -m pytest test/test.py::YoudaoNoteDownloadTest::test_load_config -v
        """
        # 当配置文件不存在时，返回默认配置
        with patch("os.path.exists", return_value=False):
            config, error = load_config()
            self.assertFalse(error)
            self.assertEqual(config.get("local_dir"), "")
            self.assertEqual(config.get("is_relative_path"), True)

    def test_check_local_dir(self):
        """
        测试本地目录创建
        python -m pytest test/test.py::YoudaoNoteDownloadTest::test_check_local_dir -v
        """
        test_dir = "test/test_download_dir"
        
        # 清理测试目录
        if os.path.exists(test_dir):
            os.rmdir(test_dir)
        
        # 测试创建目录
        os.makedirs(test_dir, exist_ok=True)
        self.assertTrue(os.path.exists(test_dir))
        
        # 清理
        os.rmdir(test_dir)


if __name__ == "__main__":
    unittest.main()
