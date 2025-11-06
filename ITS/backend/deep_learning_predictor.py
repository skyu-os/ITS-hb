"""
深度学习交通预测模型
使用LSTM/GRU进行时序预测，支持多模态特征
"""
import numpy as np
import pandas as pd
import tensorflow as tf
from tensorflow.keras.models import Sequential, Model
from tensorflow.keras.layers import LSTM, GRU, Dense, Dropout, Input, Concatenate, BatchNormalization
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau, ModelCheckpoint
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import joblib
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
import asyncio
from dataclasses import dataclass
from sqlalchemy.orm import Session
from database import SessionLocal, TrafficData, PredictionResult, ModelMetrics

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class PredictionFeatures:
    """预测特征"""
    timestamp: datetime
    location_lng: float
    location_lat: float
    hour: int
    day_of_week: int
    month: int
    is_weekend: bool
    is_peak_hour: bool
    traffic_level: float
    avg_speed: float
    congestion_ratio: float
    weather_temp: Optional[float] = None
    weather_humidity: Optional[float] = None
    is_holiday: bool = False

class FeatureEngineer:
    """特征工程器"""
    
    def __init__(self):
        self.scalers = {}
        self.feature_columns = [
            'hour', 'day_of_week', 'month', 'is_weekend', 'is_peak_hour',
            'traffic_level', 'avg_speed', 'congestion_ratio', 'weather_temp',
            'weather_humidity', 'is_holiday'
        ]
    
    def extract_features(self, traffic_data: List[TrafficData]) -> pd.DataFrame:
        """从交通数据中提取特征"""
        features = []
        
        for data in traffic_data:
            dt = data.timestamp
            features.append({
                'timestamp': dt,
                'hour': dt.hour,
                'day_of_week': dt.weekday(),
                'month': dt.month,
                'is_weekend': dt.weekday() >= 5,
                'is_peak_hour': self._is_peak_hour(dt.hour),
                'traffic_level': data.total_roads / max(1, data.total_roads),  # 标准化
                'avg_speed': data.avg_speed or 0,
                'congestion_ratio': data.congestion_ratio,
                'weather_temp': self._get_weather_temp(dt),  # 模拟天气数据
                'weather_humidity': self._get_weather_humidity(dt),  # 模拟天气数据
                'is_holiday': self._is_holiday(dt)
            })
        
        return pd.DataFrame(features)
    
    def _is_peak_hour(self, hour: int) -> bool:
        """判断是否为高峰时段"""
        return (7 <= hour <= 9) or (17 <= hour <= 19)
    
    def _get_weather_temp(self, dt: datetime) -> float:
        """获取温度（模拟数据）"""
        # 简单的季节性温度模拟
        month_temp = {
            1: 5, 2: 7, 3: 12, 4: 18, 5: 23, 6: 28,
            7: 32, 8: 31, 9: 26, 10: 20, 11: 13, 12: 7
        }
        base_temp = month_temp.get(dt.month, 20)
        # 添加日变化
        daily_variation = 5 * np.sin((dt.hour - 6) * np.pi / 12)
        return base_temp + daily_variation + np.random.normal(0, 2)
    
    def _get_weather_humidity(self, dt: datetime) -> float:
        """获取湿度（模拟数据）"""
        # 简单的湿度模拟
        base_humidity = 60 + 20 * np.sin(dt.month * np.pi / 6)
        return max(20, min(100, base_humidity + np.random.normal(0, 10)))
    
    def _is_holiday(self, dt: datetime) -> bool:
        """判断是否为节假日（简化版本）"""
        # 这里简化处理，实际应该使用节假日API
        chinese_holidays = [
            (1, 1), (1, 2), (1, 3),  # 元旦
            (5, 1), (5, 2), (5, 3),  # 劳动节
            (10, 1), (10, 2), (10, 3), (10, 4), (10, 5), (10, 6), (10, 7)  # 国庆节
        ]
        return (dt.month, dt.day) in chinese_holidays
    
    def create_sequences(self, data: pd.DataFrame, sequence_length: int = 24, target_column: str = 'congestion_ratio') -> Tuple[np.ndarray, np.ndarray]:
        """创建时序数据序列"""
        if len(data) < sequence_length + 1:
            raise ValueError(f"数据长度 {len(data)} 小于所需最小长度 {sequence_length + 1}")
        
        # 准备特征数据
        feature_data = data[self.feature_columns].values
        
        # 标准化特征
        if 'feature_scaler' not in self.scalers:
            self.scalers['feature_scaler'] = StandardScaler()
            feature_data = self.scalers['feature_scaler'].fit_transform(feature_data)
        else:
            feature_data = self.scalers['feature_scaler'].transform(feature_data)
        
        # 准备目标数据
        target_data = data[target_column].values.reshape(-1, 1)
        
        if 'target_scaler' not in self.scalers:
            self.scalers['target_scaler'] = MinMaxScaler()
            target_data = self.scalers['target_scaler'].fit_transform(target_data)
        else:
            target_data = self.scalers['target_scaler'].transform(target_data)
        
        # 创建序列
        X, y = [], []
        for i in range(len(data) - sequence_length):
            X.append(feature_data[i:i + sequence_length])
            y.append(target_data[i + sequence_length])
        
        return np.array(X), np.array(y)
    
    def save_scalers(self, filepath: str):
        """保存标准化器"""
        joblib.dump(self.scalers, filepath)
    
    def load_scalers(self, filepath: str):
        """加载标准化器"""
        self.scalers = joblib.load(filepath)

