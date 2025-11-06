import json
import pickle
import os
import numpy as np
from datetime import datetime, timedelta
import random

# 尝试导入scikit-learn，如果不可用则使用简单模型
try:
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("警告: scikit-learn未安装，将使用简单预测模型")

class TrafficPredictor:
    def __init__(self):
        self.model = None
        self.scaler = None
        self.is_trained = False
        self.model_file = "traffic_model.pkl"
        self.scaler_file = "traffic_scaler.pkl"
        
        # 尝试加载已训练的模型
        self.load_model()
        
        # 如果没有可用的模型，则创建一个
        if not self.is_trained:
            self.create_model()
    
    def create_model(self):
        """创建并训练一个简单的预测模型"""
        if SKLEARN_AVAILABLE:
            # 创建随机森林回归模型
            self.model = RandomForestRegressor(n_estimators=100, random_state=42)
            self.scaler = StandardScaler()
            
            # 生成模拟训练数据
            # 在实际应用中，这里应该加载真实的历史交通数据
            X, y = self.generate_training_data(1000)
            
            # 标准化特征
            X_scaled = self.scaler.fit_transform(X)
            
            # 训练模型
            self.model.fit(X_scaled, y)
            self.is_trained = True
            
            # 保存模型
            self.save_model()
            print("机器学习模型训练完成")
        else:
            # 如果scikit-learn不可用，使用简单模型
            self.is_trained = True
            print("使用简单预测模型")
    
    def generate_training_data(self, num_samples):
        """生成模拟训练数据"""
        X = []
        y = []
        
        for _ in range(num_samples):
            # 生成特征：小时、星期几、当前交通水平、平均速度、拥堵比例
            hour = random.randint(0, 23)
            day_of_week = random.randint(0, 6)
            traffic_level = random.uniform(0, 1)
            avg_speed = random.uniform(10, 80)
            congestion_ratio = random.uniform(0, 1)
            
            # 特征向量
            features = [hour, day_of_week, traffic_level, avg_speed, congestion_ratio]
            X.append(features)
            
            # 目标值：预测的拥堵比例
            # 在实际应用中，这应该是真实的未来交通状况
            # 这里我们使用一个简单的函数来模拟
            # 高峰时段（7-9点，17-19点）和工作日（周一至周五）更容易拥堵
            peak_hour_factor = 0
            if (7 <= hour <= 9) or (17 <= hour <= 19):
                peak_hour_factor = 0.3
            
            weekday_factor = 0
            if 0 <= day_of_week <= 4:  # 周一到周五
                weekday_factor = 0.2
            
            predicted_congestion = min(1.0, congestion_ratio + peak_hour_factor + weekday_factor + random.uniform(-0.1, 0.1))
            y.append(predicted_congestion)
        
        return np.array(X), np.array(y)
    
    def predict(self, data):
        """使用模型进行预测"""
        if not self.is_trained:
            self.create_model()
        
        # 从请求中提取数据
        traffic_level = data.get('trafficLevel', 0.5)
        avg_speed = data.get('avgSpeed', 40)
        congestion_ratio = data.get('congestionRatio', 0.3)
        
        # 获取当前时间
        now = datetime.now()
        hour = now.hour
        day_of_week = now.weekday()  # 0是周一，6是周日
        
        if SKLEARN_AVAILABLE and self.model is not None:
            # 使用机器学习模型进行预测
            features = np.array([[hour, day_of_week, traffic_level, avg_speed, congestion_ratio]])
            features_scaled = self.scaler.transform(features)
            predicted_congestion = self.model.predict(features_scaled)[0]
            predicted_congestion = max(0, min(1, predicted_congestion))  # 限制在0-1范围内
        else:
            # 使用简单预测逻辑
            peak_hour_factor = 0
            if (7 <= hour <= 9) or (17 <= hour <= 19):
                peak_hour_factor = 0.3
            
            weekday_factor = 0
            if 0 <= day_of_week <= 4:  # 周一到周五
                weekday_factor = 0.2
            
            predicted_congestion = min(1.0, congestion_ratio + peak_hour_factor + weekday_factor + random.uniform(-0.1, 0.1))
        
        # 预测速度和时间
        predicted_speed = max(10, avg_speed * (1 - predicted_congestion * 0.7) + random.uniform(-5, 5))
        predicted_time = 30 + (1 - predicted_congestion) * 20 + random.uniform(-5, 5)
        
        # 生成建议
        suggestions = []
        if predicted_congestion > 0.7:
            suggestions.append("建议避开高峰时段出行")
        if predicted_speed < 30:
            suggestions.append("考虑使用公共交通工具")
        if predicted_congestion < 0.3:
            suggestions.append("当前路况良好，适合出行")
        
        # 添加基于时间的建议
        if 7 <= hour <= 9:
            suggestions.append("早高峰时段，建议提前30分钟出发")
        elif 17 <= hour <= 19:
            suggestions.append("晚高峰时段，建议选择替代路线")
        
        return {
            "success": True,
            "message": "预测成功",
            "model_type": "机器学习模型" if SKLEARN_AVAILABLE else "简单模型",
            "metrics": {
                "congestionRatio": round(predicted_congestion, 2),
                "avgSpeed": round(predicted_speed, 1),
                "travelTime": round(predicted_time, 1)
            },
            "suggestions": suggestions,
            "prediction_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    
    def save_model(self):
        """保存模型到文件"""
        if SKLEARN_AVAILABLE and self.model is not None and self.scaler is not None:
            try:
                with open(self.model_file, 'wb') as f:
                    pickle.dump(self.model, f)
                with open(self.scaler_file, 'wb') as f:
                    pickle.dump(self.scaler, f)
                print("模型已保存")
            except Exception as e:
                print(f"保存模型时出错: {e}")
    
    def load_model(self):
        """从文件加载模型"""
        if SKLEARN_AVAILABLE and os.path.exists(self.model_file) and os.path.exists(self.scaler_file):
            try:
                with open(self.model_file, 'rb') as f:
                    self.model = pickle.load(f)
                with open(self.scaler_file, 'rb') as f:
                    self.scaler = pickle.load(f)
                self.is_trained = True
                print("模型已加载")
            except Exception as e:
                print(f"加载模型时出错: {e}")
                self.is_trained = False

# 创建全局预测器实例
predictor = TrafficPredictor()

def predict_traffic(data):
    """使用机器学习模型预测交通状况"""
    return predictor.predict(data)

if __name__ == "__main__":
    # 测试预测功能
    test_data = {
        "trafficLevel": 0.6,
        "avgSpeed": 35,
        "congestionRatio": 0.4
    }
    result = predict_traffic(test_data)
    print(json.dumps(result, indent=2, ensure_ascii=False))