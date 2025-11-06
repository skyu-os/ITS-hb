"""
智能缓存系统 - 多层缓存、智能预加载、数据压缩
提供高效的数据访问和存储策略
"""
import asyncio
import json
import pickle
import gzip
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass, asdict
import redis
import os
from concurrent.futures import ThreadPoolExecutor
import threading
from collections import OrderedDict
import time

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class CacheConfig:
    """缓存配置"""
    # Redis配置
    redis_url: str = "redis://localhost:6379"
    redis_timeout: int = 5
    redis_max_connections: int = 10
    
    # 内存缓存配置
    memory_max_size: int = 1000  # 最大缓存条目数
    memory_ttl: int = 300  # 内存缓存TTL（秒）
    
    # 缓存策略
    enable_compression: bool = True  # 启用数据压缩
    compression_threshold: int = 1024  # 压缩阈值（字节）
    
    # 预加载配置
    enable_preload: bool = True
    preload_interval: int = 60  # 预加载间隔（秒）
    
    # 缓存层级
    enable_l1_cache: bool = True  # 内存缓存
    enable_l2_cache: bool = True  # Redis缓存
    enable_l3_cache: bool = False  # 磁盘缓存

@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    value: Any
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0
    ttl: int = 300  # 生存时间（秒）
    size_bytes: int = 0
    is_compressed: bool = False

class LRUMemoryCache:
    """LRU内存缓存"""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.cache = OrderedDict()
        self.lock = threading.RLock()
        self.stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0
        }
    
    def get(self, key: str) -> Optional[CacheEntry]:
        """获取缓存条目"""
        with self.lock:
            if key in self.cache:
                # 移动到末尾（最近使用）
                entry = self.cache.pop(key)
                entry.last_accessed = datetime.utcnow()
                entry.access_count += 1
                self.cache[key] = entry
                self.stats["hits"] += 1
                return entry
            
            self.stats["misses"] += 1
            return None
    
    def put(self, key: str, entry: CacheEntry):
        """添加缓存条目"""
        with self.lock:
            # 如果已存在，更新
            if key in self.cache:
                self.cache[key] = entry
                return
            
            # 检查容量限制
            if len(self.cache) >= self.max_size:
                # 移除最久未使用的条目
                oldest_key = next(iter(self.cache))
                del self.cache[oldest_key]
                self.stats["evictions"] += 1
            
            self.cache[key] = entry
    
    def remove(self, key: str) -> bool:
        """删除缓存条目"""
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                return True
            return False
    
    def clear(self):
        """清空缓存"""
        with self.lock:
            self.cache.clear()
            self.stats = {"hits": 0, "misses": 0, "evictions": 0}
    
    def cleanup_expired(self):
        """清理过期条目"""
        now = datetime.utcnow()
        expired_keys = []
        
        with self.lock:
            for key, entry in self.cache.items():
                if (now - entry.created_at).total_seconds() > entry.ttl:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self.cache[key]
                self.stats["evictions"] += 1
        
        return len(expired_keys)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self.lock:
            total_requests = self.stats["hits"] + self.stats["misses"]
            hit_rate = (self.stats["hits"] / max(1, total_requests)) * 100
            
            return {
                **self.stats,
                "hit_rate": hit_rate,
                "size": len(self.cache),
                "max_size": self.max_size
            }

class RedisCache:
    """Redis缓存层"""
    
    def __init__(self, redis_url: str, timeout: int = 5, max_connections: int = 10):
        self.redis_url = redis_url
        self.timeout = timeout
        self.max_connections = max_connections
        self.redis_client = None
        self.connection_pool = None
        self.stats = {
            "hits": 0,
            "misses": 0,
            "errors": 0
        }
        self._connect()
    
    def _connect(self):
        """连接Redis"""
        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                decode_responses=False,  # 保持二进制数据
                socket_timeout=self.timeout,
                socket_connect_timeout=self.timeout,
                max_connections=self.max_connections
            )
            # 测试连接
            self.redis_client.ping()
            logger.info("Redis缓存连接成功")
        except Exception as e:
            logger.error(f"Redis缓存连接失败: {e}")
            self.redis_client = None
    
    def get(self, key: str) -> Optional[CacheEntry]:
        """获取缓存条目"""
        if not self.redis_client:
            self.stats["errors"] += 1
            return None
        
        try:
            data = self.redis_client.get(key)
            if data:
                # 反序列化
                entry_data = pickle.loads(data)
                entry = CacheEntry(**entry_data)
                
                # 检查是否过期
                if (datetime.utcnow() - entry.created_at).total_seconds() > entry.ttl:
                    self.delete(key)
                    self.stats["misses"] += 1
                    return None
                
                self.stats["hits"] += 1
                return entry
            
            self.stats["misses"] += 1
            return None
            
        except Exception as e:
            logger.error(f"Redis获取失败: {e}")
            self.stats["errors"] += 1
            return None
    
    def put(self, key: str, entry: CacheEntry):
        """添加缓存条目"""
        if not self.redis_client:
            self.stats["errors"] += 1
            return
        
        try:
            # 序列化
            entry_data = asdict(entry)
            data = pickle.dumps(entry_data)
            
            # 设置缓存
            self.redis_client.setex(key, entry.ttl, data)
            
        except Exception as e:
            logger.error(f"Redis设置失败: {e}")
            self.stats["errors"] += 1
    
    def delete(self, key: str) -> bool:
        """删除缓存条目"""
        if not self.redis_client:
            return False
        
        try:
            result = self.redis_client.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"Redis删除失败: {e}")
            self.stats["errors"] += 1
            return False
    
    def clear(self):
        """清空缓存"""
        if not self.redis_client:
            return
        
        try:
            self.redis_client.flushdb()
        except Exception as e:
            logger.error(f"Redis清空失败: {e}")
            self.stats["errors"] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_requests = self.stats["hits"] + self.stats["misses"] + self.stats["errors"]
        hit_rate = (self.stats["hits"] / max(1, total_requests)) * 100
        
        return {
            **self.stats,
            "hit_rate": hit_rate,
            "connected": self.redis_client is not None
        }

