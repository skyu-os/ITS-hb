"""
增强后端服务启动脚本
支持数据库初始化、模型训练、服务启动等功能
"""
import os
import sys
import argparse
import asyncio
import logging
from datetime import datetime
from pathlib import Path

# 添加当前目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from database import init_db, create_default_data_sources
from data_collector import MultiSourceDataCollector, AmapDataCollector, ScheduledCollector
from deep_learning_predictor import TrafficPredictionService
from enhanced_server import app
import uvicorn

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('backend.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def init_environment():
    """初始化环境"""
    # 检查环境变量文件
    env_file = Path('.env')
    if not env_file.exists():
        env_example = Path('.env.example')
        if env_example.exists():
            logger.info("复制环境变量示例文件...")
            import shutil
            shutil.copy('.env.example', '.env')
            logger.warning("请编辑 .env 文件配置您的API密钥和其他设置")
        else:
            logger.error("未找到 .env.example 文件")
            return False
    
    # 加载环境变量
    from dotenv import load_dotenv
    load_dotenv()
    
    # 检查必要的配置
    required_vars = ['AMAP_API_KEY']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.warning(f"缺少以下环境变量: {missing_vars}")
        logger.info("请在 .env 文件中配置这些变量")
    
    return True

def init_database():
    """初始化数据库"""
    try:
        logger.info("初始化数据库...")
        init_db()
        create_default_data_sources()
        logger.info("数据库初始化完成")
        return True
    except Exception as e:
        logger.error(f"数据库初始化失败: {str(e)}")
        return False

async def train_initial_models():
    """训练初始模型"""
    try:
        logger.info("开始训练初始预测模型...")
        
        prediction_service = TrafficPredictionService()
        
        # 检查是否有足够的数据
        try:
            X, y_congestion, y_speed = prediction_service.prepare_training_data(7)  # 先检查7天的数据
            if len(X) < 50:
                logger.warning(f"数据量不足，当前只有 {len(X)} 个样本，需要至少50个样本")
                logger.info("建议先运行数据采集任务积累更多数据")
                return False
        except Exception as e:
            logger.warning(f"检查训练数据时出错: {str(e)}")
            logger.info("将尝试使用30天的数据进行训练")
        
        # 训练模型
        success = prediction_service.train_models()
        
        if success:
            logger.info("初始模型训练完成")
            return True
        else:
            logger.error("初始模型训练失败")
            return False
            
    except Exception as e:
        logger.error(f"训练初始模型时发生错误: {str(e)}")
        return False

async def collect_initial_data():
    """采集初始数据"""
    try:
        logger.info("开始采集初始交通数据...")
        
        # 创建数据采集器
        data_collector = MultiSourceDataCollector()
        amap_api_key = os.getenv("AMAP_API_KEY")
        
        if not amap_api_key:
            logger.warning("未配置高德API密钥，跳过数据采集")
            return False
        
        amap_collector = AmapDataCollector(amap_api_key)
        data_collector.add_collector("amap", amap_collector)
        
        # 采集一些关键位置的数据
        locations = [
            {"lng": 120.15507, "lat": 30.27415, "name": "杭州市中心"},
            {"lng": 120.16199, "lat": 30.27991, "name": "西湖"},
            {"lng": 120.21083, "lat": 30.24785, "name": "钱江新城"}
        ]
        
        total_data_points = 0
        for location in locations:
            try:
                logger.info(f"采集 {location['name']} 的交通数据...")
                data_points = await data_collector.collect_from_all_sources(
                    location["lng"], location["lat"], 3.0
                )
                
                if data_points:
                    data_collector.save_to_database(data_points)
                    total_data_points += len(data_points)
                    logger.info(f"成功采集 {location['name']} 的 {len(data_points)} 条数据")
                else:
                    logger.warning(f"未能采集到 {location['name']} 的数据")
                    
            except Exception as e:
                logger.error(f"采集 {location['name']} 数据失败: {str(e)}")
        
        logger.info(f"初始数据采集完成，共采集 {total_data_points} 条数据")
        return total_data_points > 0
        
    except Exception as e:
        logger.error(f"初始数据采集失败: {str(e)}")
        return False

def start_server(host: str = "127.0.0.1", port: int = 8003, reload: bool = False):
    """启动服务器"""
    try:
        logger.info(f"启动智能交通预测API服务器...")
        logger.info(f"服务地址: http://{host}:{port}")
        logger.info(f"API文档: http://{host}:{port}/docs")
        logger.info(f"WebSocket测试: http://{host}:{port}/ws")
        
        uvicorn.run(
            "enhanced_server:app",
            host=host,
            port=port,
            reload=reload,
            log_level="info"
        )
        
    except Exception as e:
        logger.error(f"启动服务器失败: {str(e)}")
        return False

async def run_full_setup():
    """运行完整设置流程"""
    logger.info("=" * 50)
    logger.info("智能交通预测系统初始化")
    logger.info("=" * 50)
    
    # 1. 初始化环境
    if not init_environment():
        logger.error("环境初始化失败")
        return False
    
    # 2. 初始化数据库
    if not init_database():
        logger.error("数据库初始化失败")
        return False
    
    # 3. 采集初始数据
    logger.info("\n" + "=" * 30)
    logger.info("步骤 1: 采集初始数据")
    logger.info("=" * 30)
    data_success = await collect_initial_data()
    
    if data_success:
        logger.info("✓ 初始数据采集成功")
    else:
        logger.warning("⚠ 初始数据采集失败或数据不足")
        logger.info("系统仍可启动，但预测功能可能受限")
    
    # 4. 训练初始模型
    logger.info("\n" + "=" * 30)
    logger.info("步骤 2: 训练初始模型")
    logger.info("=" * 30)
    model_success = await train_initial_models()
    
    if model_success:
        logger.info("✓ 初始模型训练成功")
    else:
        logger.warning("⚠ 初始模型训练失败")
        logger.info("系统仍可启动，可在运行时重新训练模型")
    
    # 5. 启动服务器
    logger.info("\n" + "=" * 30)
    logger.info("步骤 3: 启动服务器")
    logger.info("=" * 30)
    
    logger.info("系统初始化完成，启动服务器...")
    logger.info("使用 --help 查看可用选项")
    
    return True

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="智能交通预测系统启动脚本")
    
    parser.add_argument("--init-only", action="store_true", 
                       help="仅初始化系统，不启动服务器")
    parser.add_argument("--collect-only", action="store_true",
                       help="仅采集数据，不启动服务器")
    parser.add_argument("--train-only", action="store_true",
                       help="仅训练模型，不启动服务器")
    parser.add_argument("--skip-init", action="store_true",
                       help="跳过初始化，直接启动服务器")
    parser.add_argument("--host", default="127.0.0.1",
                       help="服务器主机地址 (默认: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8003,
                       help="服务器端口 (默认: 8003)")
    parser.add_argument("--reload", action="store_true",
                       help="启用自动重载（开发模式）")
    
    args = parser.parse_args()
    
    try:
        if args.skip_init:
            # 直接启动服务器
            start_server(args.host, args.port, args.reload)
        elif args.init_only:
            # 仅初始化
            asyncio.run(run_full_setup())
            logger.info("初始化完成")
        elif args.collect_only:
            # 仅采集数据
            if not init_environment():
                return 1
            if not init_database():
                return 1
            success = asyncio.run(collect_initial_data())
            return 0 if success else 1
        elif args.train_only:
            # 仅训练模型
            if not init_environment():
                return 1
            if not init_database():
                return 1
            success = asyncio.run(train_initial_models())
            return 0 if success else 1
        else:
            # 完整流程
            if asyncio.run(run_full_setup()):
                start_server(args.host, args.port, args.reload)
            else:
                logger.error("系统初始化失败")
                return 1
    
    except KeyboardInterrupt:
        logger.info("用户中断操作")
        return 0
    except Exception as e:
        logger.error(f"运行时发生错误: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
