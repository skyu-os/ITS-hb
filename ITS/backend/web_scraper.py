"""
网络爬虫模块 - 专门用于采集交通事故等实时数据
支持多数据源、异步并发、智能去重
"""
import asyncio
import aiohttp
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
import hashlib
import re
from bs4 import BeautifulSoup
import feedparser
from urllib.parse import urljoin, urlparse
import time
from concurrent.futures import ThreadPoolExecutor
import redis
import os

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class TrafficAccident:
    """交通事故数据结构"""
    accident_id: str
    title: str
    description: str
    location: str
    lng: Optional[float] = None
    lat: Optional[float] = None
    accident_time: Optional[datetime] = None
    severity: str = "未知"  # 轻微、一般、严重、特大
    accident_type: str = "未知"  # 追尾、侧翻、碰撞等
    casualties: int = 0  # 伤亡人数
    vehicles_involved: int = 0  # 涉及车辆数
    road_condition: str = "未知"
    weather_condition: str = "未知"
    source: str = ""
    url: str = ""
    raw_content: str = ""
    collected_at: datetime = field(default_factory=datetime.utcnow)
    confidence_score: float = 1.0

class DataDeduplicator:
    """数据去重器"""
    
    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        self.recent_hashes: Set[str] = set()
        self.hash_ttl = 3600  # 1小时
    
    def generate_content_hash(self, title: str, description: str, location: str, accident_time: datetime) -> str:
        """生成内容哈希用于去重"""
        content = f"{title}_{description}_{location}_{accident_time.strftime('%Y%m%d%H%M')}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def is_duplicate(self, accident: TrafficAccident) -> bool:
        """检查是否为重复数据"""
        content_hash = self.generate_content_hash(
            accident.title, accident.description, accident.location, accident.accident_time or datetime.utcnow()
        )
        
        # 检查内存缓存
        if content_hash in self.recent_hashes:
            return True
        
        # 检查Redis缓存
        if self.redis_client:
            try:
                if self.redis_client.exists(f"accident_hash:{content_hash}"):
                    return True
            except Exception as e:
                logger.warning(f"Redis去重检查失败: {e}")
        
        return False
    
    def mark_processed(self, accident: TrafficAccident):
        """标记已处理的数据"""
        content_hash = self.generate_content_hash(
            accident.title, accident.description, accident.location, accident.accident_time or datetime.utcnow()
        )
        
        # 添加到内存缓存
        self.recent_hashes.add(content_hash)
        
        # 添加到Redis缓存
        if self.redis_client:
            try:
                self.redis_client.setex(f"accident_hash:{content_hash}", self.hash_ttl, "1")
            except Exception as e:
                logger.warning(f"Redis去重标记失败: {e}")
        
        # 清理过期的内存缓存
        if len(self.recent_hashes) > 1000:
            self.recent_hashes.clear()

class LocationExtractor:
    """地理位置提取器"""
    
    def __init__(self):
        self.location_patterns = [
            r'([^，,。.]+?市[^，,。.]+?区?[^，,。.]*?路)',
            r'([^，,。.]+?省[^，,。.]+?市[^，,。.]*?路)',
            r'([^，,。.]+?高速[^，,。.]+?段)',
            r'([^，,。.]+?国道[^，,。.]+?段)',
            r'([^，,。.]+?立交桥)',
            r'([^，,。.]+?隧道)',
        ]
    
    def extract_location(self, text: str) -> str:
        """从文本中提取地理位置"""
        for pattern in self.location_patterns:
            matches = re.findall(pattern, text)
            if matches:
                return matches[0]
        
        # 如果没有匹配到具体位置，尝试提取城市名
        city_pattern = r'([^，,。.]+?市)'
        city_matches = re.findall(city_pattern, text)
        if city_matches:
            return city_matches[0]
        
        return "未知位置"
    
    async def geocode_location(self, location: str, api_key: str = None) -> tuple[float, float]:
        """地理编码 - 将地址转换为经纬度"""
        if not api_key or location == "未知位置":
            return None, None
        
        # 这里可以集成高德地图或其他地理编码API
        # 暂时返回None，实际使用时需要实现
        return None, None

