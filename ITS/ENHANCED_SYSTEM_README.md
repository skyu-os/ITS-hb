# 智能交通预测系统 v2.0 - 增强版

基于深度学习的智能交通预测与数据分析系统，集成实时数据采集、LSTM预测模型、WebSocket实时通信等先进功能。

## 🚀 新增功能

### 1. 深度学习预测模型
- **LSTM时序预测**：基于24小时历史数据预测未来6小时交通状况
- **多模态特征**：整合时间、天气、节假日等多种特征
- **模型自动训练**：支持增量学习和定期模型更新
- **性能评估**：MAE、RMSE、R²等多种评估指标

### 2. 增强数据采集系统
- **多数据源支持**：可集成多个交通数据API
- **数据质量控制**：实时数据质量检查和异常检测
- **Redis缓存**：提升数据访问性能
- **定时采集**：自动化数据采集任务

### 3. 实时通信系统
- **WebSocket连接**：实时推送交通数据更新
- **事件订阅**：支持订阅特定位置的数据更新
- **连接管理**：自动重连和心跳检测

### 4. 完整API服务
- **RESTful API**：标准化的数据接口
- **异步处理**：后台任务和长时间操作
- **错误处理**：完善的异常处理机制

## 📁 项目结构

```
ITS/
├── backend/                    # 后端服务
│   ├── database.py            # 数据库模型和配置
│   ├── data_collector.py      # 增强数据采集服务
│   ├── deep_learning_predictor.py  # 深度学习预测模型
│   ├── enhanced_server.py    # 增强API服务器
│   ├── start_enhanced_backend.py  # 启动脚本
│   ├── .env.example         # 环境变量示例
│   └── requirements.txt     # Python依赖
├── assets/
│   ├── enhanced_ml.js       # 前端增强ML模块
│   ├── app.js             # 主应用逻辑
│   └── style.css          # 样式文件
├── index.html              # 主页面
└── ENHANCED_SYSTEM_README.md  # 本文档
```

## 🛠️ 安装和配置

### 1. 环境要求
- Python 3.8+
- Node.js (可选，用于前端开发)
- Redis (可选，用于缓存)
- PostgreSQL (可选，默认使用SQLite)

### 2. 后端安装

```bash
# 进入后端目录
cd backend

# 安装Python依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，配置您的API密钥等

# 初始化数据库
python database.py
```

### 3. 启动服务

#### 方式一：完整初始化启动
```bash
# 自动完成数据库初始化、数据采集、模型训练和服务器启动
python start_enhanced_backend.py
```

#### 方式二：分步启动
```bash
# 仅初始化系统
python start_enhanced_backend.py --init-only

# 仅采集数据
python start_enhanced_backend.py --collect-only

# 仅训练模型
python start_enhanced_backend.py --train-only

# 直接启动服务器（跳过初始化）
python start_enhanced_backend.py --skip-init
```

### 4. 开发模式启动
```bash
# 启用自动重载
python start_enhanced_backend.py --reload
```

## 🔧 配置说明

### 环境变量配置 (.env)

```bash
# 数据库配置
DATABASE_URL=sqlite:///./traffic_data.db
# 或 PostgreSQL: postgresql://user:password@localhost:5432/traffic_db

# Redis配置
REDIS_URL=redis://localhost:6379

# 高德地图API密钥（必需）
AMAP_API_KEY=your_amap_api_key_here

# API安全密钥
API_SECRET=traffic-prediction-secret-key

# 模型配置
MODEL_RETRAIN_INTERVAL=7    # 模型重新训练间隔（天）
MODEL_SEQUENCE_LENGTH=24    # 时序数据长度
PREDICTION_HORIZON=6        # 预测时长（小时）

# 数据采集配置
COLLECTION_INTERVAL=300     # 数据采集间隔（秒）
DATA_RETENTION_DAYS=30      # 数据保留天数

# 服务配置
HOST=127.0.0.1
PORT=8003
```

## 📊 API接口文档

### 基础接口

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/` | 服务首页 |
| GET | `/docs` | API文档 |

### 数据采集接口

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/collect` | 采集交通数据 |
| GET | `/api/traffic-history` | 获取历史数据 |

