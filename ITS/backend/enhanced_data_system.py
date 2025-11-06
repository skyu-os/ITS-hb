"""
增强的数据采集系统启动脚本
整合所有优化模块：爬虫、并发采集、智能缓存、事件驱动
"""
import asyncio
import logging
import os
import signal
import sys
from datetime import datetime
from typing import Dict, List, Any

# 导入我们的优化模块
from enhanced_data_collector import ConcurrentDataCollector
from event_driven_collector import EventDrivenDataCollector, start_event_server
from smart_cache import SmartCacheManager, CacheConfig
from web_scraper import EnhancedMultiSourceScraper
from database import init_db
from performance_test import PerformanceTestSuite

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/enhanced_system_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class EnhancedDataSystem:
    """增强的数据采集系统"""
    
    def __init__(self):
        self.running = False
        self.collector = None
        self.event_collector = None
        self.cache_manager = None
        self.web_scraper = None
        self.event_server_task = None
        self.scraper_task = None
        
        # 配置监控位置
        self.monitoring_locations = [
            {
                "name": "杭州市中心",
                "lng": 120.15507,
                "lat": 30.27415,
                "radius_km": 3.0
            },
            {
                "name": "西湖景区",
                "lng": 120.16199,
                "lat": 30.27991,
                "radius_km": 2.5
            },
            {
                "name": "钱江新城",
                "lng": 120.21083,
                "lat": 30.24785,
                "radius_km": 3.0
            },
            {
                "name": "武林广场",
                "lng": 120.16939,
                "lat": 30.27639,
                "radius_km": 2.0
            },
            {
                "name": "杭州东站",
                "lng": 120.21887,
                "lat": 30.26231,
                "radius_km": 3.5
            }
        ]
    
    async def initialize(self):
        """初始化系统"""
        logger.info("初始化增强数据采集系统...")
        
        try:
            # 初始化数据库
            init_db()
            logger.info("数据库初始化完成")
            
            # 初始化缓存管理器
            cache_config = CacheConfig(
                enable_compression=True,
                compression_threshold=512,
                enable_preload=True,
                preload_interval=30
            )
            self.cache_manager = SmartCacheManager(cache_config)
            logger.info("缓存管理器初始化完成")
            
            # 初始化网络爬虫
            self.web_scraper = EnhancedMultiSourceScraper()
            logger.info("网络爬虫初始化完成")
            
            # 初始化并发数据采集器
            self.collector = ConcurrentDataCollector()
            logger.info("并发数据采集器初始化完成")
            
            # 初始化事件驱动采集器
            self.event_collector = EventDrivenDataCollector(self.collector)
            logger.info("事件驱动采集器初始化完成")
            
            logger.info("系统初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"系统初始化失败: {e}")
            return False
    
    async def start(self):
        """启动系统"""
        if not await self.initialize():
            return False
        
        logger.info("启动增强数据采集系统...")
        self.running = True
        
        try:
            # 启动网络爬虫后台任务
            self.scraper_task = asyncio.create_task(
                self.web_scraper.start_continuous_scraping(interval_minutes=5)
            )
            logger.info("网络爬虫任务已启动")
            
            # 启动事件驱动监控
            await self.event_collector.start_monitoring(
                self.monitoring_locations,
                check_interval_seconds=30
            )
            logger.info("事件驱动监控已启动")
            
            # 启动WebSocket事件服务器
            self.event_server_task = asyncio.create_task(
                start_event_server(self.event_collector, host="0.0.0.0", port=8765)
            )
            logger.info("WebSocket事件服务器已启动")
            
            # 启动定期数据保存任务
            asyncio.create_task(self._periodic_data_saver())
            logger.info("定期数据保存任务已启动")
            
            # 启动系统健康检查
            asyncio.create_task(self._health_check())
            logger.info("系统健康检查已启动")
            
            logger.info("增强数据采集系统启动完成")
            
            # 显示系统状态
            await self._display_system_status()
            
            return True
            
        except Exception as e:
            logger.error(f"系统启动失败: {e}")
            return False
    
    async def stop(self):
        """停止系统"""
        logger.info("正在停止增强数据采集系统...")
        self.running = False
        
        try:
            # 停止事件监控
            if self.event_collector:
                self.event_collector.stop_monitoring()
                logger.info("事件驱动监控已停止")
            
            # 停止爬虫任务
            if self.scraper_task:
                self.scraper_task.cancel()
                try:
                    await self.scraper_task
                except asyncio.CancelledError:
                    pass
                logger.info("网络爬虫任务已停止")
            
            # 停止事件服务器
            if self.event_server_task:
                self.event_server_task.cancel()
                try:
                    await self.event_server_task
                except asyncio.CancelledError:
                    pass
                logger.info("WebSocket事件服务器已停止")
            
            # 关闭采集器
            if self.collector:
                await self.collector.close()
                logger.info("数据采集器已关闭")
            
            # 清理缓存
            if self.cache_manager:
                self.cache_manager.stop_preload_scheduler()
                logger.info("缓存管理器已停止")
            
            logger.info("增强数据采集系统已完全停止")
            
        except Exception as e:
            logger.error(f"系统停止时发生错误: {e}")
    
    async def _periodic_data_saver(self):
        """定期数据保存任务"""
        while self.running:
            try:
                # 每10分钟执行一次数据保存
                await asyncio.sleep(600)
                
                if not self.running:
                    break
                
                logger.info("执行定期数据保存...")
                
                # 保存最新的增强数据
                for location in self.monitoring_locations[:3]:  # 只保存前3个位置
                    try:
                        enhanced_data = await self.collector.collect_enhanced_data(
                            location["lng"], location["lat"], location["radius_km"]
                        )
                        if enhanced_data:
                            self.collector.save_to_database(
                                enhanced_data, location["lng"], location["lat"]
                            )
                            logger.info(f"已保存 {location['name']} 的数据")
                    except Exception as e:
                        logger.error(f"保存 {location['name']} 数据失败: {e}")
                
            except Exception as e:
                logger.error(f"定期数据保存任务出错: {e}")
    
    async def _health_check(self):
        """系统健康检查"""
        while self.running:
            try:
                # 每5分钟执行一次健康检查
                await asyncio.sleep(300)
                
                if not self.running:
                    break
                
                # 检查系统组件状态
                health_status = await self._check_system_health()
                
                if health_status["overall_health"] == "unhealthy":
                    logger.warning(f"系统健康检查发现问题: {health_status}")
                
            except Exception as e:
                logger.error(f"健康检查任务出错: {e}")
    
    async def _check_system_health(self) -> Dict[str, Any]:
        """检查系统健康状态"""
        health_status = {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_health": "healthy",
            "components": {}
        }
        
        try:
            # 检查采集器状态
            if self.collector:
                collector_stats = self.collector.get_collection_stats()
                success_rate = collector_stats.get("success_rate", 0)
                health_status["components"]["collector"] = {
                    "status": "healthy" if success_rate > 80 else "degraded",
                    "success_rate": success_rate
                }
            
            # 检查缓存状态
            if self.cache_manager:
                cache_stats = self.cache_manager.get_comprehensive_stats()
                overall_hit_rate = cache_stats["global"].get("overall_hit_rate", 0)
                health_status["components"]["cache"] = {
                    "status": "healthy" if overall_hit_rate > 70 else "degraded",
                    "hit_rate": overall_hit_rate
                }
            
            # 检查事件系统状态
            if self.event_collector:
                event_stats = self.event_collector.get_comprehensive_stats()
                monitoring_active = event_stats.get("monitoring_active", False)
                health_status["components"]["event_system"] = {
                    "status": "healthy" if monitoring_active else "unhealthy",
                    "monitoring_active": monitoring_active
                }
            
            # 综合评估
            unhealthy_components = [
                name for name, info in health_status["components"].items()
                if info["status"] == "unhealthy"
            ]
            
            if unhealthy_components:
                health_status["overall_health"] = "unhealthy"
            elif any(info["status"] == "degraded" for info in health_status["components"].values()):
                health_status["overall_health"] = "degraded"
            
        except Exception as e:
            health_status["overall_health"] = "unhealthy"
            health_status["error"] = str(e)
        
        return health_status
    
    async def _display_system_status(self):
        """显示系统状态"""
        logger.info("="*60)
        logger.info("增强数据采集系统状态")
        logger.info("="*60)
        
        logger.info(f"监控位置数量: {len(self.monitoring_locations)}")
        logger.info(f"系统运行状态: {'运行中' if self.running else '已停止'}")
        
        # 显示监控位置
        for location in self.monitoring_locations:
            logger.info(f"  - {location['name']}: ({location['lng']}, {location['lat']})")
        
        logger.info("="*60)
    
    async def run_performance_test(self):
        """运行性能测试"""
        logger.info("开始运行性能测试...")
        
        test_suite = PerformanceTestSuite()
        await test_suite.run_all_tests()
        
        # 显示测试结果摘要
        results = test_suite.results
        
        logger.info("性能测试结果摘要:")
        logger.info("="*40)
        
        if "data_collection" in results:
            dc = results["data_collection"]
            logger.info(f"数据采集性能:")
            logger.info(f"  平均采集时间: {dc['avg_collection_time']:.2f}s")
            logger.info(f"  成功率: {dc['success_rate']:.1f}%")
        
        if "cache_performance" in results:
            cp = results["cache_performance"]
            logger.info(f"缓存性能:")
            logger.info(f"  平均读取时间: {cp['avg_get_time']*1000:.2f}ms")
            logger.info(f"  命中率: {cp['hit_rate']:.1f}%")
        
        if "event_processing" in results:
            ep = results["event_processing"]
            logger.info(f"事件处理性能:")
            logger.info(f"  平均处理时间: {ep['avg_event_time']:.3f}s")
            logger.info(f"  处理率: {ep['processing_rate']:.1f} events/s")
        
        logger.info("="*40)
        logger.info("详细报告已保存到 performance_report_*.json")

# 全局系统实例
enhanced_system = None

async def main():
    """主函数"""
    global enhanced_system
    
    # 检查命令行参数
    if len(sys.argv) > 1:
        if sys.argv[1] == "--test":
            # 只运行性能测试
            system = EnhancedDataSystem()
            await system.run_performance_test()
            return
        elif sys.argv[1] == "--help":
            print("用法:")
            print("  python enhanced_data_system.py          # 启动完整系统")
            print("  python enhanced_data_system.py --test   # 运行性能测试")
            print("  python enhanced_data_system.py --help   # 显示帮助")
            return
    
    # 创建系统实例
    enhanced_system = EnhancedDataSystem()
    
    # 设置信号处理
    def signal_handler(signum, frame):
        logger.info(f"接收到信号 {signum}，正在关闭系统...")
        asyncio.create_task(enhanced_system.stop())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # 启动系统
        if await enhanced_system.start():
            logger.info("系统正在运行，按 Ctrl+C 停止...")
            
            # 保持运行
            while enhanced_system.running:
                await asyncio.sleep(1)
        else:
            logger.error("系统启动失败")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("接收到键盘中断信号")
    except Exception as e:
        logger.error(f"系统运行时发生错误: {e}")
    finally:
        # 停止系统
        if enhanced_system:
            await enhanced_system.stop()

if __name__ == "__main__":
    # 确保日志目录存在
    os.makedirs("logs", exist_ok=True)
    
    # 运行主程序
    asyncio.run(main())
