"""
增强的数据采集器 - 集成多数据源、异步并发、智能缓存
将原有的数据采集器与新的爬虫系统整合
"""
import asyncio
import aiohttp
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from database import SessionLocal, TrafficData, DataSource, get_db
import redis
import os
from concurrent.futures import ThreadPoolExecutor
import time
from web_scraper import EnhancedMultiSourceScraper, TrafficAccident
from data_collector import AmapDataCollector, TrafficDataPoint, DataQualityChecker

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class EnhancedTrafficData:
    """增强的交通数据结构"""
    # 基础路况数据
    traffic_data: Optional[TrafficDataPoint]
    # 事故数据
    accidents: List[TrafficAccident]
    # 数据源信息
    sources: List[str]
    # 采集时间
    collected_at: datetime
    # 数据质量评分
    overall_quality_score: float
    # 是否有紧急事件
    has_emergency: bool
    # 数据完整性检查
    completeness_score: float

class DataFusionEngine:
    """数据融合引擎 - 整合多源数据"""
    
    def __init__(self):
        self.quality_checker = DataQualityChecker()
    
    def fuse_data(self, traffic_data_list: List[TrafficDataPoint], 
                  accidents: List[TrafficAccident]) -> EnhancedTrafficData:
        """融合交通数据和事故数据"""
        
        # 选择质量最高的交通数据
        best_traffic_data = None
        best_quality_score = 0.0
        
        for traffic_data in traffic_data_list:
            quality_score = self.quality_checker.check_data_quality(traffic_data)
            if quality_score > best_quality_score:
                best_quality_score = quality_score
                best_traffic_data = traffic_data
        
        # 计算数据源列表
        sources = []
        if best_traffic_data:
            sources.append("高德API")
        if accidents:
            for accident in accidents:
                if accident.source not in sources:
                    sources.append(accident.source)
        
        # 检查是否有紧急事件
        has_emergency = any(
            accident.severity in ["严重", "特大"] 
            for accident in accidents
        )
        
        # 计算完整性评分
        completeness_score = self._calculate_completeness(best_traffic_data, accidents)
        
        # 计算总体质量评分
        overall_quality_score = (best_quality_score * 0.6 + 
                               completeness_score * 0.4)
        
        return EnhancedTrafficData(
            traffic_data=best_traffic_data,
            accidents=accidents,
            sources=sources,
            collected_at=datetime.utcnow(),
            overall_quality_score=overall_quality_score,
            has_emergency=has_emergency,
            completeness_score=completeness_score
        )
    
    def _calculate_completeness(self, traffic_data: Optional[TrafficDataPoint], 
                               accidents: List[TrafficAccident]) -> float:
        """计算数据完整性评分"""
        score = 0.0
        
        # 交通数据完整性 (40%)
        if traffic_data:
            if traffic_data.avg_speed is not None:
                score += 0.1
            if traffic_data.congestion_ratio > 0:
                score += 0.1
            if traffic_data.total_roads > 0:
                score += 0.1
            if traffic_data.raw_data:
                score += 0.1
        
        # 事故数据完整性 (60%)
        if accidents:
            accident_score = 0.0
            for accident in accidents[:5]:  # 最多计算5个事故
                if accident.location != "未知位置":
                    accident_score += 0.1
                if accident.accident_time:
                    accident_score += 0.1
                if accident.severity != "未知":
                    accident_score += 0.1
                if accident.description:
                    accident_score += 0.1
            
            score += min(accident_score, 0.6)
        
        return min(score, 1.0)