class LSTMTrafficPredictor:
    """LSTM交通预测模型"""
    
    def __init__(self, sequence_length: int = 24, feature_count: int = 11):
        self.sequence_length = sequence_length
        self.feature_count = feature_count
        self.model = None
        self.feature_engineer = FeatureEngineer()
        self.model_name = "LSTM_Traffic_Predictor"
        self.model_version = "1.0.0"
    
    def build_model(self, lstm_units: List[int] = [64, 32], dropout_rate: float = 0.2):
        """构建LSTM模型"""
        model = Sequential([
            LSTM(lstm_units[0], return_sequences=True, input_shape=(self.sequence_length, self.feature_count)),
            Dropout(dropout_rate),
            BatchNormalization(),
            
            LSTM(lstm_units[1], return_sequences=False),
            Dropout(dropout_rate),
            BatchNormalization(),
            
            Dense(16, activation='relu'),
            Dropout(dropout_rate),
            Dense(1, activation='sigmoid')  # 拥堵比例在0-1之间
        ])
        
        optimizer = Adam(learning_rate=0.001)
        model.compile(optimizer=optimizer, loss='mse', metrics=['mae'])
        
        self.model = model
        logger.info(f"LSTM模型构建完成，参数数量: {model.count_params()}")
        return model
    
    def train(self, train_X: np.ndarray, train_y: np.ndarray, 
              validation_split: float = 0.2, epochs: int = 100, batch_size: int = 32):
        """训练模型"""
        if self.model is None:
            self.build_model()
        
        # 回调函数
        callbacks = [
            EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True),
            ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=5, min_lr=1e-7),
            ModelCheckpoint(
                f'backend/models/{self.model_name}_best.h5',
                monitor='val_loss',
                save_best_only=True
            )
        ]
        
        # 训练模型
        history = self.model.fit(
            train_X, train_y,
            validation_split=validation_split,
            epochs=epochs,
            batch_size=batch_size,
            callbacks=callbacks,
            verbose=1
        )
        
        logger.info(f"模型训练完成，最佳验证损失: {min(history.history['val_loss']):.4f}")
        return history
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """预测"""
        if self.model is None:
            raise ValueError("模型未训练，请先调用train方法")
        
        predictions = self.model.predict(X)
        
        # 反标准化
        if self.feature_engineer.scalers.get('target_scaler'):
            predictions = self.feature_engineer.scalers['target_scaler'].inverse_transform(predictions)
        
        return predictions
    
    def evaluate(self, test_X: np.ndarray, test_y: np.ndarray) -> Dict[str, float]:
        """评估模型"""
        predictions = self.predict(test_X)
        
        # 反标准化真实值
        if self.feature_engineer.scalers.get('target_scaler'):
            test_y_original = self.feature_engineer.scalers['target_scaler'].inverse_transform(test_y)
        else:
            test_y_original = test_y
        
        # 计算评估指标
        mae = mean_absolute_error(test_y_original, predictions)
        mse = mean_squared_error(test_y_original, predictions)
        rmse = np.sqrt(mse)
        r2 = r2_score(test_y_original, predictions)
        mape = np.mean(np.abs((test_y_original - predictions) / test_y_original)) * 100
        
        metrics = {
            'mae': float(mae),
            'mse': float(mse),
            'rmse': float(rmse),
            'r2_score': float(r2),
            'mape': float(mape)
        }
        
        logger.info(f"模型评估完成: MAE={mae:.4f}, RMSE={rmse:.4f}, R²={r2:.4f}")
        return metrics
    
    def save_model(self, model_path: str, scaler_path: str):
        """保存模型和标准化器"""
        if self.model:
            self.model.save(model_path)
            self.feature_engineer.save_scalers(scaler_path)
            logger.info(f"模型已保存到 {model_path}")
    
    def load_model(self, model_path: str, scaler_path: str):
        """加载模型和标准化器"""
        self.model = tf.keras.models.load_model(model_path)
        self.feature_engineer.load_scalers(scaler_path)
        logger.info(f"模型已从 {model_path} 加载")

