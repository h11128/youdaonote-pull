# -*- coding:utf-8 -*-
"""
双向同步相关模块的单元测试

覆盖：
- SyncMetadata: 元数据增删改查
- markdown_to_note_json: Markdown → 有道 JSON 转换
- decide_action: 同步决策逻辑
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from youdaonote.sync_metadata import SyncMetadata
from youdaonote.md_to_note import markdown_to_note_json
from youdaonote.sync import decide_action, SyncAction


# ========== SyncMetadata 测试 ==========

class SyncMetadataTest(unittest.TestCase):
    """
    元数据管理测试
    python -m pytest test/test_sync.py::SyncMetadataTest -v
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.metadata_path = os.path.join(self.tmpdir, "sync_metadata.json")
        self.meta = SyncMetadata(metadata_path=self.metadata_path)

    def tearDown(self):
        if os.path.exists(self.metadata_path):
            os.remove(self.metadata_path)
        os.rmdir(self.tmpdir)

    def test_save_and_load(self):
        """保存后重新加载，数据一致"""
        # Given
        self.meta.set_file_info("a/b.md", "WEB123", cloud_mtime=1000, local_mtime=1000)

        # When
        self.meta.save()
        reloaded = SyncMetadata(metadata_path=self.metadata_path)

        # Then
        self.assertEqual(reloaded.get_file_id("a/b.md"), "WEB123")

    def test_set_and_get_file_info(self):
        """设置文件信息后能正确读取"""
        # When
        self.meta.set_file_info(
            "notes/test.md", "WEBabc123", cloud_mtime=2000,
            local_mtime=2000, parent_id="PARENT1", domain=1,
        )

        # Then
        info = self.meta.get_file_info("notes/test.md")
        self.assertIsNotNone(info)
        self.assertEqual(info["file_id"], "WEBabc123")
        self.assertEqual(info["cloud_mtime"], 2000)
        self.assertEqual(info["local_mtime"], 2000)
        self.assertEqual(info["parent_id"], "PARENT1")
        self.assertEqual(info["domain"], 1)

    def test_get_file_id_not_found(self):
        """查询不存在的路径返回 None"""
        self.assertIsNone(self.meta.get_file_id("no/such/file.md"))

    def test_remove_file(self):
        """删除后再查询返回 None"""
        # Given
        self.meta.set_file_info("x.md", "WEB1", cloud_mtime=1)

        # When
        self.meta.remove_file("x.md")

        # Then
        self.assertIsNone(self.meta.get_file_id("x.md"))

    def test_update_local_mtime(self):
        """更新本地修改时间"""
        # Given
        self.meta.set_file_info("x.md", "WEB1", cloud_mtime=100, local_mtime=100)

        # When
        self.meta.update_local_mtime("x.md", 200)

        # Then
        self.assertEqual(self.meta.get_file_info("x.md")["local_mtime"], 200)

    def test_update_cloud_mtime(self):
        """更新云端修改时间"""
        # Given
        self.meta.set_file_info("x.md", "WEB1", cloud_mtime=100, local_mtime=100)

        # When
        self.meta.update_cloud_mtime("x.md", 300)

        # Then
        self.assertEqual(self.meta.get_file_info("x.md")["cloud_mtime"], 300)

    def test_find_by_file_id(self):
        """根据云端 ID 反查本地路径"""
        # Given
        self.meta.set_file_info("a.md", "WEBA", cloud_mtime=1)
        self.meta.set_file_info("b.md", "WEBB", cloud_mtime=2)

        # Then
        self.assertEqual(self.meta.find_by_file_id("WEBA"), "a.md")
        self.assertEqual(self.meta.find_by_file_id("WEBB"), "b.md")
        self.assertIsNone(self.meta.find_by_file_id("WEBC"))

    def test_directory_operations(self):
        """目录的增删查"""
        # Given / When
        self.meta.set_dir_info("docs", "DIR1", parent_id="ROOT")

        # Then
        self.assertEqual(self.meta.get_dir_id("docs"), "DIR1")
        self.assertEqual(self.meta.find_by_dir_id("DIR1"), "docs")

        # When
        self.meta.remove_dir("docs")

        # Then
        self.assertIsNone(self.meta.get_dir_id("docs"))

    def test_get_all_files(self):
        """获取所有文件记录"""
        # Given
        self.meta.set_file_info("a.md", "A", cloud_mtime=1)
        self.meta.set_file_info("b.md", "B", cloud_mtime=2)

        # When
        all_files = self.meta.get_all_files()

        # Then
        self.assertEqual(len(all_files), 2)
        self.assertIn("a.md", all_files)
        self.assertIn("b.md", all_files)

    def test_path_normalization(self):
        """反斜杠路径被统一为正斜杠"""
        # When
        self.meta.set_file_info("a\\b\\c.md", "WEB1", cloud_mtime=1)

        # Then
        self.assertIsNotNone(self.meta.get_file_info("a/b/c.md"))

    def test_load_corrupt_file(self):
        """加载损坏的 JSON 文件不会崩溃"""
        # Given
        with open(self.metadata_path, "w") as f:
            f.write("this is not json")

        # When
        meta = SyncMetadata(metadata_path=self.metadata_path)

        # Then — 不崩溃，使用空数据
        self.assertEqual(meta.get_all_files(), {})


