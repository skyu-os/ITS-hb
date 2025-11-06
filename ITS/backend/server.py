from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import hashlib
import hmac
import json
import time
import random
from typing import Dict, List, Optional

app = FastAPI(title="智能交通预测API", description="基于机器学习的交通预测服务")

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境中应该限制为特定域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API密钥
API_SECRET = "demo-secret-key"

# 请求模型
class PredictRequest(BaseModel):
    center: List[float]  # [经度, 纬度]
    zoom: int
    timestamp: str
    trafficLevel: float
    avgSpeed: float
    congestionRatio: float
    timestamp: int  # 时间戳
    nonce: str  # 随机数

# 响应模型
class PredictResponse(BaseModel):
    success: bool
    message: str
    metrics: Dict[str, float]
    suggestions: List[str]

# 验证签名
def verify_signature(payload: str, signature: str, secret: str) -> bool:
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected_signature, signature)

# 简单的预测逻辑（实际应用中应该使用机器学习模型）
def predict_traffic(data: PredictRequest) -> Dict:
    # 这里使用简单的规则生成预测结果
    # 实际应用中应该调用机器学习模型
    
    # 基于当前拥堵比例预测未来
    current_congestion = data.congestionRatio
    
    # 模拟预测结果
    future_congestion = min(0.9, current_congestion + random.uniform(-0.1, 0.2))
    future_speed = max(10, data.avgSpeed + random.uniform(-10, 10))
    
    # 生成建议
    suggestions = []
    if future_congestion > 0.7:
        suggestions.append("建议避开高峰时段出行")
        suggestions.append("考虑使用公共交通工具")
    elif future_congestion > 0.4:
        suggestions.append("建议提前15分钟出发")
    else:
        suggestions.append("路况良好，适合出行")
    
    return {
        "congestionRatio": future_congestion,
        "avgSpeed": future_speed,
        "travelTime": 30 + random.uniform(-10, 20)  # 预计行程时间（分钟）
    }, suggestions

@app.post("/api/predict", response_model=PredictResponse)
async def predict(request: Request, x_signature: str = Header(...)):
    try:
        # 获取请求体
        body = await request.body()
        body_str = body.decode('utf-8')
        
        # 验证签名
        if not verify_signature(body_str, x_signature, API_SECRET):
            raise HTTPException(status_code=401, detail="签名验证失败")
        
        # 解析请求数据
        data = json.loads(body_str)
        predict_request = PredictRequest(**data)
        
        # 检查时间戳，防止重放攻击
        current_time = int(time.time())
        if abs(current_time - predict_request.timestamp) > 300:  # 5分钟有效期
            raise HTTPException(status_code=401, detail="请求已过期")
        
        # 执行预测
        metrics, suggestions = predict_traffic(predict_request)
        
        return PredictResponse(
            success=True,
            message="预测成功",
            metrics=metrics,
            suggestions=suggestions
        )
    
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="无效的JSON数据")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")

@app.get("/")
def read_root():
    return {"message": "智能交通预测API服务正在运行"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8003)