#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强机器学习模型演示程序
实现完整的模型训练、评估、特征分析和可视化流程
"""

import json
import time
from datetime import datetime
import sys
import os

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from enhanced_ml_model import EnhancedTrafficPredictor, LightML, get_model_report, predict_traffic

class MLDemo:
    """机器学习模型演示类"""
    
    def __init__(self):
        self.predictor = EnhancedTrafficPredictor()
        self.demo_data = None
        
    def run_complete_demo(self):
        """运行完整的演示流程"""
        print("=" * 60)
        print("增强机器学习模型完整演示")
        print("=" * 60)
        
        # 1. 数据生成
        print("\n1. 生成训练数据...")
        self.generate_demo_data()
        
        # 2. 特征工程
        print("\n2. 执行特征工程...")
        processed_data = self.feature_engineering_demo()
        
        # 3. 模型训练和评估
        print("\n3. 模型训练和评估...")
        performance = self.model_evaluation_demo()
        
        # 4. 特征重要性分析
        print("\n4. 特征重要性分析...")
        feature_analysis = self.feature_importance_demo()
        
        # 5. 预测演示
        print("\n5. 实时预测演示...")
        prediction_demo = self.prediction_demo()
        
        # 6. 生成完整报告
        print("\n6. 生成完整报告...")
        final_report = self.generate_comprehensive_report()
        
        return final_report
    
    def generate_demo_data(self):
        """生成演示数据"""
        print("正在生成1000个样本的训练数据...")
        X, y_congestion, y_speed, y_time = self.predictor.generate_enhanced_training_data(1000)
        
        self.demo_data = {
            'X': X,
            'y_congestion': y_congestion,
            'y_speed': y_speed,
            'y_time': y_time
        }
        
        print(f"数据生成完成:")
        print(f"  - 特征数量: {len(X[0])}")
        print(f"  - 样本总数: {len(X)}")
        print(f"  - 拥堵数据范围: {min(y_congestion):.3f} ~ {max(y_congestion):.3f}")
        print(f"  - 速度数据范围: {min(y_speed):.1f} ~ {max(y_speed):.1f} km/h")
        
        return self.demo_data
    
    def feature_engineering_demo(self):
        """特征工程演示"""
        if not self.demo_data:
            print("请先生成演示数据")
            return None
            
        X = self.demo_data['X']
        print("原始特征:")
        print(f"  - 特征维度: {len(X[0])}")
        print(f"  - 特征名称: {self.predictor.feature_names}")
        
        # 执行特征工程
        X_processed = self.predictor.feature_engineering(X)
        
        print("\n特征工程后:")
        print(f"  - 新特征维度: {len(X_processed[0])}")
        print(f"  - 新增特征: ['is_peak_hour', 'is_weekend', 'speed_efficiency']")
        
        # 显示第一个样本的特征变化
        print(f"\n第一个样本特征变化:")
        print(f"  原始: {X[0]}")
        print(f"  处理后: {X_processed[0]}")
        
        return X_processed
    
    def model_evaluation_demo(self):
        """模型评估演示"""
        if not self.demo_data:
            print("请先生成演示数据")
            return None
            
        X = self.demo_data['X']
        y_congestion = self.demo_data['y_congestion']
        
        # 分割训练集和测试集
        X_train, X_test, y_train, y_test = LightML.train_test_split(X, y_congestion, test_size=0.2)
        
        print(f"数据集分割:")
        print(f"  - 训练集: {len(X_train)} 样本")
        print(f"  - 测试集: {len(X_test)} 样本")
        
        # 评估模型
        metrics = self.predictor.evaluate_model(X_test, y_test)
        
        print(f"\n模型性能指标:")
        print(f"  - R² Score: {metrics['r2_score']}")
        print(f"  - 均方误差 (MSE): {metrics['mse']}")
        print(f"  - 平均绝对误差 (MAE): {metrics['mae']}")
        
        # 生成预测可视化
        predictions = [self.predictor.predict(features)['predicted_congestion'] for features in X_test]
        visualization = self.predictor.visualize_predictions(X_test, y_test, predictions)
        
        print(f"\n预测可视化摘要:")
        print(visualization)
        
        return metrics
    
    def feature_importance_demo(self):
        """特征重要性分析演示"""
        feature_importance = self.predictor.get_feature_importance()
        
        print("特征重要性分析:")
        print("-" * 40)
        
        # 按重要性排序
        sorted_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)
        
        for feature, importance in sorted_features:
            bar_length = int(importance * 30)
            bar = '█' * bar_length + '░' * (30 - bar_length)
            print(f"{feature:15s} {bar} {importance:.3f}")
        
        print("\n关键洞察:")
        print("  • 时间特征(小时)对交通预测影响最大")
        print("  • 星期几和工作日模式也很重要") 
        print("  • 实时交通水平和速度提供补充信息")
        
        return feature_importance
    
    def prediction_demo(self):
        """实时预测演示"""
        print("实时预测演示:")
        print("-" * 40)
        
        # 定义几个典型场景
        scenarios = [
            {
                'name': '周一早高峰',
                'features': [8, 1, 0.7, 25, 0.7],  # 周一8点，高拥堵
                'description': '工作日早高峰时段'
            },
            {
                'name': '周五晚高峰', 
                'features': [18, 4, 0.8, 20, 0.8],  # 周五18点，极高拥堵
                'description': '周末前晚高峰'
            },
            {
                'name': '周末中午',
                'features': [12, 6, 0.3, 55, 0.3],  # 周日12点，低拥堵
                'description': '周末休闲时段'
            },
            {
                'name': '深夜时段',
                'features': [2, 2, 0.1, 70, 0.1],  # 周二凌晨2点，极低拥堵
                'description': '深夜畅通时段'
            }
        ]
        
        results = []
        for scenario in scenarios:
            prediction = self.predictor.predict(scenario['features'])
            results.append({
                'scenario': scenario,
                'prediction': prediction
            })
            
            print(f"\n{scenario['name']} ({scenario['description']}):")
            print(f"  输入特征: {scenario['features']}")
            print(f"  预测拥堵: {prediction['predicted_congestion']}")
            print(f"  预测速度: {prediction['predicted_speed']} km/h")
            print(f"  预测时间: {prediction['predicted_time']} 分钟")
            print(f"  置信度: {prediction['confidence']}")
            
            # 提供建议
            congestion = prediction['predicted_congestion']
            if congestion > 0.7:
                print("  💡 建议: 严重拥堵，建议更改出行计划")
            elif congestion > 0.5:
                print("  💡 建议: 中度拥堵，考虑替代路线")
            else:
                print("  💡 建议: 路况良好，适合出行")
        
        return results
    
    def generate_comprehensive_report(self):
        """生成综合报告"""
        report = self.predictor.create_performance_report()
        
        print("\n" + "=" * 60)
        print("模型综合性能报告")
        print("=" * 60)
        
        print(f"\n📊 模型基本信息:")
        print(f"  • 模型类型: {report['model_type']}")
        print(f"  • 训练状态: {report['training_status']}")
        
        print(f"\n📈 性能指标:")
        metrics = report['performance_metrics']
        print(f"  • R² Score: {metrics['r2_score']}")
        print(f"  • 均方误差: {metrics['mse']}")
        print(f"  • 平均绝对误差: {metrics['mae']}")
        
        print(f"\n🔍 特征重要性:")
        importance = report['feature_importance']
        for feature, score in importance.items():
            print(f"  • {feature}: {score:.3f}")
        
        print(f"\n🧠 模型解释性:")
        interpretation = report['model_interpretation']
        for key, value in interpretation.items():
            print(f"  • {key}: {value}")
        
        print(f"\n✅ 模型优势:")
        print("  • 无需外部依赖，纯Python实现")
        print("  • 基于规则的预测逻辑，解释性强")
        print("  • 包含完整的特征工程和评估流程")
        print("  • 提供实时预测和智能建议")
        
        print(f"\n🔮 后续开发建议:")
        print("  • 可集成真实交通数据源")
        print("  • 添加深度学习模型支持")
        print("  • 实现实时数据流处理")
        print("  • 开发Web API接口")
        
        return report

def main():
    """主函数"""
    try:
        demo = MLDemo()
        
        print("开始增强机器学习模型演示...")
        start_time = time.time()
        
        # 运行完整演示
        final_report = demo.run_complete_demo()
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        print(f"\n⏱️  演示完成时间: {elapsed_time:.2f} 秒")
        print("🎉 所有功能演示完毕！")
        
        # 保存报告到文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"ml_model_report_{timestamp}.json"
        
        with open(report_filename, 'w', encoding='utf-8') as f:
            json.dump(final_report, f, ensure_ascii=False, indent=2)
        
        print(f"📄 详细报告已保存至: {report_filename}")
        
    except Exception as e:
        print(f"演示过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()