### 预测接口

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/predict` | 交通预测 |
| POST | `/api/train-models` | 训练模型 |

### 系统接口

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/model-metrics` | 获取模型指标 |
| GET | `/api/statistics` | 获取系统统计 |

### WebSocket接口

| 路径 | 描述 |
|------|------|
| `/ws` | WebSocket实时通信 |

## 🌐 前端集成

### 1. 基础使用
```javascript
// 检查增强ML服务是否可用
if (window.isEnhancedMLAvailable()) {
    // 使用增强预测
    window.runEnhancedPrediction(lng, lat, horizon);
} else {
    // 回退到基础功能
    runMLPredict();
}
```

### 2. 实时数据订阅
```javascript
// 监听实时数据更新
if (window.wsManager) {
    window.wsManager.on('traffic_update', (data) => {
        console.log('收到实时交通数据:', data);
        // 更新UI显示
    });
}
```

### 3. 模型训练监听
```javascript
// 监听模型训练完成事件
window.onModelTrainingCompleted = (result) => {
    if (result.success) {
        console.log('模型训练成功');
        // 更新UI状态
    }
};
```

## 🎯 使用示例

### 1. 交通数据采集
```bash
curl -X POST "http://localhost:8003/api/collect" \
  -H "Content-Type: application/json" \
  -d '{
    "lng": 120.15507,
    "lat": 30.27415,
    "radius_km": 3.0,
    "api_key": "your_amap_api_key"
  }'
```

### 2. 交通预测
```bash
curl -X POST "http://localhost:8003/api/predict" \
  -H "Content-Type: application/json" \
  -d '{
    "lng": 120.15507,
    "lat": 30.27415,
    "prediction_horizon": 6,
    "model_type": "lstm"
  }'
```

### 3. 模型训练
```bash
curl -X POST "http://localhost:8003/api/train-models" \
  -H "Content-Type: application/json" \
  -d '{
    "days": 30,
    "force_retrain": false
  }'
```

## 📈 性能优化

### 1. 数据库优化
- 自动清理过期数据
- 索引优化
- 连接池管理

### 2. 缓存策略
- Redis缓存热点数据
- 预测结果缓存
- API响应缓存

### 3. 模型优化
- 模型文件压缩
- 批量预测
- 增量训练

## 🐛 故障排除

### 1. 常见问题

#### Q: 模型训练失败
A: 检查以下几点：
- 确保有足够的历史数据（至少100条记录）
- 检查TensorFlow版本兼容性
- 查看日志文件获取详细错误信息

#### Q: 数据采集失败
A: 可能的原因：
- 高德API密钥无效或过期
- 网络连接问题
- API调用频率限制

#### Q: WebSocket连接断开
A: 检查：
- 服务器端口是否正确
- 防火墙设置
- 网络稳定性

### 2. 日志查看
```bash
# 查看后端日志
tail -f backend/backend.log

# 查看系统状态
curl http://localhost:8003/health
```

### 3. 性能监控
```bash
# 获取系统统计
curl http://localhost:8003/api/statistics

# 获取模型性能指标
curl http://localhost:8003/api/model-metrics
```

## 🔄 升级指南

### 从v1.0升级到v2.0

1. **备份现有数据**
```bash
cp backend/traffic_data.db backend/traffic_data.db.backup
```

2. **更新依赖**
```bash
pip install -r backend/requirements.txt
```

3. **运行迁移**
```bash
python backend/start_enhanced_backend.py --init-only
```

4. **验证升级**
```bash
curl http://localhost:8003/health
```

## 🤝 贡献指南

### 开发环境设置
```bash
# 克隆项目
git clone <repository-url>
cd ITS

# 安装后端依赖
cd backend
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env

# 启动开发服务器
python start_enhanced_backend.py --reload
```

### 代码规范
- Python代码遵循PEP 8规范
- JavaScript使用ES6+语法
- 提交前运行测试和代码检查

## 📄 许可证

本项目为演示用途，请根据实际需求配置相应的许可证。

## 📞 支持

如有问题或建议，请：
1. 查看本文档的故障排除部分
2. 检查GitHub Issues
3. 联系开发团队

---

**注意**：本系统需要有效的API密钥才能正常工作。请确保在`.env`文件中正确配置相关密钥。