# ========== markdown_to_note_json 测试 ==========

class MarkdownToNoteJsonTest(unittest.TestCase):
    """
    Markdown 转有道 JSON 格式测试
    python -m pytest test/test_sync.py::MarkdownToNoteJsonTest -v
    """

    def test_empty_input(self):
        """空字符串返回合法 JSON"""
        result = markdown_to_note_json("")
        parsed = json.loads(result)
        self.assertIn("5", parsed)

    def test_heading(self):
        """标题被转换为 h 类型节点"""
        result = markdown_to_note_json("# 一级标题")
        parsed = json.loads(result)
        contents = parsed["5"]

        # 找到 type=h 的节点
        h_nodes = [c for c in contents if c.get("6") == "h"]
        self.assertTrue(len(h_nodes) >= 1)

        # level 应为 h1
        self.assertEqual(h_nodes[0]["4"]["l"], "h1")

    def test_heading_levels(self):
        """各级标题映射正确"""
        data = [
            ("# H1", "h1"),
            ("## H2", "h2"),
            ("### H3", "h3"),
        ]
        for md_line, expected_level in data:
            result = json.loads(markdown_to_note_json(md_line))
            h_nodes = [c for c in result["5"] if c.get("6") == "h"]
            self.assertTrue(
                len(h_nodes) >= 1,
                f"'{md_line}' 没有产生 h 节点",
            )
            self.assertEqual(
                h_nodes[0]["4"]["l"], expected_level,
                f"'{md_line}' 的 level 应为 {expected_level}",
            )

    def test_unordered_list(self):
        """无序列表被转换为 l 类型节点"""
        result = json.loads(markdown_to_note_json("- 列表项"))
        l_nodes = [c for c in result["5"] if c.get("6") == "l"]
        self.assertTrue(len(l_nodes) >= 1)
        self.assertEqual(l_nodes[0]["4"]["lt"], "unordered")

    def test_ordered_list(self):
        """有序列表被转换为 l 类型节点"""
        result = json.loads(markdown_to_note_json("1. 列表项"))
        l_nodes = [c for c in result["5"] if c.get("6") == "l"]
        self.assertTrue(len(l_nodes) >= 1)
        self.assertEqual(l_nodes[0]["4"]["lt"], "ordered")

    def test_code_block(self):
        """代码块被转换为 cd 类型节点"""
        md = "```python\nprint('hello')\n```"
        result = json.loads(markdown_to_note_json(md))
        cd_nodes = [c for c in result["5"] if c.get("6") == "cd"]
        self.assertTrue(len(cd_nodes) >= 1)
        self.assertEqual(cd_nodes[0]["4"]["la"], "python")

    def test_quote(self):
        """引用被转换为 q 类型节点"""
        result = json.loads(markdown_to_note_json("> 引用文字"))
        q_nodes = [c for c in result["5"] if c.get("6") == "q"]
        self.assertTrue(len(q_nodes) >= 1)

    def test_image(self):
        """图片被转换为 im 类型节点"""
        result = json.loads(markdown_to_note_json("![alt](http://img.png)"))
        im_nodes = [c for c in result["5"] if c.get("6") == "im"]
        self.assertTrue(len(im_nodes) >= 1)
        self.assertEqual(im_nodes[0]["4"]["u"], "http://img.png")

    def test_paragraph(self):
        """普通段落不带 type"""
        result = json.loads(markdown_to_note_json("这是一段普通文字"))
        plain = [c for c in result["5"] if "6" not in c]
        self.assertTrue(len(plain) >= 1)

    def test_mixed_content(self):
        """混合内容产生正确数量的节点"""
        md = "# 标题\n\n段落\n\n- 列表\n\n> 引用"
        result = json.loads(markdown_to_note_json(md))
        # 至少包含标题、段落（含空行段落）、列表、引用
        self.assertTrue(len(result["5"]) >= 4)

    def test_result_is_valid_json(self):
        """任何输入都返回合法 JSON"""
        test_inputs = ["", "hello", "# h1\n## h2", "```\ncode\n```"]
        for md in test_inputs:
            result = markdown_to_note_json(md)
            try:
                json.loads(result)
            except json.JSONDecodeError:
                self.fail(f"输入 {repr(md)} 产生了非法 JSON")


