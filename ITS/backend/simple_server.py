import http.server
import socketserver
import json
import hashlib
import hmac
import time
import random
import urllib.parse
from datetime import datetime

# 导入机器学习模型
try:
    from ml_model import predict_traffic
    ML_MODEL_AVAILABLE = True
except ImportError:
    ML_MODEL_AVAILABLE = False
    print("警告: 无法导入机器学习模型，将使用简单预测逻辑")

# 导入增强机器学习模型
try:
    from enhanced_ml_model import enhanced_predict_traffic, get_model_report
    ENHANCED_ML_MODEL_AVAILABLE = True
except ImportError as e:
    ENHANCED_ML_MODEL_AVAILABLE = False
    print(f"警告: 无法导入增强机器学习模型: {e}")

# API配置
API_SECRET = 'your-secret-key-here'
PORT = 8003

class PredictHandler(http.server.BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        # 处理预检请求
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Signature')
        self.end_headers()
    
    def do_POST(self):
        if self.path == '/api/predict':
            # 获取请求内容长度
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            # 解析JSON数据
            try:
                data = json.loads(post_data.decode('utf-8'))
            except json.JSONDecodeError:
                self.send_error(400, "Invalid JSON")
                return
            
            # 验证签名
            signature = self.headers.get('X-Signature')
            if not signature:
                self.send_error(401, "Missing signature")
                return
            
            # 生成预期签名
            expected_signature = hmac.new(
                API_SECRET.encode('utf-8'),
                json.dumps(data, separators=(',', ':'), sort_keys=True).encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            if not hmac.compare_digest(signature, expected_signature):
                self.send_error(401, "Invalid signature")
                return
            
            # 处理预测请求
            try:
                # 获取请求的模型类型
                model_type = data.get('model_type', 'enhanced')
                
                # 根据模型类型选择预测方法
                if model_type == 'enhanced' and ENHANCED_ML_MODEL_AVAILABLE:
                    result = enhanced_predict_traffic(data)
                elif model_type == 'basic' and ML_MODEL_AVAILABLE:
                    result = predict_traffic(data)
                else:
                    # 如果指定模型不可用，使用回退机制
                    result = predict_traffic_wrapper(data)
                
                # 发送响应
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(result).encode('utf-8'))
            except Exception as e:
                self.send_error(500, f"Server error: {str(e)}")
        else:
            self.send_error(404, "Not found")
    
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write("<h1>智能交通预测API服务</h1><p>API端点: POST /api/predict</p><p>模型报告: GET /api/model_report</p>".encode('utf-8'))
        elif self.path == '/api/model_report':
            # 处理模型报告请求
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            try:
                if ENHANCED_ML_MODEL_AVAILABLE:
                    report = get_model_report()
                    response = {
                        "success": True,
                        "report": report,
                        "model_type": "增强机器学习模型"
                    }
                elif ML_MODEL_AVAILABLE:
                    response = {
                        "success": True,
                        "report": "基础机器学习模型正在运行",
                        "model_type": "基础机器学习模型"
                    }
                else:
                    response = {
                        "success": True,
                        "report": "当前使用简单预测模型",
                        "model_type": "简单模型"
                    }
                self.wfile.write(json.dumps(response).encode('utf-8'))
            except Exception as e:
                error_response = {
                    "success": False,
                    "message": f"获取模型报告失败: {str(e)}"
                }
                self.wfile.write(json.dumps(error_response).encode('utf-8'))
        else:
            self.send_error(404, "Not found")

# 如果机器学习模型不可用，则使用简单预测逻辑
def simple_predict_traffic(data):
    """简单的预测逻辑，作为机器学习模型的备用"""
    # 从请求中提取数据
    traffic_level = data.get('trafficLevel', 0.5)
    avg_speed = data.get('avgSpeed', 40)
    congestion_ratio = data.get('congestionRatio', 0.3)
    
    # 简单的预测逻辑（实际应用中应使用机器学习模型）
    # 这里只是模拟预测结果
    predicted_congestion = min(1.0, congestion_ratio + random.uniform(-0.1, 0.2))
    predicted_speed = max(10, avg_speed + random.uniform(-10, 10))
    predicted_time = 30 + (1 - predicted_congestion) * 20 + random.uniform(-5, 5)
    
    # 生成建议
    suggestions = []
    if predicted_congestion > 0.7:
        suggestions.append("建议避开高峰时段出行")
    if predicted_speed < 30:
        suggestions.append("考虑使用公共交通工具")
    if predicted_congestion < 0.3:
        suggestions.append("当前路况良好，适合出行")
    
    return {
        "success": True,
        "message": "预测成功",
        "model_type": "简单模型",
        "metrics": {
            "congestionRatio": round(predicted_congestion, 2),
            "avgSpeed": round(predicted_speed, 1),
            "travelTime": round(predicted_time, 1)
        },
        "suggestions": suggestions
    }

def predict_traffic_wrapper(data):
    """预测交通状况的包装函数，优先使用增强机器学习模型"""
    if ENHANCED_ML_MODEL_AVAILABLE:
        try:
            result = enhanced_predict_traffic(data)
            print(f"增强模型预测结果: {result}")
            return result
        except Exception as e:
            print(f"增强机器学习模型预测失败: {e}")
            # 失败时回退到基础机器学习模型
            if ML_MODEL_AVAILABLE:
                try:
                    return predict_traffic(data)
                except Exception as e2:
                    print(f"基础机器学习模型预测失败: {e2}")
                    return simple_predict_traffic(data)
            else:
                return simple_predict_traffic(data)
    elif ML_MODEL_AVAILABLE:
        try:
            return predict_traffic(data)
        except Exception as e:
            print(f"基础机器学习模型预测失败: {e}")
            return simple_predict_traffic(data)
    else:
        return simple_predict_traffic(data)

def run_server():
    with socketserver.TCPServer(("", PORT), PredictHandler) as httpd:
        print(f"服务器启动在端口 {PORT}")
        print(f"访问 http://localhost:{PORT} 查看API信息")
        print(f"API端点: http://localhost:{PORT}/api/predict")
        print(f"模型报告: http://localhost:{PORT}/api/model_report")
        
        if ENHANCED_ML_MODEL_AVAILABLE:
            print("✓ 增强机器学习模型已启用")
        elif ML_MODEL_AVAILABLE:
            print("✓ 基础机器学习模型已启用")
        else:
            print("⚠ 使用简单预测逻辑")
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n服务器已停止")

if __name__ == "__main__":
    run_server()