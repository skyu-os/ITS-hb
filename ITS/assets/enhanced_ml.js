/**
 * 增强机器学习模块
集成深度学习预测模型和实时数据通信
 */

// 全局变量
let wsConnection = null;
let mlApiBase = 'http://127.0.0.1:8003';
let isEnhancedMLAvailable = false;

// WebSocket连接管理
class WebSocketManager {
    constructor(url) {
        this.url = url;
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectInterval = 5000;
        this.heartbeatInterval = null;
        this.callbacks = {};
    }

    connect() {
        try {
            this.ws = new WebSocket(this.url);
            this.setupEventHandlers();
        } catch (error) {
            console.error('WebSocket连接失败:', error);
            this.scheduleReconnect();
        }
    }

    setupEventHandlers() {
        this.ws.onopen = () => {
            console.log('WebSocket连接已建立');
            this.reconnectAttempts = 0;
            this.startHeartbeat();
            
            // 订阅实时数据
            this.subscribe({
                lng: 120.15507,
                lat: 30.27415
            });
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            } catch (error) {
                console.error('WebSocket消息解析失败:', error);
            }
        };

        this.ws.onclose = () => {
            console.log('WebSocket连接已断开');
            this.stopHeartbeat();
            this.scheduleReconnect();
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket错误:', error);
        };
    }

    handleMessage(data) {
        const { type, data: messageData } = data;
        
        if (this.callbacks[type]) {
            this.callbacks[type].forEach(callback => {
                try {
                    callback(messageData);
                } catch (error) {
                    console.error(`回调执行失败 (${type}):`, error);
                }
            });
        }

        // 处理特定消息类型
        switch (type) {
            case 'traffic_update':
                this.handleTrafficUpdate(messageData);
                break;
            case 'new_data':
                this.handleNewData(messageData);
                break;
            case 'model_training_completed':
                this.handleTrainingCompleted(messageData);
                break;
            case 'subscription_confirmed':
                console.log('订阅确认:', messageData);
                break;
        }
    }

    handleTrafficUpdate(data) {
        // 更新实时交通数据显示
        if (window.updateTrafficDisplay) {
            window.updateTrafficDisplay(data);
        }
        
        // 更新地图上的交通状态
        if (data && data.length > 0) {
            const latestData = data[0];
            if (latestData.location && latestData.congestion_ratio !== undefined) {
                updateMapTrafficLevel(
                    latestData.location.lng, 
                    latestData.location.lat, 
                    latestData.congestion_ratio
                );
            }
        }
    }

    handleNewData(data) {
        console.log('收到新数据通知:', data);
        if (window.onNewDataCollected) {
            window.onNewDataCollected(data);
        }
    }

    handleTrainingCompleted(data) {
        console.log('模型训练完成:', data);
        if (window.onModelTrainingCompleted) {
            window.onModelTrainingCompleted(data);
        }
    }

    subscribe(location) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.send({
                type: 'subscribe',
                location: location
            });
        }
    }

    send(message) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(message));
        }
    }

    on(eventType, callback) {
        if (!this.callbacks[eventType]) {
            this.callbacks[eventType] = [];
        }
        this.callbacks[eventType].push(callback);
    }

    off(eventType, callback) {
        if (this.callbacks[eventType]) {
            const index = this.callbacks[eventType].indexOf(callback);
            if (index > -1) {
                this.callbacks[eventType].splice(index, 1);
            }
        }
    }

    startHeartbeat() {
        this.heartbeatInterval = setInterval(() => {
            this.send({ type: 'ping' });
        }, 30000);
    }

    stopHeartbeat() {
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
            this.heartbeatInterval = null;
        }
    }

    scheduleReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`尝试重新连接 (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
            
            setTimeout(() => {
                this.connect();
            }, this.reconnectInterval);
        } else {
            console.error('达到最大重连次数，停止重连');
        }
    }

    close() {
        this.stopHeartbeat();
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }
}

// 增强的ML预测服务
class EnhancedMLService {
    constructor(apiBase) {
        this.apiBase = apiBase;
        this.isAvailable = false;
        this.checkAvailability();
    }

    async checkAvailability() {
        try {
            const response = await fetch(`${this.apiBase}/health`);
            this.isAvailable = response.ok;
            return this.isAvailable;
        } catch (error) {
            console.error('增强ML服务不可用:', error);
            this.isAvailable = false;
            return false;
        }
    }

    async collectTrafficData(lng, lat, radiusKm = 3.0, apiKey) {
        try {
            const response = await fetch(`${this.apiBase}/api/collect`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    lng: lng,
                    lat: lat,
                    radius_km: radiusKm,
                    api_key: apiKey
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error('数据采集失败:', error);
            throw error;
        }
    }

    async predictTraffic(lng, lat, horizonHours = 6, modelType = 'lstm') {
        try {
            const response = await fetch(`${this.apiBase}/api/predict`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    lng: lng,
                    lat: lat,
                    prediction_horizon: horizonHours,
                    model_type: modelType
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const result = await response.json();
            
            if (result.success) {
                // 处理预测结果
                return this.formatPredictionResult(result);
            } else {
                throw new Error(result.error || '预测失败');
            }
        } catch (error) {
            console.error('交通预测失败:', error);
            throw error;
        }
    }

    formatPredictionResult(result) {
        const { predictions, model_info } = result;
        
        return {
            success: true,
            modelType: model_info.name,
            modelVersion: model_info.version,
            timestamp: result.timestamp,
            predictions: predictions.map(pred => ({
                hour: pred.hour,
                timestamp: pred.timestamp,
                congestionRatio: pred.congestion_ratio,
                predictedSpeed: pred.predicted_speed,
                confidenceScore: pred.confidence_score,
                level: this.getCongestionLevel(pred.congestion_ratio)
            })),
            summary: this.generatePredictionSummary(predictions)
        };
    }

    getCongestionLevel(congestionRatio) {
        if (congestionRatio >= 0.7) return 'severe';
        if (congestionRatio >= 0.4) return 'moderate';
        return 'light';
    }

    generatePredictionSummary(predictions) {
        if (!predictions || predictions.length === 0) {
            return null;
        }

        const avgCongestion = predictions.reduce((sum, p) => sum + p.congestion_ratio, 0) / predictions.length;
        const maxCongestion = Math.max(...predictions.map(p => p.congestion_ratio));
        const minCongestion = Math.min(...predictions.map(p => p.congestion_ratio));

        // 找出最拥堵的时间段
        const mostCongestedHour = predictions.reduce((max, p) => 
            p.congestion_ratio > max.congestion_ratio ? p : max
        );

        return {
            avgCongestionRatio: Math.round(avgCongestion * 100) / 100,
            maxCongestionRatio: Math.round(maxCongestion * 100) / 100,
            minCongestionRatio: Math.round(minCongestion * 100) / 100,
            mostCongestedHour: mostCongestedHour.hour,
            recommendation: this.generateRecommendation(avgCongestion, maxCongestion)
        };
    }

    generateRecommendation(avgCongestion, maxCongestion) {
        if (maxCongestion >= 0.8) {
            return '建议避开高峰时段，选择替代路线或公共交通';
        } else if (avgCongestion >= 0.5) {
            return '建议预留额外出行时间，关注实时路况';
        } else {
            return '路况良好，适合正常出行';
        }
    }

    async getTrafficHistory(lng, lat, hours = 24) {
        try {
            const response = await fetch(
                `${this.apiBase}/api/traffic-history?lng=${lng}&lat=${lat}&hours=${hours}`
            );

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error('获取交通历史失败:', error);
            throw error;
        }
    }

    async getModelMetrics() {
        try {
            const response = await fetch(`${this.apiBase}/api/model-metrics`);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error('获取模型指标失败:', error);
            throw error;
        }
    }

    async getStatistics() {
        try {
            const response = await fetch(`${this.apiBase}/api/statistics`);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error('获取统计信息失败:', error);
            throw error;
        }
    }

    async trainModels(days = 30, forceRetrain = false) {
        try {
            const response = await fetch(`${this.apiBase}/api/train-models`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    days: days,
                    force_retrain: forceRetrain
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error('模型训练失败:', error);
            throw error;
        }
    }
}

// 全局实例
let enhancedMLService = null;
let wsManager = null;

// 初始化增强ML功能
async function initEnhancedML() {
    try {
        // 创建服务实例
        enhancedMLService = new EnhancedMLService(mlApiBase);
        
        // 检查服务可用性
        isEnhancedMLAvailable = await enhancedMLService.checkAvailability();
        
        if (isEnhancedMLAvailable) {
            console.log('增强ML服务已启用');
            
            // 建立WebSocket连接
            wsManager = new WebSocketManager(`ws://127.0.0.1:8003/ws`);
            wsManager.connect();
            
            // 设置事件回调
            if (window.onEnhancedMLReady) {
                window.onEnhancedMLReady();
            }
        } else {
            console.warn('增强ML服务不可用，使用基础功能');
            if (window.onEnhancedMLUnavailable) {
                window.onEnhancedMLUnavailable();
            }
        }
    } catch (error) {
        console.error('增强ML初始化失败:', error);
        isEnhancedMLAvailable = false;
    }
}

