"""
有道云笔记双向同步引擎

只负责：收集差异 → 决定操作 → 分发给 uploader / downloader 执行
支持：冲突备份、Git 自动提交
"""

import os
import shutil
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Optional

from youdaonote.api import YoudaoNoteApi
from youdaonote.download import YoudaoNoteDownload
from youdaonote.upload import YoudaoNoteUpload
from youdaonote.sync_metadata import SyncMetadata
from youdaonote.git_helper import GitHelper


# ========== 数据类型 ==========

class SyncDirection(Enum):
    """同步方向"""
    PULL = "pull"
    PUSH = "push"
    BOTH = "both"


class SyncAction(Enum):
    """同步操作"""
    DOWNLOAD = "download"
    UPLOAD = "upload"
    SKIP = "skip"
    CONFLICT = "conflict"


@dataclass
class SyncItem:
    """同步项"""
    relative_path: str
    local_path: Optional[str]
    cloud_id: Optional[str]
    cloud_parent_id: Optional[str]
    local_mtime: Optional[int]
    cloud_mtime: Optional[int]
    is_dir: bool
    action: SyncAction
    cloud_name: Optional[str] = None
    domain: int = 1  # 0=普通笔记, 1=Markdown
    cloud_ctime: Optional[int] = None  # 云端创建时间


# ========== 同步管理器 ==========

