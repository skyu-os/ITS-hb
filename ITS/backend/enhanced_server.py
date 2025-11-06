"""
增强的API服务器
集成数据采集、预测模型、实时通信等功能
"""
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends, BackgroundTasks, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
import json
import asyncio
import logging
from datetime import datetime, timedelta
import hashlib
import hmac
import time
import os
from sqlalchemy.orm import Session

from database import get_db, TrafficData, PredictionResult, ModelMetrics, init_db
from data_collector import MultiSourceDataCollector, AmapDataCollector, ScheduledCollector
from deep_learning_predictor import TrafficPredictionService
import redis

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="智能交通预测API v2.0",
    description="基于深度学习的智能交通预测与数据分析服务",
    version="2.0.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局变量
data_collector = MultiSourceDataCollector()
prediction_service = TrafficPredictionService()
scheduled_collector = ScheduledCollector(data_collector)
websocket_connections = set()
redis_client = None

# API配置
API_SECRET = os.getenv("API_SECRET", "traffic-prediction-secret-key")

# 请求模型
class TrafficDataRequest(BaseModel):
    lng: float = Field(..., description="经度")
    lat: float = Field(..., description="纬度")
    radius_km: float = Field(3.0, description="半径(公里)")
    api_key: Optional[str] = Field(None, description="高德API密钥")
    include_events: bool = Field(True, description="是否包含交通事件")

class PredictionRequest(BaseModel):
    lng: float = Field(..., description="经度")
    lat: float = Field(..., description="纬度")
    prediction_horizon: int = Field(6, description="预测时长(小时)")
    model_type: str = Field("lstm", description="模型类型: lstm, multimodal")

class ModelTrainingRequest(BaseModel):
    days: int = Field(30, description="训练数据天数")
    force_retrain: bool = Field(False, description="是否强制重新训练")

class WebSocketMessage(BaseModel):
    type: str
    data: Dict[str, Any]
    timestamp: datetime

class ConnectionManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket连接建立，当前连接数: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket连接断开，当前连接数: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"发送个人消息失败: {str(e)}")
    
    async def broadcast(self, message: Dict[str, Any]):
        """广播消息给所有连接"""
        if not self.active_connections:
            return
        
        message_str = json.dumps(message, ensure_ascii=False, default=str)
        disconnected = []
        
        for connection in self.active_connections:
            try:
                await connection.send_text(message_str)
            except Exception as e:
                logger.error(f"广播消息失败: {str(e)}")
                disconnected.append(connection)
        
        # 移除断开的连接
        for conn in disconnected:
            self.active_connections.remove(conn)

manager = ConnectionManager()

def setup_redis():
    """设置Redis连接"""
    global redis_client
    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        redis_client = redis.from_url(redis_url, decode_responses=True)
        redis_client.ping()
        logger.info("Redis连接成功")
    except Exception as e:
        logger.warning(f"Redis连接失败: {str(e)}")
        redis_client = None

def verify_signature(payload: str, signature: str, secret: str) -> bool:
    """验证签名"""
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected_signature, signature)

async def init_services():
    """初始化服务"""
    try:
        # 初始化数据库
        init_db()
        logger.info("数据库初始化完成")
        
        # 设置Redis
        setup_redis()
        
        # 添加数据采集器
        amap_api_key = os.getenv("AMAP_API_KEY")
        if amap_api_key:
            amap_collector = AmapDataCollector(amap_api_key)
            data_collector.add_collector("amap", amap_collector)
            logger.info("高德数据采集器已添加")
        
        logger.info("所有服务初始化完成")
        
    except Exception as e:
        logger.error(f"服务初始化失败: {str(e)}")

@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    await init_services()
    
    # 启动后台任务
    asyncio.create_task(start_background_tasks())

async def start_background_tasks():
    """启动后台任务"""
    # 启动定时数据采集（可选）
    # asyncio.create_task(run_scheduled_collection())
    
    # 启动实时数据推送
    asyncio.create_task(broadcast_real_time_data())

async def run_scheduled_collection():
    """运行定时采集"""
    try:
        logger.info("启动定时数据采集...")
        scheduled_collector.start_scheduled_collection()
    except Exception as e:
        logger.error(f"定时采集启动失败: {str(e)}")