// 增强的预测函数
async function runEnhancedPrediction(lng, lat, horizon = 6) {
    if (!isEnhancedMLAvailable || !enhancedMLService) {
        console.warn('增强ML服务不可用，回退到基础预测');
        return runMLPredict(); // 使用原有的基础预测
    }

    try {
        showLoading('正在进行深度学习预测...');
        
        const result = await enhancedMLService.predictTraffic(lng, lat, horizon);
        
        if (result.success) {
            displayEnhancedPredictionResult(result);
            updatePredictionVisualization(result);
        } else {
            throw new Error(result.error || '预测失败');
        }
    } catch (error) {
        console.error('增强预测失败:', error);
        showError('预测失败: ' + error.message);
        
        // 回退到基础预测
        console.log('回退到基础预测...');
        return runMLPredict();
    } finally {
        hideLoading();
    }
}

// 显示增强预测结果
function displayEnhancedPredictionResult(result) {
    const panel = document.getElementById('opt-report');
    if (!panel) return;

    const { predictions, summary, modelType, modelVersion } = result;
    
    let html = `
        <div class="enhanced-prediction-header">
            <div class="model-info">
                <span class="badge success">深度学习预测</span>
                <span class="model-details">${modelType} v${modelVersion}</span>
            </div>
        </div>
    `;

    if (summary) {
        html += `
            <div class="prediction-summary">
                <div class="item"><span>平均拥堵比例</span><span class="badge">${(summary.avgCongestionRatio * 100).toFixed(1)}%</span></div>
                <div class="item"><span>最高拥堵比例</span><span class="badge">${(summary.maxCongestionRatio * 100).toFixed(1)}%</span></div>
                <div class="item"><span>最拥堵时段</span><span class="badge">${summary.mostCongestedHour}:00</span></div>
                <div class="item"><span>建议</span><span class="badge">${summary.recommendation}</span></div>
            </div>
        `;
    }

    html += '<div class="prediction-details"><div class="label">详细预测：</div>';
    
    predictions.forEach(pred => {
        const levelClass = `level-${pred.level}`;
        html += `
            <div class="prediction-item ${levelClass}">
                <span>${pred.hour}:00</span>
                <span class="badge">拥堵 ${(pred.congestionRatio * 100).toFixed(1)}%</span>
                <span class="badge">速度 ${pred.predictedSpeed.toFixed(1)}km/h</span>
                <span class="badge">置信度 ${(pred.confidenceScore * 100).toFixed(1)}%</span>
            </div>
        `;
    });
    
    html += '</div>';
    
    panel.innerHTML = html;
    panel.classList.remove('empty');
}

