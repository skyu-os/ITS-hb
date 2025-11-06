# 智能交通预测后端服务

这是智能交通预测系统的后端API服务，提供基于机器学习的交通预测功能。

## 功能特点

- HMAC-SHA256签名验证，确保API安全
- CORS支持，允许前端跨域访问
- 简单的预测逻辑（可替换为实际的机器学习模型）
- RESTful API设计

## 安装与运行

### 方法一：使用批处理文件（Windows）

1. 双击运行 `start_backend.bat`
2. 等待依赖安装完成
3. 服务将在 http://127.0.0.1:8003 上运行

### 方法二：手动安装

1. 安装Python依赖：
   ```
   pip install -r requirements.txt
   ```

2. 启动服务：
   ```
   python server.py
   ```

3. 服务将在 http://127.0.0.1:8003 上运行

## API文档

### 预测接口

- **URL**: `POST /api/predict`
- **描述**: 基于当前交通数据预测未来交通状况

#### 请求头

- `Content-Type`: `application/json`
- `X-Signature`: HMAC-SHA256签名

#### 请求体

```json
{
  "center": [经度, 纬度],
  "zoom": 缩放级别,
  "timestamp": "ISO时间戳",
  "trafficLevel": 交通拥堵指数,
  "avgSpeed": 平均速度,
  "congestionRatio": 拥堵比例,
  "timestamp": Unix时间戳,
  "nonce": "随机字符串"
}
```

#### 响应体

```json
{
  "success": true,
  "message": "预测成功",
  "metrics": {
    "congestionRatio": 0.65,
    "avgSpeed": 35.2,
    "travelTime": 42.5
  },
  "suggestions": [
    "建议避开高峰时段出行",
    "考虑使用公共交通工具"
  ]
}
```

## 安全说明

- API使用HMAC-SHA256签名验证请求
- 请求包含时间戳和随机数，防止重放攻击
- 生产环境中应限制CORS来源域名
- 建议在生产环境中使用HTTPS

## 集成说明

前端应用（`assets/ml.js`）已经配置为与此后端服务通信。确保后端服务在 http://127.0.0.1:8003 上运行，然后在前端点击"智能交通预测"按钮即可使用预测功能。

## 扩展开发

当前实现使用简单的规则生成预测结果。要集成实际的机器学习模型（如插件目录中的STGCN模型），可以修改`predict_traffic`函数，加载模型并进行预测。

## 故障排除

1. **端口占用**: 如果8003端口被占用，可以修改`server.py`中的端口号
2. **依赖安装失败**: 确保Python版本为3.7或更高，并使用pip安装依赖
3. **签名验证失败**: 检查前端和后端的API_SECRET是否一致
4. **CORS错误**: 确保前端URL在CORS允许的来源列表中