class ConcurrentDataCollector:
    """并发数据采集器"""
    
    def __init__(self):
        self.amap_collector = None
        self.web_scraper = EnhancedMultiSourceScraper()
        self.fusion_engine = DataFusionEngine()
        self.redis_client = None
        self.session_pool = None
        self._setup_connections()
        self.executor = ThreadPoolExecutor(max_workers=8)
        
        # 采集统计
        self.stats = {
            "total_collections": 0,
            "successful_collections": 0,
            "failed_collections": 0,
            "avg_collection_time": 0.0,
            "last_collection_time": None
        }
    
    def _setup_connections(self):
        """设置连接"""
        try:
            # Redis连接
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            self.redis_client.ping()
            logger.info("增强采集器Redis连接成功")
        except Exception as e:
            logger.warning(f"增强采集器Redis连接失败: {e}")
            self.redis_client = None
        
        # 高德API采集器
        api_key = os.getenv("AMAP_API_KEY", "your_api_key_here")
        self.amap_collector = AmapDataCollector(api_key)
    
    async def collect_enhanced_data(self, lng: float, lat: float, 
                                  radius_km: float = 3.0) -> Optional[EnhancedTrafficData]:
        """增强的数据采集 - 并发采集多源数据"""
        start_time = time.time()
        
        try:
            # 并发执行采集任务
            tasks = [
                self._collect_traffic_data_async(lng, lat, radius_km),
                self._collect_accidents_async(lng, lat, radius_km),
                self._collect_additional_sources_async(lng, lat, radius_km)
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 解析结果
            traffic_data_list = []
            accidents = []
            additional_sources = []
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"采集任务 {i} 失败: {result}")
                    self.stats["failed_collections"] += 1
                elif i == 0 and result:  # 交通数据
                    if isinstance(result, list):
                        traffic_data_list = result
                    else:
                        traffic_data_list = [result]
                elif i == 1 and result:  # 事故数据
                    accidents = result
                elif i == 2 and result:  # 附加数据源
                    additional_sources = result
            
            # 数据融合
            enhanced_data = self.fusion_engine.fuse_data(traffic_data_list, accidents)
            
            # 更新统计
            collection_time = time.time() - start_time
            self._update_stats(collection_time, True)
            
            # 缓存结果
            await self._cache_enhanced_data(lng, lat, enhanced_data)
            
            logger.info(f"增强数据采集完成 - 耗时: {collection_time:.2f}s, "
                       f"数据源: {enhanced_data.sources}, "
                       f"事故数: {len(accidents)}")
            
            return enhanced_data
            
        except Exception as e:
            logger.error(f"增强数据采集失败: {e}")
            self._update_stats(time.time() - start_time, False)
            return None
    
    async def _collect_traffic_data_async(self, lng: float, lat: float, 
                                        radius_km: float) -> List[TrafficDataPoint]:
        """异步采集交通数据"""
        try:
            if not self.amap_collector:
                return []
            
            # 可以在这里添加其他地图API的并发调用
            tasks = []
            
            # 高德地图
            tasks.append(self.amap_collector.collect_traffic_data(lng, lat, radius_km))
            
            # 可以添加百度地图、腾讯地图等其他数据源
            # tasks.append(self._collect_baidu_traffic(lng, lat, radius_km))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            traffic_data_list = []
            for result in results:
                if isinstance(result, TrafficDataPoint):
                    traffic_data_list.append(result)
                elif isinstance(result, Exception):
                    logger.error(f"交通数据采集异常: {result}")
            
            return traffic_data_list
            
        except Exception as e:
            logger.error(f"异步采集交通数据失败: {e}")
            return []
    
    async def _collect_accidents_async(self, lng: float, lat: float, 
                                     radius_km: float) -> List[TrafficAccident]:
        """异步采集事故数据"""
        try:
            # 首先从缓存获取
            cached_accidents = await self._get_cached_accidents()
            if cached_accidents:
                # 过滤地理位置相关的事故
                filtered_accidents = self._filter_accidents_by_location(
                    cached_accidents, lng, lat, radius_km
                )
                return filtered_accidents
            
            # 如果缓存没有，启动爬虫采集
            accidents = await self.web_scraper.collect_all_accidents()
            
            # 地理位置过滤
            filtered_accidents = self._filter_accidents_by_location(
                accidents, lng, lat, radius_km
            )
            
            return filtered_accidents
            
        except Exception as e:
            logger.error(f"异步采集事故数据失败: {e}")
            return []
    
    async def _collect_additional_sources_async(self, lng: float, lat: float, 
                                             radius_km: float) -> List[str]:
        """采集其他数据源"""
        sources = []
        try:
            # 可以在这里添加其他数据源的采集
            # 例如：交通摄像头、传感器数据等
            
            # 模拟其他数据源检查
            if await self._check_traffic_cameras(lng, lat, radius_km):
                sources.append("交通摄像头")
            
            if await self._check_weather_data(lng, lat):
                sources.append("天气数据")
            
        except Exception as e:
            logger.error(f"采集附加数据源失败: {e}")
        
        return sources
    
    def _filter_accidents_by_location(self, accidents: List[TrafficAccident], 
                                    lng: float, lat: float, 
                                    radius_km: float) -> List[TrafficAccident]:
        """根据地理位置过滤事故"""
        # 这里可以实现更精确的地理过滤
        # 暂时返回所有事故，实际使用时可以根据经纬度距离过滤
        
        # 过滤最近24小时的事故
        recent_time = datetime.utcnow() - timedelta(hours=24)
        recent_accidents = [
            accident for accident in accidents
            if accident.accident_time and accident.accident_time > recent_time
        ]
        
        return recent_accidents
    
    async def _get_cached_accidents(self) -> Optional[List[TrafficAccident]]:
        """从缓存获取事故数据"""
        if not self.redis_client:
            return None
        
        try:
            cached_data = self.redis_client.get("latest_accidents")
            if cached_data:
                accident_dicts = json.loads(cached_data)
                accidents = []
                
                for accident_dict in accident_dicts:
                    accident = TrafficAccident(
                        accident_id=accident_dict["accident_id"],
                        title=accident_dict["title"],
                        description="",  # 缓存中不保存详细描述
                        location=accident_dict["location"],
                        severity=accident_dict["severity"],
                        source=accident_dict["source"],
                        collected_at=datetime.fromisoformat(accident_dict["collected_at"])
                    )
                    if accident_dict["accident_time"]:
                        accident.accident_time = datetime.fromisoformat(accident_dict["accident_time"])
                    accidents.append(accident)
                
                return accidents
                
        except Exception as e:
            logger.error(f"获取缓存事故数据失败: {e}")
        
        return None
    
    async def _cache_enhanced_data(self, lng: float, lat: float, 
                                 data: EnhancedTrafficData):
        """缓存增强数据"""
        if not self.redis_client:
            return
        
        try:
            cache_key = f"enhanced_traffic:{lng:.4f}:{lat:.4f}"
            
            # 准备缓存数据
            cache_data = {
                "collected_at": data.collected_at.isoformat(),
                "sources": data.sources,
                "overall_quality_score": data.overall_quality_score,
                "has_emergency": data.has_emergency,
                "completeness_score": data.completeness_score,
                "accident_count": len(data.accidents),
                "accident_summary": [
                    {
                        "title": accident.title,
                        "location": accident.location,
                        "severity": accident.severity
                    }
                    for accident in data.accidents[:5]  # 只缓存前5个事故摘要
                ]
            }
            
            if data.traffic_data:
                cache_data["traffic_summary"] = {
                    "congestion_ratio": data.traffic_data.congestion_ratio,
                    "avg_speed": data.traffic_data.avg_speed,
                    "total_roads": data.traffic_data.total_roads
                }
            
            # 缓存5分钟
            self.redis_client.setex(cache_key, 300, json.dumps(cache_data, ensure_ascii=False))
            
        except Exception as e:
            logger.error(f"缓存增强数据失败: {e}")
    
    async def _check_traffic_cameras(self, lng: float, lat: float, 
                                  radius_km: float) -> bool:
        """检查交通摄像头数据可用性"""
        # 这里可以实现交通摄像头API的调用
        # 暂时返回False，表示数据不可用
        return False
    
    async def _check_weather_data(self, lng: float, lat: float) -> bool:
        """检查天气数据可用性"""
        # 这里可以实现天气API的调用
        # 暂时返回False，表示数据不可用
        return False
    
    def _update_stats(self, collection_time: float, success: bool):
        """更新采集统计"""
        self.stats["total_collections"] += 1
        
        if success:
            self.stats["successful_collections"] += 1
        else:
            self.stats["failed_collections"] += 1
        
        # 更新平均采集时间
        total_time = self.stats["avg_collection_time"] * (self.stats["total_collections"] - 1)
        self.stats["avg_collection_time"] = (total_time + collection_time) / self.stats["total_collections"]
        
        self.stats["last_collection_time"] = datetime.utcnow()
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """获取采集统计信息"""
        return {
            **self.stats,
            "success_rate": (
                self.stats["successful_collections"] / max(1, self.stats["total_collections"])
            ) * 100
        }
    
    def save_to_database(self, enhanced_data: EnhancedTrafficData, lng: float, lat: float):
        """保存增强数据到数据库"""
        if not enhanced_data.traffic_data:
            logger.warning("没有交通数据可保存")
            return
        
        db = SessionLocal()
        try:
            # 保存交通数据
            db_traffic_data = TrafficData(
                timestamp=enhanced_data.traffic_data.timestamp,
                location_lng=lng,
                location_lat=lat,
                radius_km=enhanced_data.traffic_data.radius_km,
                total_roads=enhanced_data.traffic_data.total_roads,
                congested_roads=enhanced_data.traffic_data.congested_roads,
                slow_roads=enhanced_data.traffic_data.slow_roads,
                clear_roads=enhanced_data.traffic_data.clear_roads,
                avg_speed=enhanced_data.traffic_data.avg_speed,
                congestion_ratio=enhanced_data.traffic_data.congestion_ratio,
                raw_data=json.dumps({
                    "enhanced_data": {
                        "sources": enhanced_data.sources,
                        "accident_count": len(enhanced_data.accidents),
                        "has_emergency": enhanced_data.has_emergency,
                        "quality_score": enhanced_data.overall_quality_score
                    },
                    "original_traffic": enhanced_data.traffic_data.raw_data
                }, ensure_ascii=False),
                data_quality_score=enhanced_data.overall_quality_score,
                is_anomaly=enhanced_data.traffic_data.is_anomaly
            )
            db.add(db_traffic_data)
            db.commit()
            
            logger.info(f"成功保存增强交通数据到数据库")
            
        except Exception as e:
            db.rollback()
            logger.error(f"保存增强数据到数据库失败: {e}")
        finally:
            db.close()
    
    async def close(self):
        """关闭连接"""
        if self.amap_collector:
            await self.amap_collector.close()
        
        if self.executor:
            self.executor.shutdown(wait=True)