// 更新预测可视化
function updatePredictionVisualization(result) {
    // 创建预测图表
    const chartContainer = document.getElementById('prediction-chart');
    if (chartContainer) {
        createPredictionChart(result.predictions);
    }
    
    // 更新地图热力图
    if (map && result.predictions.length > 0) {
        const firstPrediction = result.predictions[0];
        drawEnhancedPredictionHeat(firstPrediction.congestionRatio);
    }
}

// 创建预测图表
function createPredictionChart(predictions) {
    const chartContainer = document.getElementById('prediction-chart');
    if (!chartContainer) return;

    const hours = predictions.map(p => p.hour);
    const congestionValues = predictions.map(p => p.congestionRatio * 100);
    const speedValues = predictions.map(p => p.predictedSpeed);

    const chartHtml = `
        <div class="prediction-chart">
            <h4>未来${predictions.length}小时预测趋势</h4>
            <div class="chart-container">
                <canvas id="prediction-canvas" width="400" height="200"></canvas>
            </div>
        </div>
    `;

    chartContainer.innerHTML = chartHtml;

    // 绘制简单图表
    setTimeout(() => {
        drawSimpleChart(hours, congestionValues, speedValues);
    }, 100);
}

// 绘制简单图表
function drawSimpleChart(hours, congestionValues, speedValues) {
    const canvas = document.getElementById('prediction-canvas');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;

    // 清空画布
    ctx.clearRect(0, 0, width, height);

    // 绘制网格
    ctx.strokeStyle = '#e0e0e0';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
        const y = (height / 4) * i;
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
    }

    // 绘制拥堵比例曲线
    ctx.strokeStyle = '#ff6b6b';
    ctx.lineWidth = 2;
    ctx.beginPath();
    
    const maxCongestion = Math.max(...congestionValues);
    const xStep = width / (hours.length - 1);
    
    hours.forEach((hour, i) => {
        const x = i * xStep;
        const y = height - (congestionValues[i] / maxCongestion) * height;
        
        if (i === 0) {
            ctx.moveTo(x, y);
        } else {
            ctx.lineTo(x, y);
        }
    });
    
    ctx.stroke();

    // 绘制数据点
    ctx.fillStyle = '#ff6b6b';
    hours.forEach((hour, i) => {
        const x = i * xStep;
        const y = height - (congestionValues[i] / maxCongestion) * height;
        
        ctx.beginPath();
        ctx.arc(x, y, 3, 0, 2 * Math.PI);
        ctx.fill();
        
        // 添加时间标签
        ctx.fillStyle = '#333';
        ctx.font = '10px Arial';
        ctx.textAlign = 'center';
        ctx.fillText(`${hour}:00`, x, height - 5);
    });
}