async def broadcast_real_time_data():
    """广播实时数据"""
    while True:
        try:
            # 获取最新的交通数据
            db = next(get_db())
            latest_data = db.query(TrafficData).order_by(
                TrafficData.timestamp.desc()
            ).limit(10).all()
            
            if latest_data:
                # 构造广播消息
                message = {
                    "type": "traffic_update",
                    "data": [
                        {
                            "timestamp": data.timestamp.isoformat(),
                            "location": {"lng": data.location_lng, "lat": data.location_lat},
                            "congestion_ratio": data.congestion_ratio,
                            "avg_speed": data.avg_speed,
                            "data_quality_score": data.data_quality_score,
                            "is_anomaly": data.is_anomaly
                        }
                        for data in latest_data
                    ]
                }
                
                await manager.broadcast(message)
            
            await asyncio.sleep(60)  # 每分钟推送一次
            
        except Exception as e:
            logger.error(f"实时数据广播失败: {str(e)}")
            await asyncio.sleep(30)

# API路由
@app.get("/", response_class=HTMLResponse)
async def root():
    """根路径"""
    return """
    <html>
        <head>
            <title>智能交通预测API</title>
        </head>
        <body>
            <h1>智能交通预测API v2.0</h1>
            <p>基于深度学习的智能交通预测与数据分析服务</p>
            <ul>
                <li><a href="/docs">API文档</a></li>
                <li><a href="/health">健康检查</a></li>
                <li><a href="/ws">WebSocket测试</a></li>
            </ul>
        </body>
    </html>
    """

@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "database": "connected",
            "redis": "connected" if redis_client else "disconnected",
            "data_collector": "ready",
            "prediction_service": "ready"
        }
    }