class SeverityClassifier:
    """事故严重程度分类器"""
    
    def __init__(self):
        self.severity_keywords = {
            "特大": ["死亡", "多人", "惨烈", "重大", "特大事故"],
            "严重": ["重伤", "多人伤亡", "严重", "大火", "爆炸"],
            "一般": ["受伤", "轻伤", "车辆损坏", "交通中断"],
            "轻微": ["刮擦", "小事故", "轻微", "无人员伤亡"]
        }
    
    def classify_severity(self, title: str, description: str) -> str:
        """根据关键词分类事故严重程度"""
        text = f"{title} {description}".lower()
        
        for severity, keywords in self.severity_keywords.items():
            for keyword in keywords:
                if keyword in text:
                    return severity
        
        return "一般"

class AccidentDataScraper:
    """交通事故数据爬虫基类"""
    
    def __init__(self, redis_client=None):
        self.session = None
        self.deduplicator = DataDeduplicator(redis_client)
        self.location_extractor = LocationExtractor()
        self.severity_classifier = SeverityClassifier()
        self.redis_client = redis_client
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def parse_accident_time(self, time_str: str) -> Optional[datetime]:
        """解析事故时间"""
        if not time_str:
            return None
        
        # 常见时间格式模式
        patterns = [
            r'(\d{4})年(\d{1,2})月(\d{1,2})日(\d{1,2})时(\d{1,2})分',
            r'(\d{4})-(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{1,2})',
            r'(\d{1,2})月(\d{1,2})日(\d{1,2})时(\d{1,2})分',
            r'今天(\d{1,2})时(\d{1,2})分',
            r'(\d{1,2})时(\d{1,2})分',
        ]
        
        current_year = datetime.now().year
        
        for pattern in patterns:
            match = re.search(pattern, time_str)
            if match:
                try:
                    groups = match.groups()
                    if len(groups) == 5:
                        if len(groups[0]) == 4:  # 包含年份
                            year, month, day, hour, minute = map(int, groups)
                        else:  # 不包含年份，使用当前年份
                            month, day, hour, minute = map(int, groups)
                            year = current_year
                        return datetime(year, month, day, hour, minute)
                except ValueError:
                    continue
        
        # 如果无法解析，返回当前时间
        return datetime.utcnow()