class MultiModalPredictor:
    """多模态预测器 - 结合多种特征"""
    
    def __init__(self):
        self.congestion_model = None
        self.speed_model = None
        self.feature_engineer = FeatureEngineer()
        self.model_name = "MultiModal_Traffic_Predictor"
        self.model_version = "2.0.0"
    
    def build_models(self):
        """构建多模态模型"""
        # 共享的LSTM层
        input_layer = Input(shape=(24, len(self.feature_engineer.feature_columns)))
        
        # LSTM特征提取
        lstm_out = LSTM(64, return_sequences=True)(input_layer)
        lstm_out = Dropout(0.2)(lstm_out)
        lstm_out = LSTM(32, return_sequences=False)(lstm_out)
        lstm_out = Dropout(0.2)(lstm_out)
        
        # 拥堵预测分支
        congestion_branch = Dense(16, activation='relu')(lstm_out)
        congestion_branch = Dropout(0.2)(congestion_branch)
        congestion_output = Dense(1, activation='sigmoid', name='congestion')(congestion_branch)
        
        # 速度预测分支
        speed_branch = Dense(16, activation='relu')(lstm_out)
        speed_branch = Dropout(0.2)(speed_branch)
        speed_output = Dense(1, activation='linear', name='speed')(speed_branch)
        
        # 创建模型
        model = Model(inputs=input_layer, outputs=[congestion_output, speed_output])
        
        optimizer = Adam(learning_rate=0.001)
        model.compile(
            optimizer=optimizer,
            loss={
                'congestion': 'mse',
                'speed': 'mse'
            },
            loss_weights={
                'congestion': 1.0,
                'speed': 0.5
            },
            metrics={
                'congestion': 'mae',
                'speed': 'mae'
            }
        )
        
        self.congestion_model = model
        logger.info(f"多模态模型构建完成，参数数量: {model.count_params()}")
        return model
    
    def train(self, train_X: np.ndarray, train_y_congestion: np.ndarray, train_y_speed: np.ndarray,
              validation_split: float = 0.2, epochs: int = 100, batch_size: int = 32):
        """训练多模态模型"""
        if self.congestion_model is None:
            self.build_models()
        
        # 回调函数
        callbacks = [
            EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True),
            ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=5, min_lr=1e-7)
        ]
        
        # 训练模型
        history = self.congestion_model.fit(
            train_X, {'congestion': train_y_congestion, 'speed': train_y_speed},
            validation_split=validation_split,
            epochs=epochs,
            batch_size=batch_size,
            callbacks=callbacks,
            verbose=1
        )
        
        logger.info(f"多模态模型训练完成")
        return history

