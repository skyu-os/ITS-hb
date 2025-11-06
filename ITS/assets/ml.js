// 智能交通预测功能模块
// HMAC-SHA256 签名工具
function signHMACSHA256(data, secret) {
  const encoder = new TextEncoder();
  const keyData = encoder.encode(secret);
  const messageData = encoder.encode(JSON.stringify(data));
  
  return crypto.subtle.importKey(
    'raw',
    keyData,
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  ).then(key => {
    return crypto.subtle.sign('HMAC', key, messageData);
  }).then(signature => {
    const hashArray = Array.from(new Uint8Array(signature));
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
  });
}

// 采集当前交通快照
function snapshotTrafficHistory() {
  // 简化版：从地图中心点获取当前交通状态
  const center = map.getCenter();
  const zoom = map.getZoom();
  const timestamp = new Date().toISOString();
  
  // 模拟交通数据（实际应从地图API获取）
  return {
    center: [center.lng, center.lat],
    zoom,
    timestamp,
    trafficLevel: Math.random() * 5, // 0-5 交通拥堵指数
    avgSpeed: 20 + Math.random() * 40, // 20-60 km/h
    congestionRatio: Math.random() * 0.8 // 0-0.8 拥堵比例
  };
}

// 渲染预测结果
function renderPredictResult(data) {
  const resultPanel = document.querySelector('#predict-result .predict-content');
  if (!resultPanel) return;
  
  resultPanel.classList.remove('empty');
  
  // 预测指标
  const metrics = data.metrics || {};
  const suggestions = data.suggestions || [];
  
  let html = '<div class="predict-metrics">';
  
  // 渲染三个核心指标
  if (metrics.congestionRatio !== undefined) {
    html += `<div class="predict-item">
      <div class="predict-label">拥堵比例</div>
      <div class="predict-value">${(metrics.congestionRatio * 100).toFixed(1)}%</div>
    </div>`;
  }
  
  if (metrics.avgSpeed !== undefined) {
    html += `<div class="predict-item">
      <div class="predict-label">平均速度</div>
      <div class="predict-value">${metrics.avgSpeed.toFixed(1)} km/h</div>
    </div>`;
  }
  
  if (metrics.travelTime !== undefined) {
    html += `<div class="predict-item">
      <div class="predict-label">预计行程时间</div>
      <div class="predict-value">${metrics.travelTime.toFixed(1)} 分钟</div>
    </div>`;
  }
  
  html += '</div>';
  
  // 渲染建议
  if (suggestions.length > 0) {
    html += '<div class="predict-suggestions"><h4>优化建议</h4><ul>';
    suggestions.forEach(s => {
      html += `<li>${s}</li>`;
    });
    html += '</ul></div>';
  }
  
  resultPanel.innerHTML = html;
}

// 调用预测API
async function callPredictAPI(data) {
  const API_BASE = window.ML_API_BASE || 'http://127.0.0.1:8003';
  const API_SECRET = window.ML_API_SECRET || 'demo-secret-key';
  
  // 获取选择的模型类型
  const modelSelect = document.getElementById('model-type');
  const modelType = modelSelect ? modelSelect.value : 'enhanced';
  
  // 添加时间戳和随机数防止重放攻击
  const payload = {
    ...data,
    model_type: modelType,
    timestamp: Date.now(),
    nonce: Math.random().toString(36).substring(2)
  };
  
  // 生成签名
  const signature = await signHMACSHA256(payload, API_SECRET);
  
  const response = await fetch(`${API_BASE}/api/predict`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Signature': signature
    },
    body: JSON.stringify(payload)
  });
  
  if (!response.ok) {
    throw new Error(`预测API调用失败: ${response.status} ${response.statusText}`);
  }
  
  return await response.json();
}

// 智能交通预测主函数
async function runMLPredict() {
  const btn = document.getElementById('btn-ml-predict');
  if (!btn) return;
  
  // 禁用按钮，显示加载状态
  const originalText = btn.textContent;
  btn.disabled = true;
  btn.textContent = '预测中...';
  
  try {
    // 采集当前交通快照
    const trafficData = snapshotTrafficHistory();
    
    // 调用预测API
    const result = await callPredictAPI(trafficData);
    
    // 渲染结果
    renderPredictResult(result);
    
    // 显示成功提示
    btn.textContent = '预测完成';
    setTimeout(() => {
      btn.textContent = originalText;
      btn.disabled = false;
    }, 2000);
  } catch (error) {
    console.error('预测失败:', error);
    
    // 显示错误提示
    btn.textContent = '预测失败';
    setTimeout(() => {
      btn.textContent = originalText;
      btn.disabled = false;
    }, 2000);
    
    // 在结果面板显示错误
    const resultPanel = document.querySelector('#predict-result .predict-content');
    if (resultPanel) {
      resultPanel.classList.remove('empty');
      resultPanel.innerHTML = `<div class="error">预测失败: ${error.message}</div>`;
    }
  }
}

// 暴露全局函数供app.js调用
window.runMLPredict = runMLPredict;