# ========== decide_action 测试 ==========

class DecideActionTest(unittest.TestCase):
    """
    同步决策逻辑测试
    python -m pytest test/test_sync.py::DecideActionTest -v
    """

    def test_neither_exists(self):
        """两边都不存在 → 跳过"""
        result = decide_action(
            local_exists=False, cloud_exists=False,
            local_mtime=None, cloud_mtime=None,
            meta_local_mtime=None, meta_cloud_mtime=None,
        )
        self.assertEqual(result, SyncAction.SKIP)

    def test_only_local(self):
        """只有本地 → 上传"""
        result = decide_action(
            local_exists=True, cloud_exists=False,
            local_mtime=1000, cloud_mtime=None,
            meta_local_mtime=None, meta_cloud_mtime=None,
        )
        self.assertEqual(result, SyncAction.UPLOAD)

    def test_only_cloud(self):
        """只有云端 → 下载"""
        result = decide_action(
            local_exists=False, cloud_exists=True,
            local_mtime=None, cloud_mtime=1000,
            meta_local_mtime=None, meta_cloud_mtime=None,
        )
        self.assertEqual(result, SyncAction.DOWNLOAD)

    def test_both_unchanged(self):
        """两边都没有变化 → 跳过"""
        result = decide_action(
            local_exists=True, cloud_exists=True,
            local_mtime=100, cloud_mtime=100,
            meta_local_mtime=100, meta_cloud_mtime=100,
        )
        self.assertEqual(result, SyncAction.SKIP)

    def test_only_local_changed(self):
        """只有本地修改 → 上传"""
        result = decide_action(
            local_exists=True, cloud_exists=True,
            local_mtime=200, cloud_mtime=100,
            meta_local_mtime=100, meta_cloud_mtime=100,
        )
        self.assertEqual(result, SyncAction.UPLOAD)

    def test_only_cloud_changed(self):
        """只有云端修改 → 下载"""
        result = decide_action(
            local_exists=True, cloud_exists=True,
            local_mtime=100, cloud_mtime=200,
            meta_local_mtime=100, meta_cloud_mtime=100,
        )
        self.assertEqual(result, SyncAction.DOWNLOAD)

    def test_both_changed_local_newer(self):
        """两边都改了，本地更新 → 上传"""
        result = decide_action(
            local_exists=True, cloud_exists=True,
            local_mtime=300, cloud_mtime=200,
            meta_local_mtime=100, meta_cloud_mtime=100,
        )
        self.assertEqual(result, SyncAction.UPLOAD)

    def test_both_changed_cloud_newer(self):
        """两边都改了，云端更新 → 下载"""
        result = decide_action(
            local_exists=True, cloud_exists=True,
            local_mtime=200, cloud_mtime=300,
            meta_local_mtime=100, meta_cloud_mtime=100,
        )
        self.assertEqual(result, SyncAction.DOWNLOAD)

    def test_both_changed_same_time(self):
        """两边都改了，时间相同 → 冲突"""
        result = decide_action(
            local_exists=True, cloud_exists=True,
            local_mtime=200, cloud_mtime=200,
            meta_local_mtime=100, meta_cloud_mtime=100,
        )
        self.assertEqual(result, SyncAction.CONFLICT)

    def test_no_metadata_both_exist(self):
        """没有元数据记录，两边都有 → 根据时间决定"""
        result = decide_action(
            local_exists=True, cloud_exists=True,
            local_mtime=500, cloud_mtime=300,
            meta_local_mtime=None, meta_cloud_mtime=None,
        )
        self.assertEqual(result, SyncAction.UPLOAD)


if __name__ == "__main__":
    unittest.main()