// 增强的热力图绘制
function drawEnhancedPredictionHeat(intensity) {
    const center = map.getCenter();
    const radiusKm = 3.0;
    const radiusM = Math.max(200, Math.min(5000, radiusKm * 1000));
    
    // 根据拥堵强度确定颜色
    let color, opacity;
    if (intensity >= 0.7) {
        color = '#ff4444';
        opacity = 0.6;
    } else if (intensity >= 0.4) {
        color = '#ff8800';
        opacity = 0.5;
    } else {
        color = '#00cc00';
        opacity = 0.4;
    }
    
    // 移除旧的预测覆盖物
    if (window.predictionAreaOverlay) {
        map.remove(window.predictionAreaOverlay);
    }
    
    // 创建新的预测覆盖物
    window.predictionAreaOverlay = new AMap.Circle({
        center: center,
        radius: radiusM,
        strokeColor: color,
        strokeWeight: 2,
        strokeOpacity: 0.8,
        fillColor: color,
        fillOpacity: opacity,
        zIndex: 50,
        extData: {
            type: 'prediction',
            intensity: intensity,
            timestamp: new Date().toISOString()
        }
    });
    
    map.add(window.predictionAreaOverlay);
    
    // 添加信息窗口
    const infoWindow = new AMap.InfoWindow({
        content: `
            <div class="prediction-info">
                <h4>深度学习预测结果</h4>
                <p>拥堵强度: ${(intensity * 100).toFixed(1)}%</p>
                <p>预测时间: ${new Date().toLocaleString()}</p>
            </div>
        `,
        offset: new AMap.Pixel(0, -20)
    });
    
    window.predictionAreaOverlay.on('click', () => {
        infoWindow.open(map, center);
    });
}

