#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
海外部署验证测试脚本
测试ITS智能交通系统的海外部署配置
"""

import os
import subprocess
import json
import re
from pathlib import Path

class DeploymentTester:
    def __init__(self):
        self.test_results = []
        self.project_root = Path(__file__).parent
        
    def print_header(self, title):
        print(f"\n{'='*50}")
        print(f"{title}")
        print(f"{'='*50}")
        
    def print_result(self, test_name, passed):
        if passed:
            print(f"✅ {test_name}: 通过")
            self.test_results.append(f"✅ {test_name}")
        else:
            print(f"❌ {test_name}: 失败")
            self.test_results.append(f"❌ {test_name}")
    
    def test_project_structure(self):
        """测试项目结构"""
        self.print_header("1. 项目结构检查")
        
        required_files = [
            "index.html",
            "vercel.json", 
            "backend/Dockerfile",
            "backend/railway.json",
            "assets/api-config.js",
            "setup_database.sh",
            "DEPLOYMENT_GUIDE.md",
            "backend/requirements.txt",
            "backend/enhanced_server.py"
        ]
        
        all_files_exist = True
        for file_path in required_files:
            full_path = self.project_root / file_path
            if full_path.exists():
                print(f"✅ {file_path} 存在")
            else:
                print(f"❌ {file_path} 缺失")
                all_files_exist = False
                
        self.print_result("项目结构检查", all_files_exist)
    
    def test_configuration_files(self):
        """测试配置文件"""
        self.print_header("2. 配置文件验证")
        
        # Vercel配置验证
        try:
            with open(self.project_root / "vercel.json", 'r', encoding='utf-8') as f:
                vercel_config = json.load(f)
                has_version = 'version' in vercel_config
                self.print_result("Vercel配置验证", has_version)
        except:
            self.print_result("Vercel配置验证", False)
        
        # API配置验证
        try:
            api_config_path = self.project_root / "assets" / "api-config.js"
            with open(api_config_path, 'r', encoding='utf-8') as f:
                content = f.read()
                has_railway = 'railway.app' in content
                self.print_result("API配置验证", has_railway)
        except:
            self.print_result("API配置验证", False)
        
        # Railway配置验证
        try:
            railway_config_path = self.project_root / "backend" / "railway.json"
            with open(railway_config_path, 'r', encoding='utf-8') as f:
                content = f.read()
                has_nixpacks = 'NIXPACKS' in content
                self.print_result("Railway配置验证", has_nixpacks)
        except:
            self.print_result("Railway配置验证", False)
    
    def test_amap_configuration(self):
        """测试高德API配置"""
        self.print_header("3. 高德API配置测试")
        
        # 检查index.html中的高德API配置
        try:
            index_path = self.project_root / "index.html"
            with open(index_path, 'r', encoding='utf-8') as f:
                content = f.read()
                has_api_key = '86df572bc935c2874d78a25289bab364' in content
                has_security_config = '_AMapSecurityConfig' in content
                has_js_api = 'webapi.amap.com' in content
                
                self.print_result("高德API密钥配置", has_api_key)
                self.print_result("高德安全配置", has_security_config)
                self.print_result("高德JS API加载", has_js_api)
        except Exception as e:
            print(f"❌ 高德配置检查失败: {e}")
            self.print_result("高德API密钥配置", False)
    
    def test_backend_configurations(self):
        """测试后端配置"""
        self.print_header("4. 后端配置测试")
        
        # 检查后端CORS配置
        try:
            server_path = self.project_root / "backend" / "enhanced_server.py"
            with open(server_path, 'r', encoding='utf-8') as f:
                content = f.read()
                has_cors = 'CORSMiddleware' in content
                has_health = '@app.get.*health' in content
                has_websocket = 'WebSocket' in content
                
                self.print_result("后端CORS配置", has_cors)
                self.print_result("健康检查API", has_health)
                self.print_result("WebSocket支持", has_websocket)
        except Exception as e:
            print(f"❌ 后端配置检查失败: {e}")
            self.print_result("后端CORS配置", False)
    
    def test_database_configurations(self):
        """测试数据库配置"""
        self.print_header("5. 数据库配置测试")
        
        # 检查数据库配置文件
        has_postgres = (self.project_root / "backend" / "database_production.py").exists()
        has_supabase = (self.project_root / "backend" / "database_supabase.py").exists()
        has_env_example = (self.project_root / "backend" / ".env.example").exists()
        
        self.print_result("PostgreSQL配置", has_postgres)
        self.print_result("Supabase配置", has_supabase)
        self.print_result("环境变量模板", has_env_example)
    
    def test_frontend_functionality(self):
        """测试前端功能"""
        self.print_header("6. 前端功能测试")
        
        try:
            app_path = self.project_root / "assets" / "app.js"
            with open(app_path, 'r', encoding='utf-8') as f:
                content = f.read()
                has_init_map = 'initMap' in content
                has_init_routing = 'initRouting' in content
                has_api_config = 'api-config.js' in content
                
                self.print_result("前端地图功能", has_init_map)
                self.print_result("前端路线规划", has_init_routing)
                self.print_result("API配置加载", has_api_config)
        except Exception as e:
            print(f"❌ 前端功能检查失败: {e}")
            self.print_result("前端地图功能", False)
    
    def test_security_configurations(self):
        """测试安全配置"""
        self.print_header("7. 安全配置测试")
        
        # 检查HTTPS配置
        try:
            api_config_path = self.project_root / "assets" / "api-config.js"
            with open(api_config_path, 'r', encoding='utf-8') as f:
                content = f.read()
                has_https = 'https://' in content
                self.print_result("HTTPS配置", has_https)
        except:
            self.print_result("HTTPS配置", False)
        
        # 检查API密钥保护
        try:
            server_path = self.project_root / "backend" / "enhanced_server.py"
            with open(server_path, 'r', encoding='utf-8') as f:
                content = f.read()
                has_api_secret = 'API_SECRET' in content
                self.print_result("API密钥保护", has_api_secret)
        except:
            self.print_result("API密钥保护", False)
    
    def test_documentation(self):
        """测试文档完整性"""
        self.print_header("8. 文档完整性测试")
        
        try:
            guide_path = self.project_root / "DEPLOYMENT_GUIDE.md"
            with open(guide_path, 'r', encoding='utf-8') as f:
                content = f.read()
                has_deploy_steps = '部署步骤' in content
                has_troubleshooting = '故障排除' in content
                has_cost_info = '成本' in content or '费用' in content
                
                self.print_result("部署文档", has_deploy_steps)
                self.print_result("故障排除文档", has_troubleshooting)
                self.print_result("成本说明", has_cost_info)
        except Exception as e:
            print(f"❌ 文档检查失败: {e}")
            self.print_result("部署文档", False)
    
    def test_deployment_readiness(self):
        """测试部署就绪性"""
        self.print_header("9. 部署就绪性测试")
        
        # 检查Git配置
        has_git = (self.project_root / ".git").exists()
        has_gitignore = (self.project_root / ".gitignore").exists()
        
        self.print_result("Git配置", has_git)
        self.print_result("Git忽略文件", has_gitignore)
    
    def generate_report(self):
        """生成测试报告"""
        self.print_header("测试结果汇总")
        
        # 统计结果
        passed_tests = [t for t in self.test_results if t.startswith("✅")]
        failed_tests = [t for t in self.test_results if t.startswith("❌")]
        
        print(f"\n通过的测试 ({len(passed_tests)}个):")
        for test in passed_tests:
            print(f"  {test}")
        
        if failed_tests:
            print(f"\n失败的测试 ({len(failed_tests)}个):")
            for test in failed_tests:
                print(f"  {test}")
        
        # 总体评估
        total_tests = len(self.test_results)
        passed_count = len(passed_tests)
        failed_count = len(failed_tests)
        
        print(f"\n总体评估:")
        print(f"总测试数: {total_tests}")
        print(f"通过数: {passed_count}")
        print(f"失败数: {failed_count}")
        
        if failed_count == 0:
            print(f"\n🎉 所有测试通过！海外部署配置完成！")
            print(f"✅ 项目已准备好部署到海外")
            print(f"\n下一步:")
            print(f"1. 按照 DEPLOYMENT_GUIDE.md 进行部署")
            print(f"2. 配置高德API密钥")
            print(f"3. 设置环境变量")
            print(f"4. 提交代码到GitHub并部署")
        elif failed_count <= 3:
            print(f"\n⚠️ 大部分测试通过，有少量问题需要修复")
            print(f"请检查失败的测试项目并修复后再进行部署")
        else:
            print(f"\n❌ 多个测试失败，请检查配置")
            print(f"修复问题后重新运行此测试脚本")
        
        # 部署建议
        print(f"\n部署建议:")
        print(f"免费部署平台推荐:")
        print(f"• 前端: https://vercel.com")
        print(f"• 后端: https://railway.app") 
        print(f"• 数据库: https://supabase.com")
        print(f"\n快速部署步骤:")
        print(f"1. git init && git add . && git commit -m 'Initial'")
        print(f"2. 推送到GitHub")
        print(f"3. 连接Vercel和Railway")
        print(f"4. 配置环境变量")
        print(f"5. 完成部署！")
    
    def run_all_tests(self):
        """运行所有测试"""
        print("=== ITS海外部署验证测试 ===")
        
        self.test_project_structure()
        self.test_configuration_files()
        self.test_amap_configuration()
        self.test_backend_configurations()
        self.test_database_configurations()
        self.test_frontend_functionality()
        self.test_security_configurations()
        self.test_documentation()
        self.test_deployment_readiness()
        
        self.generate_report()

if __name__ == "__main__":
    tester = DeploymentTester()
    tester.run_all_tests()