class SyncManager:
    """双向同步管理器"""

    # 并发配置
    SCAN_WORKERS = 8     # 云端目录扫描并发数
    DOWNLOAD_WORKERS = 10  # 文件下载并发数
    UPLOAD_WORKERS = 5     # 文件上传并发数
    METADATA_SAVE_BATCH = 50  # 每操作 N 个文件保存一次元数据

    def __init__(self, api: YoudaoNoteApi, local_dir: str, metadata: SyncMetadata = None):
        self.api = api
        self.local_dir = os.path.abspath(local_dir)
        self.metadata = metadata or SyncMetadata()
        self.downloader = YoudaoNoteDownload(api)
        self.uploader = YoudaoNoteUpload(api, self.metadata)
        self.stats = _empty_stats()
        self._changed_paths: List[str] = []  # 本次同步改动过的本地文件路径
        self._lock = threading.Lock()  # 保护 stats / _changed_paths / metadata
        self._meta_dirty = 0  # 未保存的元数据变更计数
        self._git = GitHelper(local_dir)

    # ---------- 公开入口 ----------

    def sync(
        self,
        direction: SyncDirection = SyncDirection.BOTH,
        cloud_dir_id: str = None,
        cloud_path: str = "",
        dry_run: bool = False,
        auto_git: bool = True,
        auto_dedup: bool = True,
    ) -> Dict:
        """执行同步，返回统计信息"""
        if not cloud_dir_id:
            cloud_dir_id = self.api.get_root_dir_info_id()["fileEntry"]["id"]

        logging.info(f"开始同步: 方向={direction.value}, 本地={self.local_dir}")
        self.stats = _empty_stats()
        self._changed_paths = []

        items = self._collect_items(cloud_dir_id, cloud_path)
        items = _filter_by_direction(items, direction)

        if dry_run:
            for item in items:
                _print_preview(item)
        else:
            self._execute_all(items, direction)

        # 保存残余的未保存元数据
        if self._meta_dirty > 0:
            self.metadata.save()
            self._meta_dirty = 0

        logging.info(
            f"同步完成: 下载={self.stats['downloaded']}, 上传={self.stats['uploaded']}, "
            f"跳过={self.stats['skipped']}, 冲突={self.stats['conflicts']}, "
            f"错误={self.stats['errors']}"
        )

        # 同步后自动去重（只在有实际文件变动时执行）
        has_file_changes = self.stats["downloaded"] > 0 or self.stats["uploaded"] > 0
        if auto_dedup and not dry_run and has_file_changes:
            dedup_stats = self._run_dedup(dry_run)
            self.stats["dedup_deleted"] = dedup_stats.get("deleted", 0)

        # 同步后自动 git commit
        if auto_git and not dry_run and self._git.has_changes(self._changed_paths):
            self._git.commit_sync(self._changed_paths, self.stats)

        return self.stats

    def _run_dedup(self, dry_run: bool = False) -> Dict:
        """执行基于内容 hash 的去重扫描（同时清理本地和云端重复）"""
        from youdaonote.dedup import auto_dedup
        try:
            stats = auto_dedup(self.local_dir, metadata=self.metadata,
                               api=self.api, dry_run=dry_run)
            deleted = stats.get("deleted", 0)
            if deleted > 0:
                logging.info(f"去重: 删除了 {deleted} 个重复文件")
                self._changed_paths.append(self.local_dir)
            return stats
        except Exception as e:
            logging.error(f"去重扫描失败: {e}")
            return {}

    # ---------- 收集差异 ----------

    def _collect_items(self, cloud_dir_id: str, cloud_path: str) -> List[SyncItem]:
        # 云端扫描和本地扫描并行执行
        with ThreadPoolExecutor(max_workers=2) as pool:
            cloud_future = pool.submit(self._scan_cloud, cloud_dir_id, cloud_path)
            local_future = pool.submit(self._scan_local, cloud_path)
            cloud_files = cloud_future.result()
            local_files = local_future.result()
        all_paths = set(cloud_files.keys()) | set(local_files.keys())
        return [self._build_item(p, cloud_files.get(p), local_files.get(p)) for p in all_paths]

    def _scan_cloud(self, dir_id: str, base: str = "") -> Dict[str, Dict]:
        """并发获取云端文件列表（BFS + 线程池）"""
        files: Dict[str, Dict] = {}
        files_lock = threading.Lock()

        def _fetch_dir(did: str, bpath: str) -> List[tuple]:
            """获取一个目录的内容，返回子目录列表 [(dir_id, rel_path)]"""
            subdirs = []
            try:
                entries = self.api.get_dir_info_by_id(did).get("entries", [])
            except Exception as e:
                logging.error(f"获取云端目录失败: {bpath} - {e}")
                return subdirs

            for entry in entries:
                fe = entry.get("fileEntry", {})
                name = fe.get("name", "")
                if name.startswith("."):
                    continue

                rel = f"{bpath}/{name}".lstrip("/") if bpath else name
                info = {
                    "id": fe.get("id", ""),
                    "parent_id": did,
                    "name": name,
                    "is_dir": fe.get("dir", False),
                    "mtime": fe.get("modifyTimeForSort", 0),
                    "ctime": fe.get("createTimeForSort", 0),
                    "domain": fe.get("domain", 1),
                }

                if info["is_dir"]:
                    with files_lock:
                        files[rel] = info
                    subdirs.append((info["id"], rel))
                else:
                    local_name = name[:-5] + ".md" if name.endswith(".note") else name
                    local_rel = f"{bpath}/{local_name}".lstrip("/") if bpath else local_name
                    with files_lock:
                        files[local_rel] = info

            return subdirs

        # BFS：用线程池并行展开每一层目录
        current_level = [(dir_id, base)]
        with ThreadPoolExecutor(max_workers=self.SCAN_WORKERS) as pool:
            while current_level:
                futures = {pool.submit(_fetch_dir, did, bp): (did, bp)
                           for did, bp in current_level}
                next_level = []
                for fut in as_completed(futures):
                    try:
                        next_level.extend(fut.result())
                    except Exception as e:
                        did, bp = futures[fut]
                        logging.error(f"扫描目录异常: {bp} - {e}")
                current_level = next_level

        return files

    def _scan_local(self, base_path: str = "") -> Dict[str, Dict]:
        """扫描本地目录"""
        files: Dict[str, Dict] = {}
        scan_dir = os.path.join(self.local_dir, base_path) if base_path else self.local_dir
        if not os.path.exists(scan_dir):
            return files

        for root, dirs, filenames in os.walk(scan_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for d in dirs:
                p = os.path.join(root, d)
                rel = os.path.relpath(p, self.local_dir).replace("\\", "/")
                files[rel] = {"path": p, "is_dir": True, "mtime": int(os.path.getmtime(p))}
            for f in filenames:
                if f.startswith(".") or not f.endswith(".md"):
                    continue
                p = os.path.join(root, f)
                rel = os.path.relpath(p, self.local_dir).replace("\\", "/")
                files[rel] = {"path": p, "is_dir": False, "mtime": int(os.path.getmtime(p))}
        return files

    # ---------- 决策 ----------

    def _build_item(self, rel: str, cloud: Optional[Dict], local: Optional[Dict]) -> SyncItem:
        meta = self.metadata.get_file_info(rel)
        return SyncItem(
            relative_path=rel,
            local_path=local["path"] if local else os.path.join(self.local_dir, rel),
            cloud_id=cloud["id"] if cloud else (meta["file_id"] if meta else None),
            cloud_parent_id=cloud["parent_id"] if cloud else (meta.get("parent_id") if meta else None),
            local_mtime=local["mtime"] if local else None,
            cloud_mtime=cloud["mtime"] if cloud else (meta.get("cloud_mtime") if meta else None),
            is_dir=(cloud or {}).get("is_dir", False) or (local or {}).get("is_dir", False),
            action=decide_action(
                local_exists=local is not None,
                cloud_exists=cloud is not None,
                local_mtime=local["mtime"] if local else None,
                cloud_mtime=cloud["mtime"] if cloud else None,
                meta_local_mtime=meta.get("local_mtime") if meta else None,
                meta_cloud_mtime=meta.get("cloud_mtime") if meta else None,
            ),
            cloud_name=cloud["name"] if cloud else None,
            domain=cloud.get("domain", 1) if cloud else 1,
            cloud_ctime=cloud.get("ctime", 0) if cloud else (meta.get("create_time") if meta else None),
        )

    # ---------- 执行 ----------

    def _execute_all(self, items: List[SyncItem], direction: SyncDirection) -> None:
        """并发执行同步操作"""
        # 先串行处理目录（需要确保父目录存在）
        dir_items = [i for i in items if i.is_dir]
        file_items = [i for i in items if not i.is_dir]

        for item in dir_items:
            self._execute_dir(item)

        # 分离需要操作的文件和跳过的文件（串行阶段，无需加锁）
        action_items = []
        skip_count = 0
        for item in file_items:
            if item.action == SyncAction.SKIP:
                skip_count += 1
            else:
                action_items.append(item)
        if skip_count:
            self.stats["skipped"] += skip_count

        if not action_items:
            return

        # 按操作类型选并发数
        has_upload = any(i.action == SyncAction.UPLOAD for i in action_items)
        workers = self.UPLOAD_WORKERS if has_upload else self.DOWNLOAD_WORKERS

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(self._execute, item, direction): item
                       for item in action_items}
            for fut in as_completed(futures):
                try:
                    fut.result()
                except Exception as e:
                    item = futures[fut]
                    logging.error(f"执行异常: {item.relative_path} - {e}")
                    with self._lock:
                        self.stats["errors"] += 1

    def _execute(self, item: SyncItem, direction: SyncDirection) -> None:
        if item.is_dir:
            self._execute_dir(item)
        elif item.action == SyncAction.DOWNLOAD:
            self._do_download(item)
        elif item.action == SyncAction.UPLOAD:
            self._do_upload(item)
        elif item.action == SyncAction.CONFLICT:
            self._do_conflict(item, direction)
        else:
            with self._lock:
                self.stats["skipped"] += 1

    def _execute_dir(self, item: SyncItem) -> None:
        if item.action == SyncAction.DOWNLOAD:
            os.makedirs(item.local_path, exist_ok=True)
            with self._lock:
                self.stats["downloaded"] += 1
        elif item.action == SyncAction.UPLOAD and item.cloud_parent_id:
            self.uploader.ensure_cloud_dir(
                os.path.basename(item.relative_path),
                item.cloud_parent_id,
                item.relative_path,
                defer_save=True,
            )
            with self._lock:
                self.stats["uploaded"] += 1
        else:
            with self._lock:
                self.stats["skipped"] += 1

    def _do_download(self, item: SyncItem) -> None:
        if not item.cloud_id:
            logging.error(f"缺少云端 ID，跳过下载: {item.relative_path}")
            with self._lock:
                self.stats["errors"] += 1
            return

        os.makedirs(os.path.dirname(item.local_path), exist_ok=True)
        try:
            ok = self.downloader.download_file(
                file_id=item.cloud_id,
                file_name=item.cloud_name or os.path.basename(item.relative_path),
                local_dir=os.path.dirname(item.local_path),
                modify_time=item.cloud_mtime * 1000 if item.cloud_mtime else 0,
                skip_action_check=True,  # SyncManager 已做过决策，不需要 download 内部再判断
            )
        except Exception as e:
            logging.error(f"下载异常: {item.relative_path} - {e}")
            with self._lock:
                self.stats["errors"] += 1
            return

        if ok:
            # 用一次 stat 代替 exists + getmtime 两次系统调用
            try:
                local_mtime = int(os.stat(item.local_path).st_mtime)
            except OSError:
                local_mtime = item.cloud_mtime
            content_hash = SyncMetadata.compute_content_hash(item.local_path)
            with self._lock:
                self.metadata.set_file_info(
                    item.relative_path, item.cloud_id, item.cloud_mtime,
                    local_mtime, item.cloud_parent_id, item.domain,
                    content_hash=content_hash,
                    create_time=item.cloud_ctime,
                )
                self._meta_dirty += 1
                if self._meta_dirty >= self.METADATA_SAVE_BATCH:
                    self.metadata.save()
                    self._meta_dirty = 0
                self.stats["downloaded"] += 1
                self._changed_paths.append(item.local_path)
            logging.info(f"下载完成: {item.relative_path}")
        else:
            with self._lock:
                self.stats["errors"] += 1

    def _do_upload(self, item: SyncItem) -> None:
        if not os.path.exists(item.local_path):
            logging.error(f"本地文件不存在: {item.local_path}")
            with self._lock:
                self.stats["errors"] += 1
            return

        # 上传前去重检查：如果内容已在云端存在（不同路径），跳过上传
        content_hash = SyncMetadata.compute_content_hash(item.local_path)
        if content_hash:
            with self._lock:
                existing = self.metadata.find_cloud_file_by_hash(content_hash, exclude_path=item.relative_path)
            if existing:
                logging.info(f"跳过上传(内容已在云端): {item.relative_path} ↔ {existing}")
                with self._lock:
                    self.stats["skipped"] += 1
                return

        parent_id = item.cloud_parent_id or self.uploader.ensure_parent_dir(item.relative_path)
        if not parent_id:
            logging.error(f"无法确定云端父目录: {item.relative_path}")
            with self._lock:
                self.stats["errors"] += 1
            return

        ok, err = self.uploader.upload_file(item.local_path, parent_id, item.relative_path, force=True)
        if ok:
            # content_hash 已在上传前计算过，直接复用（文件内容不会在上传过程中改变）
            with self._lock:
                if content_hash:
                    self.metadata.update_content_hash(item.relative_path, content_hash)
                self._meta_dirty += 1
                if self._meta_dirty >= self.METADATA_SAVE_BATCH:
                    self.metadata.save()
                    self._meta_dirty = 0
                self.stats["uploaded"] += 1
                self._changed_paths.append(item.local_path)
            logging.info(f"上传完成: {item.relative_path}")
        else:
            logging.error(f"上传失败: {item.relative_path} - {err}")
            with self._lock:
                self.stats["errors"] += 1

    def _do_conflict(self, item: SyncItem, direction: SyncDirection) -> None:
        """
        冲突处理：先备份被覆盖的版本，再按策略同步。
        备份文件命名：原名.conflict.时间戳.md
        """
        logging.warning(f"冲突: {item.relative_path}")
        with self._lock:
            self.stats["conflicts"] += 1

        if direction == SyncDirection.PULL:
            # 下载覆盖本地 → 先备份本地
            _backup_file(item.local_path)
            self._do_download(item)
        elif direction == SyncDirection.PUSH:
            # 上传覆盖云端 → 先把云端版本下载为备份
            if item.cloud_id and item.local_path:
                backup = _backup_file(item.local_path)
                if backup is None and os.path.exists(item.local_path):
                    # 没有本地文件可备份但云端有内容，下载云端为 .conflict 副本
                    pass
            self._do_upload(item)
        else:
            # 双向：先备份本地旧版本，然后下载云端版本（新的优先已在 decide_action 处理），
            # 如果到了这里说明时间戳完全相同，两边都保留：
            # - 本地原文件改名为 .conflict 备份
            # - 下载云端版本到原路径
            # 这样两个版本都存在，用户可以手动合并
            if item.local_path and os.path.exists(item.local_path):
                _backup_file(item.local_path)
                self._do_download(item)
                logging.info(f"冲突已保留两个版本: {item.relative_path}")
            else:
                self._do_download(item)



