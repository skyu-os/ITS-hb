#!/bin/bash

# 部署验证测试脚本
# 测试海外部署的各项功能

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== ITS海外部署验证测试 ===${NC}"

# 测试配置
BACKEND_URL="https://its-traffic-api.up.railway.app"
FRONTEND_URL="https://its-traffic.vercel.app"

# 记录测试结果
TEST_RESULTS=()

# 测试函数
test_result() {
    local test_name="$1"
    local result="$2"
    if [ "$result" = "PASS" ]; then
        echo -e "${GREEN}✅ $test_name: 通过${NC}"
        TEST_RESULTS+=("✅ $test_name")
    else
        echo -e "${RED}❌ $test_name: 失败${NC}"
        TEST_RESULTS+=("❌ $test_name")
    fi
}

# 1. 检查项目结构
echo -e "\n${YELLOW}1. 检查项目结构...${NC}"

check_file() {
    if [ -f "$1" ]; then
        echo "✅ $1 存在"
        return 0
    else
        echo "❌ $1 缺失"
        return 1
    fi
}

# 检查关键文件
FILES_TO_CHECK=(
    "index.html"
    "vercel.json"
    "backend/Dockerfile"
    "backend/railway.json"
    "assets/api-config.js"
    "setup_database.sh"
    "DEPLOYMENT_GUIDE.md"
    "backend/requirements.txt"
    "backend/enhanced_server.py"
)

project_ok=true
for file in "${FILES_TO_CHECK[@]}"; do
    if ! check_file "$file"; then
        project_ok=false
    fi
done

if [ "$project_ok" = true ]; then
    test_result "项目结构检查" "PASS"
else
    test_result "项目结构检查" "FAIL"
fi

# 2. 验证配置文件
echo -e "\n${YELLOW}2. 验证配置文件...${NC}"

# 检查Vercel配置
if grep -q '"version": 2' vercel.json 2>/dev/null; then
    test_result "Vercel配置验证" "PASS"
else
    test_result "Vercel配置验证" "FAIL"
fi

# 检查API配置
if grep -q 'baseURL.*railway.app' assets/api-config.js 2>/dev/null; then
    test_result "API配置验证" "PASS"
else
    test_result "API配置验证" "FAIL"
fi

# 检查Railway配置
if grep -q '"builder": "NIXPACKS"' backend/railway.json 2>/dev/null; then
    test_result "Railway配置验证" "PASS"
else
    test_result "Railway配置验证" "FAIL"
fi

# 3. 网络连通性测试
echo -e "\n${YELLOW}3. 网络连通性测试...${NC}"

# 测试Vercel
if curl -s --head --request GET "$FRONTEND_URL" | grep "200 OK" > /dev/null 2>&1; then
    test_result "Vercel访问测试" "PASS"
else
    test_result "Vercel访问测试" "FAIL"
fi

# 测试Railway
if curl -s --head --request GET "$BACKEND_URL/health" | grep "200 OK" > /dev/null 2>&1; then
    test_result "Railway API访问测试" "PASS"
else
    test_result "Railway API访问测试" "FAIL"
fi

# 4. 高德API密钥测试
echo -e "\n${YELLOW}4. 高德API配置测试...${NC}"

# 检查index.html中的高德API配置
if grep -q "86df572bc935c2874d78a25289bab364" index.html 2>/dev/null; then
    test_result "高德API密钥配置" "PASS"
else
    test_result "高德API密钥配置" "FAIL"
fi

# 5. CORS配置测试
echo -e "\n${YELLOW}5. CORS配置测试...${NC}"

# 检查后端CORS配置
if grep -q "allow_origins.*\[" backend/enhanced_server.py 2>/dev/null; then
    test_result "后端CORS配置" "PASS"
else
    test_result "后端CORS配置" "FAIL"
fi

# 检查前端CORS配置
if grep -q "Access-Control-Allow-Origin" vercel.json 2>/dev/null; then
    test_result "前端CORS配置" "PASS"
else
    test_result "前端CORS配置" "FAIL"
fi

# 6. 数据库配置测试
echo -e "\n${YELLOW}6. 数据库配置测试...${NC}"

# 检查数据库配置文件
if [ -f "backend/database_production.py" ] || [ -f "backend/database_supabase.py" ]; then
    test_result "数据库配置文件" "PASS"
else
    test_result "数据库配置文件" "FAIL"
fi

# 检查环境变量文件
if [ -f "backend/.env.example" ]; then
    test_result "环境变量模板" "PASS"
else
    test_result "环境变量模板" "FAIL"
fi

# 7. 功能测试
echo -e "\n${YELLOW}7. 功能模块测试...${NC}"

