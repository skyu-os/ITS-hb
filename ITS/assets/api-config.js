// API配置 - 海外部署版本
const API_CONFIG = {
  // 开发环境配置
  development: {
    baseURL: 'http://localhost:8000',
    wsURL: 'ws://localhost:8000'
  },
  
  // 生产环境配置 - 部署到Railway
  production: {
    baseURL: 'https://its-traffic-api.up.railway.app', // Railway后端地址
    wsURL: 'wss://its-traffic-api.up.railway.app'
  },
  
  // 获取当前环境的API配置
  getCurrentConfig() {
    // 根据域名或环境变量判断当前环境
    if (typeof window !== 'undefined') {
      const hostname = window.location.hostname;
      
      // 如果是本地开发环境
      if (hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '0.0.0.0') {
        return this.development;
      }
      
      // 如果是Vercel部署的生产环境
      if (hostname.includes('vercel.app')) {
        return this.production;
      }
      
      // 如果是Netlify部署的生产环境
      if (hostname.includes('netlify.app')) {
        return this.production;
      }
    }
    
    // 默认返回生产配置
    return this.production;
  }
};

// 环境检测和API地址设置
function initAPIConfig() {
  const config = API_CONFIG.getCurrentConfig();
  window.API_BASE_URL = config.baseURL;
  window.WS_BASE_URL = config.wsURL;
  console.log('API配置已初始化:', config);
}

// 数据库配置
const DATABASE_CONFIG = {
  // 开发环境 (SQLite)
  development: {
    type: 'sqlite',
    path: './backend/traffic_data.db'
  },
  
  // 生产环境 (PostgreSQL)
  production: {
    type: 'postgresql',
    url: 'postgresql://user:password@localhost:5432/traffic_db'
  },
  
  getCurrentConfig() {
    const config = API_CONFIG.getCurrentConfig();
    if (config === API_CONFIG.development) {
      return this.development;
    } else {
      return this.production;
    }
  }
};

// 初始化配置
document.addEventListener('DOMContentLoaded', () => {
  initAPIConfig();
});

// 导出配置供其他模块使用
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { API_CONFIG, DATABASE_CONFIG };
}
