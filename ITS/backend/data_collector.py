"""
增强的数据采集服务
支持多数据源、实时采集、数据质量控制
"""
import asyncio
import aiohttp
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from database import SessionLocal, TrafficData, DataSource, get_db
import schedule
import time
from concurrent.futures import ThreadPoolExecutor
import redis
import os

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class TrafficDataPoint:
    """交通数据点"""
    timestamp: datetime
    location_lng: float
    location_lat: float
    radius_km: float
    total_roads: int
    congested_roads: int
    slow_roads: int
    clear_roads: int
    avg_speed: Optional[float]
    congestion_ratio: float
    raw_data: str
    data_quality_score: float = 1.0
    is_anomaly: bool = False

class DataQualityChecker:
    """数据质量检查器"""
    
    def __init__(self):
        self.speed_limits = {"min": 5, "max": 120}  # km/h
        self.congestion_limits = {"min": 0.0, "max": 1.0}
    
    def check_data_quality(self, data: TrafficDataPoint) -> float:
        """检查数据质量并返回质量分数 (0-1)"""
        quality_score = 1.0
        
        # 检查速度合理性
        if data.avg_speed:
            if data.avg_speed < self.speed_limits["min"] or data.avg_speed > self.speed_limits["max"]:
                quality_score *= 0.5
        
        # 检查拥堵比例合理性
        if data.congestion_ratio < self.congestion_limits["min"] or data.congestion_ratio > self.congestion_limits["max"]:
            quality_score *= 0.5
        
        # 检查数据完整性
        if data.total_roads == 0:
            quality_score *= 0.3
        
        # 检查时间戳合理性（不能是未来时间，不能太旧）
        now = datetime.utcnow()
        if data.timestamp > now:
            quality_score *= 0.1
        elif (now - data.timestamp).total_seconds() > 3600:  # 超过1小时
            quality_score *= 0.8
        
        return max(0.0, quality_score)
    
    def detect_anomaly(self, data: TrafficDataPoint, historical_data: List[TrafficDataPoint]) -> bool:
        """检测异常数据"""
        if len(historical_data) < 10:
            return False
        
        # 使用IQR方法检测异常
        recent_speeds = [d.avg_speed for d in historical_data[-20:] if d.avg_speed is not None]
        recent_congestion = [d.congestion_ratio for d in historical_data[-20:]]
        
        if not recent_speeds or not recent_congestion:
            return False
        
        # 速度异常检测
        speed_q1, speed_q3 = np.percentile(recent_speeds, [25, 75])
        speed_iqr = speed_q3 - speed_q1
        speed_lower = speed_q1 - 1.5 * speed_iqr
        speed_upper = speed_q3 + 1.5 * speed_iqr
        
        # 拥堵比例异常检测
        congestion_q1, congestion_q3 = np.percentile(recent_congestion, [25, 75])
        congestion_iqr = congestion_q3 - congestion_q1
        congestion_lower = congestion_q1 - 1.5 * congestion_iqr
        congestion_upper = congestion_q3 + 1.5 * congestion_iqr
        
        if data.avg_speed and (data.avg_speed < speed_lower or data.avg_speed > speed_upper):
            return True
        
        if data.congestion_ratio < congestion_lower or data.congestion_ratio > congestion_upper:
            return True
        
        return False

class AmapTrafficEvent:
    """交通事件数据结构"""
    def __init__(self, event_data: Dict):
        self.event_id = event_data.get("id", "")
        self.event_type = event_data.get("type", "")
        self.event_type_name = event_data.get("type_name", "")
        self.direction = event_data.get("direction", "")
        self.road_name = event_data.get("name", "")
        self.status = event_data.get("status", "")
        self.time = event_data.get("time", "")
        self.lng = event_data.get("lng", 0.0)
        self.lat = event_data.get("lat", 0.0)
        self.citycode = event_data.get("citycode", "")
        self.adcode = event_data.get("adcode", "")
        self.raw_data = json.dumps(event_data, ensure_ascii=False)