class RealTimeDataMonitor:
    """实时数据监控器 - 事件驱动的数据采集"""
    
    def __init__(self, collector: ConcurrentDataCollector):
        self.collector = collector
        self.monitoring_locations = []
        self.monitoring_active = False
        self.emergency_callbacks = []
    
    def add_monitoring_location(self, lng: float, lat: float, radius_km: float = 3.0, 
                               name: str = "未命名位置"):
        """添加监控位置"""
        location = {
            "lng": lng,
            "lat": lat,
            "radius_km": radius_km,
            "name": name,
            "last_check": datetime.utcnow(),
            "emergency_count": 0
        }
        self.monitoring_locations.append(location)
        logger.info(f"添加监控位置: {name} ({lng}, {lat})")
    
    def add_emergency_callback(self, callback):
        """添加紧急事件回调"""
        self.emergency_callbacks.append(callback)
    
    async def start_monitoring(self, check_interval_seconds: int = 30):
        """启动实时监控"""
        self.monitoring_active = True
        logger.info(f"启动实时监控，检查间隔: {check_interval_seconds}秒")
        
        while self.monitoring_active:
            try:
                await self._check_all_locations()
                await asyncio.sleep(check_interval_seconds)
            except Exception as e:
                logger.error(f"实时监控检查失败: {e}")
                await asyncio.sleep(5)  # 出错后短暂等待
    
    def stop_monitoring(self):
        """停止实时监控"""
        self.monitoring_active = False
        logger.info("实时监控已停止")
    
    async def _check_all_locations(self):
        """检查所有监控位置"""
        for location in self.monitoring_locations:
            try:
                enhanced_data = await self.collector.collect_enhanced_data(
                    location["lng"], location["lat"], location["radius_km"]
                )
                
                if enhanced_data and enhanced_data.has_emergency:
                    await self._handle_emergency_event(location, enhanced_data)
                
                location["last_check"] = datetime.utcnow()
                
            except Exception as e:
                logger.error(f"检查位置 {location['name']} 失败: {e}")
    
    async def _handle_emergency_event(self, location: Dict, enhanced_data: EnhancedTrafficData):
        """处理紧急事件"""
        location["emergency_count"] += 1
        
        emergency_info = {
            "location": location,
            "enhanced_data": enhanced_data,
            "timestamp": datetime.utcnow()
        }
        
        logger.warning(f"发现紧急事件 - 位置: {location['name']}, "
                      f"事故数: {len(enhanced_data.accidents)}")
        
        # 调用所有紧急事件回调
        for callback in self.emergency_callbacks:
            try:
                await callback(emergency_info)
            except Exception as e:
                logger.error(f"紧急事件回调执行失败: {e}")