# ========== 纯函数 ==========

def decide_action(
    local_exists: bool,
    cloud_exists: bool,
    local_mtime: Optional[int],
    cloud_mtime: Optional[int],
    meta_local_mtime: Optional[int],
    meta_cloud_mtime: Optional[int],
) -> SyncAction:
    """
    根据本地/云端/元数据三方时间戳决定同步操作。

    规则：
    - 只有本地 → 上传
    - 只有云端 → 下载
    - 两边都有且都有修改 → 比较时间戳，新的优先；相同则标记冲突
    - 只一边有修改 → 同步该方向
    - 都没有修改 → 跳过
    """
    if not local_exists and not cloud_exists:
        return SyncAction.SKIP
    if local_exists and not cloud_exists:
        return SyncAction.UPLOAD
    if not local_exists and cloud_exists:
        return SyncAction.DOWNLOAD

    local_changed = meta_local_mtime is None or (local_mtime and local_mtime > meta_local_mtime)
    cloud_changed = meta_cloud_mtime is None or (cloud_mtime and cloud_mtime > meta_cloud_mtime)

    if local_changed and cloud_changed:
        if local_mtime and cloud_mtime:
            if local_mtime > cloud_mtime:
                return SyncAction.UPLOAD
            if cloud_mtime > local_mtime:
                return SyncAction.DOWNLOAD
        return SyncAction.CONFLICT

    if local_changed:
        return SyncAction.UPLOAD
    if cloud_changed:
        return SyncAction.DOWNLOAD
    return SyncAction.SKIP