class GovernmentWebsiteScraper(AccidentDataScraper):
    """政府网站爬虫 - 采集官方发布的交通事故信息"""
    
    def __init__(self, redis_client=None):
        super().__init__(redis_client)
        self.gov_urls = {
            "杭州交警": "http://hzjj.hangzhou.gov.cn/",
            "浙江交警": "http://gat.zj.gov.cn/",
            "公安部交管局": "https://www.mps.gov.cn/"
        }
    
    async def scrape_hangzhou_traffic(self) -> List[TrafficAccident]:
        """爬取杭州交警网站"""
        accidents = []
        
        try:
            url = "http://hzjj.hangzhou.gov.cn/col/col1229218650/index.html"
            async with self.session.get(url) as response:
                if response.status == 200:
                    html = await response.text()
                    accidents = await self._parse_gov_news(html, "杭州交警", url)
        except Exception as e:
            logger.error(f"爬取杭州交警网站失败: {e}")
        
        return accidents
    
    async def _parse_gov_news(self, html: str, source: str, base_url: str) -> List[TrafficAccident]:
        """解析政府网站新闻"""
        accidents = []
        soup = BeautifulSoup(html, 'html.parser')
        
        # 查找新闻列表
        news_items = soup.find_all('li', class_='news-item') or soup.find_all('div', class_='news')
        
        for item in news_items[:10]:  # 限制最新10条
            try:
                title_elem = item.find('a') or item.find('h3')
                if not title_elem:
                    continue
                
                title = title_elem.get_text(strip=True)
                if not any(keyword in title for keyword in ['事故', '交通', '路况', '管制']):
                    continue
                
                link = title_elem.get('href')
                if link:
                    full_url = urljoin(base_url, link)
                    
                    # 获取详细内容
                    detail_html = await self._get_page_content(full_url)
                    if detail_html:
                        accident = await self._parse_accident_detail(detail_html, title, source, full_url)
                        if accident and not self.deduplicator.is_duplicate(accident):
                            accidents.append(accident)
                            
            except Exception as e:
                logger.error(f"解析新闻项失败: {e}")
                continue
        
        return accidents
    
    async def _get_page_content(self, url: str) -> str:
        """获取页面内容"""
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.text()
        except Exception as e:
            logger.error(f"获取页面内容失败 {url}: {e}")
        return ""
    
    async def _parse_accident_detail(self, html: str, title: str, source: str, url: str) -> Optional[TrafficAccident]:
        """解析事故详情"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # 提取正文内容
        content_elem = soup.find('div', class_='content') or soup.find('div', class_='article-content')
        if not content_elem:
            content_elem = soup.find('body')
        
        description = content_elem.get_text(strip=True) if content_elem else ""
        
        # 提取时间
        time_elem = soup.find('span', class_='time') or soup.find('div', class_='date')
        time_str = time_elem.get_text(strip=True) if time_elem else ""
        accident_time = self.parse_accident_time(time_str)
        
        # 提取位置
        location = self.location_extractor.extract_location(f"{title} {description}")
        
        # 分类严重程度
        severity = self.severity_classifier.classify_severity(title, description)
        
        # 生成ID
        accident_id = hashlib.md5(f"{title}_{url}_{accident_time}".encode()).hexdigest()[:16]
        
        return TrafficAccident(
            accident_id=accident_id,
            title=title,
            description=description[:500],  # 限制长度
            location=location,
            accident_time=accident_time,
            severity=severity,
            source=source,
            url=url,
            raw_content=html[:1000]  # 限制原始内容长度
        )

class RSSFeedScraper(AccidentDataScraper):
    """RSS订阅爬虫 - 采集新闻媒体的交通信息"""
    
    def __init__(self, redis_client=None):
        super().__init__(redis_client)
        self.rss_feeds = {
            "新浪汽车": "http://rss.sina.com.cn/auto.xml",
            "网易汽车": "http://rss.163.com/rss/auto.xml",
            "腾讯汽车": "http://rss.qq.com/auto.xml"
        }
    
    async def scrape_rss_feeds(self) -> List[TrafficAccident]:
        """爬取所有RSS订阅源"""
        all_accidents = []
        
        for source, feed_url in self.rss_feeds.items():
            try:
                accidents = await self._scrape_single_feed(feed_url, source)
                all_accidents.extend(accidents)
                logger.info(f"从 {source} 采集到 {len(accidents)} 条交通信息")
            except Exception as e:
                logger.error(f"爬取RSS源 {source} 失败: {e}")
        
        return all_accidents
    
    async def _scrape_single_feed(self, feed_url: str, source: str) -> List[TrafficAccident]:
        """爬取单个RSS源"""
        accidents = []
        
        try:
            # 获取RSS内容
            async with self.session.get(feed_url) as response:
                if response.status == 200:
                    rss_content = await response.text()
                    
                    # 解析RSS
                    feed = feedparser.parse(rss_content)
                    
                    for entry in feed.entries[:20]:  # 最新20条
                        title = entry.title
                        
                        # 过滤交通相关内容
                        if not any(keyword in title for keyword in ['事故', '交通', '车祸', '路况', '封路', '管制']):
                            continue
                        
                        description = entry.description if hasattr(entry, 'description') else ""
                        link = entry.link if hasattr(entry, 'link') else ""
                        
                        # 解析时间
                        accident_time = None
                        if hasattr(entry, 'published'):
                            accident_time = self.parse_accident_time(entry.published)
                        
                        # 提取位置
                        location = self.location_extractor.extract_location(f"{title} {description}")
                        
                        # 分类严重程度
                        severity = self.severity_classifier.classify_severity(title, description)
                        
                        # 生成ID
                        accident_id = hashlib.md5(f"{title}_{link}_{accident_time}".encode()).hexdigest()[:16]
                        
                        accident = TrafficAccident(
                            accident_id=accident_id,
                            title=title,
                            description=description[:500],
                            location=location,
                            accident_time=accident_time,
                            severity=severity,
                            source=source,
                            url=link,
                            raw_content=description[:1000]
                        )
                        
                        if not self.deduplicator.is_duplicate(accident):
                            accidents.append(accident)
                            
        except Exception as e:
            logger.error(f"解析RSS源失败 {feed_url}: {e}")
        
        return accidents

class SocialMediaScraper(AccidentDataScraper):
    """社交媒体爬虫 - 采集实时交通信息"""
    
    def __init__(self, redis_client=None):
        super().__init__(redis_client)
        # 这里可以集成微博API或其他社交媒体API
        # 由于API限制，这里提供框架
    
    async def scrape_weibo_traffic(self) -> List[TrafficAccident]:
        """爬取微博交通信息"""
        # 实际实现需要微博API或使用微博搜索页面
        # 这里提供框架，实际使用时需要实现
        logger.info("微博爬虫功能待实现，需要API授权")
        return []

class EnhancedMultiSourceScraper:
    """增强的多源爬虫管理器"""
    
    def __init__(self):
        self.scrapers = {}
        self.redis_client = None
        self._setup_redis()
        self.executor = ThreadPoolExecutor(max_workers=4)
    
    def _setup_redis(self):
        """设置Redis连接"""
        try:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            self.redis_client.ping()
            logger.info("爬虫Redis连接成功")
        except Exception as e:
            logger.warning(f"爬虫Redis连接失败，将使用内存去重: {e}")
            self.redis_client = None
    
    async def collect_all_accidents(self) -> List[TrafficAccident]:
        """从所有数据源采集交通事故信息"""
        all_accidents = []
        
        # 并发执行所有爬虫
        tasks = [
            self._scrape_with_timeout("gov", self._scrape_government_sites),
            self._scrape_with_timeout("rss", self._scrape_rss_feeds),
            self._scrape_with_timeout("social", self._scrape_social_media)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"爬虫执行异常: {result}")
            elif isinstance(result, list):
                all_accidents.extend(result)
        
        # 按时间排序
        all_accidents.sort(key=lambda x: x.collected_at, reverse=True)
        
        logger.info(f"总共采集到 {len(all_accidents)} 条交通事故信息")
        return all_accidents
    
    async def _scrape_with_timeout(self, name: str, scraper_func, timeout: int = 60) -> List[TrafficAccident]:
        """带超时的爬虫执行"""
        try:
            return await asyncio.wait_for(scraper_func(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.error(f"爬虫 {name} 执行超时")
            return []
        except Exception as e:
            logger.error(f"爬虫 {name} 执行失败: {e}")
            return []
    
    async def _scrape_government_sites(self) -> List[TrafficAccident]:
        """爬取政府网站"""
        async with GovernmentWebsiteScraper(self.redis_client) as scraper:
            return await scraper.scrape_hangzhou_traffic()
    
    async def _scrape_rss_feeds(self) -> List[TrafficAccident]:
        """爬取RSS订阅"""
        async with RSSFeedScraper(self.redis_client) as scraper:
            return await scraper.scrape_rss_feeds()
    
    async def _scrape_social_media(self) -> List[TrafficAccident]:
        """爬取社交媒体"""
        async with SocialMediaScraper(self.redis_client) as scraper:
            return await scraper.scrape_weibo_traffic()
    
    def save_accidents_to_cache(self, accidents: List[TrafficAccident]):
        """保存事故数据到缓存"""
        if not self.redis_client or not accidents:
            return
        
        try:
            cache_key = "latest_accidents"
            accident_data = []
            
            for accident in accidents[:50]:  # 缓存最新50条
                accident_dict = {
                    "accident_id": accident.accident_id,
                    "title": accident.title,
                    "location": accident.location,
                    "severity": accident.severity,
                    "accident_time": accident.accident_time.isoformat() if accident.accident_time else None,
                    "source": accident.source,
                    "collected_at": accident.collected_at.isoformat()
                }
                accident_data.append(accident_dict)
            
            self.redis_client.setex(cache_key, 1800, json.dumps(accident_data, ensure_ascii=False))  # 30分钟过期
            logger.info(f"已缓存 {len(accident_data)} 条事故数据")
            
        except Exception as e:
            logger.error(f"保存事故数据到缓存失败: {e}")
    
    async def start_continuous_scraping(self, interval_minutes: int = 10):
        """启动持续爬虫任务"""
        logger.info(f"启动持续爬虫任务，间隔 {interval_minutes} 分钟")
        
        while True:
            try:
                accidents = await self.collect_all_accidents()
                self.save_accidents_to_cache(accidents)
                
                # 等待下次执行
                await asyncio.sleep(interval_minutes * 60)
                
            except Exception as e:
                logger.error(f"持续爬虫任务执行失败: {e}")
                await asyncio.sleep(60)  # 出错后等待1分钟再重试

async def test_scraper():
    """测试爬虫功能"""
    scraper = EnhancedMultiSourceScraper()
    accidents = await scraper.collect_all_accidents()
    
    print(f"采集到 {len(accidents)} 条交通事故信息:")
    for i, accident in enumerate(accidents[:5]):
        print(f"\n{i+1}. {accident.title}")
        print(f"   位置: {accident.location}")
        print(f"   严重程度: {accident.severity}")
        print(f"   来源: {accident.source}")
        print(f"   时间: {accident.accident_time}")

if __name__ == "__main__":
    asyncio.run(test_scraper())
