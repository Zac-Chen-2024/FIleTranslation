#!/usr/bin/env python3
"""
测试前端和后端连接的脚本
"""

import requests
import json

# 配置
BASE_URL = "http://localhost:5000"
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "password123"

def test_cors():
    """测试CORS配置"""
    print("🔍 测试CORS配置...")
    
    headers = {
        'Origin': 'http://localhost:3000',
        'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'Content-Type, Authorization'
    }
    
    try:
        response = requests.options(f"{BASE_URL}/api/auth/signin", headers=headers)
        print(f"   OPTIONS请求状态码: {response.status_code}")
        print(f"   CORS头: {dict(response.headers)}")
        
        if 'Access-Control-Allow-Origin' in response.headers:
            print("   ✅ CORS配置正常")
            return True
        else:
            print("   ❌ CORS配置有问题")
            return False
    except Exception as e:
        print(f"   ❌ CORS测试失败: {e}")
        return False

def test_auth_flow():
    """测试完整的认证流程"""
    print("\n🔍 测试认证流程...")
    
    # 测试登录
    login_data = {
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/auth/signin", json=login_data)
        print(f"   登录请求状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            token = result.get('token')
            user = result.get('user')
            
            print(f"   ✅ 登录成功")
            print(f"   用户: {user.get('name')} ({user.get('email')})")
            print(f"   Token: {token[:20]}...")
            
            # 测试获取用户信息
            headers = {"Authorization": f"Bearer {token}"}
            user_response = requests.get(f"{BASE_URL}/api/auth/user", headers=headers)
            
            if user_response.status_code == 200:
                print("   ✅ Token验证成功")
                return True
            else:
                print("   ❌ Token验证失败")
                return False
        else:
            print(f"   ❌ 登录失败: {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ 认证测试失败: {e}")
        return False

def test_api_endpoints():
    """测试主要API端点"""
    print("\n🔍 测试API端点...")
    
    endpoints = [
        ("/", "GET", "主页"),
        ("/health", "GET", "健康检查"),
        ("/api/test", "GET", "测试端点")
    ]
    
    all_passed = True
    
    for endpoint, method, name in endpoints:
        try:
            response = requests.get(f"{BASE_URL}{endpoint}")
            status = "✅" if response.status_code < 400 else "❌"
            print(f"   {status} {name}: {response.status_code}")
            
            if response.status_code >= 400:
                all_passed = False
                
        except Exception as e:
            print(f"   ❌ {name}: 连接失败 - {e}")
            all_passed = False
    
    return all_passed

def main():
    """主测试函数"""
    print("=" * 60)
    print("🧪 前端后端连接测试")
    print("=" * 60)
    print(f"后端地址: {BASE_URL}")
    print(f"前端地址: http://localhost:3000 (预期)")
    print()
    
    # 测试基础连接
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"✅ 后端连接正常: {response.status_code}")
    except Exception as e:
        print(f"❌ 后端连接失败: {e}")
        print("请确认后端服务是否启动 (python app.py)")
        return False
    
    # 运行各项测试
    cors_ok = test_cors()
    auth_ok = test_auth_flow()
    api_ok = test_api_endpoints()
    
    print("\n" + "=" * 60)
    print("📋 测试结果总结:")
    print(f"   CORS配置: {'✅ 正常' if cors_ok else '❌ 异常'}")
    print(f"   认证流程: {'✅ 正常' if auth_ok else '❌ 异常'}")
    print(f"   API端点: {'✅ 正常' if api_ok else '❌ 异常'}")
    
    if cors_ok and auth_ok and api_ok:
        print("\n🎉 所有测试通过！前端应该可以正常连接后端了。")
        print("\n📋 下一步:")
        print("1. 启动前端: cd react-frontend && npm start")
        print("2. 浏览器访问: http://localhost:3000")
        print("3. 使用测试账户登录: test@example.com / password123")
    else:
        print("\n⚠️ 部分测试失败，请检查配置")
    
    print("=" * 60)

if __name__ == '__main__':
    main()

