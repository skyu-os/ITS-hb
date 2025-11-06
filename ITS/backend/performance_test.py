"""
性能测试和优化脚本 - 测试数据采集系统的性能提升
包括并发测试、缓存性能、事件处理等
"""
import asyncio
import time
import json
import logging
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Any
import matplotlib.pyplot as plt
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
import psutil
import os

# 导入我们的模块
from enhanced_data_collector import ConcurrentDataCollector
from event_driven_collector import EventDrivenDataCollector, EventType, EventPriority
from smart_cache import SmartCacheManager
from web_scraper import EnhancedMultiSourceScraper

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PerformanceTestSuite:
    """性能测试套件"""
    
    def __init__(self):
        self.results = {}
        self.test_locations = [
            {"name": "杭州市中心", "lng": 120.15507, "lat": 30.27415},
            {"name": "西湖", "lng": 120.16199, "lat": 30.27991},
            {"name": "钱江新城", "lng": 120.21083, "lat": 30.24785},
            {"name": "武林广场", "lng": 120.16939, "lat": 30.27639},
            {"name": "杭州东站", "lng": 120.21887, "lat": 30.26231}
        ]
    
    async def run_all_tests(self):
        """运行所有性能测试"""
        logger.info("开始运行性能测试套件...")
        
        # 测试1: 数据采集性能
        await self.test_data_collection_performance()
        
        # 测试2: 缓存性能
        await self.test_cache_performance()
        
        # 测试3: 事件处理性能
        await self.test_event_processing_performance()
        
        # 测试4: 并发性能
        await self.test_concurrent_performance()
        
        # 测试5: 内存和CPU使用率
        await self.test_resource_usage()
        
        # 生成性能报告
        self.generate_performance_report()
        
        logger.info("性能测试完成")
    
    async def test_data_collection_performance(self):
        """测试数据采集性能"""
        logger.info("测试数据采集性能...")
        
        collector = ConcurrentDataCollector()
        collection_times = []
        success_count = 0
        
        try:
            # 测试10次采集
            for i in range(10):
                start_time = time.time()
                
                for location in self.test_locations:
                    try:
                        enhanced_data = await collector.collect_enhanced_data(
                            location["lng"], location["lat"], 3.0
                        )
                        if enhanced_data:
                            success_count += 1
                    except Exception as e:
                        logger.error(f"采集失败 {location['name']}: {e}")
                
                end_time = time.time()
                collection_times.append(end_time - start_time)
                
                logger.info(f"第 {i+1} 次采集完成，耗时: {collection_times[-1]:.2f}s")
                
                # 间隔5秒
                await asyncio.sleep(5)
        
        finally:
            await collector.close()
        
        # 计算统计数据
        self.results["data_collection"] = {
            "avg_collection_time": statistics.mean(collection_times),
            "min_collection_time": min(collection_times),
            "max_collection_time": max(collection_times),
            "success_rate": (success_count / (10 * len(self.test_locations))) * 100,
            "total_collections": len(collection_times),
            "locations_tested": len(self.test_locations)
        }
        
        logger.info(f"数据采集性能测试完成 - 平均耗时: {self.results['data_collection']['avg_collection_time']:.2f}s")
    
    async def test_cache_performance(self):
        """测试缓存性能"""
        logger.info("测试缓存性能...")
        
        cache = SmartCacheManager()
        cache_times = {
            "put": [],
            "get": [],
            "hit_rate": []
        }
        
        try:
            # 测试缓存写入性能
            for i in range(1000):
                test_data = {"data": f"test_data_{i}", "timestamp": datetime.utcnow().isoformat()}
                
                start_time = time.time()
                await cache.put(f"test_key_{i}", test_data)
                put_time = time.time() - start_time
                cache_times["put"].append(put_time)
            
            # 测试缓存读取性能
            hits = 0
            for i in range(1000):
                start_time = time.time()
                result = await cache.get(f"test_key_{i}")
                get_time = time.time() - start_time
                cache_times["get"].append(get_time)
                
                if result:
                    hits += 1
            
            # 测试缓存命中率
            hit_rate = (hits / 1000) * 100
            
            self.results["cache_performance"] = {
                "avg_put_time": statistics.mean(cache_times["put"]),
                "avg_get_time": statistics.mean(cache_times["get"]),
                "hit_rate": hit_rate,
                "total_operations": 2000,
                "cache_stats": cache.get_comprehensive_stats()
            }
            
            logger.info(f"缓存性能测试完成 - 写入: {self.results['cache_performance']['avg_put_time']*1000:.2f}ms, "
                       f"读取: {self.results['cache_performance']['avg_get_time']*1000:.2f}ms, "
                       f"命中率: {hit_rate:.1f}%")
        
        finally:
            await cache.clear()
    
    async def test_event_processing_performance(self):
        """测试事件处理性能"""
        logger.info("测试事件处理性能...")
        
        collector = ConcurrentDataCollector()
        event_collector = EventDrivenDataCollector(collector)
        
        event_times = []
        processed_events = 0
        
        try:
            # 启动事件监控
            await event_collector.start_monitoring(self.test_locations[:2], check_interval_seconds=5)
            
            # 手动创建测试事件
            for i in range(50):
                start_time = time.time()
                
                event_id = await event_collector.create_custom_event(
                    event_type=EventType.DATA_UPDATE,
                    title=f"测试事件 {i+1}",
                    description=f"这是第 {i+1} 个测试事件",
                    lng=self.test_locations[i % len(self.test_locations)]["lng"],
                    lat=self.test_locations[i % len(self.test_locations)]["lat"],
                    priority=EventPriority.MEDIUM
                )
                
                end_time = time.time()
                event_times.append(end_time - start_time)
                
                # 等待事件处理
                await asyncio.sleep(0.5)
            
            # 等待所有事件处理完成
            await asyncio.sleep(10)
            
            processed_events = event_collector.stats["events_processed"]
            
        finally:
            event_collector.stop_monitoring()
            await collector.close()
        
        self.results["event_processing"] = {
            "avg_event_time": statistics.mean(event_times),
            "min_event_time": min(event_times),
            "max_event_time": max(event_times),
            "total_events": len(event_times),
            "processed_events": processed_events,
            "processing_rate": processed_events / max(1, sum(event_times))
        }
        
        logger.info(f"事件处理性能测试完成 - 平均处理时间: {self.results['event_processing']['avg_event_time']:.3f}s")
    
    async def test_concurrent_performance(self):
        """测试并发性能"""
        logger.info("测试并发性能...")
        
        async def concurrent_collection_task(location: Dict[str, Any], task_id: int):
            """并发采集任务"""
            collector = ConcurrentDataCollector()
            try:
                start_time = time.time()
                enhanced_data = await collector.collect_enhanced_data(
                    location["lng"], location["lat"], 3.0
                )
                end_time = time.time()
                
                return {
                    "task_id": task_id,
                    "location": location["name"],
                    "duration": end_time - start_time,
                    "success": enhanced_data is not None
                }
            finally:
                await collector.close()
        
        # 测试不同并发级别
        concurrency_levels = [1, 2, 4, 8, 16]
        results = {}
        
        for concurrency in concurrency_levels:
            logger.info(f"测试并发级别: {concurrency}")
            
            start_time = time.time()
            
            # 创建并发任务
            tasks = []
            for i in range(concurrency):
                location = self.test_locations[i % len(self.test_locations)]
                task = concurrent_collection_task(location, i)
                tasks.append(task)
            
            # 执行并发任务
            task_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            end_time = time.time()
            total_time = end_time - start_time
            
            # 统计结果
            successful_tasks = [r for r in task_results if isinstance(r, dict) and r.get("success")]
            failed_tasks = [r for r in task_results if isinstance(r, Exception)]
            
            results[concurrency] = {
                "total_time": total_time,
                "successful_tasks": len(successful_tasks),
                "failed_tasks": len(failed_tasks),
                "success_rate": (len(successful_tasks) / concurrency) * 100,
                "avg_task_duration": statistics.mean([r["duration"] for r in successful_tasks]) if successful_tasks else 0,
                "throughput": len(successful_tasks) / total_time
            }
            
            logger.info(f"并发级别 {concurrency} 完成 - 成功率: {results[concurrency]['success_rate']:.1f}%, "
                       f"吞吐量: {results[concurrency]['throughput']:.2f} tasks/s")
        
        self.results["concurrent_performance"] = results
    
    async def test_resource_usage(self):
        """测试资源使用率"""
        logger.info("测试资源使用率...")
        
        # 记录初始资源使用
        initial_cpu = psutil.cpu_percent()
        initial_memory = psutil.virtual_memory().percent
        
        collector = ConcurrentDataCollector()
        
        try:
            # 运行5分钟的持续采集
            start_time = time.time()
            resource_samples = []
            
            while time.time() - start_time < 300:  # 5分钟
                # 执行数据采集
                for location in self.test_locations[:3]:
                    await collector.collect_enhanced_data(
                        location["lng"], location["lat"], 3.0
                    )
                
                # 记录资源使用
                cpu_usage = psutil.cpu_percent()
                memory_usage = psutil.virtual_memory().percent
                
                resource_samples.append({
                    "timestamp": datetime.utcnow(),
                    "cpu_percent": cpu_usage,
                    "memory_percent": memory_usage,
                    "memory_mb": psutil.virtual_memory().used / 1024 / 1024
                })
                
                await asyncio.sleep(10)
        
        finally:
            await collector.close()
        
        # 计算资源使用统计
        cpu_values = [s["cpu_percent"] for s in resource_samples]
        memory_values = [s["memory_percent"] for s in resource_samples]
        
        self.results["resource_usage"] = {
            "initial_cpu": initial_cpu,
            "initial_memory": initial_memory,
            "avg_cpu": statistics.mean(cpu_values),
            "max_cpu": max(cpu_values),
            "avg_memory": statistics.mean(memory_values),
            "max_memory": max(memory_values),
            "sample_count": len(resource_samples),
            "test_duration_seconds": 300
        }
        
        logger.info(f"资源使用测试完成 - 平均CPU: {self.results['resource_usage']['avg_cpu']:.1f}%, "
                   f"平均内存: {self.results['resource_usage']['avg_memory']:.1f}%")
    
    def generate_performance_report(self):
        """生成性能报告"""
        logger.info("生成性能报告...")
        
        report = {
            "test_timestamp": datetime.utcnow().isoformat(),
            "system_info": self._get_system_info(),
            "test_results": self.results,
            "summary": self._generate_summary()
        }
        
        # 保存报告到文件
        report_file = f"backend/performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        
        # 生成可视化报告
        self._generate_visual_report()
        
        logger.info(f"性能报告已保存到: {report_file}")
        
        return report
    
    def _get_system_info(self) -> Dict[str, Any]:
        """获取系统信息"""
        return {
            "cpu_count": psutil.cpu_count(),
            "memory_total_gb": psutil.virtual_memory().total / 1024 / 1024 / 1024,
            "platform": os.name,
            "python_version": f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}"
        }
    
    def _generate_summary(self) -> Dict[str, Any]:
        """生成性能摘要"""
        summary = {}
        
        if "data_collection" in self.results:
            summary["data_collection"] = {
                "performance_rating": self._rate_performance(
                    self.results["data_collection"]["avg_collection_time"], 
                    [5.0, 3.0, 1.0]  # 差、一般、好的阈值
                ),
                "key_metrics": {
                    "平均采集时间": f"{self.results['data_collection']['avg_collection_time']:.2f}s",
                    "成功率": f"{self.results['data_collection']['success_rate']:.1f}%"
                }
            }
        
        if "cache_performance" in self.results:
            summary["cache_performance"] = {
                "performance_rating": self._rate_performance(
                    self.results["cache_performance"]["avg_get_time"] * 1000, 
                    [10.0, 5.0, 1.0]  # 毫秒阈值
                ),
                "key_metrics": {
                    "平均读取时间": f"{self.results['cache_performance']['avg_get_time']*1000:.2f}ms",
                    "命中率": f"{self.results['cache_performance']['hit_rate']:.1f}%"
                }
            }
        
        if "event_processing" in self.results:
            summary["event_processing"] = {
                "performance_rating": self._rate_performance(
                    self.results["event_processing"]["avg_event_time"], 
                    [1.0, 0.5, 0.1]  # 秒阈值
                ),
                "key_metrics": {
                    "平均事件处理时间": f"{self.results['event_processing']['avg_event_time']:.3f}s",
                    "处理率": f"{self.results['event_processing']['processing_rate']:.1f} events/s"
                }
            }
        
        return summary
    
    def _rate_performance(self, value: float, thresholds: List[float]) -> str:
        """性能评级"""
        if value <= thresholds[2]:
            return "优秀"
        elif value <= thresholds[1]:
            return "良好"
        elif value <= thresholds[0]:
            return "一般"
        else:
            return "需要优化"
    
    def _generate_visual_report(self):
        """生成可视化报告"""
        try:
            # 创建图表
            fig, axes = plt.subplots(2, 2, figsize=(15, 10))
            fig.suptitle('数据采集系统性能测试报告', fontsize=16)
            
            # 1. 数据采集性能
            if "data_collection" in self.results:
                ax1 = axes[0, 0]
                ax1.bar(['平均时间', '最短时间', '最长时间'], [
                    self.results["data_collection"]["avg_collection_time"],
                    self.results["data_collection"]["min_collection_time"],
                    self.results["data_collection"]["max_collection_time"]
                ])
                ax1.set_title('数据采集时间')
                ax1.set_ylabel('时间 (秒)')
            
            # 2. 缓存性能
            if "cache_performance" in self.results:
                ax2 = axes[0, 1]
                ax2.bar(['写入时间', '读取时间'], [
                    self.results["cache_performance"]["avg_put_time"] * 1000,
                    self.results["cache_performance"]["avg_get_time"] * 1000
                ])
                ax2.set_title('缓存操作时间')
                ax2.set_ylabel('时间 (毫秒)')
            
            # 3. 并发性能
            if "concurrent_performance" in self.results:
                ax3 = axes[1, 0]
                concurrency_levels = list(self.results["concurrent_performance"].keys())
                throughputs = [self.results["concurrent_performance"][level]["throughput"] 
                              for level in concurrency_levels]
                ax3.plot(concurrency_levels, throughputs, 'bo-')
                ax3.set_title('并发性能')
                ax3.set_xlabel('并发级别')
                ax3.set_ylabel('吞吐量 (tasks/s)')
            
            # 4. 资源使用率
            if "resource_usage" in self.results:
                ax4 = axes[1, 1]
                ax4.bar(['CPU使用率', '内存使用率'], [
                    self.results["resource_usage"]["avg_cpu"],
                    self.results["resource_usage"]["avg_memory"]
                ])
                ax4.set_title('平均资源使用率')
                ax4.set_ylabel('使用率 (%)')
            
            # 保存图表
            chart_file = f"backend/performance_chart_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            plt.tight_layout()
            plt.savefig(chart_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"性能图表已保存到: {chart_file}")
            
        except Exception as e:
            logger.error(f"生成可视化报告失败: {e}")