async def test_enhanced_collector():
    """测试增强数据采集器"""
    collector = ConcurrentDataCollector()
    
    # 测试杭州数据采集
    lng, lat = 120.15507, 30.27415  # 杭州市中心
    
    enhanced_data = await collector.collect_enhanced_data(lng, lat, 3.0)
    
    if enhanced_data:
        print(f"采集成功!")
        print(f"数据源: {enhanced_data.sources}")
        print(f"交通数据: 拥堵比例={enhanced_data.traffic_data.congestion_ratio:.3f}" 
              f" if enhanced_data.traffic_data else '无'")
        print(f"事故数量: {len(enhanced_data.accidents)}")
        print(f"紧急事件: {enhanced_data.has_emergency}")
        print(f"质量评分: {enhanced_data.overall_quality_score:.3f}")
        
        # 显示事故信息
        for i, accident in enumerate(enhanced_data.accidents[:3]):
            print(f"事故 {i+1}: {accident.title}")
            print(f"  位置: {accident.location}")
            print(f"  严重程度: {accident.severity}")
    else:
        print("采集失败")
    
    # 显示统计信息
    stats = collector.get_collection_stats()
    print(f"\n采集统计: {stats}")
    
    await collector.close()

if __name__ == "__main__":
    asyncio.run(test_enhanced_collector())