# 检查前端功能
if grep -q "initMap\|initRouting" assets/app.js 2>/dev/null; then
    test_result "前端地图功能" "PASS"
else
    test_result "前端地图功能" "FAIL"
fi

# 检查后端API
if grep -q "@app.get.*health" backend/enhanced_server.py 2>/dev/null; then
    test_result "后端健康检查API" "PASS"
else
    test_result "后端健康检查API" "FAIL"
fi

# 检查WebSocket支持
if grep -q "WebSocket" backend/enhanced_server.py 2>/dev/null; then
    test_result "WebSocket支持" "PASS"
else
    test_result "WebSocket支持" "FAIL"
fi

# 8. 性能优化检查
echo -e "\n${YELLOW}8. 性能优化检查...${NC}"

# 检查静态资源优化
if grep -q "compression" vercel.json 2>/dev/null || grep -q "gzip" vercel.json 2>/dev/null; then
    test_result "静态资源优化" "PASS"
else
    test_result "静态资源优化" "FAIL"
fi

# 检查缓存配置
if grep -q "Cache-Control" vercel.json 2>/dev/null || [ -f "netlify.toml" ]; then
    test_result "缓存配置" "PASS"
else
    test_result "缓存配置" "FAIL"
fi

# 9. 安全性检查
echo -e "\n${YELLOW}9. 安全性检查...${NC}"

# 检查HTTPS配置
if grep -q "https://" assets/api-config.js 2>/dev/null; then
    test_result "HTTPS配置" "PASS"
else
    test_result "HTTPS配置" "FAIL"
fi

# 检查API密钥保护
if grep -q "API_SECRET" backend/enhanced_server.py 2>/dev/null; then
    test_result "API密钥保护" "PASS"
else
    test_result "API密钥保护" "FAIL"
fi

# 10. 文档完整性检查
echo -e "\n${YELLOW}10. 文档完整性检查...${NC}"

# 检查部署文档
if grep -q "部署步骤" DEPLOYMENT_GUIDE.md 2>/dev/null; then
    test_result "部署文档" "PASS"
else
    test_result "部署文档" "FAIL"
fi

# 检查故障排除文档
if grep -q "故障排除" DEPLOYMENT_GUIDE.md 2>/dev/null; then
    test_result "故障排除文档" "PASS"
else
    test_result "故障排除文档" "FAIL"
fi

# 生成测试报告
echo -e "\n${BLUE}=== 测试结果汇总 ===${NC}"
echo -e "${YELLOW}通过的测试:${NC}"
for result in "${TEST_RESULTS[@]}"; do
    if [[ $result == ✅* ]]; then
        echo -e "  $result"
    fi
done

echo -e "\n${YELLOW}失败的测试:${NC}"
failed_count=0
for result in "${TEST_RESULTS[@]}"; do
    if [[ $result == ❌* ]]; then
        echo -e "  $result"
        ((failed_count++))
    fi
done

total_tests=${#TEST_RESULTS[@]}
passed_tests=$((total_tests - failed_count))

echo -e "\n${BLUE}=== 总体评估 ===${NC}"
echo -e "总测试数: $total_tests"
echo -e "通过数: $passed_tests"
echo -e "失败数: $failed_count"

if [ $failed_count -eq 0 ]; then
    echo -e "\n${GREEN}🎉 所有测试通过！海外部署配置完成！${NC}"
    echo -e "${GREEN}✅ 项目已准备好部署到海外${NC}"
    echo -e "\n${YELLOW}下一步:${NC}"
    echo -e "1. 按照 DEPLOYMENT_GUIDE.md 进行部署"
    echo -e "2. 配置高德API密钥"
    echo -e "3. 设置环境变量"
    echo -e "4. 提交代码到GitHub并部署"
elif [ $failed_count -le 3 ]; then
    echo -e "\n${YELLOW}⚠️  大部分测试通过，有少量问题需要修复${NC}"
    echo -e "${YELLOW}请检查失败的测试项目并修复后再进行部署${NC}"
else
    echo -e "\n${RED}❌ 多个测试失败，请检查配置${NC}"
    echo -e "${RED}修复问题后重新运行此测试脚本${NC}"
fi

echo -e "\n${BLUE}=== 部署建议 ===${NC}"
echo -e "${YELLOW}免费部署平台推荐:${NC}"
echo -e "• 前端: https://vercel.com"
echo -e "• 后端: https://railway.app"
echo -e "• 数据库: https://supabase.com"
echo -e "\n${YELLOW}快速部署步骤:${NC}"
echo -e "1. git init && git add . && git commit -m 'Initial'"
echo -e "2. 推送到GitHub"
echo -e "3. 连接Vercel和Railway"
echo -e "4. 配置环境变量"
echo -e "5. 完成部署！"

exit 0