class PerformanceOptimizer:
    """性能优化器"""
    
    def __init__(self):
        self.optimization_suggestions = []
    
    def analyze_performance(self, results: Dict[str, Any]) -> List[str]:
        """分析性能并提供建议"""
        suggestions = []
        
        # 分析数据采集性能
        if "data_collection" in results:
            avg_time = results["data_collection"]["avg_collection_time"]
            success_rate = results["data_collection"]["success_rate"]
            
            if avg_time > 5.0:
                suggestions.append("数据采集时间过长，建议优化网络连接或减少API调用频率")
            
            if success_rate < 90:
                suggestions.append("数据采集成功率较低，建议检查API配置和网络稳定性")
        
        # 分析缓存性能
        if "cache_performance" in results:
            hit_rate = results["cache_performance"]["hit_rate"]
            avg_get_time = results["cache_performance"]["avg_get_time"] * 1000
            
            if hit_rate < 80:
                suggestions.append("缓存命中率较低，建议调整缓存策略或增加缓存容量")
            
            if avg_get_time > 5:
                suggestions.append("缓存读取时间较长，建议优化缓存实现或使用更快的存储")
        
        # 分析事件处理性能
        if "event_processing" in results:
            processing_rate = results["event_processing"]["processing_rate"]
            
            if processing_rate < 10:
                suggestions.append("事件处理率较低，建议优化事件处理逻辑或增加处理线程")
        
        # 分析资源使用
        if "resource_usage" in results:
            avg_cpu = results["resource_usage"]["avg_cpu"]
            avg_memory = results["resource_usage"]["avg_memory"]
            
            if avg_cpu > 80:
                suggestions.append("CPU使用率过高，建议优化算法或增加计算资源")
            
            if avg_memory > 80:
                suggestions.append("内存使用率过高，建议优化内存管理或增加内存")
        
        # 分析并发性能
        if "concurrent_performance" in results:
            for level, data in results["concurrent_performance"].items():
                if data["success_rate"] < 90:
                    suggestions.append(f"并发级别 {level} 时成功率较低，建议优化并发处理逻辑")
        
        self.optimization_suggestions = suggestions
        return suggestions
    
    def generate_optimization_report(self) -> str:
        """生成优化报告"""
        if not self.optimization_suggestions:
            return "系统性能表现良好，暂无优化建议。"
        
        report = "性能优化建议：\n\n"
        for i, suggestion in enumerate(self.optimization_suggestions, 1):
            report += f"{i}. {suggestion}\n"
        
        return report

async def main():
    """主函数"""
    # 运行性能测试
    test_suite = PerformanceTestSuite()
    await test_suite.run_all_tests()
    
    # 性能分析和优化建议
    optimizer = PerformanceOptimizer()
    suggestions = optimizer.analyze_performance(test_suite.results)
    
    print("\n" + "="*50)
    print("性能测试完成")
    print("="*50)
    
    print("\n主要性能指标:")
    if "data_collection" in test_suite.results:
        dc = test_suite.results["data_collection"]
        print(f"  数据采集: 平均 {dc['avg_collection_time']:.2f}s, 成功率 {dc['success_rate']:.1f}%")
    
    if "cache_performance" in test_suite.results:
        cp = test_suite.results["cache_performance"]
        print(f"  缓存性能: 读取 {cp['avg_get_time']*1000:.2f}ms, 命中率 {cp['hit_rate']:.1f}%")
    
    if "event_processing" in test_suite.results:
        ep = test_suite.results["event_processing"]
        print(f"  事件处理: 平均 {ep['avg_event_time']:.3f}s, 处理率 {ep['processing_rate']:.1f} events/s")
    
    print("\n优化建议:")
    print(optimizer.generate_optimization_report())

if __name__ == "__main__":
    asyncio.run(main())