class DataCompressor:
    """数据压缩器"""
    
    @staticmethod
    def compress(data: bytes) -> bytes:
        """压缩数据"""
        return gzip.compress(data)
    
    @staticmethod
    def decompress(data: bytes) -> bytes:
        """解压缩数据"""
        return gzip.decompress(data)
    
    @staticmethod
    def should_compress(data_size: int, threshold: int = 1024) -> bool:
        """判断是否应该压缩"""
        return data_size > threshold

class SmartCacheManager:
    """智能缓存管理器 - 多层缓存系统"""
    
    def __init__(self, config: CacheConfig = None):
        self.config = config or CacheConfig()
        
        # 初始化缓存层
        self.l1_cache = LRUMemoryCache(self.config.memory_max_size) if self.config.enable_l1_cache else None
        self.l2_cache = RedisCache(
            self.config.redis_url, 
            self.config.redis_timeout,
            self.config.redis_max_connections
        ) if self.config.enable_l2_cache else None
        
        # 压缩器
        self.compressor = DataCompressor()
        
        # 预加载任务
        self.preload_tasks = []
        self.preload_running = False
        
        # 统计信息
        self.global_stats = {
            "total_requests": 0,
            "l1_hits": 0,
            "l2_hits": 0,
            "misses": 0,
            "compression_savings": 0
        }
        
        # 后台清理任务
        self.cleanup_task = None
        self._start_cleanup_task()
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存数据"""
        self.global_stats["total_requests"] += 1
        
        # L1缓存（内存）
        if self.l1_cache:
            entry = self.l1_cache.get(key)
            if entry:
                self.global_stats["l1_hits"] += 1
                return self._decompress_if_needed(entry.value)
        
        # L2缓存（Redis）
        if self.l2_cache:
            entry = self.l2_cache.get(key)
            if entry:
                self.global_stats["l2_hits"] += 1
                value = self._decompress_if_needed(entry.value)
                
                # 回填L1缓存
                if self.l1_cache:
                    self.l1_cache.put(key, entry)
                
                return value
        
        # 缓存未命中
        self.global_stats["misses"] += 1
        return None
    
    async def put(self, key: str, value: Any, ttl: int = None) -> bool:
        """存储缓存数据"""
        if ttl is None:
            ttl = self.config.memory_ttl
        
        # 压缩数据（如果需要）
        compressed_value, is_compressed = self._compress_if_needed(value)
        
        # 创建缓存条目
        entry = CacheEntry(
            key=key,
            value=compressed_value,
            created_at=datetime.utcnow(),
            last_accessed=datetime.utcnow(),
            ttl=ttl,
            size_bytes=len(compressed_value),
            is_compressed=is_compressed
        )
        
        success = True
        
        # 存储到L1缓存
        if self.l1_cache:
            self.l1_cache.put(key, entry)
        
        # 存储到L2缓存
        if self.l2_cache:
            self.l2_cache.put(key, entry)
        
        return success
    
    async def delete(self, key: str) -> bool:
        """删除缓存数据"""
        success = True
        
        if self.l1_cache:
            self.l1_cache.remove(key)
        
        if self.l2_cache:
            success = self.l2_cache.delete(key) and success
        
        return success
    
    async def clear(self):
        """清空所有缓存"""
        if self.l1_cache:
            self.l1_cache.clear()
        
        if self.l2_cache:
            self.l2_cache.clear()
        
        # 重置统计
        self.global_stats = {
            "total_requests": 0,
            "l1_hits": 0,
            "l2_hits": 0,
            "misses": 0,
            "compression_savings": 0
        }
    
    def _compress_if_needed(self, value: Any) -> Tuple[Any, bool]:
        """根据需要压缩数据"""
        if not self.config.enable_compression:
            return value, False
        
        # 序列化数据
        try:
            serialized = pickle.dumps(value)
            data_size = len(serialized)
            
            # 检查是否需要压缩
            if self.compressor.should_compress(data_size, self.config.compression_threshold):
                compressed = self.compressor.compress(serialized)
                
                # 记录压缩节省的空间
                savings = data_size - len(compressed)
                self.global_stats["compression_savings"] += savings
                
                return compressed, True
            
            return serialized, False
            
        except Exception as e:
            logger.error(f"数据压缩失败: {e}")
            return value, False
    
    def _decompress_if_needed(self, value: Any) -> Any:
        """根据需要解压缩数据"""
        if isinstance(value, bytes):
            try:
                # 尝试解压缩
                decompressed = self.compressor.decompress(value)
                return pickle.loads(decompressed)
            except:
                # 如果解压缩失败，尝试直接反序列化
                try:
                    return pickle.loads(value)
                except:
                    return value
        return value
    
    def _start_cleanup_task(self):
        """启动后台清理任务"""
        if not self.l1_cache:
            return
        
        def cleanup_worker():
            while True:
                try:
                    # 每5分钟清理一次过期条目
                    time.sleep(300)
                    if self.l1_cache:
                        cleaned = self.l1_cache.cleanup_expired()
                        if cleaned > 0:
                            logger.info(f"清理了 {cleaned} 个过期缓存条目")
                except Exception as e:
                    logger.error(f"缓存清理任务失败: {e}")
        
        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()
    
    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """获取综合统计信息"""
        stats = {
            "global": self.global_stats.copy(),
            "config": asdict(self.config)
        }
        
        # 计算命中率
        total_requests = self.global_stats["total_requests"]
        if total_requests > 0:
            stats["global"]["overall_hit_rate"] = (
                (self.global_stats["l1_hits"] + self.global_stats["l2_hits"]) / total_requests
            ) * 100
        else:
            stats["global"]["overall_hit_rate"] = 0.0
        
        # L1缓存统计
        if self.l1_cache:
            stats["l1_cache"] = self.l1_cache.get_stats()
        
        # L2缓存统计
        if self.l2_cache:
            stats["l2_cache"] = self.l2_cache.get_stats()
        
        return stats
    
    async def preload_data(self, keys: List[str], data_loader_func):
        """预加载数据"""
        if not self.config.enable_preload:
            return
        
        async def preload_worker():
            for key in keys:
                try:
                    # 检查是否已缓存
                    cached_value = await self.get(key)
                    if cached_value is None:
                        # 加载数据
                        value = await data_loader_func(key)
                        if value is not None:
                            await self.put(key, value)
                            logger.info(f"预加载缓存: {key}")
                except Exception as e:
                    logger.error(f"预加载失败 {key}: {e}")
        
        # 并发预加载
        tasks = [preload_worker() for _ in range(3)]  # 3个并发worker
        await asyncio.gather(*tasks)
    
    def start_preload_scheduler(self, preload_keys: List[str], data_loader_func):
        """启动预加载调度器"""
        if not self.config.enable_preload:
            return
        
        async def scheduler():
            while self.preload_running:
                try:
                    await self.preload_data(preload_keys, data_loader_func)
                    await asyncio.sleep(self.config.preload_interval)
                except Exception as e:
                    logger.error(f"预加载调度失败: {e}")
                    await asyncio.sleep(60)
        
        self.preload_running = True
        self.preload_tasks.append(asyncio.create_task(scheduler()))
        logger.info("预加载调度器已启动")
    
    def stop_preload_scheduler(self):
        """停止预加载调度器"""
        self.preload_running = False
        for task in self.preload_tasks:
            task.cancel()
        self.preload_tasks.clear()
        logger.info("预加载调度器已停止")

# 全局缓存管理器实例
_cache_manager = None

def get_cache_manager() -> SmartCacheManager:
    """获取全局缓存管理器实例"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = SmartCacheManager()
    return _cache_manager

async def test_cache():
    """测试缓存系统"""
    cache = SmartCacheManager()
    
    # 测试基本操作
    print("测试缓存基本操作...")
    
    # 存储数据
    await cache.put("test_key1", {"data": "test_value1"}, ttl=60)
    await cache.put("test_key2", {"data": "test_value2"}, ttl=60)
    
    # 获取数据
    value1 = await cache.get("test_key1")
    value2 = await cache.get("test_key2")
    value3 = await cache.get("nonexistent_key")
    
    print(f"获取test_key1: {value1}")
    print(f"获取test_key2: {value2}")
    print(f"获取nonexistent_key: {value3}")
    
    # 测试压缩
    large_data = "x" * 2000  # 2KB数据，应该被压缩
    await cache.put("large_data", large_data)
    compressed_value = await cache.get("large_data")
    print(f"大数据压缩测试: {len(compressed_value) == len(large_data)}")
    
    # 显示统计信息
    stats = cache.get_comprehensive_stats()
    print(f"\n缓存统计信息:")
    print(json.dumps(stats, indent=2, default=str))

if __name__ == "__main__":
    asyncio.run(test_cache())
