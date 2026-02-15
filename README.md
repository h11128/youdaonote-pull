# youdaonote-pull

有道云笔记导出工具，将笔记下载到本地并转换为 Markdown 格式。

## 功能

- 📥 全量导出笔记（支持增量更新）
- 🔄 双向同步（本地 ↔ 云端）
- 📝 自动转换 XML/JSON 格式为 Markdown
- 🖼️ 下载图片到本地或上传到图床
- 🖥️ GUI 图形界面
- ⌨️ CLI 命令行工具
- 🔍 搜索笔记功能

## 安装

### 方式一：pip 安装（推荐）

```bash
pip install youdaonote-pull[full]
```

### 方式二：从源码安装

```bash
git clone https://github.com/DeppWang/youdaonote-pull.git
cd youdaonote-pull
pip install -r requirements.txt
```

## 快速开始

### 1. 登录

```bash
# 自动登录（会弹出浏览器，扫码或输入账号登录）
python -m youdaonote login
```

> 首次运行前需安装 Playwright：`pip install playwright && playwright install chromium`

### 2. 导出笔记

```bash
# 全量导出
python -m youdaonote pull

# 导出到指定目录
python -m youdaonote pull --dir ./backup

# 只导出指定目录
python -m youdaonote pull --ydnote-dir 工作笔记
```

### 3. 双向同步

```bash
# 双向同步（云端和本地互相更新）
python -m youdaonote sync

# 只上传（本地 → 云端）
python -m youdaonote sync --push

# 只下载（云端 → 本地）
python -m youdaonote sync --pull

# 预览模式（查看会执行哪些操作，但不实际执行）
python -m youdaonote sync --dry-run

# 指定同步目录
python -m youdaonote sync --dir E:/Projects/notes
```

同步规则：
- 只有本地有的文件 → 上传到云端
- 只有云端有的文件 → 下载到本地
- 两边都有且有修改 → 较新的版本覆盖较旧的
- 支持 Markdown 和普通笔记格式

### 4. 其他命令

```bash
# 启动图形界面
python -m youdaonote gui

# 列出目录结构
python -m youdaonote list

# 搜索笔记
python -m youdaonote search 关键词

# 搜索并下载
python -m youdaonote download 关键词
```

## 项目结构

```
├── youdaonote/             # 核心包
│   ├── __main__.py         # CLI 入口
│   ├── gui.py              # GUI 界面
│   ├── api.py              # API 封装
│   ├── search.py           # 搜索引擎
│   ├── download.py         # 下载引擎
│   ├── upload.py           # 上传引擎
│   ├── sync.py             # 双向同步引擎
│   ├── sync_metadata.py    # 同步元数据管理
│   ├── md_to_note.py       # Markdown → 有道 JSON 转换
│   ├── cookies.py          # Cookie 管理
│   └── covert.py           # 格式转换（云端 → Markdown）
├── config/                 # 配置文件
│   ├── cookies.json        # 登录凭证（自动生成）
│   ├── config.json         # 导出配置
│   └── sync_metadata.json  # 同步元数据（自动生成）
└── tools/                  # 辅助工具
```

## 配置文件

编辑 `config/config.json`：

```json
{
    "local_dir": "",           // 本地目录（留空则当前目录）
    "ydnote_dir": "",          // 只导出指定目录（留空则全部）
    "smms_secret_token": "",   // SM.MS 图床 token（可选）
    "is_relative_path": true   // 图片使用相对路径
}
```

## 命令行参数

```bash
python -m youdaonote --help

# 可用命令
  login      登录有道云笔记（使用浏览器）
  gui        启动图形界面
  pull       全量导出所有笔记
  sync       双向同步笔记
  list       列出目录内容
  search     搜索文件或文件夹
  download   搜索并下载

# pull 参数
  --dir, -d       导出目录（默认: ./youdaonote）
  --ydnote-dir, -y  只导出有道云中的指定目录

# sync 参数
  --dir, -d       本地同步目录（默认从配置读取）
  --push          只上传（本地 → 云端）
  --pull          只下载（云端 → 本地）
  --dry-run       预览模式（不执行实际操作）

# search/download 参数
  keyword         搜索关键词
  --type, -t      搜索类型 (all/folder/file)
  --exact, -e     精确匹配
  --dir, -d       下载目录
```

## 常见问题

### Cookies 过期

重新运行登录命令：

```bash
python -m youdaonote login
```

### 缺少依赖

```bash
# 安装完整依赖
pip install youdaonote-pull[full]

# 或手动安装
pip install playwright && playwright install chromium
```

### GUI 启动失败

确保系统已安装 tkinter（Python 自带，通常无需额外安装）。

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest test/

# 格式化代码
black youdaonote/
```

## License

MIT