class AmapDataCollector:
    """高德地图数据采集器"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.traffic_base_url = "https://restapi.amap.com/v3/traffic/status"
        self.event_base_url = "https://restapi.amap.com/v3/traffic/event"
        self.session = None
        self.quality_checker = DataQualityChecker()
    
    async def collect_traffic_data(self, lng: float, lat: float, radius_km: float = 3.0) -> Optional[TrafficDataPoint]:
        """采集指定位置的交通数据"""
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        try:
            # 构造查询参数 - 使用圆形查询
            radius_m = int(radius_km * 1000)
            location = f"{lng},{lat}"
            url = f"{self.base_url}/circle"
            params = {
                "location": location,
                "radius": radius_m,
                "extensions": "all",
                "output": "json",
                "key": self.api_key
            }
            
            async with self.session.get(url, params=params, timeout=30) as response:
                if response.status != 200:
                    logger.error(f"高德API请求失败: {response.status}")
                    return None
                
                data = await response.json()
                
                if data.get("status") != "1":
                    logger.error(f"高德API返回错误: {data.get('info', '未知错误')}")
                    return None
                
                return self._parse_traffic_data(data, lng, lat, radius_km)
                
        except Exception as e:
            logger.error(f"采集交通数据时发生错误: {str(e)}")
            return None
    
    def _parse_traffic_data(self, data: Dict, lng: float, lat: float, radius_km: float) -> TrafficDataPoint:
        """解析高德API返回的交通数据"""
        traffic_info = data.get("trafficinfo", {})
        roads = traffic_info.get("roads", [])
        
        # 统计各种状态的道路数量
        total_roads = len(roads)
        congested_roads = 0  # 状态3
        slow_roads = 0       # 状态2
        clear_roads = 0      # 状态1
        speed_sum = 0
        speed_count = 0
        
        for road in roads:
            status = str(road.get("status", "0"))
            if status == "3":
                congested_roads += 1
            elif status == "2":
                slow_roads += 1
            elif status == "1":
                clear_roads += 1
            
            speed = road.get("speed")
            if speed is not None:
                speed_sum += float(speed)
                speed_count += 1
        
        avg_speed = speed_sum / speed_count if speed_count > 0 else None
        congestion_ratio = congested_roads / total_roads if total_roads > 0 else 0.0
        
        return TrafficDataPoint(
            timestamp=datetime.utcnow(),
            location_lng=lng,
            location_lat=lat,
            radius_km=radius_km,
            total_roads=total_roads,
            congested_roads=congested_roads,
            slow_roads=slow_roads,
            clear_roads=clear_roads,
            avg_speed=avg_speed,
            congestion_ratio=congestion_ratio,
            raw_data=json.dumps(data, ensure_ascii=False)
        )
    
    async def collect_traffic_events(self, lng: float, lat: float, radius_km: float = 3.0) -> List[AmapTrafficEvent]:
        """采集指定位置的交通事件"""
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        try:
            # 构造查询参数 - 使用矩形查询
            radius_deg = radius_km / 111  # 大约1度=111km
            min_lng, min_lat = lng - radius_deg, lat - radius_deg
            max_lng, max_lat = lng + radius_deg, lat + radius_deg
            
            params = {
                "rectangle": f"{min_lng},{min_lat},{max_lng},{max_lat}",
                "extensions": "all",
                "output": "json",
                "key": self.api_key
            }
            
            async with self.session.get(self.event_base_url, params=params, timeout=30) as response:
                if response.status != 200:
                    logger.error(f"高德事件API请求失败: {response.status}")
                    return []
                
                data = await response.json()
                
                if data.get("status") != "1":
                    logger.error(f"高德事件API返回错误: {data.get('info', '未知错误')}")
                    return []
                
                return self._parse_traffic_events(data)
                
        except Exception as e:
            logger.error(f"采集交通事件时发生错误: {str(e)}")
            return []
    
    def _parse_traffic_events(self, data: Dict) -> List[AmapTrafficEvent]:
        """解析高德API返回的交通事件数据"""
        events = []
        traffic_info = data.get("trafficinfo", {})
        event_list = traffic_info.get("events", [])
        
        for event_data in event_list:
            try:
                event = AmapTrafficEvent(event_data)
                events.append(event)
            except Exception as e:
                logger.error(f"解析交通事件失败: {str(e)}")
                continue
        
        logger.info(f"解析到 {len(events)} 个交通事件")
        return events
    
    async def collect_real_time_status(self, lng: float, lat: float, radius_km: float = 3.0) -> Dict[str, Any]:
        """采集实时路况综合数据"""
        # 并发采集路况和事件
        tasks = [
            self.collect_traffic_data(lng, lat, radius_km),
            self.collect_traffic_events(lng, lat, radius_km)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        traffic_data = None
        traffic_events = []
        
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"数据采集异常: {str(result)}")
            elif isinstance(result, TrafficDataPoint):
                traffic_data = result
            elif isinstance(result, list):
                traffic_events = result
        
        return {
            "traffic_data": traffic_data,
            "traffic_events": traffic_events,
            "event_count": len(traffic_events),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def close(self):
        """关闭会话"""
        if self.session:
            await self.session.close()

class MultiSourceDataCollector:
    """多数据源采集器"""
    
    def __init__(self):
        self.collectors = {}
        self.quality_checker = DataQualityChecker()
        self.redis_client = None
        self._setup_redis()
    
    def _setup_redis(self):
        """设置Redis连接"""
        try:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            self.redis_client.ping()
            logger.info("Redis连接成功")
        except Exception as e:
            logger.warning(f"Redis连接失败，将使用内存缓存: {str(e)}")
            self.redis_client = None
    
    def add_collector(self, name: str, collector):
        """添加数据采集器"""
        self.collectors[name] = collector
        logger.info(f"已添加数据采集器: {name}")
    
    async def collect_from_all_sources(self, lng: float, lat: float, radius_km: float = 3.0) -> List[TrafficDataPoint]:
        """从所有数据源采集数据"""
        tasks = []
        for name, collector in self.collectors.items():
            if hasattr(collector, 'collect_traffic_data'):
                task = self._collect_with_error_handling(name, collector, lng, lat, radius_km)
                tasks.append(task)
        
        if not tasks:
            logger.warning("没有可用的数据采集器")
            return []
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 过滤异常结果
        valid_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"数据采集异常: {str(result)}")
            elif isinstance(result, TrafficDataPoint):
                valid_results.append(result)
        
        return valid_results
    
    async def _collect_with_error_handling(self, name: str, collector, lng: float, lat: float, radius_km: float):
        """带错误处理的数据采集"""
        try:
            return await collector.collect_traffic_data(lng, lat, radius_km)
        except Exception as e:
            logger.error(f"数据源 {name} 采集失败: {str(e)}")
            return None
    
    def save_to_database(self, data_points: List[TrafficDataPoint]):
        """保存数据到数据库"""
        if not data_points:
            return
        
        db = SessionLocal()
        try:
            # 获取历史数据用于异常检测
            recent_data = db.query(TrafficData).filter(
                TrafficData.location_lng == data_points[0].location_lng,
                TrafficData.location_lat == data_points[0].location_lat,
                TrafficData.timestamp >= datetime.utcnow() - timedelta(days=7)
            ).order_by(TrafficData.timestamp.desc()).limit(100).all()
            
            for data_point in data_points:
                # 数据质量检查
                quality_score = self.quality_checker.check_data_quality(data_point)
                data_point.data_quality_score = quality_score
                
                # 异常检测
                data_point.is_anomaly = self.quality_checker.detect_anomaly(data_point, recent_data)
                
                # 保存到数据库
                db_traffic_data = TrafficData(
                    timestamp=data_point.timestamp,
                    location_lng=data_point.location_lng,
                    location_lat=data_point.location_lat,
                    radius_km=data_point.radius_km,
                    total_roads=data_point.total_roads,
                    congested_roads=data_point.congested_roads,
                    slow_roads=data_point.slow_roads,
                    clear_roads=data_point.clear_roads,
                    avg_speed=data_point.avg_speed,
                    congestion_ratio=data_point.congestion_ratio,
                    raw_data=data_point.raw_data,
                    data_quality_score=data_point.data_quality_score,
                    is_anomaly=data_point.is_anomaly
                )
                db.add(db_traffic_data)
            
            db.commit()
            logger.info(f"成功保存 {len(data_points)} 条交通数据")
            
            # 更新Redis缓存
            if self.redis_client:
                cache_key = f"traffic:{data_points[0].location_lng}:{data_points[0].location_lat}"
                cache_data = {
                    "timestamp": data_points[0].timestamp.isoformat(),
                    "congestion_ratio": data_points[0].congestion_ratio,
                    "avg_speed": data_points[0].avg_speed
                }
                self.redis_client.setex(cache_key, 300, json.dumps(cache_data))  # 5分钟过期
                
        except Exception as e:
            db.rollback()
            logger.error(f"保存数据到数据库失败: {str(e)}")
        finally:
            db.close()

class ScheduledCollector:
    """定时数据采集调度器"""
    
    def __init__(self, multi_collector: MultiSourceDataCollector):
        self.multi_collector = multi_collector
        self.is_running = False
    
    def start_scheduled_collection(self):
        """启动定时采集"""
        # 每5分钟采集一次数据
        schedule.every(5).minutes.do(self._scheduled_collect)
        
        # 每小时清理过期数据
        schedule.every().hour.do(self._cleanup_old_data)
        
        self.is_running = True
        logger.info("定时采集任务已启动")
        
        while self.is_running:
            schedule.run_pending()
            time.sleep(30)  # 每30秒检查一次
    
    def stop_scheduled_collection(self):
        """停止定时采集"""
        self.is_running = False
        schedule.clear()
        logger.info("定时采集任务已停止")
    
    def _scheduled_collect(self):
        """定时采集任务"""
        # 默认采集杭州的交通数据
        default_locations = [
            {"lng": 120.15507, "lat": 30.27415, "name": "杭州市中心"},
            {"lng": 120.16199, "lat": 30.27991, "name": "西湖"},
            {"lng": 120.21083, "lat": 30.24785, "name": "钱江新城"}
        ]
        
        async def collect_all():
            for location in default_locations:
                try:
                    data_points = await self.multi_collector.collect_from_all_sources(
                        location["lng"], location["lat"], 3.0
                    )
                    if data_points:
                        self.multi_collector.save_to_database(data_points)
                        logger.info(f"成功采集 {location['name']} 的交通数据")
                except Exception as e:
                    logger.error(f"采集 {location['name']} 数据失败: {str(e)}")
        
        # 在新的事件循环中运行异步任务
        asyncio.run(collect_all())
    
    def _cleanup_old_data(self):
        """清理过期数据"""
        db = SessionLocal()
        try:
            # 删除30天前的数据
            cutoff_date = datetime.utcnow() - timedelta(days=30)
            deleted_count = db.query(TrafficData).filter(
                TrafficData.timestamp < cutoff_date
            ).delete()
            db.commit()
            logger.info(f"清理了 {deleted_count} 条过期数据")
        except Exception as e:
            db.rollback()
            logger.error(f"清理过期数据失败: {str(e)}")
        finally:
            db.close()

async def main():
    """主函数 - 用于测试"""
    from database import init_db
    
    # 初始化数据库
    init_db()
    
    # 创建多数据源采集器
    multi_collector = MultiSourceDataCollector()
    
    # 添加高德数据采集器
    api_key = os.getenv("AMAP_API_KEY", "your_api_key_here")
    amap_collector = AmapDataCollector(api_key)
    multi_collector.add_collector("amap", amap_collector)
    
    # 测试数据采集
    lng, lat = 120.15507, 30.27415  # 杭州
    data_points = await multi_collector.collect_from_all_sources(lng, lat, 3.0)
    
    if data_points:
        multi_collector.save_to_database(data_points)
        print(f"成功采集并保存了 {len(data_points)} 条数据")
        for i, data in enumerate(data_points):
            print(f"数据 {i+1}: 拥堵比例={data.congestion_ratio:.3f}, 平均速度={data.avg_speed:.1f}km/h")
    else:
        print("未能采集到数据")
    
    await amap_collector.close()

if __name__ == "__main__":
    asyncio.run(main())