@app.post("/api/collect")
async def collect_traffic_data(request: TrafficDataRequest, background_tasks: BackgroundTasks):
    """采集交通数据"""
    try:
        # 添加高德数据采集器（如果尚未添加）
        if "amap" not in data_collector.collectors and request.api_key:
            amap_collector = AmapDataCollector(request.api_key)
            data_collector.add_collector("amap", amap_collector)
        
        # 异步采集数据
        background_tasks.add_task(
            collect_data_background, 
            request.lng, 
            request.lat, 
            request.radius_km,
            request.include_events
        )
        
        return {
            "success": True,
            "message": "数据采集任务已启动",
            "location": {"lng": request.lng, "lat": request.lat},
            "radius_km": request.radius_km,
            "include_events": request.include_events
        }
        
    except Exception as e:
        logger.error(f"数据采集失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"数据采集失败: {str(e)}")

async def collect_data_background(lng: float, lat: float, radius_km: float, include_events: bool = True):
    """后台数据采集任务"""
    try:
        # 获取高德数据采集器
        amap_collector = data_collector.collectors.get("amap")
        if amap_collector and include_events:
            # 并发采集路况和事件
            real_time_data = await amap_collector.collect_real_time_status(lng, lat, radius_km)
            
            # 保存路况数据
            if real_time_data.get("traffic_data"):
                traffic_data = real_time_data["traffic_data"]
                data_collector.save_to_database([traffic_data])
            
            # 广播综合数据
            message = {
                "type": "traffic_update_with_events",
                "data": {
                    "location": {"lng": lng, "lat": lat},
                    "traffic_data": {
                        "congestion_ratio": real_time_data.get("traffic_data", {}).congestion_ratio,
                        "avg_speed": real_time_data.get("traffic_data", {}).avg_speed,
                        "total_roads": real_time_data.get("traffic_data", {}).total_roads
                    },
                    "traffic_events": [
                        {
                            "event_id": event.event_id,
                            "event_type": event.event_type_name,
                            "road_name": event.road_name,
                            "status": event.status,
                            "time": event.time,
                            "lng": event.lng,
                            "lat": event.lat
                        }
                        for event in real_time_data.get("traffic_events", [])
                    ],
                    "event_count": real_time_data.get("event_count", 0),
                    "timestamp": real_time_data.get("timestamp")
                }
            }
            await manager.broadcast(message)
        else:
            # 传统数据采集
            data_points = await data_collector.collect_from_all_sources(lng, lat, radius_km)
            if data_points:
                data_collector.save_to_database(data_points)
                
                # 广播新数据
                message = {
                    "type": "new_data",
                    "data": {
                        "location": {"lng": lng, "lat": lat},
                        "data_count": len(data_points),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
                await manager.broadcast(message)
            
    except Exception as e:
        logger.error(f"后台数据采集失败: {str(e)}")

@app.get("/api/traffic-events")
async def get_traffic_events(
    lng: float,
    lat: float,
    radius_km: float = 3.0,
    db: Session = Depends(get_db)
):
    """获取交通事件信息"""
    try:
        # 获取高德数据采集器
        amap_collector = data_collector.collectors.get("amap")
        if not amap_collector:
            raise HTTPException(status_code=503, detail="高德数据采集器未初始化")
        
        # 采集实时交通事件
        events = await amap_collector.collect_traffic_events(lng, lat, radius_km)
        
        return {
            "success": True,
            "location": {"lng": lng, "lat": lat},
            "radius_km": radius_km,
            "event_count": len(events),
            "events": [
                {
                    "event_id": event.event_id,
                    "event_type": event.event_type,
                    "event_type_name": event.event_type_name,
                    "direction": event.direction,
                    "road_name": event.road_name,
                    "status": event.status,
                    "time": event.time,
                    "lng": event.lng,
                    "lat": event.lat,
                    "citycode": event.citycode,
                    "adcode": event.adcode
                }
                for event in events
            ],
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"获取交通事件失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取交通事件失败: {str(e)}")

@app.get("/api/real-time-traffic")
async def get_real_time_traffic(
    lng: float,
    lat: float,
    radius_km: float = 3.0,
    include_events: bool = True,
    db: Session = Depends(get_db)
):
    """获取实时综合交通信息"""
    try:
        # 获取高德数据采集器
        amap_collector = data_collector.collectors.get("amap")
        if not amap_collector:
            raise HTTPException(status_code=503, detail="高德数据采集器未初始化")
        
        # 采集实时综合数据
        real_time_data = await amap_collector.collect_real_time_status(lng, lat, radius_km)
        
        result = {
            "success": True,
            "location": {"lng": lng, "lat": lat},
            "radius_km": radius_km,
            "timestamp": real_time_data.get("timestamp"),
        }
        
        # 添加路况数据
        traffic_data = real_time_data.get("traffic_data")
        if traffic_data:
            result["traffic_data"] = {
                "congestion_ratio": traffic_data.congestion_ratio,
                "avg_speed": traffic_data.avg_speed,
                "total_roads": traffic_data.total_roads,
                "congested_roads": traffic_data.congested_roads,
                "slow_roads": traffic_data.slow_roads,
                "clear_roads": traffic_data.clear_roads,
                "data_quality_score": traffic_data.data_quality_score,
                "is_anomaly": traffic_data.is_anomaly
            }
        else:
            result["traffic_data"] = None
        
        # 添加交通事件
        if include_events:
            result["traffic_events"] = [
                {
                    "event_id": event.event_id,
                    "event_type": event.event_type_name,
                    "road_name": event.road_name,
                    "status": event.status,
                    "time": event.time,
                    "lng": event.lng,
                    "lat": event.lat
                }
                for event in real_time_data.get("traffic_events", [])
            ]
            result["event_count"] = real_time_data.get("event_count", 0)
        else:
            result["traffic_events"] = []
            result["event_count"] = 0
        
        return result
        
    except Exception as e:
        logger.error(f"获取实时交通信息失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取实时交通信息失败: {str(e)}")

@app.post("/api/predict")
async def predict_traffic(request: PredictionRequest):
    """交通预测"""
    try:
        result = prediction_service.predict_traffic(
            request.lng, 
            request.lat, 
            request.prediction_horizon
        )
        
        if result["success"]:
            # 保存预测结果到数据库
            db = next(get_db())
            try:
                # 保存第一个小时的预测结果
                first_prediction = result["predictions"][0] if result["predictions"] else None
                if first_prediction:
                    prediction_record = PredictionResult(
                        timestamp=datetime.utcnow(),
                        prediction_type=f"hourly_{request.prediction_horizon}h",
                        location_lng=request.lng,
                        location_lat=request.lat,
                        radius_km=3.0,
                        predicted_congestion=first_prediction["congestion_ratio"],
                        predicted_speed=first_prediction["predicted_speed"],
                        predicted_travel_time=30.0,  # 简化值
                        confidence_score=first_prediction["confidence_score"],
                        model_name=result["model_info"]["name"],
                        model_version=result["model_info"]["version"],
                        prediction_horizon_hours=request.prediction_horizon
                    )
                    db.add(prediction_record)
                    db.commit()
            finally:
                db.close()
        
        return result
        
    except Exception as e:
        logger.error(f"交通预测失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"交通预测失败: {str(e)}")

@app.post("/api/train-models")
async def train_models(request: ModelTrainingRequest):
    """训练预测模型"""
    try:
        # 异步训练模型
        task = asyncio.create_task(train_models_background(request.days, request.force_retrain))
        
        return {
            "success": True,
            "message": "模型训练任务已启动",
            "training_days": request.days,
            "force_retrain": request.force_retrain
        }
        
    except Exception as e:
        logger.error(f"模型训练启动失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"模型训练启动失败: {str(e)}")

async def train_models_background(days: int, force_retrain: bool):
    """后台模型训练任务"""
    try:
        logger.info(f"开始训练模型，使用 {days} 天的数据")
        
        success = prediction_service.train_models()
        
        # 广播训练结果
        message = {
            "type": "model_training_completed",
            "data": {
                "success": success,
                "training_days": days,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        await manager.broadcast(message)
        
        if success:
            logger.info("模型训练完成")
        else:
            logger.error("模型训练失败")
            
    except Exception as e:
        logger.error(f"后台模型训练失败: {str(e)}")
        
        # 广播训练失败消息
        message = {
            "type": "model_training_failed",
            "data": {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        await manager.broadcast(message)

@app.get("/api/traffic-history")
async def get_traffic_history(
    lng: float,
    lat: float,
    hours: int = 24,
    db: Session = Depends(get_db)
):
    """获取交通历史数据"""
    try:
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        traffic_data = db.query(TrafficData).filter(
            TrafficData.location_lng == lng,
            TrafficData.location_lat == lat,
            TrafficData.timestamp >= cutoff_time
        ).order_by(TrafficData.timestamp.desc()).all()
        
        return {
            "success": True,
            "location": {"lng": lng, "lat": lat},
            "time_range_hours": hours,
            "data_count": len(traffic_data),
            "data": [
                {
                    "timestamp": data.timestamp.isoformat(),
                    "congestion_ratio": data.congestion_ratio,
                    "avg_speed": data.avg_speed,
                    "total_roads": data.total_roads,
                    "data_quality_score": data.data_quality_score,
                    "is_anomaly": data.is_anomaly
                }
                for data in traffic_data
            ]
        }
        
    except Exception as e:
        logger.error(f"获取交通历史数据失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取数据失败: {str(e)}")

@app.get("/api/model-metrics")
async def get_model_metrics(db: Session = Depends(get_db)):
    """获取模型性能指标"""
    try:
        metrics = db.query(ModelMetrics).order_by(
            ModelMetrics.timestamp.desc()
        ).limit(20).all()
        
        return {
            "success": True,
            "metrics_count": len(metrics),
            "metrics": [
                {
                    "model_name": metric.model_name,
                    "model_version": metric.model_version,
                    "timestamp": metric.timestamp.isoformat(),
                    "mae": metric.mae,
                    "mse": metric.mse,
                    "rmse": metric.rmse,
                    "r2_score": metric.r2_score,
                    "mape": metric.mape
                }
                for metric in metrics
            ]
        }
        
    except Exception as e:
        logger.error(f"获取模型指标失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取指标失败: {str(e)}")

@app.get("/api/statistics")
async def get_statistics(db: Session = Depends(get_db)):
    """获取系统统计信息"""
    try:
        # 数据统计
        total_traffic_records = db.query(TrafficData).count()
        total_predictions = db.query(PredictionResult).count()
        
        # 最近24小时的数据
        yesterday = datetime.utcnow() - timedelta(hours=24)
        recent_traffic = db.query(TrafficData).filter(
            TrafficData.timestamp >= yesterday
        ).count()
        
        # 数据质量统计
        avg_quality = db.query(TrafficData).all()
        if avg_quality:
            avg_quality_score = sum(d.data_quality_score for d in avg_quality) / len(avg_quality)
            anomaly_count = sum(1 for d in avg_quality if d.is_anomaly)
        else:
            avg_quality_score = 0
            anomaly_count = 0
        
        return {
            "success": True,
            "statistics": {
                "total_traffic_records": total_traffic_records,
                "total_predictions": total_predictions,
                "recent_24h_records": recent_traffic,
                "avg_data_quality_score": round(avg_quality_score, 3),
                "anomaly_count": anomaly_count,
                "websocket_connections": len(manager.active_connections),
                "redis_status": "connected" if redis_client else "disconnected"
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"获取统计信息失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取统计失败: {str(e)}")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket端点"""
    await manager.connect(websocket)
    try:
        while True:
            # 接收客户端消息
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                
                # 处理不同类型的消息
                if message.get("type") == "subscribe":
                    # 客户端订阅特定位置的数据
                    location = message.get("location")
                    if location:
                        await manager.send_personal_message(
                            json.dumps({
                                "type": "subscription_confirmed",
                                "location": location,
                                "timestamp": datetime.utcnow().isoformat()
                            }),
                            websocket
                        )
                
                elif message.get("type") == "ping":
                    # 心跳检测
                    await manager.send_personal_message(
                        json.dumps({
                            "type": "pong",
                            "timestamp": datetime.utcnow().isoformat()
                        }),
                        websocket
                    )
                    
            except json.JSONDecodeError:
                await manager.send_personal_message(
                    json.dumps({
                        "type": "error",
                        "message": "Invalid JSON format"
                    }),
                    websocket
                )
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket处理错误: {str(e)}")
        manager.disconnect(websocket)

@app.get("/ws", response_class=HTMLResponse)
async def websocket_test_page():
    """WebSocket测试页面"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>WebSocket测试</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .messages { border: 1px solid #ccc; height: 300px; overflow-y: scroll; padding: 10px; margin: 10px 0; }
            .message { margin: 5px 0; padding: 5px; }
            .traffic { background-color: #e3f2fd; }
            .system { background-color: #f3e5f5; }
            button { padding: 10px 20px; margin: 5px; }
        </style>
    </head>
    <body>
        <h1>WebSocket实时数据测试</h1>
        <div class="messages" id="messages"></div>
        <button onclick="subscribe()">订阅数据</button>
        <button onclick="ping()">发送心跳</button>
        <button onclick="disconnect()">断开连接</button>
        
        <script>
            const ws = new WebSocket('ws://localhost:8003/ws');
            const messages = document.getElementById('messages');
            
            ws.onopen = function(event) {
                addMessage('系统', 'WebSocket连接已建立', 'system');
            };
            
            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                addMessage('服务器', JSON.stringify(data, null, 2), 'traffic');
            };
            
            ws.onclose = function(event) {
                addMessage('系统', 'WebSocket连接已断开', 'system');
            };
            
            ws.onerror = function(error) {
                addMessage('系统', 'WebSocket错误: ' + error, 'system');
            };
            
            function addMessage(sender, content, type) {
                const div = document.createElement('div');
                div.className = 'message ' + type;
                div.innerHTML = `<strong>${sender}:</strong> ${content}`;
                messages.appendChild(div);
                messages.scrollTop = messages.scrollHeight;
            }
            
            function subscribe() {
                ws.send(JSON.stringify({
                    type: 'subscribe',
                    location: { lng: 120.15507, lat: 30.27415 }
                }));
            }
            
            function ping() {
                ws.send(JSON.stringify({ type: 'ping' }));
            }
            
            function disconnect() {
                ws.close();
            }
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8003)
