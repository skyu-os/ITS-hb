"""
数据库模型和连接配置
"""
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# 数据库配置
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./traffic_data.db")

# 创建数据库引擎
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class TrafficData(Base):
    """交通数据表"""
    __tablename__ = "traffic_data"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    location_lng = Column(Float, nullable=False, index=True)
    location_lat = Column(Float, nullable=False, index=True)
    radius_km = Column(Float, default=3.0)
    
    # 交通统计数据
    total_roads = Column(Integer, default=0)
    congested_roads = Column(Integer, default=0)
    slow_roads = Column(Integer, default=0)
    clear_roads = Column(Integer, default=0)
    avg_speed = Column(Float, nullable=True)
    congestion_ratio = Column(Float, default=0.0)
    
    # 原始数据
    raw_data = Column(Text, nullable=True)  # JSON格式的原始数据
    
    # 数据质量标记
    data_quality_score = Column(Float, default=1.0)
    is_anomaly = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)

class PredictionResult(Base):
    """预测结果表"""
    __tablename__ = "prediction_results"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    prediction_type = Column(String(50), nullable=False)  # hourly, daily, weekly
    location_lng = Column(Float, nullable=False)
    location_lat = Column(Float, nullable=False)
    radius_km = Column(Float, default=3.0)
    
    # 预测指标
    predicted_congestion = Column(Float, nullable=False)
    predicted_speed = Column(Float, nullable=False)
    predicted_travel_time = Column(Float, nullable=False)
    confidence_score = Column(Float, default=0.0)
    
    # 模型信息
    model_name = Column(String(100), nullable=False)
    model_version = Column(String(20), nullable=False)
    feature_importance = Column(Text, nullable=True)  # JSON格式
    
    # 实际结果（用于模型评估）
    actual_congestion = Column(Float, nullable=True)
    actual_speed = Column(Float, nullable=True)
    actual_travel_time = Column(Float, nullable=True)
    
    prediction_horizon_hours = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)

class DataSource(Base):
    """数据源配置表"""
    __tablename__ = "data_sources"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    type = Column(String(50), nullable=False)  # api, file, stream
    url = Column(String(500), nullable=True)
    api_key = Column(String(200), nullable=True)
    config = Column(Text, nullable=True)  # JSON格式的配置
    is_active = Column(Boolean, default=True)
    last_fetch = Column(DateTime, nullable=True)
    fetch_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ModelMetrics(Base):
    """模型性能指标表"""
    __tablename__ = "model_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String(100), nullable=False)
    model_version = Column(String(20), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # 评估指标
    mae = Column(Float, nullable=True)  # 平均绝对误差
    mse = Column(Float, nullable=True)  # 均方误差
    rmse = Column(Float, nullable=True)  # 均方根误差
    r2_score = Column(Float, nullable=True)  # R²分数
    mape = Column(Float, nullable=True)  # 平均绝对百分比误差
    
    # 训练信息
    training_samples = Column(Integer, default=0)
    training_time_seconds = Column(Float, default=0)
    feature_count = Column(Integer, default=0)
    
    # 模型参数
    hyperparameters = Column(Text, nullable=True)  # JSON格式

def get_db() -> Session:
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """初始化数据库"""
    Base.metadata.create_all(bind=engine)

# 创建默认数据源
def create_default_data_sources():
    db = SessionLocal()
    try:
        # 检查是否已存在默认数据源
        existing = db.query(DataSource).filter(DataSource.name == "高德交通API").first()
        if not existing:
            amap_source = DataSource(
                name="高德交通API",
                type="api",
                url="https://restapi.amap.com/v3/traffic/status",
                config='{"extensions": "all", "output": "json"}',
                is_active=True
            )
            db.add(amap_source)
            db.commit()
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
    create_default_data_sources()
    print("数据库初始化完成")
