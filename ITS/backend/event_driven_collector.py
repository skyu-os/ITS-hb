"""
事件驱动数据采集系统 - 基于事件触发的实时数据采集
支持WebSocket实时通信、事件队列、优先级处理
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Set
from dataclasses import dataclass, field, asdict
from enum import Enum
import websockets
from websockets.server import WebSocketServerProtocol
import redis
from collections import deque
import heapq
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import uuid

from enhanced_data_collector import ConcurrentDataCollector, EnhancedTrafficData
from web_scraper import TrafficAccident
from smart_cache import SmartCacheManager, get_cache_manager

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EventType(Enum):
    """事件类型"""
    TRAFFIC_CONGESTION = "traffic_congestion"      # 交通拥堵
    ACCIDENT_DETECTED = "accident_detected"        # 检测到事故
    EMERGENCY_VEHICLE = "emergency_vehicle"        # 救护车辆
    ROAD_CLOSURE = "road_closure"                 # 道路封闭
    WEATHER_ALERT = "weather_alert"               # 天气预警
    SYSTEM_ALERT = "system_alert"                 # 系统预警
    DATA_UPDATE = "data_update"                   # 数据更新
    CUSTOM_EVENT = "custom_event"                 # 自定义事件

class EventPriority(Enum):
    """事件优先级"""
    CRITICAL = 1    # 紧急（事故、道路封闭）
    HIGH = 2        # 高（严重拥堵、救护车辆）
    MEDIUM = 3      # 中（一般拥堵、天气预警）
    LOW = 4         # 低（数据更新、系统信息）

@dataclass
class TrafficEvent:
    """交通事件"""
    event_id: str
    event_type: EventType
    priority: EventPriority
    title: str
    description: str
    location_lng: float
    location_lat: float
    radius_km: float
    timestamp: datetime
    source: str
    data: Dict[str, Any] = field(default_factory=dict)
    processed: bool = False
    processing_time: Optional[float] = None
    callback_count: int = 0

@dataclass
class EventSubscription:
    """事件订阅"""
    subscription_id: str
    event_types: Set[EventType]
    location_filters: List[Dict[str, Any]]  # 地理位置过滤条件
    priority_filters: Set[EventPriority]
    callback: Callable
    active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)

class EventQueue:
    """事件队列 - 优先级队列"""
    
    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self._queue = []
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self.stats = {
            "total_events": 0,
            "processed_events": 0,
            "dropped_events": 0,
            "queue_size": 0
        }
    
    def put(self, event: TrafficEvent) -> bool:
        """添加事件到队列"""
        with self._condition:
            if len(self._queue) >= self.max_size:
                # 队列已满，丢弃最低优先级的事件
                try:
                    heapq.heappop(self._queue)
                    self.stats["dropped_events"] += 1
                    logger.warning("事件队列已满，丢弃最低优先级事件")
                except IndexError:
                    return False
            
            # 使用优先级和时间戳作为排序键
            priority_value = event.priority.value
            timestamp = event.timestamp.timestamp()
            heapq.heappush(self._queue, (priority_value, timestamp, event))
            self.stats["total_events"] += 1
            self.stats["queue_size"] = len(self._queue)
            
            # 通知等待的消费者
            self._condition.notify()
            return True
    
    def get(self, timeout: float = None) -> Optional[TrafficEvent]:
        """从队列获取事件"""
        with self._condition:
            # 等待事件可用
            while not self._queue:
                if timeout:
                    if not self._condition.wait(timeout):
                        return None
                else:
                    self._condition.wait()
            
            try:
                _, _, event = heapq.heappop(self._queue)
                self.stats["queue_size"] = len(self._queue)
                return event
            except IndexError:
                return None
    
    def get_batch(self, max_batch_size: int = 10, timeout: float = 1.0) -> List[TrafficEvent]:
        """批量获取事件"""
        events = []
        start_time = time.time()
        
        while len(events) < max_batch_size and (time.time() - start_time) < timeout:
            event = self.get(timeout=0.1)  # 短暂超时
            if event:
                events.append(event)
            else:
                break
        
        return events
    
    def size(self) -> int:
        """获取队列大小"""
        with self._lock:
            return len(self._queue)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            return {
                **self.stats,
                "queue_size": len(self._queue)
            }

class EventPublisher:
    """事件发布器"""
    
    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        self.websocket_connections: Set[WebSocketServerProtocol] = set()
        self.subscribers: Dict[str, EventSubscription] = {}
        self.stats = {
            "published_events": 0,
            "websocket_broadcasts": 0,
            "redis_publishes": 0,
            "subscriber_notifications": 0
        }
    
    async def publish_event(self, event: TrafficEvent):
        """发布事件"""
        self.stats["published_events"] += 1
        
        # WebSocket广播
        await self._broadcast_websocket(event)
        
        # Redis发布
        await self._publish_redis(event)
        
        # 订阅者通知
        await self._notify_subscribers(event)
    
    async def _broadcast_websocket(self, event: TrafficEvent):
        """WebSocket广播"""
        if not self.websocket_connections:
            return
        
        event_data = {
            "type": "traffic_event",
            "data": asdict(event),
            "timestamp": datetime.utcnow().isoformat()
        }
        message = json.dumps(event_data, ensure_ascii=False, default=str)
        
        # 广播给所有连接的客户端
        disconnected = set()
        for websocket in self.websocket_connections:
            try:
                await websocket.send(message)
                self.stats["websocket_broadcasts"] += 1
            except Exception as e:
                logger.error(f"WebSocket发送失败: {e}")
                disconnected.add(websocket)
        
        # 移除断开的连接
        self.websocket_connections -= disconnected
    
    async def _publish_redis(self, event: TrafficEvent):
        """Redis发布"""
        if not self.redis_client:
            return
        
        try:
            channel = f"traffic_events:{event.event_type.value}"
            event_data = {
                "event_id": event.event_id,
                "event_type": event.event_type.value,
                "priority": event.priority.value,
                "location_lng": event.location_lng,
                "location_lat": event.location_lat,
                "data": event.data
            }
            
            self.redis_client.publish(channel, json.dumps(event_data, ensure_ascii=False))
            self.stats["redis_publishes"] += 1
            
        except Exception as e:
            logger.error(f"Redis发布失败: {e}")
    
    async def _notify_subscribers(self, event: TrafficEvent):
        """通知订阅者"""
        for subscription in self.subscribers.values():
            if not subscription.active:
                continue
            
            # 检查事件类型匹配
            if event.event_type not in subscription.event_types:
                continue
            
            # 检查优先级匹配
            if event.priority not in subscription.priority_filters:
                continue
            
            # 检查地理位置匹配
            if not self._matches_location_filter(event, subscription.location_filters):
                continue
            
            try:
                # 调用回调函数
                if asyncio.iscoroutinefunction(subscription.callback):
                    await subscription.callback(event)
                else:
                    subscription.callback(event)
                
                subscription.callback_count += 1
                self.stats["subscriber_notifications"] += 1
                
            except Exception as e:
                logger.error(f"订阅者回调执行失败: {e}")
    
    def _matches_location_filter(self, event: TrafficEvent, 
                               location_filters: List[Dict[str, Any]]) -> bool:
        """检查地理位置匹配"""
        if not location_filters:
            return True
        
        for filter_config in location_filters:
            # 简单的距离检查
            if "center_lng" in filter_config and "center_lat" in filter_config:
                center_lng = filter_config["center_lng"]
                center_lat = filter_config["center_lat"]
                max_radius = filter_config.get("radius_km", float('inf'))
                
                # 计算距离（简化版本）
                distance = self._calculate_distance(
                    event.location_lng, event.location_lat,
                    center_lng, center_lat
                )
                
                if distance <= max_radius + event.radius_km:
                    return True
        
        return False
    
    def _calculate_distance(self, lng1: float, lat1: float, 
                           lng2: float, lat2: float) -> float:
        """计算两点间距离（公里）"""
        # 简化的距离计算
        return ((lng2 - lng1) ** 2 + (lat2 - lat1) ** 2) ** 0.5 * 111
    
    def add_websocket_connection(self, websocket: WebSocketServerProtocol):
        """添加WebSocket连接"""
        self.websocket_connections.add(websocket)
        logger.info(f"新增WebSocket连接，当前连接数: {len(self.websocket_connections)}")
    
    def remove_websocket_connection(self, websocket: WebSocketServerProtocol):
        """移除WebSocket连接"""
        self.websocket_connections.discard(websocket)
        logger.info(f"移除WebSocket连接，当前连接数: {len(self.websocket_connections)}")
    
    def subscribe(self, subscription: EventSubscription) -> str:
        """添加事件订阅"""
        self.subscribers[subscription.subscription_id] = subscription
        logger.info(f"添加事件订阅: {subscription.subscription_id}")
        return subscription.subscription_id
    
    def unsubscribe(self, subscription_id: str) -> bool:
        """取消事件订阅"""
        if subscription_id in self.subscribers:
            del self.subscribers[subscription_id]
            logger.info(f"取消事件订阅: {subscription_id}")
            return True
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            "websocket_connections": len(self.websocket_connections),
            "active_subscriptions": len(self.subscribers)
        }

class EventDrivenDataCollector:
    """事件驱动数据采集器"""
    
    def __init__(self, collector: ConcurrentDataCollector):
        self.collector = collector
        self.event_queue = EventQueue()
        self.event_publisher = EventPublisher()
        self.cache_manager = get_cache_manager()
        
        # 监控配置
        self.monitoring_locations = []
        self.monitoring_active = False
        
        # 事件检测配置
        self.congestion_threshold = 0.7  # 拥堵阈值
        self.emergency_keywords = ["事故", "火灾", "爆炸", "伤亡", "紧急"]
        
        # 后台任务
        self.event_processor_task = None
        self.monitor_task = None
        
        # 统计信息
        self.stats = {
            "events_detected": 0,
            "events_processed": 0,
            "processing_errors": 0,
            "start_time": datetime.utcnow()
        }
    
    async def start_monitoring(self, locations: List[Dict[str, Any]], 
                             check_interval_seconds: int = 30):
        """启动事件监控"""
        self.monitoring_locations = locations
        self.monitoring_active = True
        
        # 启动事件处理器
        self.event_processor_task = asyncio.create_task(self._event_processor())
        
        # 启动监控任务
        self.monitor_task = asyncio.create_task(
            self._monitoring_loop(check_interval_seconds)
        )
        
        logger.info("事件驱动数据采集已启动")
    
    def stop_monitoring(self):
        """停止监控"""
        self.monitoring_active = False
        
        if self.event_processor_task:
            self.event_processor_task.cancel()
        
        if self.monitor_task:
            self.monitor_task.cancel()
        
        logger.info("事件驱动数据采集已停止")
    
    async def _monitoring_loop(self, check_interval_seconds: int):
        """监控循环"""
        while self.monitoring_active:
            try:
                for location in self.monitoring_locations:
                    await self._check_location_events(location)
                
                await asyncio.sleep(check_interval_seconds)
                
            except Exception as e:
                logger.error(f"监控循环错误: {e}")
                await asyncio.sleep(5)
    
    async def _check_location_events(self, location: Dict[str, Any]):
        """检查位置事件"""
        try:
            lng = location["lng"]
            lat = location["lat"]
            radius_km = location.get("radius_km", 3.0)
            location_name = location.get("name", f"位置{lng},{lat}")
            
            # 采集数据
            enhanced_data = await self.collector.collect_enhanced_data(lng, lat, radius_km)
            
            if not enhanced_data:
                return
            
            # 检测各种事件
            await self._detect_congestion_event(location_name, enhanced_data)
            await self._detect_accident_events(location_name, enhanced_data)
            await self._detect_emergency_events(location_name, enhanced_data)
            
        except Exception as e:
            logger.error(f"检查位置事件失败 {location.get('name', 'Unknown')}: {e}")
    
    async def _detect_congestion_event(self, location_name: str, 
                                     enhanced_data: EnhancedTrafficData):
        """检测拥堵事件"""
        if not enhanced_data.traffic_data:
            return
        
        congestion_ratio = enhanced_data.traffic_data.congestion_ratio
        
        # 检测严重拥堵
        if congestion_ratio >= self.congestion_threshold:
            priority = EventPriority.HIGH if congestion_ratio >= 0.9 else EventPriority.MEDIUM
            
            event = TrafficEvent(
                event_id=str(uuid.uuid4()),
                event_type=EventType.TRAFFIC_CONGESTION,
                priority=priority,
                title=f"{location_name}交通拥堵",
                description=f"拥堵比例: {congestion_ratio:.1%}",
                location_lng=enhanced_data.traffic_data.location_lng,
                location_lat=enhanced_data.traffic_data.location_lat,
                radius_km=enhanced_data.traffic_data.radius_km,
                timestamp=datetime.utcnow(),
                source="auto_detection",
                data={
                    "congestion_ratio": congestion_ratio,
                    "avg_speed": enhanced_data.traffic_data.avg_speed,
                    "total_roads": enhanced_data.traffic_data.total_roads
                }
            )
            
            await self._queue_event(event)
    
    async def _detect_accident_events(self, location_name: str, 
                                    enhanced_data: EnhancedTrafficData):
        """检测事故事件"""
        for accident in enhanced_data.accidents:
            # 检查是否为新事故
            if self._is_new_accident(accident):
                priority = EventPriority.CRITICAL if accident.severity in ["严重", "特大"] else EventPriority.HIGH
                
                event = TrafficEvent(
                    event_id=str(uuid.uuid4()),
                    event_type=EventType.ACCIDENT_DETECTED,
                    priority=priority,
                    title=f"{location_name}交通事故",
                    description=accident.title,
                    location_lng=enhanced_data.traffic_data.location_lng if enhanced_data.traffic_data else 0.0,
                    location_lat=enhanced_data.traffic_data.location_lat if enhanced_data.traffic_data else 0.0,
                    radius_km=3.0,
                    timestamp=datetime.utcnow(),
                    source="web_scraper",
                    data={
                        "accident_id": accident.accident_id,
                        "severity": accident.severity,
                        "location": accident.location,
                        "source": accident.source
                    }
                )
                
                await self._queue_event(event)
    
    async def _detect_emergency_events(self, location_name: str, 
                                     enhanced_data: EnhancedTrafficData):
        """检测紧急事件"""
        # 检查是否有紧急关键词
        for accident in enhanced_data.accidents:
            text = f"{accident.title} {accident.description}".lower()
            
            for keyword in self.emergency_keywords:
                if keyword in text:
                    event = TrafficEvent(
                        event_id=str(uuid.uuid4()),
                        event_type=EventType.EMERGENCY_VEHICLE,
                        priority=EventPriority.CRITICAL,
                        title=f"{location_name}紧急事件",
                        description=f"检测到紧急情况: {keyword}",
                        location_lng=enhanced_data.traffic_data.location_lng if enhanced_data.traffic_data else 0.0,
                        location_lat=enhanced_data.traffic_data.location_lat if enhanced_data.traffic_data else 0.0,
                        radius_km=5.0,
                        timestamp=datetime.utcnow(),
                        source="keyword_detection",
                        data={
                            "keyword": keyword,
                            "accident_id": accident.accident_id
                        }
                    )
                    
                    await self._queue_event(event)
                    break
    
    def _is_new_accident(self, accident: TrafficAccident) -> bool:
        """检查是否为新事故"""
        # 简单实现：检查最近1小时内是否已处理过
        cache_key = f"processed_accident:{accident.accident_id}"
        # 这里应该使用缓存来检查，简化实现
        return True
    
    async def _queue_event(self, event: TrafficEvent):
        """将事件加入队列"""
        success = self.event_queue.put(event)
        if success:
            self.stats["events_detected"] += 1
            logger.info(f"检测到事件: {event.event_type.value} - {event.title}")
        else:
            logger.error(f"事件队列已满，丢弃事件: {event.event_id}")
    
    async def _event_processor(self):
        """事件处理器"""
        while self.monitoring_active:
            try:
                # 批量处理事件
                events = self.event_queue.get_batch(max_batch_size=5, timeout=1.0)
                
                if not events:
                    await asyncio.sleep(0.1)
                    continue
                
                for event in events:
                    await self._process_single_event(event)
                
            except Exception as e:
                logger.error(f"事件处理错误: {e}")
                self.stats["processing_errors"] += 1
                await asyncio.sleep(1)
    
    async def _process_single_event(self, event: TrafficEvent):
        """处理单个事件"""
        start_time = time.time()
        
        try:
            # 标记为已处理
            event.processed = True
            event.processing_time = time.time() - start_time
            
            # 发布事件
            await self.event_publisher.publish_event(event)
            
            # 缓存事件
            await self._cache_event(event)
            
            self.stats["events_processed"] += 1
            
            logger.info(f"处理事件完成: {event.event_id} "
                       f"(耗时: {event.processing_time:.3f}s)")
            
        except Exception as e:
            logger.error(f"处理事件失败 {event.event_id}: {e}")
            self.stats["processing_errors"] += 1
    
    async def _cache_event(self, event: TrafficEvent):
        """缓存事件"""
        cache_key = f"event:{event.event_id}"
        event_data = asdict(event)
        await self.cache_manager.put(cache_key, event_data, ttl=3600)  # 1小时
    
    async def create_custom_event(self, event_type: EventType, title: str, 
                                 description: str, lng: float, lat: float, 
                                 priority: EventPriority = EventPriority.MEDIUM,
                                 data: Dict[str, Any] = None) -> str:
        """创建自定义事件"""
        event = TrafficEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            priority=priority,
            title=title,
            description=description,
            location_lng=lng,
            location_lat=lat,
            radius_km=3.0,
            timestamp=datetime.utcnow(),
            source="manual",
            data=data or {}
        )
        
        await self._queue_event(event)
        return event.event_id
    
    def add_event_subscription(self, subscription: EventSubscription) -> str:
        """添加事件订阅"""
        return self.event_publisher.subscribe(subscription)
    
    def remove_event_subscription(self, subscription_id: str) -> bool:
        """移除事件订阅"""
        return self.event_publisher.unsubscribe(subscription_id)
    
    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """获取综合统计信息"""
        uptime = datetime.utcnow() - self.stats["start_time"]
        
        return {
            "collector_stats": self.stats,
            "queue_stats": self.event_queue.get_stats(),
            "publisher_stats": self.event_publisher.get_stats(),
            "cache_stats": self.cache_manager.get_comprehensive_stats(),
            "uptime_seconds": uptime.total_seconds(),
            "monitoring_active": self.monitoring_active,
            "monitoring_locations": len(self.monitoring_locations)
        }

# WebSocket处理器
async def handle_websocket_connection(websocket: WebSocketServerProtocol, path: str, 
                                   event_collector: EventDrivenDataCollector):
    """处理WebSocket连接"""
    event_collector.event_publisher.add_websocket_connection(websocket)
    
    try:
        # 发送欢迎消息
        welcome_msg = {
            "type": "welcome",
            "message": "连接到事件驱动数据采集系统",
            "timestamp": datetime.utcnow().isoformat()
        }
        await websocket.send(json.dumps(welcome_msg, ensure_ascii=False))
        
        # 保持连接
        async for message in websocket:
            try:
                data = json.loads(message)
                
                # 处理客户端消息
                if data.get("type") == "subscribe":
                    # 处理订阅请求
                    await handle_subscription_request(websocket, data, event_collector)
                elif data.get("type") == "unsubscribe":
                    # 处理取消订阅请求
                    await handle_unsubscribe_request(websocket, data, event_collector)
                
            except json.JSONDecodeError:
                error_msg = {"type": "error", "message": "无效的JSON格式"}
                await websocket.send(json.dumps(error_msg))
            except Exception as e:
                error_msg = {"type": "error", "message": f"处理消息失败: {e}"}
                await websocket.send(json.dumps(error_msg))
                
    except websockets.exceptions.ConnectionClosed:
        logger.info("WebSocket连接已关闭")
    except Exception as e:
        logger.error(f"WebSocket处理错误: {e}")
    finally:
        event_collector.event_publisher.remove_websocket_connection(websocket)

async def handle_subscription_request(websocket: WebSocketServerProtocol, 
                                    data: Dict[str, Any], 
                                    event_collector: EventDrivenDataCollector):
    """处理订阅请求"""
    try:
        subscription_id = data.get("subscription_id", str(uuid.uuid4()))
        event_types = {EventType(t) for t in data.get("event_types", [])}
        priorities = {EventPriority(p) for p in data.get("priorities", [])}
        
        # 创建订阅
        subscription = EventSubscription(
            subscription_id=subscription_id,
            event_types=event_types,
            location_filters=data.get("location_filters", []),
            priority_filters=priorities,
            callback=lambda event: None  # WebSocket连接不需要回调
        )
        
        event_collector.add_event_subscription(subscription)
        
        response = {
            "type": "subscription_confirmed",
            "subscription_id": subscription_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        await websocket.send(json.dumps(response, ensure_ascii=False))
        
    except Exception as e:
        error_msg = {"type": "error", "message": f"订阅失败: {e}"}
        await websocket.send(json.dumps(error_msg))

async def handle_unsubscribe_request(websocket: WebSocketServerProtocol, 
                                  data: Dict[str, Any], 
                                  event_collector: EventDrivenDataCollector):
    """处理取消订阅请求"""
    try:
        subscription_id = data.get("subscription_id")
        if subscription_id:
            event_collector.remove_event_subscription(subscription_id)
        
        response = {
            "type": "unsubscription_confirmed",
            "subscription_id": subscription_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        await websocket.send(json.dumps(response, ensure_ascii=False))
        
    except Exception as e:
        error_msg = {"type": "error", "message": f"取消订阅失败: {e}"}
        await websocket.send(json.dumps(error_msg))

async def start_event_server(event_collector: EventDrivenDataCollector, 
                           host: str = "localhost", port: int = 8765):
    """启动WebSocket事件服务器"""
    logger.info(f"启动事件服务器: ws://{host}:{port}")
    
    # 使用partial传递event_collector参数
    from functools import partial
    handler = partial(handle_websocket_connection, event_collector=event_collector)
    
    async with websockets.serve(handler, host, port):
        await asyncio.Future()  # 保持服务器运行

async def test_event_driven_collector():
    """测试事件驱动采集器"""
    from enhanced_data_collector import ConcurrentDataCollector
    
    # 创建采集器
    collector = ConcurrentDataCollector()
    event_collector = EventDrivenDataCollector(collector)
    
    # 设置监控位置
    locations = [
        {
            "name": "杭州市中心",
            "lng": 120.15507,
            "lat": 30.27415,
            "radius_km": 3.0
        }
    ]
    
    # 启动监控
    await event_collector.start_monitoring(locations, check_interval_seconds=10)
    
    try:
        # 运行30秒进行测试
        await asyncio.sleep(30)
        
        # 显示统计信息
        stats = event_collector.get_comprehensive_stats()
        print("事件驱动采集统计:")
        print(json.dumps(stats, indent=2, default=str))
        
    finally:
        event_collector.stop_monitoring()
        await collector.close()

if __name__ == "__main__":
    asyncio.run(test_event_driven_collector())
