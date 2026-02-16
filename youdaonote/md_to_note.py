"""
Markdown 转有道云笔记 JSON 格式

将 Markdown 文本转换为有道云笔记的 JSON 格式，用于上传普通笔记（.note）
"""

import json
import re
import uuid
from typing import List, Dict, Any


def _generate_id() -> str:
    """生成随机 ID（4 字符 + 时间戳风格）"""
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    import random
    prefix = "".join(random.choice(chars) for _ in range(4))
    timestamp = str(int(__import__("time").time() * 1000))[-13:]
    return f"{prefix}-{timestamp}"


def _create_text_node(text: str, attrs: List[Dict] = None) -> Dict:
    """
    创建文本节点
    
    :param text: 文本内容
    :param attrs: 文本属性（粗体、斜体等）
    :return: 节点字典
    """
    node = {"8": text}
    if attrs:
        node["9"] = attrs
    return node


def _create_paragraph(text: str, text_attrs: List[Dict] = None) -> Dict:
    """
    创建普通段落
    
    :param text: 段落文本
    :param text_attrs: 文本属性
    :return: 段落字典
    """
    text_node = _create_text_node(text, text_attrs)
    return {
        "3": _generate_id(),
        "5": [{
            "2": "2",
            "3": _generate_id(),
            "7": [text_node]
        }]
    }


def _create_heading(text: str, level: int) -> Dict:
    """
    创建标题
    
    :param text: 标题文本
    :param level: 标题级别（1-6）
    :return: 标题字典
    """
    return {
        "3": _generate_id(),
        "4": {"l": f"h{level}"},
        "5": [{
            "2": "2",
            "3": _generate_id(),
            "7": [{"8": text}]
        }],
        "6": "h"
    }


def _create_list_item(text: str, ordered: bool = False, level: int = 1) -> Dict:
    """
    创建列表项
    
    :param text: 列表文本
    :param ordered: 是否有序列表
    :param level: 缩进级别
    :return: 列表项字典
    """
    list_type = "ordered" if ordered else "unordered"
    return {
        "3": _generate_id(),
        "4": {"lt": list_type, "ll": level},
        "5": [{
            "2": "2",
            "3": _generate_id(),
            "7": [{"8": text}]
        }],
        "6": "l"
    }


def _create_code_block(code: str, language: str = "") -> Dict:
    """
    创建代码块
    
    :param code: 代码内容
    :param language: 编程语言
    :return: 代码块字典
    """
    lines = code.split("\n")
    code_lines = []
    for line in lines:
        code_lines.append({
            "3": _generate_id(),
            "5": [{
                "2": "2",
                "3": _generate_id(),
                "7": [{"8": line}]
            }]
        })
    
    return {
        "3": _generate_id(),
        "4": {"la": language},
        "5": code_lines,
        "6": "cd"
    }


def _create_quote(text: str) -> Dict:
    """
    创建引用块
    
    :param text: 引用文本
    :return: 引用块字典
    """
    lines = text.split("\n")
    quote_lines = []
    for line in lines:
        quote_lines.append({
            "3": _generate_id(),
            "5": [{
                "2": "2",
                "3": _generate_id(),
                "7": [{"8": line}]
            }]
        })
    
    return {
        "3": _generate_id(),
        "5": quote_lines,
        "6": "q"
    }


def _create_image(url: str, alt: str = "") -> Dict:
    """
    创建图片
    
    :param url: 图片 URL
    :param alt: 替代文本
    :return: 图片字典
    """
    return {
        "3": _generate_id(),
        "4": {"u": url},
        "6": "im"
    }


def _create_link(text: str, url: str) -> Dict:
    """
    创建链接（作为段落的一部分）
    
    :param text: 链接文本
    :param url: 链接 URL
    :return: 链接节点
    """
    return {
        "3": _generate_id(),
        "4": {"hf": url},
        "5": [{
            "2": "2",
            "3": _generate_id(),
            "7": [{"8": text}]
        }],
        "6": "li"
    }


def _parse_inline_formatting(text: str) -> List[Dict]:
    """
    解析行内格式（粗体、斜体、链接等）
    
    :param text: 原始文本
    :return: 节点列表
    """
    nodes = []
    
    # 简单处理：暂时不解析行内格式，直接作为纯文本
    # 后续可以增加对 **粗体**、*斜体*、[链接](url) 等的解析
    if text:
        nodes.append(_create_text_node(text))
    
    return nodes


