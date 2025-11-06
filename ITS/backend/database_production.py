"""生产环境数据库配置"""
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import redis

# 数据库URL
DATABASE_URL = os.getenv(
    'DATABASE_URL',
    'postgresql://traffic_user:traffic_secure_pass_2024@db.railway.com:5432/traffic_db'
)

# 创建数据库引擎
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_recycle=300,
    pool_pre_ping=True,
    echo=False
)

# 创建会话
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建基础模型
Base = declarative_base()

# Redis配置
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis.railway.com:6379/0')
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """初始化数据库"""
    Base.metadata.create_all(bind=engine)
