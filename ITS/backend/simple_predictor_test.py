#!/usr/bin/env python3
"""
简化的预测器测试
不依赖TensorFlow等重型库，使用基础统计方法进行预测
"""

import sqlite3
import json
import random
import math
from datetime import datetime, timedelta
from typing import Dict, List, Any

class SimpleTrafficPredictor:
    """简化的交通预测器"""
    
    def __init__(self):
        self.db_path = 'traffic_data.db'
        self.model_name = "Simple_Statistical_Predictor"
        self.model_version = "1.0.0"
    
    def create_sample_data(self):
        """创建示例数据用于测试"""
        print("创建示例交通数据...")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS traffic_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                location_lng REAL,
                location_lat REAL,
                total_roads INTEGER,
                congested_roads INTEGER,
                avg_speed REAL,
                congestion_ratio REAL
            )
        ''')
        
        # 生成示例数据
        base_time = datetime.utcnow() - timedelta(days=7)
        
        for i in range(168):  # 7天的每小时数据
            timestamp = base_time + timedelta(hours=i)
            
            # 模拟交通模式：早晚高峰拥堵
            hour = timestamp.hour
            if 7 <= hour <= 9 or 17 <= hour <= 19:
                congestion_ratio = 0.6 + random.uniform(-0.1, 0.1)  # 高峰拥堵
                avg_speed = 20 + random.uniform(-5, 5)
            elif 22 <= hour or hour <= 6:
                congestion_ratio = 0.1 + random.uniform(-0.05, 0.05)  # 夜间通畅
                avg_speed = 50 + random.uniform(-5, 5)
            else:
                congestion_ratio = 0.3 + random.uniform(-0.1, 0.1)  # 平峰
                avg_speed = 35 + random.uniform(-5, 5)
            
            total_roads = 100
            congested_roads = int(total_roads * congestion_ratio)
            
            cursor.execute('''
                INSERT INTO traffic_data 
                (timestamp, location_lng, location_lat, total_roads, congested_roads, avg_speed, congestion_ratio)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (timestamp, 120.15507, 30.27415, total_roads, congested_roads, avg_speed, congestion_ratio))
        
        conn.commit()
        conn.close()
        print("示例数据创建完成")
    
    def get_historical_data(self, location_lng: float, location_lat: float, days: int = 7) -> List[Dict]:
        """获取历史数据"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 确保表存在
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS traffic_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                location_lng REAL,
                location_lat REAL,
                total_roads INTEGER,
                congested_roads INTEGER,
                avg_speed REAL,
                congestion_ratio REAL
            )
        ''')
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        try:
            cursor.execute('''
                SELECT timestamp, total_roads, congested_roads, avg_speed, congestion_ratio
                FROM traffic_data 
                WHERE location_lng = ? AND location_lat = ? AND timestamp >= ?
                ORDER BY timestamp
            ''', (location_lng, location_lat, cutoff_date))
            
            data = []
            for row in cursor.fetchall():
                data.append({
                    'timestamp': datetime.fromisoformat(row[0]),
                    'total_roads': row[1],
                    'congested_roads': row[2],
                    'avg_speed': row[3],
                    'congestion_ratio': row[4]
                })
        except Exception as e:
            print(f"查询数据时出错: {e}")
            data = []
        
        conn.close()
        return data
    
    def simple_predict(self, historical_data: List[Dict], prediction_horizon: int = 6) -> List[Dict]:
        """使用简单统计方法进行预测"""
        if len(historical_data) < 24:
            raise ValueError("历史数据不足，至少需要24小时数据")
        
        predictions = []
        
        for hour_ahead in range(1, prediction_horizon + 1):
            future_time = datetime.utcnow() + timedelta(hours=hour_ahead)
            future_hour = future_time.hour
            
            # 基于历史数据的同一时段进行预测
            same_hour_data = [d['congestion_ratio'] for d in historical_data 
                            if d['timestamp'].hour == future_hour]
            
            if same_hour_data:
                # 使用同一时段的平均值作为预测
                predicted_congestion = sum(same_hour_data) / len(same_hour_data)
                # 添加一些随机变化
                predicted_congestion += random.uniform(-0.05, 0.05)
                predicted_congestion = max(0, min(1, predicted_congestion))
            else:
                # 如果没有历史数据，使用平均值
                avg_congestion = sum(d['congestion_ratio'] for d in historical_data[-24:]) / 24
                predicted_congestion = avg_congestion
            
            # 基于拥堵比例估算速度
            predicted_speed = 50 * (1 - predicted_congestion) + 15
            
            prediction = {
                'hour': future_hour,
                'timestamp': future_time.isoformat(),
                'congestion_ratio': predicted_congestion,
                'predicted_speed': predicted_speed,
                'confidence_score': 0.75  # 简化的置信度
            }
            
            predictions.append(prediction)
        
        return predictions
    
    def predict_traffic(self, location_lng: float, location_lat: float, 
                       prediction_horizon: int = 6) -> Dict[str, Any]:
        """主预测函数"""
        try:
            print(f"开始预测交通状况...")
            print(f"位置: ({location_lng}, {location_lat})")
            print(f"预测时长: {prediction_horizon} 小时")
            
            # 获取历史数据
            historical_data = self.get_historical_data(location_lng, location_lat)
            
            if len(historical_data) < 24:
                # 如果没有足够的历史数据，创建示例数据
                print("历史数据不足，创建示例数据...")
                self.create_sample_data()
                historical_data = self.get_historical_data(location_lng, location_lat)
            
            print(f"获取到 {len(historical_data)} 条历史记录")
            
            # 进行预测
            predictions = self.simple_predict(historical_data, prediction_horizon)
            
            # 构建结果
            result = {
                "success": True,
                "location": {"lng": location_lng, "lat": location_lat},
                "prediction_horizon_hours": prediction_horizon,
                "predictions": predictions,
                "model_info": {
                    "name": self.model_name,
                    "version": self.model_version,
                    "type": "statistical"
                },
                "data_points_used": len(historical_data),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            print("预测完成！")
            return result
            
        except Exception as e:
            print(f"预测失败: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

def main():
    """测试函数"""
    print("🚀 简化交通预测器测试")
    print("=" * 50)
    
    predictor = SimpleTrafficPredictor()
    
    # 测试预测
    result = predictor.predict_traffic(120.15507, 30.27415, 6)
    
    print("\n📊 预测结果:")
    print("=" * 30)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    return result["success"]

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