// 更新地图交通等级
function updateMapTrafficLevel(lng, lat, congestionRatio) {
    // 这里可以根据实时数据更新地图上的交通显示
    // 例如更新特定区域的颜色、添加标记等
    
    const level = getCongestionLevel(congestionRatio);
    const color = getCongestionColor(congestionRatio);
    
    console.log(`更新交通状态 - 位置: [${lng}, ${lat}], 拥堵等级: ${level}, 比例: ${(congestionRatio * 100).toFixed(1)}%`);
}

// 辅助函数
function showLoading(message = '加载中...') {
    const existingLoader = document.getElementById('enhanced-ml-loader');
    if (!existingLoader) {
        const loader = document.createElement('div');
        loader.id = 'enhanced-ml-loader';
        loader.className = 'enhanced-ml-loader';
        loader.innerHTML = `
            <div class="loader-content">
                <div class="spinner"></div>
                <div class="loader-message">${message}</div>
            </div>
        `;
        document.body.appendChild(loader);
    }
}

function hideLoading() {
    const loader = document.getElementById('enhanced-ml-loader');
    if (loader) {
        loader.remove();
    }
}

function showError(message) {
    alert('错误: ' + message);
}

// 导出全局函数
window.initEnhancedML = initEnhancedML;
window.runEnhancedPrediction = runEnhancedPrediction;
window.enhancedMLService = enhancedMLService;
window.wsManager = wsManager;
window.isEnhancedMLAvailable = () => isEnhancedMLAvailable;

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    // 延迟初始化，确保其他脚本已加载
    setTimeout(initEnhancedML, 1000);
});

// 添加CSS样式
const enhancedMLStyles = `
    .enhanced-ml-loader {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.7);
        display: flex;
        justify-content: center;
        align-items: center;
        z-index: 10000;
    }
    
    .loader-content {
        background: white;
        padding: 30px;
        border-radius: 10px;
        text-align: center;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
    }
    
    .spinner {
        width: 40px;
        height: 40px;
        border: 4px solid #f3f3f3;
        border-top: 4px solid #007bff;
        border-radius: 50%;
        animation: spin 1s linear infinite;
        margin: 0 auto 15px;
    }
    
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    
    .enhanced-prediction-header {
        margin-bottom: 15px;
        padding: 10px;
        background: #f8f9fa;
        border-radius: 5px;
    }
    
    .model-info {
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    
    .model-details {
        font-size: 0.9em;
        color: #666;
    }
    
    .prediction-summary {
        margin: 15px 0;
        padding: 15px;
        background: #e3f2fd;
        border-radius: 5px;
        border-left: 4px solid #2196f3;
    }
    
    .prediction-details {
        margin-top: 15px;
    }
    
    .prediction-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 12px;
        margin: 5px 0;
        border-radius: 4px;
        background: #f5f5f5;
    }
    
    .prediction-item.level-severe {
        background: #ffebee;
        border-left: 4px solid #f44336;
    }
    
    .prediction-item.level-moderate {
        background: #fff8e1;
        border-left: 4px solid #ff9800;
    }
    
    .prediction-item.level-light {
        background: #e8f5e8;
        border-left: 4px solid #4caf50;
    }
    
    .prediction-chart {
        margin: 20px 0;
        padding: 15px;
        background: white;
        border-radius: 5px;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
    }
    
    .chart-container {
        margin-top: 10px;
    }
    
    .prediction-info {
        padding: 10px;
        min-width: 200px;
    }
    
    .prediction-info h4 {
        margin: 0 0 10px 0;
        color: #333;
    }
    
    .prediction-info p {
        margin: 5px 0;
        color: #666;
    }
`;

// 动态添加样式
const styleSheet = document.createElement('style');
styleSheet.textContent = enhancedMLStyles;
document.head.appendChild(styleSheet);