def _parse_markdown_line(line: str) -> Dict:
    """
    解析单行 Markdown
    
    :param line: Markdown 行
    :return: 节点字典
    """
    line = line.rstrip()
    
    # 空行
    if not line:
        return _create_paragraph("")
    
    # 标题 (# ## ### etc)
    heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
    if heading_match:
        level = len(heading_match.group(1))
        text = heading_match.group(2)
        return _create_heading(text, level)
    
    # 无序列表 (- * +)
    unordered_match = re.match(r'^(\s*)[-*+]\s+(.+)$', line)
    if unordered_match:
        indent = len(unordered_match.group(1))
        level = (indent // 2) + 1 if indent else 1
        text = unordered_match.group(2)
        return _create_list_item(text, ordered=False, level=level)
    
    # 有序列表 (1. 2. etc)
    ordered_match = re.match(r'^(\s*)\d+\.\s+(.+)$', line)
    if ordered_match:
        indent = len(ordered_match.group(1))
        level = (indent // 2) + 1 if indent else 1
        text = ordered_match.group(2)
        return _create_list_item(text, ordered=True, level=level)
    
    # 引用 (>)
    quote_match = re.match(r'^>\s*(.*)$', line)
    if quote_match:
        text = quote_match.group(1)
        return _create_quote(text)
    
    # 图片 ![alt](url)
    image_match = re.match(r'^!\[([^\]]*)\]\(([^)]+)\)$', line)
    if image_match:
        alt = image_match.group(1)
        url = image_match.group(2)
        return _create_image(url, alt)
    
    # 分隔线 (--- *** ___)
    if re.match(r'^[-*_]{3,}$', line):
        return _create_paragraph("---")
    
    # 普通段落
    return _create_paragraph(line)


def markdown_to_note_json(md_content: str) -> str:
    """
    将 Markdown 转换为有道云笔记 JSON 格式
    
    :param md_content: Markdown 文本
    :return: 有道云笔记 JSON 字符串
    """
    lines = md_content.split("\n")
    content_list = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # 代码块处理
        code_match = re.match(r'^```(\w*)$', line)
        if code_match:
            language = code_match.group(1)
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code_lines.append(lines[i])
                i += 1
            code_content = "\n".join(code_lines)
            content_list.append(_create_code_block(code_content, language))
            i += 1  # 跳过结束的 ```
            continue
        
        # 多行引用处理
        if line.startswith(">"):
            quote_lines = []
            while i < len(lines) and lines[i].startswith(">"):
                quote_text = re.sub(r'^>\s*', '', lines[i])
                quote_lines.append(quote_text)
                i += 1
            quote_content = "\n".join(quote_lines)
            content_list.append(_create_quote(quote_content))
            continue
        
        # 单行处理
        node = _parse_markdown_line(line)
        content_list.append(node)
        i += 1
    
    # 构建完整的 JSON 结构
    doc_id = _generate_id()
    result = {
        "2": "1",
        "3": doc_id,
        "4": {
            "version": 1,
            "incompatibleVersion": 0,
            "fv": "0"
        },
        "5": content_list,
        "title": "",
        "__compress__": True
    }
    
    return json.dumps(result, ensure_ascii=False)


def note_json_to_markdown(json_content: str) -> str:
    """
    将有道云笔记 JSON 格式转换为 Markdown（使用现有的 covert.py 逻辑）
    
    :param json_content: 有道云笔记 JSON 字符串
    :return: Markdown 文本
    """
    # 复用现有的转换逻辑
    from youdaonote.covert import JsonConvert
    
    try:
        json_data = json.loads(json_content)
    except json.JSONDecodeError:
        return json_content
    
    json_contents = json_data.get("5", [])
    new_content_list = []
    converter = JsonConvert()
    
    for content in json_contents:
        content_type = content.get("6")
        
        if content_type:
            convert_func = getattr(converter, f"convert_{content_type}_func", None)
            if convert_func:
                line_content = convert_func(content)
            else:
                line_content = converter.convert_text_func(content)
        else:
            line_content = converter.convert_text_func(content)
        
        if line_content:
            new_content_list.append(line_content)
    
    return "\n\n".join(new_content_list)