class TrafficPredictionService:
    """交通预测服务"""
    
    def __init__(self):
        self.predictors = {}
        self.feature_engineer = FeatureEngineer()
        self._init_predictors()
    
    def _init_predictors(self):
        """初始化预测器"""
        # LSTM预测器
        lstm_predictor = LSTMTrafficPredictor()
        try:
            lstm_predictor.load_model(
                'backend/models/lstm_traffic_predictor.h5',
                'backend/models/lstm_scalers.pkl'
            )
            logger.info("LSTM模型加载成功")
        except:
            logger.warning("LSTM模型文件不存在，将创建新模型")
            lstm_predictor.build_model()
        
        self.predictors['lstm'] = lstm_predictor
        
        # 多模态预测器
        multi_predictor = MultiModalPredictor()
        try:
            multi_predictor.build_models()
            logger.info("多模态预测器初始化成功")
        except Exception as e:
            logger.error(f"多模态预测器初始化失败: {str(e)}")
        
        self.predictors['multimodal'] = multi_predictor
    
    def prepare_training_data(self, days: int = 30) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """准备训练数据"""
        db = SessionLocal()
        try:
            # 获取最近days天的数据
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            traffic_data = db.query(TrafficData).filter(
                TrafficData.timestamp >= cutoff_date
            ).order_by(TrafficData.timestamp).all()
            
            if len(traffic_data) < 100:
                raise ValueError(f"数据量不足，当前只有 {len(traffic_data)} 条记录")
            
            # 提取特征
            features_df = self.feature_engineer.extract_features(traffic_data)
            
            # 创建序列
            X_congestion, y_congestion = self.feature_engineer.create_sequences(
                features_df, sequence_length=24, target_column='congestion_ratio'
            )
            X_speed, y_speed = self.feature_engineer.create_sequences(
                features_df, sequence_length=24, target_column='avg_speed'
            )
            
            logger.info(f"准备训练数据完成: {len(X_congestion)} 个样本")
            return X_congestion, y_congestion, y_speed
            
        finally:
            db.close()
    
    def train_models(self):
        """训练所有模型"""
        try:
            # 准备训练数据
            X, y_congestion, y_speed = self.prepare_training_data(30)
            
            # 分割训练集和测试集
            X_train, X_test, y_c_train, y_c_test = train_test_split(
                X, y_congestion, test_size=0.2, random_state=42
            )
            _, _, y_s_train, y_s_test = train_test_split(
                X, y_speed, test_size=0.2, random_state=42
            )
            
            # 训练LSTM模型
            logger.info("开始训练LSTM模型...")
            lstm_predictor = self.predictors['lstm']
            history = lstm_predictor.train(X_train, y_c_train)
            
            # 评估LSTM模型
            lstm_metrics = lstm_predictor.evaluate(X_test, y_c_test)
            self._save_model_metrics('lstm', lstm_metrics)
            
            # 训练多模态模型
            logger.info("开始训练多模态模型...")
            multi_predictor = self.predictors['multimodal']
            multi_history = multi_predictor.train(X_train, y_c_train, y_s_train)
            
            # 保存模型
            self._save_models()
            
            logger.info("所有模型训练完成")
            return True
            
        except Exception as e:
            logger.error(f"模型训练失败: {str(e)}")
            return False
    
    def predict_traffic(self, location_lng: float, location_lat: float, 
                       prediction_horizon: int = 6) -> Dict[str, Any]:
        """预测交通状况"""
        try:
            # 获取最近的历史数据
            db = SessionLocal()
            recent_data = db.query(TrafficData).filter(
                TrafficData.location_lng == location_lng,
                TrafficData.location_lat == location_lat,
                TrafficData.timestamp >= datetime.utcnow() - timedelta(days=7)
            ).order_by(TrafficData.timestamp.desc()).limit(100).all()
            
            if len(recent_data) < 24:
                raise ValueError("历史数据不足，无法进行预测")
            
            # 准备特征
            features_df = self.feature_engineer.extract_features(recent_data)
            
            # 创建输入序列（使用最近24小时的数据）
            if len(features_df) >= 24:
                input_data = features_df.tail(24)[self.feature_engineer.feature_columns].values
                input_data = self.feature_engineer.scalers['feature_scaler'].transform(input_data)
                input_sequence = input_data.reshape(1, 24, len(self.feature_engineer.feature_columns))
            else:
                raise ValueError("数据不足以创建预测序列")
            
            # 使用LSTM模型预测
            lstm_predictor = self.predictors['lstm']
            lstm_predictions = []
            
            for i in range(prediction_horizon):
                pred = lstm_predictor.predict(input_sequence)
                lstm_predictions.append(pred[0][0])
                
                # 更新输入序列（用于多步预测）
                # 这里简化处理，实际应该滚动更新
            
            # 生成预测结果
            result = {
                "success": True,
                "location": {"lng": location_lng, "lat": location_lat},
                "prediction_horizon_hours": prediction_horizon,
                "predictions": [],
                "model_info": {
                    "name": lstm_predictor.model_name,
                    "version": lstm_predictor.model_version
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # 生成未来每个小时的预测
            for i, congestion_ratio in enumerate(lstm_predictions):
                future_time = datetime.utcnow() + timedelta(hours=i+1)
                
                # 基于拥堵比例估算速度
                estimated_speed = 40 * (1 - congestion_ratio) + 20  # 简化估算
                
                prediction = {
                    "hour": future_time.hour,
                    "timestamp": future_time.isoformat(),
                    "congestion_ratio": float(congestion_ratio),
                    "predicted_speed": float(estimated_speed),
                    "confidence_score": 0.85  # 简化的置信度
                }
                result["predictions"].append(prediction)
            
            return result
            
        except Exception as e:
            logger.error(f"交通预测失败: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        finally:
            db.close()
    
    def _save_models(self):
        """保存所有模型"""
        import os
        os.makedirs('backend/models', exist_ok=True)
        
        lstm_predictor = self.predictors['lstm']
        lstm_predictor.save_model(
            'backend/models/lstm_traffic_predictor.h5',
            'backend/models/lstm_scalers.pkl'
        )
        
        # 保存多模态模型
        multi_predictor = self.predictors['multimodal']
        if multi_predictor.congestion_model:
            multi_predictor.congestion_model.save('backend/models/multimodal_predictor.h5')
            self.feature_engineer.save_scalers('backend/models/multimodal_scalers.pkl')
        
        logger.info("所有模型已保存")
    
    def _save_model_metrics(self, model_type: str, metrics: Dict[str, float]):
        """保存模型指标到数据库"""
        db = SessionLocal()
        try:
            model_metrics = ModelMetrics(
                model_name=f"{self.model_name}_{model_type}",
                model_version=self.model_version,
                mae=metrics.get('mae'),
                mse=metrics.get('mse'),
                rmse=metrics.get('rmse'),
                r2_score=metrics.get('r2_score'),
                mape=metrics.get('mape')
            )
            db.add(model_metrics)
            db.commit()
            logger.info(f"{model_type} 模型指标已保存")
        except Exception as e:
            db.rollback()
            logger.error(f"保存模型指标失败: {str(e)}")
        finally:
            db.close()

async def main():
    """主函数 - 用于测试"""
    # 初始化预测服务
    prediction_service = TrafficPredictionService()
    
    # 训练模型
    success = prediction_service.train_models()
    if success:
        print("模型训练成功")
        
        # 测试预测
        result = prediction_service.predict_traffic(120.15507, 30.27415, 6)
        print("预测结果:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("模型训练失败")

if __name__ == "__main__":
    asyncio.run(main())