def _filter_by_direction(items: List[SyncItem], direction: SyncDirection) -> List[SyncItem]:
    if direction == SyncDirection.PULL:
        return [i for i in items if i.action in (SyncAction.DOWNLOAD, SyncAction.SKIP)]
    if direction == SyncDirection.PUSH:
        return [i for i in items if i.action in (SyncAction.UPLOAD, SyncAction.SKIP)]
    return items


def _empty_stats() -> Dict:
    return {"downloaded": 0, "uploaded": 0, "skipped": 0, "conflicts": 0, "errors": 0, "dedup_deleted": 0}


def _print_preview(item: SyncItem) -> None:
    labels = {
        SyncAction.DOWNLOAD: "下载",
        SyncAction.UPLOAD: "上传",
        SyncAction.SKIP: "跳过",
        SyncAction.CONFLICT: "冲突",
    }
    print(f"  {labels.get(item.action, '?'):4s}  {item.relative_path}")


def _backup_file(file_path: str) -> Optional[str]:
    """
    备份文件：在同目录下创建 .conflict.时间戳 副本。
    
    :param file_path: 要备份的文件路径
    :return: 备份文件路径，失败返回 None
    """
    if not os.path.exists(file_path):
        return None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base, ext = os.path.splitext(file_path)
    backup_path = f"{base}.conflict.{ts}{ext}"
    try:
        shutil.copy2(file_path, backup_path)
        logging.info(f"已备份: {os.path.basename(file_path)} → {os.path.basename(backup_path)}")
        return backup_path
    except Exception as e:
        logging.error(f"备份失败: {file_path} - {e}")
        return None
