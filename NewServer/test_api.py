#!/usr/bin/env python3
"""
智能文书翻译平台 - API测试脚本
"""

import requests
import json
import time

# 配置
BASE_URL = "http://localhost:5000"
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "password123"

class APITester:
    def __init__(self, base_url):
        self.base_url = base_url
        self.token = None
        self.user_id = None
        self.client_id = None
        
    def print_result(self, test_name, response):
        """打印测试结果"""
        status = "✅" if response.status_code < 400 else "❌"
        print(f"{status} {test_name}")
        print(f"   状态码: {response.status_code}")
        
        try:
            data = response.json()
            if response.status_code < 400:
                print(f"   响应: {json.dumps(data, ensure_ascii=False, indent=2)}")
            else:
                print(f"   错误: {data.get('error', '未知错误')}")
        except:
            print(f"   响应: {response.text}")
        print()
        
        return response.status_code < 400
    
    def test_health(self):
        """测试健康检查"""
        print("🔍 测试健康检查接口")
        response = requests.get(f"{self.base_url}/health")
        return self.print_result("健康检查", response)
    
    def test_signup(self):
        """测试用户注册"""
        print("🔍 测试用户注册")
        data = {
            "name": "测试用户",
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        }
        response = requests.post(f"{self.base_url}/api/auth/signup", json=data)
        success = self.print_result("用户注册", response)
        
        if success:
            result = response.json()
            self.token = result.get('token')
            self.user_id = result.get('user', {}).get('uid')
        
        return success
    
    def test_signin(self):
        """测试用户登录"""
        print("🔍 测试用户登录")
        data = {
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        }
        response = requests.post(f"{self.base_url}/api/auth/signin", json=data)
        success = self.print_result("用户登录", response)
        
        if success:
            result = response.json()
            self.token = result.get('token')
            self.user_id = result.get('user', {}).get('uid')
            
        return success
    
    def test_get_user(self):
        """测试获取用户信息"""
        print("🔍 测试获取用户信息")
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.get(f"{self.base_url}/api/auth/user", headers=headers)
        return self.print_result("获取用户信息", response)
    
    def test_add_client(self):
        """测试添加客户"""
        print("🔍 测试添加客户")
        headers = {"Authorization": f"Bearer {self.token}"}
        data = {
            "name": "张先生",
            "caseType": "移民签证",
            "caseDate": "2024-01-15"
        }
        response = requests.post(f"{self.base_url}/api/clients", json=data, headers=headers)
        success = self.print_result("添加客户", response)
        
        if success:
            result = response.json()
            self.client_id = result.get('client', {}).get('cid')
            
        return success
    
    def test_get_clients(self):
        """测试获取客户列表"""
        print("🔍 测试获取客户列表")
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.get(f"{self.base_url}/api/clients", headers=headers)
        return self.print_result("获取客户列表", response)
    
    def test_get_materials(self):
        """测试获取材料列表"""
        print("🔍 测试获取材料列表")
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.get(f"{self.base_url}/api/clients/{self.client_id}/materials", headers=headers)
        return self.print_result("获取材料列表", response)
    
    def test_add_url_material(self):
        """测试添加网页材料"""
        print("🔍 测试添加网页材料")
        headers = {"Authorization": f"Bearer {self.token}"}
        data = {
            "urls": [
                "https://www.example.com",
                "https://www.baidu.com"
            ]
        }
        response = requests.post(f"{self.base_url}/api/clients/{self.client_id}/materials/urls", 
                               json=data, headers=headers)
        return self.print_result("添加网页材料", response)
    
    def test_logout(self):
        """测试用户登出"""
        print("🔍 测试用户登出")
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.post(f"{self.base_url}/api/auth/logout", headers=headers)
        return self.print_result("用户登出", response)
    
    def run_all_tests(self):
        """运行所有测试"""
        print("=" * 60)
        print("🧪 智能文书翻译平台 - API测试")
        print("=" * 60)
        
        # 基础功能测试
        if not self.test_health():
            print("❌ 服务器健康检查失败，请确认服务是否启动")
            return False
        
        # 认证流程测试
        if not self.test_signup():
            print("ℹ️ 注册失败，可能用户已存在，尝试登录...")
            if not self.test_signin():
                print("❌ 登录也失败，认证测试终止")
                return False
        
        if not self.token:
            print("❌ 未获取到Token，认证测试失败")
            return False
        
        print(f"✅ 认证成功，Token: {self.token[:20]}...")
        
        # 用户信息测试
        self.test_get_user()
        
        # 客户管理测试
        self.test_add_client()
        self.test_get_clients()
        
        # 材料管理测试
        if self.client_id:
            self.test_get_materials()
            self.test_add_url_material()
        
        # 登出测试
        self.test_logout()
        
        print("=" * 60)
        print("✅ API测试完成")
        print("=" * 60)
        
        return True

def main():
    """主函数"""
    tester = APITester(BASE_URL)
    
    try:
        tester.run_all_tests()
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到服务器，请确认服务是否在运行")
        print(f"💡 服务地址: {BASE_URL}")
        print("💡 启动命令: python app.py 或 python run_server.py")
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {str(e)}")

if __name__ == '__main__':
    main()