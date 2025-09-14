from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os
import time
import base64
import re
import json
import math
import asyncio
import subprocess
import argparse
import sys
from datetime import datetime
from pathlib import Path
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

# 浏览器和翻译相关
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException, TimeoutException
from openai import OpenAI

# PDF生成相关
try:
    from pyppeteer import launch
    from PIL import Image
    PYPPETEER_AVAILABLE = True
except ImportError:
    PYPPETEER_AVAILABLE = False
    print("⚠️ 警告: pyppeteer 或 PIL 未安装，部分PDF生成功能可能不可用")

app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 禁用Flask的自动URL重定向
app.url_map.strict_slashes = False

# 添加请求日志中间件
@app.before_request
def log_request_info():
    if request.path.startswith('/preview/'):
        print(f"🔍 预览请求: {request.method} {request.path}")
        print(f"  - 完整URL: {request.url}")
        print(f"  - Headers: {dict(request.headers)}")

# 创建必要的文件夹
os.makedirs('downloads', exist_ok=True)
os.makedirs('original_snapshot', exist_ok=True)
os.makedirs('translated_snapshot', exist_ok=True)
os.makedirs('poster_output', exist_ok=True)
os.makedirs('web_translation_output', exist_ok=True)
os.makedirs('uploads', exist_ok=True)
os.makedirs('image_translation_output', exist_ok=True)  # 新增：图片翻译输出目录

# ========== 原有的Google翻译功能 ==========

def sanitize_title(title):
    """对网页标题进行简单清洗，去掉非法字符并限制长度。"""
    title = title.strip().replace('\n', ' ')
    title = re.sub(r'[\\/*?:"<>|]', '_', title)
    return title[:50]

def print_to_pdf(driver, pdf_path, paper_width=8.27, paper_height=11.7, margins=None, scale=0.9):
    """调用 Chrome DevTools Protocol 的 Page.printToPDF 命令"""
    if margins is None:
        margins = {"top": 0.4, "bottom": 0.4, "left": 0.4, "right": 0.4}
    
    print_options = {
        "paperWidth": paper_width,
        "paperHeight": paper_height,
        "marginTop": margins.get("top", 0.4),
        "marginBottom": margins.get("bottom", 0.4),
        "marginLeft": margins.get("left", 0.4),
        "marginRight": margins.get("right", 0.4),
        "printBackground": True,
        "scale": scale,  # 90% 缩放比例
        "preferCSSPageSize": False
    }
    result = driver.execute_cdp_cmd("Page.printToPDF", print_options)
    pdf_data = base64.b64decode(result['data'])
    with open(pdf_path, "wb") as f:
        f.write(pdf_data)
    print(f"已保存 PDF: {pdf_path}")

def setup_chrome(disable_js=False):
    """创建 Chrome WebDriver 实例"""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--window-size=1280,800")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-setuid-sandbox")
    if disable_js:
        prefs = {"profile.managed_default_content_settings.javascript": 2}
        options.add_experimental_option("prefs", prefs)
    driver = webdriver.Chrome(options=options)
    return driver

def hide_google_translate_toolbar(driver):
    """移除 Google Translate 顶部工具栏"""
    try:
        driver.execute_script("var nv = document.getElementById('gt-nvframe'); if(nv){ nv.remove(); }")
        driver.execute_script("""
            var css = document.createElement("style");
            css.type = "text/css";
            css.innerHTML = `
                .goog-te-gadget, .goog-te-gadget-simple, #goog-gt-tt { display: none !important; }
            `;
            document.head.appendChild(css);
        """)
        print("已移除 Google Translate 顶部工具栏。")
    except Exception as e:
        print(f"移除顶部工具栏时出错：{e}")

def capture_translated_pdf_for_api(url, base_dir, wait_time=5):
    """使用 Google Translate 强制将页面翻译成英文"""
    try:
        driver = setup_chrome(disable_js=False)
        translate_url = f"https://translate.google.com/translate?hl=en&sl=zh-CN&u={url}&prev=search"
        driver.get(translate_url)
        time.sleep(wait_time)
        hide_google_translate_toolbar(driver)
        time.sleep(1)
        title = sanitize_title(driver.title)
        out_folder = os.path.join(base_dir, "translated_snapshot")
        os.makedirs(out_folder, exist_ok=True)
        pdf_path = os.path.join(out_folder, f"{title}.pdf")
        small_margins = {"top": 0.05, "bottom": 0.05, "left": 0.05, "right": 0.05}
        print_to_pdf(driver, pdf_path, margins=small_margins, scale=0.7)
        driver.quit()
        
        return pdf_path, f"{title}.pdf"
    except Exception as e:
        if 'driver' in locals():
            driver.quit()
        raise e

# ========== 海报翻译类（增强版）==========

class PosterTranslator:
    """海报翻译类，处理从图像到PDF的完整流程（增强版）"""
    
    def __init__(self, api_key=None, pdflatex_path=None):
        """
        初始化海报翻译器
        
        Args:
            api_key (str): OpenAI API密钥
            pdflatex_path (str): pdflatex.exe的路径，如果为None则使用默认路径
        """
        # 配置API密钥
        self.api_key = api_key or self._load_api_key()
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key)
            self.log("✅ OpenAI API密钥已配置", "SUCCESS")
        else:
            self.client = None
            self.log("⚠️ OpenAI API密钥未设置", "WARNING")
        
        # 智能检测pdflatex路径
        self.pdflatex_path = self._detect_pdflatex_path(pdflatex_path)
        
        # 定义海报转LaTeX的详细提示词
        self.custom_prompt = """
Upload a poster image and generate "directly compilable LaTeX code" that faithfully reproduces the layout of the poster, including all poster information. The requirements are as follows:

Layout Reproduction:
Analyze each image individually and accurately reproduce its geometric layout and content distribution. Do not omit any poster information. For guest photos, preserve the original geometric structure (e.g., horizontal row, triangular layout, etc.) by using rectangular boxes as placeholders with the word "Photo" centered inside. Ensure that each photo placeholder is immediately followed by the corresponding guest's name and title (and any additional provided information) in a clearly arranged manner. Arrange these photo blocks in a visually balanced way, ensuring minimal but sufficient spacing.

Text and Typography:
Translate all content into English, including the title, event time, agenda table, guest information, and placeholder descriptions. The title's font size should be slightly larger than the body text to maintain visual hierarchy (use \large or \Large, but not \huge or \Huge). Keep the overall layout compact by avoiding excessive vertical skips. Bold guest names and titles moderately. The body text and agenda table must remain clear and easy to read.

Complete Page Layout:
Ensure that all content fits within the page boundaries without overflowing. Keep margins and line spacing balanced so that the final design is neither too cramped nor too sparse. Avoid large empty spaces and big gaps between sections. Ensure the poster retains a single-page layout if possible.

Image and Text Alignment:
Ensure that guest photos and their corresponding names/titles are strictly aligned. Even if some guest descriptions are longer, maintain a neat and well-aligned overall appearance.

Table Formatting:
Use reasonable column widths and clear lines for the agenda table. To avoid odd line breaks, you can use packages such as tabularx or array if needed. All table content must be in English, with accurate times and topics. Avoid splitting rows across lines and ensure consistent horizontal and vertical alignment.

Additional Table Formatting Precautions:
When formatting tables, ensure that multi-line content within any table cell is enclosed in braces (e.g., { ... }) or placed inside a minipage. This prevents the line break command (\\) used within a cell from being mistaken as the end of a row, avoiding extra alignment tab errors.

Placeholder Consistency:
Use rectangular boxes for guest photos, with the word "Photo" centered inside, and if a QR code is present, use a rectangular box labeled "QR Code" centered inside. Absolutely do not use "Image" or any other text label for these placeholders. Each placeholder must read "Photo" to indicate a person's picture. Keep placeholders sized appropriately so they align well with the text.

Strict No-External-Files Policy:
The generated LaTeX code must be 100% self-contained. It must NOT under any circumstances reference external files.
- Absolutely forbid the use of the \includegraphics command.
- All visual elements, including placeholders for photos and QR codes, must be drawn using native LaTeX commands.
- For a photo placeholder, you MUST use a `\\fbox` or `\\framebox` containing the word "Photo". For example: `\\fbox{\parbox[c][1.5cm][c]{2.5cm}{\centering Photo}}`. Do not use any other method.
- The final output must compile without needing any external image files like .jpg, .png, etc. The entire PDF must be generated from this single .tex file alone.

Special Character Escaping:
Ensure that all special characters, especially the ampersand (&) within any text, are properly escaped (for example, replace any "&" with "\&") so that the generated LaTeX code compiles without errors.

Style Restrictions:
Do not use any color commands (such as \\textcolor, \color, or \\usepackage{xcolor}) in the generated LaTeX code. Additionally, do not use the commands \huge or \Huge anywhere in the code; if emphasis is needed, only use \large or \Large. This is to ensure the layout remains compact, elegant, and adheres strictly to the design guidelines.

Only return the raw LaTeX code. Do not enclose it in triple backticks, markdown, or any additional formatting. The output should start with \documentclass and end with \end{document} exactly, with no extra characters or quotes.

Output Requirement:
Output complete LaTeX source code that the user can compile directly without any modifications. The layout must be compact and aesthetically pleasing, while also exuding a sense of grandeur and elegance. Ensure refined margins, minimal whitespace, and balanced spacing so that the final design is both tight and visually imposing.
"""

    def _detect_pdflatex_path(self, custom_path=None):
        """智能检测pdflatex路径"""
        self.log("正在检测pdflatex路径...", "DEBUG")
        
        # 如果提供了自定义路径，先尝试
        if custom_path and os.path.exists(custom_path):
            self.log(f"使用自定义pdflatex路径: {custom_path}", "SUCCESS")
            return custom_path
        
        # 常见的MiKTeX安装路径（Windows）
        common_paths = [
            r"F:\tex\miktex\bin\x64\pdflatex.exe",  # 原始路径
            r"C:\Program Files\MiKTeX\miktex\bin\x64\pdflatex.exe",
            r"C:\Users\{}\AppData\Local\Programs\MiKTeX\miktex\bin\x64\pdflatex.exe".format(os.getenv('USERNAME', '')),
            r"C:\Program Files (x86)\MiKTeX\miktex\bin\pdflatex.exe",
            r"D:\MiKTeX\miktex\bin\x64\pdflatex.exe",
            r"E:\MiKTeX\miktex\bin\x64\pdflatex.exe"
        ]
        
        # 检查常见路径
        for path in common_paths:
            if os.path.exists(path):
                self.log(f"找到pdflatex: {path}", "SUCCESS")
                return path
        
        # 检查系统PATH
        try:
            result = subprocess.run(["pdflatex", "--version"], 
                                 check=True, capture_output=True, text=True, timeout=10)
            self.log("在系统PATH中找到pdflatex", "SUCCESS")
            return "pdflatex"
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        # 如果都找不到，返回默认路径并记录警告
        default_path = r"F:\tex\miktex\bin\x64\pdflatex.exe"
        self.log(f"未找到pdflatex，使用默认路径: {default_path}", "WARNING")
        return default_path

    def log(self, message, level="INFO"):
        """详细状态日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = {
            "INFO": "ℹ️",
            "SUCCESS": "✅", 
            "WARNING": "⚠️",
            "ERROR": "❌",
            "DEBUG": "🔍"
        }
        print(f"[{timestamp}] {prefix.get(level, 'ℹ️')} {message}")

    def _load_api_key(self):
        """从环境变量或配置文件加载API密钥"""
        self.log("正在查找OpenAI API密钥...", "DEBUG")
        
        # 尝试从环境变量获取
        api_key = os.getenv('OPENAI_API_KEY')
        if api_key:
            self.log("从环境变量获取API密钥", "DEBUG")
            return api_key
        
        # 尝试从配置文件获取
        # config_files = ['api_key.txt', 'openai_key.txt', 'config.json']
        config_files = ['config/openai_api_key.txt', 'api_key.txt', 'openai_key.txt', 'config.json']
        for config_file in config_files:
            if os.path.exists(config_file):
                try:
                    self.log(f"尝试从 {config_file} 读取API密钥", "DEBUG")
                    with open(config_file, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        if config_file.endswith('.json'):
                            data = json.loads(content)
                            return data.get('openai_api_key') or data.get('api_key')
                        else:
                            return content
                except Exception as e:
                    self.log(f"读取配置文件 {config_file} 失败: {e}", "WARNING")
        
        self.log("未找到API密钥配置", "WARNING")
        return None

    def check_requirements(self):
        """详细检查运行环境和要求"""
        self.log("🔍 开始详细环境检查...", "INFO")
        
        check_results = {
            "api_key": {"status": False, "details": [], "solutions": []},
            "pdflatex": {"status": False, "details": [], "solutions": []},
            "python_modules": {"status": False, "details": [], "solutions": []},
            "file_permissions": {"status": False, "details": [], "solutions": []}
        }
        
        # 1. 详细检查API密钥
        self.log("步骤1: 检查OpenAI API密钥配置", "DEBUG")
        api_check = self._check_api_key_detailed()
        check_results["api_key"] = api_check
        
        # 2. 详细检查pdflatex
        self.log("步骤2: 检查LaTeX环境", "DEBUG")
        latex_check = self._check_pdflatex_detailed()
        check_results["pdflatex"] = latex_check
        
        # 3. 检查Python模块
        self.log("步骤3: 检查Python模块依赖", "DEBUG")
        modules_check = self._check_python_modules()
        check_results["python_modules"] = modules_check
        
        # 4. 检查文件权限
        self.log("步骤4: 检查文件系统权限", "DEBUG")
        permissions_check = self._check_file_permissions()
        check_results["file_permissions"] = permissions_check
        
        # 汇总检查结果
        all_passed = all(result["status"] for result in check_results.values())
        
        if all_passed:
            self.log("🎉 所有环境检查通过!", "SUCCESS")
            return True
        else:
            self._generate_detailed_error_report(check_results)
            return False

    def _check_api_key_detailed(self):
        """详细检查API密钥配置"""
        result = {"status": False, "details": [], "solutions": []}
        
        # 检查环境变量
        env_key = os.getenv('OPENAI_API_KEY')
        if env_key:
            result["details"].append("✅ 环境变量 OPENAI_API_KEY 存在")
            if len(env_key.strip()) > 0:
                result["details"].append(f"✅ 密钥长度: {len(env_key)} 字符")
                if env_key.startswith('sk-'):
                    result["details"].append("✅ 密钥格式正确 (以sk-开头)")
                    result["status"] = True
                else:
                    result["details"].append("⚠️ 密钥格式可能有误 (不以sk-开头)")
                    result["solutions"].append("检查密钥是否为有效的OpenAI API密钥")
            else:
                result["details"].append("❌ 环境变量为空")
                result["solutions"].append("设置有效的OPENAI_API_KEY环境变量")
        else:
            result["details"].append("❌ 环境变量 OPENAI_API_KEY 未设置")
        
        # 检查配置文件
        config_files = [
            'config/openai_api_key.txt',
            'api_key.txt', 
            'openai_key.txt', 
            'config.json'
        ]
        
        found_config = False
        for config_file in config_files:
            if os.path.exists(config_file):
                found_config = True
                result["details"].append(f"✅ 找到配置文件: {config_file}")
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        if config_file.endswith('.json'):
                            data = json.loads(content)
                            key = data.get('openai_api_key') or data.get('api_key')
                            if key:
                                result["details"].append("✅ JSON配置文件包含API密钥")
                                if not result["status"] and key.startswith('sk-'):
                                    result["status"] = True
                            else:
                                result["details"].append("❌ JSON配置文件缺少API密钥字段")
                        else:
                            if content and content.startswith('sk-'):
                                result["details"].append("✅ 配置文件包含有效格式的API密钥")
                                if not result["status"]:
                                    result["status"] = True
                            else:
                                result["details"].append("❌ 配置文件密钥格式无效")
                except Exception as e:
                    result["details"].append(f"❌ 读取配置文件失败: {e}")
                    result["solutions"].append(f"检查文件 {config_file} 的权限和格式")
                break
        
        if not found_config and not env_key:
            result["details"].append("❌ 未找到任何API密钥配置")
            result["solutions"].extend([
                "方案1: 设置环境变量 OPENAI_API_KEY",
                "方案2: 创建 config/openai_api_key.txt 文件并写入密钥",
                "方案3: 创建 api_key.txt 文件并写入密钥",
                "请访问 https://platform.openai.com/account/api-keys 获取API密钥"
            ])
        
        return result

    def _check_pdflatex_detailed(self):
        """详细检查pdflatex环境"""
        result = {"status": False, "details": [], "solutions": []}
        
        # 检查配置的路径
        if self.pdflatex_path != "pdflatex":
            result["details"].append(f"🔍 检查配置路径: {self.pdflatex_path}")
            if os.path.exists(self.pdflatex_path):
                result["details"].append("✅ 配置路径存在")
                # 检查文件权限
                if os.access(self.pdflatex_path, os.X_OK):
                    result["details"].append("✅ 文件具有执行权限")
                    try:
                        # 测试执行
                        proc = subprocess.run([self.pdflatex_path, "--version"], 
                                            capture_output=True, text=True, timeout=10)
                        if proc.returncode == 0:
                            version_info = proc.stdout.split('\n')[0] if proc.stdout else "未知版本"
                            result["details"].append(f"✅ pdflatex版本: {version_info}")
                            result["status"] = True
                        else:
                            result["details"].append(f"❌ pdflatex执行失败: {proc.stderr}")
                            result["solutions"].append("检查pdflatex安装是否完整")
                    except subprocess.TimeoutExpired:
                        result["details"].append("❌ pdflatex执行超时")
                        result["solutions"].append("检查pdflatex是否响应")
                    except Exception as e:
                        result["details"].append(f"❌ pdflatex执行异常: {e}")
                else:
                    result["details"].append("❌ 文件没有执行权限")
                    result["solutions"].append(f"授予执行权限: chmod +x {self.pdflatex_path}")
            else:
                result["details"].append("❌ 配置路径不存在")
                result["solutions"].append("检查路径是否正确或重新安装LaTeX")
        
        # 检查系统PATH
        result["details"].append("🔍 检查系统PATH中的pdflatex")
        try:
            proc = subprocess.run(["pdflatex", "--version"], 
                                capture_output=True, text=True, timeout=10)
            if proc.returncode == 0:
                result["details"].append("✅ 系统PATH中找到pdflatex")
                version_info = proc.stdout.split('\n')[0] if proc.stdout else "未知版本"
                result["details"].append(f"✅ 系统pdflatex版本: {version_info}")
                if not result["status"]:
                    result["status"] = True
            else:
                result["details"].append("❌ 系统PATH中pdflatex执行失败")
        except subprocess.TimeoutExpired:
            result["details"].append("❌ 系统pdflatex执行超时")
        except FileNotFoundError:
            result["details"].append("❌ 系统PATH中未找到pdflatex")
        except Exception as e:
            result["details"].append(f"❌ 系统pdflatex检查异常: {e}")
        
        # 检查常见的LaTeX发行版
        common_latex_paths = [
            "C:\\Program Files\\MiKTeX\\miktex\\bin\\x64\\pdflatex.exe",
            "C:\\Users\\{username}\\AppData\\Local\\Programs\\MiKTeX\\miktex\\bin\\x64\\pdflatex.exe",
            "/usr/bin/pdflatex",
            "/usr/local/bin/pdflatex",
            "/Library/TeX/texbin/pdflatex"
        ]
        
        username = os.getenv('USERNAME', os.getenv('USER', ''))
        result["details"].append("🔍 检查常见LaTeX安装位置")
        found_latex = False
        
        for path_template in common_latex_paths:
            path = path_template.replace('{username}', username)
            if os.path.exists(path):
                result["details"].append(f"✅ 找到LaTeX安装: {path}")
                found_latex = True
                if not result["status"]:
                    # 更新配置建议
                    result["solutions"].append(f"可以手动设置路径: {path}")
                break
        
        if not found_latex:
            result["details"].append("❌ 未找到常见的LaTeX安装")
        
        # 添加安装建议
        if not result["status"]:
            result["solutions"].extend([
                "安装建议:",
                "Windows: 下载并安装 MiKTeX (https://miktex.org/download)",
                "macOS: 安装 MacTeX (https://www.tug.org/mactex/)",
                "Linux: sudo apt-get install texlive-latex-base",
                "安装后重启命令行或IDE",
                "确保LaTeX程序添加到系统PATH"
            ])
        
        return result

    def _check_python_modules(self):
        """检查Python模块依赖"""
        result = {"status": True, "details": [], "solutions": []}
        
        required_modules = [
            ('openai', 'OpenAI API客户端'),
            ('PIL', 'Python图像处理库'),
            ('pathlib', 'Python路径处理'),
            ('base64', 'Base64编码'),
            ('json', 'JSON处理'),
            ('subprocess', '子进程管理'),
            ('os', '操作系统接口')
        ]
        
        missing_modules = []
        for module_name, description in required_modules:
            try:
                __import__(module_name)
                result["details"].append(f"✅ {module_name}: {description}")
            except ImportError:
                result["details"].append(f"❌ {module_name}: {description} - 缺失")
                missing_modules.append(module_name)
        
        if missing_modules:
            result["status"] = False
            result["solutions"].append(f"安装缺失的模块: pip install {' '.join(missing_modules)}")
        
        return result

    def _check_file_permissions(self):
        """检查文件系统权限"""
        result = {"status": True, "details": [], "solutions": []}
        
        # 检查输出目录权限
        output_dirs = ['poster_output', 'uploads', 'downloads']
        
        for dir_name in output_dirs:
            try:
                os.makedirs(dir_name, exist_ok=True)
                # 测试写入权限
                test_file = os.path.join(dir_name, 'test_permission.tmp')
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
                result["details"].append(f"✅ {dir_name}: 读写权限正常")
            except PermissionError:
                result["details"].append(f"❌ {dir_name}: 权限不足")
                result["status"] = False
                result["solutions"].append(f"授予目录写入权限: {dir_name}")
            except Exception as e:
                result["details"].append(f"❌ {dir_name}: 检查失败 - {e}")
                result["status"] = False
        
        return result

    def _generate_detailed_error_report(self, check_results):
        """生成详细的错误报告"""
        self.log("=" * 60, "ERROR")
        self.log("🚨 环境检查失败 - 详细报告", "ERROR")
        self.log("=" * 60, "ERROR")
        
        for category, result in check_results.items():
            status_icon = "✅" if result["status"] else "❌"
            category_name = {
                "api_key": "OpenAI API密钥",
                "pdflatex": "LaTeX环境",
                "python_modules": "Python模块",
                "file_permissions": "文件权限"
            }.get(category, category)
            
            self.log(f"\n{status_icon} {category_name}:", "ERROR" if not result["status"] else "SUCCESS")
            
            for detail in result["details"]:
                print(f"   {detail}")
            
            if result["solutions"] and not result["status"]:
                self.log("   💡 解决方案:", "WARNING")
                for i, solution in enumerate(result["solutions"], 1):
                    print(f"      {i}. {solution}")
        
        self.log("\n" + "=" * 60, "ERROR")
        self.log("请解决上述问题后重试", "ERROR")
        self.log("=" * 60, "ERROR")

    def check_requirements_with_details(self):
        """检查环境并返回详细结果（用于API响应）"""
        self.log("🔍 开始详细环境检查...", "INFO")
        
        check_results = {
            "api_key": {"status": False, "details": [], "solutions": []},
            "pdflatex": {"status": False, "details": [], "solutions": []},
            "python_modules": {"status": False, "details": [], "solutions": []},
            "file_permissions": {"status": False, "details": [], "solutions": []}
        }
        
        # 执行各项检查
        check_results["api_key"] = self._check_api_key_detailed()
        check_results["pdflatex"] = self._check_pdflatex_detailed()
        check_results["python_modules"] = self._check_python_modules()
        check_results["file_permissions"] = self._check_file_permissions()
        
        # 汇总结果
        all_passed = all(result["status"] for result in check_results.values())
        
        if all_passed:
            self.log("🎉 所有环境检查通过!", "SUCCESS")
            return {
                'success': True,
                'message': '环境检查通过'
            }
        else:
            # 生成详细报告
            self._generate_detailed_error_report(check_results)
            
            # 准备API响应数据
            error_summary = []
            all_details = {}
            all_solutions = []
            
            for category, result in check_results.items():
                category_name = {
                    "api_key": "OpenAI API密钥",
                    "pdflatex": "LaTeX环境", 
                    "python_modules": "Python模块",
                    "file_permissions": "文件权限"
                }.get(category, category)
                
                if not result["status"]:
                    error_summary.append(f"❌ {category_name}: 检查失败")
                    all_details[category_name] = {
                        'details': result["details"],
                        'solutions': result["solutions"]
                    }
                    all_solutions.extend(result["solutions"])
                else:
                    error_summary.append(f"✅ {category_name}: 正常")
            
            return {
                'success': False,
                'error_summary': '; '.join(error_summary),
                'details': all_details,
                'solutions': all_solutions
            }

    def validate_image_file(self, image_path):
        """验证图像文件"""
        self.log(f"验证图像文件: {image_path}", "DEBUG")
        
        if not os.path.exists(image_path):
            self.log(f"文件不存在: {image_path}", "ERROR")
            return False
        
        if not os.path.isfile(image_path):
            self.log(f"不是文件: {image_path}", "ERROR")
            return False
        
        file_size = os.path.getsize(image_path)
        if file_size == 0:
            self.log(f"文件大小为0: {image_path}", "ERROR")
            return False
        
        self.log(f"文件验证通过，大小: {file_size} bytes", "SUCCESS")
        return True

    def encode_image_to_base64(self, image_path):
        """
        将图像文件编码为base64格式
        
        Args:
            image_path (str): 图像文件路径
            
        Returns:
            str: base64编码的图像数据
        """
        try:
            self.log(f"编码图像文件: {image_path}", "DEBUG")
            
            if not self.validate_image_file(image_path):
                raise FileNotFoundError(f"图像文件验证失败: {image_path}")
            
            with open(image_path, "rb") as image_file:
                image_data = image_file.read()
                image_base64 = base64.b64encode(image_data).decode("utf-8")
            
            self.log(f"图像编码成功，数据长度: {len(image_base64)} 字符", "SUCCESS")
            return image_base64
            
        except FileNotFoundError as e:
            self.log(f"文件未找到: {str(e)}", "ERROR")
            raise
        except Exception as e:
            self.log(f"图像编码失败: {str(e)}", "ERROR")
            raise Exception(f"图像编码失败: {str(e)}")

    def poster_to_latex(self, image_path, output_tex_file="output.tex"):
        """
        将海报图像转换为LaTeX代码
        
        Args:
            image_path (str): 海报图像路径
            output_tex_file (str): 输出的LaTeX文件名
            
        Returns:
            str: 生成的LaTeX代码
        """
        self.log(f"开始分析海报图像: {image_path}", "INFO")
        
        if not self.client:
            raise Exception("OpenAI API密钥未设置，无法生成LaTeX代码")
        
        # 编码图像
        image_base64 = self.encode_image_to_base64(image_path)
        
        # 确定图像MIME类型
        image_ext = Path(image_path).suffix.lower()
        if image_ext in ['.png']:
            mime_type = "image/png"
        elif image_ext in ['.jpg', '.jpeg']:
            mime_type = "image/jpeg"
        else:
            mime_type = "image/png"  # 默认为PNG
        
        self.log(f"图像类型: {mime_type}", "DEBUG")
        
        # 构建图像payload
        image_payload = {
            "type": "image_url",
            "image_url": {
                "url": f"data:{mime_type};base64,{image_base64}"
            }
        }
        
        # 调用OpenAI API
        self.log("调用OpenAI API生成LaTeX代码...", "INFO")
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that outputs complete LaTeX code for poster layout recreation."
                    },
                    {"role": "user", "content": self.custom_prompt},
                    {"role": "user", "content": [image_payload]}
                ]
            )
            
            # latex_code = response.choices[0].message.content
            raw_response = response.choices[0].message.content

            # --- START: 这是我们新增的清理代码 ---
            self.log("正在清理AI返回的LaTeX代码...", "DEBUG")
            # 使用正则表达式移除Markdown代码块标记
            cleaned_code = re.sub(r'^```(latex)?\s*', '', raw_response, flags=re.MULTILINE)
            cleaned_code = re.sub(r'```\s*$', '', cleaned_code, flags=re.MULTILINE)
            # 移除开头和结尾可能存在的任何空白字符
            latex_code = cleaned_code.strip()
            # --- END: 清理代码结束 ---
            self.log("LaTeX代码生成成功!", "SUCCESS")
            
            # 保存LaTeX代码到文件
            try:
                with open(output_tex_file, "w", encoding="utf-8") as f:
                    f.write(latex_code)
                self.log(f"LaTeX代码已保存到: {output_tex_file}", "SUCCESS")
            except Exception as e:
                self.log(f"保存LaTeX文件失败: {e}", "ERROR")
                raise
            
            return latex_code
            
        except Exception as e:
            self.log(f"OpenAI API调用失败: {str(e)}", "ERROR")
            raise Exception(f"OpenAI API调用失败: {str(e)}")

    def compile_tex_to_pdf(self, tex_filename):
        """
        编译LaTeX文件为PDF（增强版）
        
        Args:
            tex_filename (str): LaTeX文件名
            
        Returns:
            str: 生成的PDF文件路径
        """
        try:
            self.log(f"开始编译LaTeX文件: {tex_filename}", "INFO")
            
            if not os.path.exists(tex_filename):
                raise FileNotFoundError(f"LaTeX文件不存在: {tex_filename}")
            
            # 检查LaTeX文件内容
            file_size = os.path.getsize(tex_filename)
            self.log(f"LaTeX文件大小: {file_size} bytes", "DEBUG")
            
            if file_size == 0:
                raise Exception("LaTeX文件为空")
            
            # 确定pdflatex命令
            pdflatex_cmd = self._get_pdflatex_command()
            
            # 编译LaTeX文件 - 获取文件所在目录
            tex_dir = os.path.dirname(os.path.abspath(tex_filename))
            tex_basename = os.path.basename(tex_filename)
            
            self.log("执行pdflatex编译...", "DEBUG")
            self.log(f"工作目录: {tex_dir}", "DEBUG")
            self.log(f"编译文件: {tex_basename}", "DEBUG")
            self.log(f"使用命令: {pdflatex_cmd}", "DEBUG")
            
            # 清理之前的辅助文件
            self._cleanup_before_compile(tex_filename)
            
            # 尝试编译（可能需要多次）
            max_attempts = 2
            for attempt in range(max_attempts):
                self.log(f"编译尝试 {attempt + 1}/{max_attempts}", "INFO")
                
                try:
                    result = subprocess.run(
                        [pdflatex_cmd, "-interaction=nonstopmode", "-halt-on-error", tex_basename], 
                        capture_output=True, text=True, cwd=tex_dir, timeout=60
                    )
                except UnicodeDecodeError:
                    # 如果出现编码问题，使用错误忽略模式
                    result = subprocess.run(
                        [pdflatex_cmd, "-interaction=nonstopmode", "-halt-on-error", tex_basename], 
                        capture_output=True, text=True, cwd=tex_dir, errors='ignore', timeout=60
                    )
                except subprocess.TimeoutExpired:
                    raise Exception("pdflatex编译超时（60秒）")
                
                # 详细的错误分析
                if result.returncode != 0:
                    self.log(f"编译尝试 {attempt + 1} 失败，返回码: {result.returncode}", "ERROR")
                    
                    # 分析错误类型
                    error_analysis = self._analyze_compilation_error(result.stdout, result.stderr)
                    
                    if error_analysis["is_miktex_update_issue"]:
                        raise Exception(
                            "MiKTeX需要更新。请按以下步骤操作：\n"
                            "1. 打开 MiKTeX Console (管理员模式)\n"
                            "2. 点击 'Check for updates'\n"
                            "3. 安装所有可用更新\n"
                            "4. 重启应用程序\n"
                            f"详细错误: {error_analysis['error_message']}"
                        )
                    
                    if error_analysis["is_missing_package"]:
                        self.log(f"检测到缺失包: {error_analysis['missing_packages']}", "WARNING")
                        if attempt < max_attempts - 1:
                            self.log("尝试自动安装缺失包...", "INFO")
                            self._install_missing_packages(error_analysis['missing_packages'])
                            continue
                    
                    if attempt == max_attempts - 1:
                        # 最后一次尝试失败，输出详细错误
                        self._output_detailed_error(result.stdout, result.stderr, tex_filename)
                        raise Exception(f"pdflatex编译失败，返回码: {result.returncode}")
                else:
                    self.log("pdflatex编译成功!", "SUCCESS")
                    if result.stdout:
                        self.log(f"编译输出摘要: {result.stdout[:200]}...", "DEBUG")
                    break
            
            # 检查PDF是否生成
            pdf_filename = tex_filename.replace(".tex", ".pdf")
            if os.path.exists(pdf_filename):
                pdf_size = os.path.getsize(pdf_filename)
                self.log(f"PDF编译成功: {pdf_filename} ({pdf_size} bytes)", "SUCCESS")
                return pdf_filename
            else:
                raise Exception("PDF文件未生成，即使编译返回成功")
            
        except subprocess.CalledProcessError as e:
            self.log(f"编译过程出错: {e}", "ERROR")
            raise Exception(f"编译 {tex_filename} 时出错: {e}")

    def _get_pdflatex_command(self):
        """获取可用的pdflatex命令"""
        if self.pdflatex_path == "pdflatex":
            return "pdflatex"
        elif os.path.exists(self.pdflatex_path):
            return self.pdflatex_path
        else:
            # 最后尝试系统PATH
            try:
                subprocess.run(["pdflatex", "--version"], 
                             check=True, capture_output=True, text=True, timeout=5)
                return "pdflatex"
            except:
                raise FileNotFoundError(
                    f"pdflatex未找到。请检查MiKTeX安装或路径配置。\n"
                    f"当前配置路径: {self.pdflatex_path}\n"
                    "建议：\n"
                    "1. 重新安装MiKTeX\n"
                    "2. 确保MiKTeX添加到系统PATH\n"
                    "3. 或者手动指定pdflatex.exe的完整路径"
                )

    def _cleanup_before_compile(self, tex_filename):
        """编译前清理辅助文件"""
        base_name = tex_filename.replace(".tex", "")
        cleanup_extensions = ["aux", "log", "out", "toc", "nav", "snm", "fdb_latexmk", "fls"]
        
        for ext in cleanup_extensions:
            aux_file = f"{base_name}.{ext}"
            try:
                if os.path.exists(aux_file):
                    os.remove(aux_file)
                    self.log(f"清理旧文件: {aux_file}", "DEBUG")
            except Exception as e:
                self.log(f"清理文件 {aux_file} 时出错: {e}", "WARNING")

    def _analyze_compilation_error(self, stdout, stderr):
        """分析编译错误"""
        analysis = {
            "is_miktex_update_issue": False,
            "is_missing_package": False,
            "missing_packages": [],
            "error_message": "",
            "suggestions": []
        }
        
        error_text = (stdout or "") + (stderr or "")
        error_text_lower = error_text.lower()
        
        # 检查MiKTeX更新问题
        miktex_update_keywords = [
            "you have not checked for miktex updates",
            "miktex update required",
            "miktex console",
            "check for updates"
        ]
        
        for keyword in miktex_update_keywords:
            if keyword in error_text_lower:
                analysis["is_miktex_update_issue"] = True
                analysis["error_message"] = error_text[:500]
                break
        
        # 检查缺失包
        import re
        package_patterns = [
            r"File `([^']+\.sty)' not found",
            r"LaTeX Error: File `([^']+)' not found",
            r"! Package (\w+) Error"
        ]
        
        for pattern in package_patterns:
            matches = re.findall(pattern, error_text)
            for match in matches:
                package_name = match.replace('.sty', '')
                if package_name not in analysis["missing_packages"]:
                    analysis["missing_packages"].append(package_name)
                    analysis["is_missing_package"] = True
        
        return analysis

    def _install_missing_packages(self, packages):
        """尝试安装缺失的包"""
        for package in packages:
            try:
                self.log(f"尝试安装包: {package}", "INFO")
                # 使用MiKTeX包管理器安装
                subprocess.run(["mpm", "--install", package], 
                             check=True, capture_output=True, text=True, timeout=30)
                self.log(f"包安装成功: {package}", "SUCCESS")
            except Exception as e:
                self.log(f"包安装失败: {package} - {e}", "WARNING")

    def _output_detailed_error(self, stdout, stderr, tex_filename):
        """输出详细的错误信息"""
        self.log("=== 详细编译错误信息 ===", "ERROR")
        
        if stdout:
            self.log("编译输出 (stdout):", "DEBUG")
            # 输出最后1000个字符，这通常包含关键错误信息
            print(stdout[-1000:] if len(stdout) > 1000 else stdout)
        
        if stderr:
            self.log("编译错误 (stderr):", "DEBUG")
            print(stderr[-1000:] if len(stderr) > 1000 else stderr)
        
        # 尝试查找.log文件获取更多信息
        log_file = tex_filename.replace(".tex", ".log")
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    log_content = f.read()
                    # 查找错误行
                    lines = log_content.split('\n')
                    error_lines = [line for line in lines if 'error' in line.lower() or '!' in line]
                    if error_lines:
                        self.log("LaTeX日志中的错误行:", "DEBUG")
                        for line in error_lines[-10:]:  # 显示最后10个错误行
                            print(f"  {line}")
            except Exception as e:
                self.log(f"无法读取LaTeX日志文件: {e}", "WARNING")

    def clean_auxiliary_files(self, tex_filename):
        """
        清理编译过程中产生的辅助文件
        
        Args:
            tex_filename (str): LaTeX文件名
        """
        base_name = tex_filename.replace(".tex", "")
        auxiliary_extensions = ["aux", "log", "out", "toc", "nav", "snm"]
        
        cleaned_files = []
        for ext in auxiliary_extensions:
            aux_file = f"{base_name}.{ext}"
            try:
                if os.path.exists(aux_file):
                    os.remove(aux_file)
                    cleaned_files.append(aux_file)
            except Exception as e:
                self.log(f"清理文件 {aux_file} 时出错: {e}", "WARNING")
        
        if cleaned_files:
            self.log(f"已清理辅助文件: {', '.join(cleaned_files)}", "SUCCESS")

    def translate_poster_complete(self, image_path, output_base_name="output", clean_aux=True):
        """
        完整的海报翻译流程：图像 -> LaTeX -> PDF
        
        Args:
            image_path (str): 海报图像路径
            output_base_name (str): 输出文件基础名称
            clean_aux (bool): 是否清理辅助文件
            
        Returns:
            dict: 包含生成文件信息的字典
        """
        self.log("🚀 开始海报翻译流程...", "INFO")
        
        try:
            # 验证图像文件
            if not self.validate_image_file(image_path):
                raise FileNotFoundError(f"图像文件无效: {image_path}")
            
            # 第一步：生成LaTeX代码
            tex_filename = f"{output_base_name}.tex"
            self.log("第1步: 生成LaTeX代码", "INFO")
            latex_code = self.poster_to_latex(image_path, tex_filename)
            
            # 第二步：编译PDF
            self.log("第2步: 编译PDF", "INFO")
            pdf_filename = self.compile_tex_to_pdf(tex_filename)
            
            # 第三步：清理辅助文件（可选）
            if clean_aux:
                self.log("第3步: 清理辅助文件", "INFO")
                self.clean_auxiliary_files(tex_filename)
            
            result = {
                "success": True,
                "tex_file": tex_filename,
                "pdf_file": pdf_filename,
                "image_file": image_path,
                "latex_code_length": len(latex_code)
            }
            
            self.log("🎉 海报翻译完成!", "SUCCESS")
            self.log(f"   输入图像: {image_path}", "INFO")
            self.log(f"   LaTeX文件: {tex_filename}", "INFO")
            self.log(f"   PDF文件: {pdf_filename}", "INFO")
            
            return result
            
        except Exception as e:
            self.log(f"海报翻译失败: {str(e)}", "ERROR")
            return {
                "success": False,
                "error": str(e),
                "image_file": image_path
            }

# ========== 网页翻译工作流程类 ==========

class WebTranslationWorkflow:
    """网页翻译工作流程类（增强版）"""
    
    def __init__(self, api_key=None, output_dir="web_translation_output"):
        """初始化工作流程"""
        self.api_key = api_key or self._load_api_key()
        self.output_dir = output_dir
        self.client = OpenAI(api_key=self.api_key) if self.api_key else None
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 状态检查配置
        self.max_retries = 3
        self.retry_delay = 2
        self.pdf_timeout = 30

    def log_status(self, message, level="INFO"):
        """详细状态日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = {
            "INFO": "ℹ️",
            "SUCCESS": "✅", 
            "WARNING": "⚠️",
            "ERROR": "❌",
            "DEBUG": "🔍"
        }
        print(f"[{timestamp}] {prefix.get(level, 'ℹ️')} {message}")

    def check_chrome_status(self, driver):
        """检查Chrome浏览器状态"""
        try:
            # 检查浏览器是否还活着
            driver.current_url
            self.log_status("Chrome浏览器状态正常", "SUCCESS")
            return True
        except Exception as e:
            self.log_status(f"Chrome浏览器状态异常: {str(e)}", "ERROR")
            return False

    def check_file_status(self, file_path):
        """检查文件状态"""
        if not os.path.exists(file_path):
            self.log_status(f"文件不存在: {file_path}", "ERROR")
            return False
        
        file_size = os.path.getsize(file_path)
        self.log_status(f"文件存在，大小: {file_size} bytes", "SUCCESS")
        
        if file_size == 0:
            self.log_status("警告：文件大小为0", "WARNING")
            return False
        
        return True

    def _load_api_key(self):
        """从环境变量或配置文件加载API密钥"""
        api_key = os.getenv('OPENAI_API_KEY')
        if api_key:
            return api_key
        
        config_files = ['api_key.txt', 'openai_key.txt', 'config.json']
        for config_file in config_files:
            if os.path.exists(config_file):
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        if config_file.endswith('.json'):
                            data = json.loads(content)
                            return data.get('openai_api_key') or data.get('api_key')
                        else:
                            return content
                except Exception:
                    continue
        return None

    @staticmethod
    def sanitize_url_to_foldername(url):
        """将URL转换为安全的文件夹名称"""
        url = re.sub(r'^https?:\/\/', '', url, flags=re.IGNORECASE)
        folder = re.sub(r'[^0-9A-Za-z]+', '_', url)
        return folder.strip('_')

    def setup_chrome_enhanced(self, disable_js=False, headless=True):
        """创建增强的Chrome WebDriver实例"""
        self.log_status("正在初始化Chrome WebDriver...", "INFO")
        
        options = Options()
        
        # 基本配置
        if headless:
            options.add_argument("--headless")
            self.log_status("启用无头模式", "DEBUG")
        
        # 增强稳定性配置
        options.add_argument("--window-size=1280,800")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-setuid-sandbox")
        options.add_argument("--disable-dev-shm-usage")  # 解决内存问题
        options.add_argument("--disable-gpu")  # 禁用GPU加速
        options.add_argument("--disable-extensions")  # 禁用扩展
        options.add_argument("--disable-plugins")  # 禁用插件
        options.add_argument("--disable-images")  # 禁用图片加载以提高速度
        options.add_argument("--disable-javascript") if disable_js else None
        
        # 文件访问权限
        options.add_argument("--allow-file-access-from-files")
        options.add_argument("--disable-web-security")
        
        # 网络配置
        options.add_argument("--disable-features=TranslateUI")
        options.add_argument("--disable-ipc-flooding-protection")
        
        if disable_js:
            prefs = {"profile.managed_default_content_settings.javascript": 2}
            options.add_experimental_option("prefs", prefs)
            self.log_status("已禁用JavaScript", "DEBUG")
        
        # 设置页面加载策略
        options.page_load_strategy = 'normal'
        
        try:
            # 尝试创建WebDriver
            service = Service()
            driver = webdriver.Chrome(service=service, options=options)
            
            # 设置超时
            driver.set_page_load_timeout(self.pdf_timeout)
            driver.implicitly_wait(10)
            
            self.log_status("Chrome WebDriver初始化成功", "SUCCESS")
            self.log_status(f"Chrome版本: {driver.capabilities['browserVersion']}", "DEBUG")
            
            return driver
            
        except Exception as e:
            self.log_status(f"Chrome WebDriver初始化失败: {str(e)}", "ERROR")
            raise Exception(f"Chrome WebDriver初始化失败: {e}")

    def print_to_pdf_with_retry(self, driver, pdf_path, paper_width=8.27, paper_height=11.7):
        """使用重试机制的PDF生成"""
        self.log_status(f"开始生成PDF: {pdf_path}", "INFO")
        
        print_options = {
            "paperWidth": paper_width,
            "paperHeight": paper_height,
            "marginTop": 0.4,
            "marginBottom": 0.4,
            "marginLeft": 0.4,
            "marginRight": 0.4,
            "printBackground": True,
            "scale": 0.9,  # 90% 缩放比例
            "preferCSSPageSize": False
        }
        
        for attempt in range(self.max_retries):
            try:
                self.log_status(f"PDF生成尝试 {attempt + 1}/{self.max_retries}", "INFO")
                
                # 检查浏览器状态
                if not self.check_chrome_status(driver):
                    raise Exception("Chrome浏览器状态异常")
                
                # 等待页面完全加载
                self.log_status("等待页面加载完成...", "DEBUG")
                time.sleep(3)
                
                # 检查页面状态
                page_title = driver.title
                self.log_status(f"当前页面标题: {page_title}", "DEBUG")
                
                # 调用CDP命令生成PDF
                self.log_status("调用Chrome DevTools Protocol生成PDF...", "DEBUG")
                result = driver.execute_cdp_cmd("Page.printToPDF", print_options)
                
                if 'data' not in result:
                    raise Exception("PDF生成失败：未返回PDF数据")
                
                # 解码PDF数据
                self.log_status("解码PDF数据...", "DEBUG")
                pdf_data = base64.b64decode(result['data'])
                pdf_size = len(pdf_data)
                self.log_status(f"PDF数据大小: {pdf_size} bytes", "DEBUG")
                
                if pdf_size == 0:
                    raise Exception("PDF数据为空")
                
                # 保存PDF文件
                os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
                with open(pdf_path, "wb") as f:
                    f.write(pdf_data)
                
                # 验证文件保存
                if self.check_file_status(pdf_path):
                    self.log_status(f"PDF生成成功: {pdf_path}", "SUCCESS")
                    return True
                else:
                    raise Exception("PDF文件保存失败")
                    
            except Exception as e:
                self.log_status(f"PDF生成尝试 {attempt + 1} 失败: {str(e)}", "ERROR")
                
                if attempt < self.max_retries - 1:
                    self.log_status(f"等待 {self.retry_delay} 秒后重试...", "WARNING")
                    time.sleep(self.retry_delay)
                else:
                    raise Exception(f"PDF生成失败，已重试 {self.max_retries} 次: {str(e)}")
        
        return False

    def fetch_webpage_simple(self, url, wait_time=3):
        """简化的网页获取方法（仅获取HTML内容，不下载资源）"""
        self.log_status(f"开始获取网页: {url}", "INFO")
        
        folder_name = self.sanitize_url_to_foldername(url)
        base_dir = os.path.join(self.output_dir, folder_name)
        snapshot_dir = os.path.join(base_dir, "original_snapshot")
        os.makedirs(snapshot_dir, exist_ok=True)
        
        self.log_status(f"输出目录: {snapshot_dir}", "DEBUG")

        driver = None
        try:
            driver = self.setup_chrome_enhanced(disable_js=True)
            
            self.log_status(f"访问URL: {url}", "INFO")
            driver.get(url)
            
            self.log_status(f"等待页面加载 {wait_time} 秒...", "DEBUG")
            time.sleep(wait_time)

            # 获取页面信息
            title = sanitize_title(driver.title)
            self.log_status(f"页面标题: {title}", "DEBUG")
            
            # 生成原始PDF
            pdf_path = os.path.join(snapshot_dir, f"{title}_original.pdf")
            self.print_to_pdf_with_retry(driver, pdf_path)

            # 保存HTML内容
            self.log_status("保存HTML内容...", "DEBUG")
            html_content = driver.page_source
            html_path = os.path.join(snapshot_dir, "index.html")
            
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            
            self.check_file_status(html_path)

            return {
                "success": True,
                "url": url,
                "folder_name": folder_name,
                "base_dir": base_dir,
                "snapshot_dir": snapshot_dir,
                "html_path": html_path,
                "original_pdf_path": pdf_path,
                "title": title
            }

        except Exception as e:
            self.log_status(f"网页获取失败: {str(e)}", "ERROR")
            return {
                "success": False,
                "error": str(e),
                "url": url
            }
        finally:
            if driver:
                try:
                    self.log_status("关闭Chrome浏览器...", "DEBUG")
                    driver.quit()
                    self.log_status("Chrome浏览器已关闭", "SUCCESS")
                except Exception as e:
                    self.log_status(f"关闭浏览器时出错: {str(e)}", "WARNING")

    def translate_html(self, html_path, output_path=None):
        """使用GPT翻译HTML内容"""
        self.log_status(f"开始翻译HTML: {html_path}", "INFO")
        
        if not self.client:
            self.log_status("OpenAI API密钥未设置", "ERROR")
            return {
                "success": False,
                "error": "OpenAI API密钥未设置"
            }

        if not self.check_file_status(html_path):
            return {
                "success": False,
                "error": f"HTML文件不存在或无效: {html_path}"
            }

        if not output_path:
            dir_path = os.path.dirname(html_path)
            output_path = os.path.join(dir_path, "index_translated.html")

        if os.path.exists(output_path):
            self.log_status(f"翻译文件已存在，跳过翻译: {output_path}", "WARNING")
            return {
                "success": True,
                "translated_path": output_path,
                "skipped": True
            }

        try:
            with open(html_path, "r", encoding="utf-8") as f:
                html_content = f.read()

            content_size = len(html_content)
            self.log_status(f"HTML内容大小: {content_size} 字符", "DEBUG")

            user_prompt = (
                "Please translate the following HTML content from Chinese to English. "
                "Keep the HTML structure and any existing English text as is. "
                "Only translate the Chinese text into English. "
                "Preserve all HTML tags, attributes, and formatting:\n\n"
                + html_content
            )

            self.log_status("调用OpenAI API进行翻译...", "INFO")
            completion = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "user",
                    "content": user_prompt
                }],
                temperature=0.3
            )

            translated_text = completion.choices[0].message.content
            translated_size = len(translated_text)
            self.log_status(f"翻译完成，大小: {translated_size} 字符", "DEBUG")

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(translated_text)

            if self.check_file_status(output_path):
                self.log_status("HTML翻译完成", "SUCCESS")
                return {
                    "success": True,
                    "translated_path": output_path,
                    "original_length": content_size,
                    "translated_length": translated_size
                }
            else:
                raise Exception("翻译文件保存失败")

        except Exception as e:
            self.log_status(f"翻译失败: {str(e)}", "ERROR")
            return {
                "success": False,
                "error": f"翻译失败: {str(e)}"
            }

    def generate_pdf_from_html_simple(self, html_path, pdf_output=None):
        """从HTML生成PDF（带详细检查）"""
        self.log_status(f"开始PDF生成流程: {html_path}", "INFO")
        
        if not self.check_file_status(html_path):
            return {
                "success": False,
                "error": f"HTML文件不存在或无效: {html_path}"
            }

        if not pdf_output:
            dir_path = os.path.dirname(html_path)
            base_name = os.path.splitext(os.path.basename(html_path))[0]
            pdf_output = os.path.join(dir_path, f"{base_name}.pdf")

        self.log_status(f"PDF输出路径: {pdf_output}", "DEBUG")

        driver = None
        try:
            driver = self.setup_chrome_enhanced()
            
            local_file = os.path.abspath(html_path)
            self.log_status(f"本地文件路径: {local_file}", "DEBUG")
            
            # 修复Windows文件路径问题
            if os.name == 'nt':  # Windows
                file_url = f"file:///{local_file.replace(os.sep, '/')}"
            else:  # Unix/Linux/Mac
                file_url = f"file://{local_file}"
            
            self.log_status(f"访问本地文件URL: {file_url}", "INFO")
            
            # 设置更长的超时时间
            driver.set_page_load_timeout(60)
            
            try:
                driver.get(file_url)
                self.log_status("本地HTML文件加载成功", "SUCCESS")
            except TimeoutException:
                self.log_status("页面加载超时，但继续尝试生成PDF", "WARNING")
            
            # 检查页面状态
            try:
                page_title = driver.title
                self.log_status(f"页面标题: {page_title}", "DEBUG")
                
                # 检查页面内容
                page_source_size = len(driver.page_source)
                self.log_status(f"页面源码大小: {page_source_size} 字符", "DEBUG")
                
                if page_source_size < 100:
                    self.log_status("警告：页面内容过少，可能加载失败", "WARNING")
                
            except Exception as e:
                self.log_status(f"获取页面信息时出错: {str(e)}", "WARNING")
            
            # 生成PDF
            self.print_to_pdf_with_retry(driver, pdf_output)
            
            return {
                "success": True,
                "pdf_path": pdf_output,
                "file_size": os.path.getsize(pdf_output)
            }

        except Exception as e:
            self.log_status(f"PDF生成失败: {str(e)}", "ERROR")
            return {
                "success": False,
                "error": f"PDF生成失败: {str(e)}"
            }
        finally:
            if driver:
                try:
                    self.log_status("关闭Chrome浏览器...", "DEBUG")
                    driver.quit()
                    self.log_status("Chrome浏览器已关闭", "SUCCESS")
                except Exception as e:
                    self.log_status(f"关闭浏览器时出错: {str(e)}", "WARNING")

# ========== 百度图片翻译类 ==========

# class BaiduImageTranslationTester:
#     """百度图片翻译API封装类"""
    
    # def __init__(self, api_key=None, secret_key=None):
    #     # 使用项目中现有的API凭据，也允许传入自定义凭据
    #     self.api_key = api_key or "OHh0W1083PSfOEp4VsjLvgvn"
    #     self.secret_key = secret_key or "RQQxPsWq9p2sNmvGTdwPgwjtFlG9BDFY"
    #     self.access_token = None

class BaiduImageTranslationTester:
    """百度图片翻译API封装类"""

    def __init__(self, api_key=None, secret_key=None):
        # 优先使用传入的key，其次从文件加载，最后使用代码中的默认值
        self.api_key = api_key or self._load_key_from_file('config/baidu_api_key.txt') or "OHh0W1083PSfOEp4VsjLvgvn"
        self.secret_key = secret_key or self._load_key_from_file('config/baidu_secret_key.txt') or "RQQxPsWq9p2sNmvGTdwPgwjtFlG9BDFY"
        self.access_token = None

    def _load_key_from_file(self, file_path):
        """一个用来从文件安全读取密钥的辅助函数"""
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    key = f.read().strip()
                    if key:
                        print(f"✅ 成功从 {file_path} 加载密钥。")
                        return key
            except Exception as e:
                print(f"⚠️ 警告: 无法从 {file_path} 读取密钥: {e}")
        return None

    # ... 类的其他方法 (log_status, get_access_token 等) 保持不变 ...
    
    def log_status(self, message, level="INFO"):
        """状态日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = {
            "INFO": "ℹ️",
            "SUCCESS": "✅", 
            "WARNING": "⚠️",
            "ERROR": "❌",
            "DEBUG": "🔍"
        }
        print(f"[{timestamp}] {prefix.get(level, 'ℹ️')} {message}")
    
    def get_access_token(self):
        """获取百度AI平台的access_token"""
        self.log_status("正在获取百度API access_token...", "INFO")
        
        token_url = f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={self.api_key}&client_secret={self.secret_key}"
        
        try:
            response = requests.post(token_url)
            if response.status_code == 200:
                result = response.json()
                if "access_token" in result:
                    self.access_token = result["access_token"]
                    self.log_status(f"获取access_token成功: {self.access_token[:20]}...", "SUCCESS")
                    return True
                else:
                    self.log_status(f"获取token失败: {result}", "ERROR")
                    return False
            else:
                self.log_status(f"HTTP请求失败: {response.status_code} - {response.text}", "ERROR")
                return False
        except Exception as e:
            self.log_status(f"获取access_token异常: {e}", "ERROR")
            return False
    
    def call_image_translation_api(self, image_path, from_lang="en", to_lang="zh", paste_type=1):
        """
        调用百度图片翻译API
        :param image_path: 图片文件路径
        :param from_lang: 源语言 (en, zh, jp等)
        :param to_lang: 目标语言 (en, zh, jp等)
        :param paste_type: 贴图类型 (0: 不贴图, 1: 整图贴图, 2: 块贴图)
        :return: API响应结果
        """
        if not self.access_token:
            self.log_status("请先获取access_token", "ERROR")
            return None
        
        api_url = f"https://aip.baidubce.com/file/2.0/mt/pictrans/v1?access_token={self.access_token}"
        
        try:
            # 检查文件是否存在
            if not os.path.exists(image_path):
                self.log_status(f"图片文件不存在: {image_path}", "ERROR")
                return None
            
            # 读取图片文件
            with open(image_path, 'rb') as f:
                image_data = f.read()
            
            self.log_status(f"正在翻译图片: {image_path}", "INFO")
            self.log_status(f"翻译方向: {from_lang} -> {to_lang}", "DEBUG")
            self.log_status(f"贴图类型: {paste_type}", "DEBUG")
            
            # 准备请求数据
            files = {
                'image': ('image.jpg', image_data, 'image/jpeg')
            }
            
            data = {
                'from': from_lang,
                'to': to_lang,
                'v': '3',
                'paste': str(paste_type)
            }
            
            # 发送请求
            response = requests.post(api_url, files=files, data=data)
            
            if response.status_code == 200:
                result = response.json()
                self.log_status("API调用成功", "SUCCESS")
                return result
            else:
                self.log_status(f"API调用失败: {response.status_code} - {response.text}", "ERROR")
                return None
                
        except FileNotFoundError:
            self.log_status(f"图片文件未找到: {image_path}", "ERROR")
            return None
        except Exception as e:
            self.log_status(f"API调用异常: {e}", "ERROR")
            return None
    
    def save_translated_image(self, translation_result, output_path="translated_image.jpg"):
        """
        保存翻译后的图片
        :param translation_result: API返回的翻译结果
        :param output_path: 输出图片路径
        :return: 是否保存成功
        """
        try:
            if (translation_result and 
                translation_result.get("data") and 
                translation_result["data"].get("pasteImg")):
                
                encoded_image = translation_result["data"]["pasteImg"]
                
                # 确保输出目录存在
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                
                with open(output_path, "wb") as f:
                    f.write(base64.b64decode(encoded_image))
                
                self.log_status(f"翻译后的图片已保存到: {output_path}", "SUCCESS")
                return output_path
            else:
                self.log_status("翻译结果中没有包含翻译后的图片数据", "WARNING")
                return None
        except Exception as e:
            self.log_status(f"保存翻译后图片失败: {e}", "ERROR")
            return None
    
    def extract_text_info(self, translation_result):
        """提取翻译结果中的文本信息（根据百度API文档格式）"""
        text_info = {
            "detected_texts": [],
            "translated_texts": [],
            "summary_src": "",
            "summary_dst": "",
            "translation_direction": "",
            "total_blocks": 0
        }
        
        if not translation_result or not translation_result.get("data"):
            return text_info
        
        data = translation_result["data"]
        
        # 获取翻译方向
        from_lang = data.get("from", "")
        to_lang = data.get("to", "")
        text_info["translation_direction"] = f"{from_lang} -> {to_lang}"
        
        # 获取摘要文本
        text_info["summary_src"] = data.get("sumSrc", "")
        text_info["summary_dst"] = data.get("sumDst", "")
        
        # 获取详细文本块信息
        if data.get("content"):
            text_info["total_blocks"] = len(data["content"])
            
            for i, content in enumerate(data["content"]):
                src_text = content.get("src", "")
                dst_text = content.get("dst", "")
                rect_str = content.get("rect", "")
                points = content.get("points", [])
                line_count = content.get("lineCount", 1)
                
                # 解析rect字符串 - 格式为 "x y width height"
                position = {"left": 0, "top": 0, "width": 0, "height": 0}
                if rect_str and isinstance(rect_str, str):
                    try:
                        parts = rect_str.strip().split()
                        if len(parts) >= 4:
                            position = {
                                "left": int(parts[0]),
                                "top": int(parts[1]),
                                "width": int(parts[2]),
                                "height": int(parts[3])
                            }
                    except (ValueError, IndexError) as e:
                        self.log_status(f"解析rect失败: {rect_str} - {e}", "WARNING")
                
                # 添加检测到的文本
                if src_text:
                    text_info["detected_texts"].append({
                        "text": src_text,
                        "position": position,
                        "points": points,
                        "line_count": line_count,
                        "block_index": i
                    })
                
                # 添加翻译后的文本
                if dst_text:
                    text_info["translated_texts"].append({
                        "text": dst_text,
                        "position": position,
                        "points": points,
                        "line_count": line_count,
                        "block_index": i
                    })
        
        return text_info
    
    def translate_image_complete(self, image_path, from_lang="en", to_lang="zh", save_image=True):
        """
        完整的图片翻译流程
        :param image_path: 图片路径
        :param from_lang: 源语言
        :param to_lang: 目标语言
        :param save_image: 是否保存翻译后的图片
        :return: 翻译结果字典
        """
        self.log_status("🚀 开始图片翻译流程...", "INFO")
        
        try:
            # 1. 获取access_token
            self.log_status("步骤1: 获取access_token", "DEBUG")
            if not self.get_access_token():
                return {
                    "success": False,
                    "error": "获取百度API access_token失败"
                }
            
            # 2. 调用图片翻译API
            self.log_status("步骤2: 调用图片翻译API", "DEBUG")
            translation_result = self.call_image_translation_api(
                image_path, from_lang, to_lang, paste_type=1 if save_image else 0
            )
            
            if not translation_result:
                self.log_status("API调用返回None", "ERROR")
                return {
                    "success": False,
                    "error": "调用百度图片翻译API失败"
                }
            
            # 调试：打印完整的API响应
            import json
            self.log_status(f"API响应: {json.dumps(translation_result, ensure_ascii=False)}", "DEBUG")
            
            # 检查API返回的错误 - 修复类型比较问题
            self.log_status("步骤3: 检查API响应", "DEBUG")
            error_code = translation_result.get("error_code")
            self.log_status(f"检查error_code: {error_code} (类型: {type(error_code)})", "DEBUG")
            
            # 处理error_code可能是字符串或整数的情况
            is_success = False
            if error_code is None:
                is_success = True  # 没有error_code字段，可能是成功
            elif isinstance(error_code, str):
                is_success = (error_code == "0" or error_code.lower() == "success")
            elif isinstance(error_code, int):
                is_success = (error_code == 0)
            else:
                # 尝试转换为整数比较
                try:
                    is_success = (int(error_code) == 0)
                except (ValueError, TypeError):
                    is_success = False
            
            if not is_success:
                self.log_status(f"API返回错误: code={error_code}, msg={translation_result.get('error_msg')}", "ERROR")
                return {
                    "success": False,
                    "error": f"百度API错误: {translation_result.get('error_msg', '未知错误')}",
                    "error_code": error_code
                }
            
            # 检查是否有数据（双重验证）
            if not translation_result.get("data"):
                self.log_status("API响应中缺少data字段", "ERROR")
                return {
                    "success": False,
                    "error": "百度API未返回翻译数据"
                }
            
            self.log_status("API响应检查通过！", "SUCCESS")
            
            # 3. 提取文本信息
            self.log_status("步骤4: 提取文本信息", "DEBUG")
            text_info = self.extract_text_info(translation_result)
            
            # 4. 保存翻译后的图片（如果需要）
            translated_image_path = None
            if save_image:
                self.log_status("步骤5: 保存翻译图片", "DEBUG")
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_filename = f"translated_image_{timestamp}.jpg"
                output_path = os.path.join("image_translation_output", output_filename)
                translated_image_path = self.save_translated_image(translation_result, output_path)
                
                if translated_image_path:
                    self.log_status(f"图片保存成功: {translated_image_path}", "SUCCESS")
                else:
                    self.log_status("图片保存失败", "WARNING")
            
            result = {
                "success": True,
                "original_image": image_path,
                "translated_image": translated_image_path,
                "text_info": text_info,
                "translation_direction": f"{from_lang} -> {to_lang}",
                "has_translated_image": translated_image_path is not None
            }
            
            self.log_status("🎉 图片翻译完成!", "SUCCESS")
            self.log_status(f"返回结果: success={result['success']}", "DEBUG")
            return result
            
        except Exception as e:
            self.log_status(f"图片翻译失败: {str(e)}", "ERROR")
            import traceback
            self.log_status(f"错误堆栈: {traceback.format_exc()}", "DEBUG")
            return {
                "success": False,
                "error": f"图片翻译失败: {str(e)}"
            }

# ========== Flask 路由 ==========

@app.route('/')
def index():
    return jsonify({
        'message': '翻译平台后端API - 增强版',
        'version': '2.1',
        'features': {
            'detailed_logging': True,
            'retry_mechanism': True,
            'pdf_scaling': '90%',
            'enhanced_chrome_config': True,
            'error_handling': True,
            'baidu_image_translation': True
        },
        'endpoints': {
            'webpage_google_translate': '/api/webpage-google-translate',
            'webpage_gpt_translate': '/api/webpage-gpt-translate',
            'poster_translate': '/api/poster-translate',
            'image_translate': '/api/image-translate',
            'health': '/health',
            'test': '/api/test',
            'test_poster_environment': '/api/test/poster-environment'
        },
        'downloads': {
            'general': '/download/<filename>',
            'translated': '/download/translated/<filename>',
            'poster': '/download/poster/<filename>',
            'workflow': '/download/workflow/<folder>/<filename>',
            'image': '/download/image/<filename>'
        },
        'previews': {
            'poster_pdf': '/preview/poster/<filename>',
            'translated_pdf': '/preview/translated/<filename>',
            'workflow_pdf': '/preview/workflow/<folder>/<filename>'
        },
        'supported_languages': {
            'image_translation': ['en', 'zh', 'jp', 'ko', 'es', 'fr', 'th', 'ar', 'ru', 'pt', 'de', 'it', 'vi', 'hi'],
            'translation_pairs': [
                'en ↔ zh', 'en ↔ jp', 'zh ↔ jp', 'en ↔ ko', 'zh ↔ ko', 
                'en ↔ es', 'en ↔ fr', 'en ↔ th', 'en ↔ ar', 'en ↔ ru'
            ]
        }
    })

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.route('/api/webpage-google-translate', methods=['POST'])
def webpage_google_translate():
    """Google方式网页翻译API"""
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({
                'success': False, 
                'error': '请提供网页URL'
            }), 400
        
        url = data['url'].strip()
        if not url:
            return jsonify({
                'success': False, 
                'error': 'URL不能为空'
            }), 400
        
        if not (url.startswith('http://') or url.startswith('https://')):
            url = 'https://' + url
        
        print(f"开始处理URL: {url}")
        
        pdf_path, pdf_filename = capture_translated_pdf_for_api(url, '.')
        
        print(f"翻译完成，PDF文件: {pdf_filename}")
        
        return jsonify({
            'success': True,
            'message': '网页翻译完成',
            'original_url': url,
            'pdf_filename': pdf_filename,
            'download_url': f'/download/translated/{pdf_filename}',
            'file_size': os.path.getsize(pdf_path)
        })
        
    except Exception as e:
        print(f"翻译过程中出错: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'翻译失败: {str(e)}'
        }), 500

@app.route('/api/webpage-gpt-translate', methods=['POST'])
def webpage_gpt_translate():
    """GPT方式网页翻译API"""
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({
                'success': False, 
                'error': '请提供网页URL'
            }), 400
        
        url = data['url'].strip()
        api_key = data.get('api_key')
        
        if not url:
            return jsonify({
                'success': False, 
                'error': 'URL不能为空'
            }), 400
        
        if not (url.startswith('http://') or url.startswith('https://')):
            url = 'https://' + url
        
        print(f"开始GPT翻译处理URL: {url}")
        
        # 创建工作流实例
        workflow = WebTranslationWorkflow(api_key=api_key)
        
        # 步骤1: 获取网页
        fetch_result = workflow.fetch_webpage_simple(url)
        if not fetch_result["success"]:
            return jsonify({
                'success': False,
                'error': f'网页获取失败: {fetch_result["error"]}'
            }), 500
        
        # 步骤2: 翻译HTML
        translate_result = workflow.translate_html(fetch_result["html_path"])
        if not translate_result["success"]:
            return jsonify({
                'success': False,
                'error': f'翻译失败: {translate_result["error"]}'
            }), 500
        
        # 步骤3: 生成PDF
        pdf_result = workflow.generate_pdf_from_html_simple(translate_result["translated_path"])
        if not pdf_result["success"]:
            return jsonify({
                'success': False,
                'error': f'PDF生成失败: {pdf_result["error"]}'
            }), 500
        
        print(f"GPT翻译完成，PDF文件: {pdf_result['pdf_path']}")
        print(f"文件夹名称: {fetch_result['folder_name']}")
        print(f"PDF文件名: {os.path.basename(pdf_result['pdf_path'])}")
        print(f"生成的下载URL: /download/workflow/{fetch_result['folder_name']}/{os.path.basename(pdf_result['pdf_path'])}")
        
        return jsonify({
            'success': True,
            'message': 'GPT网页翻译完成',
            'original_url': url,
            'pdf_filename': os.path.basename(pdf_result['pdf_path']),
            'download_url': f'/download/workflow/{fetch_result["folder_name"]}/{os.path.basename(pdf_result["pdf_path"])}',
            'file_size': pdf_result['file_size'],
            'original_pdf_url': f'/download/workflow/{fetch_result["folder_name"]}/{os.path.basename(fetch_result["original_pdf_path"])}',
            'html_url': f'/download/workflow/{fetch_result["folder_name"]}/index_translated.html'
        })
        
    except Exception as e:
        print(f"GPT翻译过程中出错: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'GPT翻译失败: {str(e)}'
        }), 500

@app.route('/api/poster-translate', methods=['POST'])
def poster_translate():
    """海报翻译API（增强版）"""
    try:
        print("\n" + "="*50)
        print("🚀 开始海报翻译API请求处理")
        
        # 检查是否有文件上传
        if 'image' not in request.files:
            print("❌ 错误: 未找到上传的图像文件")
            return jsonify({
                'success': False,
                'error': '请上传海报图像文件',
                'details': '表单中缺少image字段'
            }), 400
        
        file = request.files['image']
        api_key = request.form.get('api_key')
        
        print(f"📄 接收文件: {file.filename}")
        print(f"🔑 API密钥: {'已提供' if api_key else '使用默认配置'}")
        
        if file.filename == '':
            print("❌ 错误: 文件名为空")
            return jsonify({
                'success': False,
                'error': '未选择文件',
                'details': '文件名为空'
            }), 400
        
        # 检查文件类型 - 增强版支持更多格式
        allowed_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff'}
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in allowed_extensions:
            print(f"❌ 错误: 不支持的文件格式: {file_ext}")
            return jsonify({
                'success': False,
                'error': '不支持的文件格式',
                'details': f'仅支持以下格式: {", ".join(allowed_extensions)}'
            }), 400
        
        # 保存上传的文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"poster_{timestamp}{file_ext}"
        upload_path = os.path.join('uploads', filename)
        file.save(upload_path)
        
        # 验证文件大小
        file_size = os.path.getsize(upload_path)
        print(f"📊 文件大小: {file_size:,} bytes")
        
        if file_size == 0:
            print("❌ 错误: 文件大小为0")
            return jsonify({
                'success': False,
                'error': '上传的文件无效',
                'details': '文件大小为0'
            }), 400
        
        print(f"💾 文件已保存: {upload_path}")
        
        # 创建海报翻译器实例（增强版）
        translator = PosterTranslator(api_key=api_key)
        
        # 检查运行环境
        print("\n" + "🔧" * 20 + " 环境检查 " + "🔧" * 20)
        check_result = translator.check_requirements_with_details()
        
        if not check_result['success']:
            print("❌ 环境检查失败")
            # 清理上传的文件
            try:
                os.remove(upload_path)
                print(f"🧹 已清理临时文件: {upload_path}")
            except Exception as e:
                print(f"⚠️ 清理临时文件失败: {e}")
            
            return jsonify({
                'success': False,
                'error': '运行环境检查失败',
                'details': check_result['error_summary'],
                'diagnostic_info': check_result['details'],
                'solutions': check_result['solutions'],
                'help_message': '请根据下方诊断信息解决环境问题后重试'
            }), 500
        
        # 设置输出文件路径
        output_base = os.path.join('poster_output', f"poster_{timestamp}")
        
        print(f"🎯 输出基础路径: {output_base}")
        
        # 使用增强版的完整翻译流程
        result = translator.translate_poster_complete(
            image_path=upload_path,
            output_base_name=output_base,
            clean_aux=True
        )
        
        # 清理上传的临时文件
        try:
            os.remove(upload_path)
            print(f"🧹 已清理临时文件: {upload_path}")
        except Exception as e:
            print(f"⚠️ 清理临时文件失败: {e}")
        
        if result['success']:
            print("🎉 海报翻译完成成功!")
            
            response_data = {
                'success': True,
                'message': '海报翻译完成',
                'latex_generated': True,
                'pdf_generated': True,
                'pdf_message': '编译成功',
                'tex_filename': os.path.basename(result['tex_file']),
                'pdf_filename': os.path.basename(result['pdf_file']),
                'latex_download_url': f'/download/poster/{os.path.basename(result["tex_file"])}',
                'pdf_download_url': f'/download/poster/{os.path.basename(result["pdf_file"])}',
                'latex_code_length': result['latex_code_length'],
                'file_size': os.path.getsize(result['pdf_file']),
                'processing_time': '完成',
                'details': {
                    'input_file': file.filename,
                    'input_size': file_size,
                    'output_tex': os.path.basename(result['tex_file']),
                    'output_pdf': os.path.basename(result['pdf_file']),
                    'latex_length': result['latex_code_length']
                }
            }
            
            print(f"📄 生成文件:")
            print(f"   - LaTeX: {response_data['tex_filename']}")
            print(f"   - PDF: {response_data['pdf_filename']}")
            print(f"   - LaTeX代码长度: {response_data['latex_code_length']} 字符")
            print(f"   - PDF文件大小: {response_data['file_size']:,} bytes")
            
            return jsonify(response_data)
            
        else:
            print(f"❌ 海报翻译失败: {result['error']}")
            
            return jsonify({
                'success': False,
                'error': '海报翻译失败',
                'details': result['error'],
                'latex_generated': False,
                'pdf_generated': False
            }), 500
        
    except Exception as e:
        print(f"❌ 海报翻译API发生异常: {str(e)}")
        
        # 清理可能的临时文件
        try:
            if 'upload_path' in locals() and os.path.exists(upload_path):
                os.remove(upload_path)
        except:
            pass
        
        return jsonify({
            'success': False,
            'error': f'海报翻译失败: {str(e)}',
            'details': '处理过程中发生异常'
        }), 500

# @app.route('/api/image-translate', methods=['POST'])
# def image_translate():
#     """百度图片翻译API"""
#     try:
#         print("\n" + "="*50)
#         print("🚀 开始百度图片翻译API请求处理")

#         if 'image' not in request.files:
#             print("❌ 错误: 未找到上传的图像文件")
#             return jsonify({
#                 'success': False,
#                 'error': '请上传图像文件',
#                 'details': '表单中缺少image字段'
#             }), 400
        
#         file = request.files['image']
#         api_key = request.form.get('api_key')
#         secret_key = request.form.get('secret_key')

#         print(f"📄 接收文件: {file.filename}")
#         print(f"🔑 API密钥: {'已提供' if api_key else '使用默认配置'}")
#         print(f"🔑 Secret密钥: {'已提供' if secret_key else '使用默认配置'}")

#         if file.filename == '':
#             print("❌ 错误: 文件名为空")
#             return jsonify({
#                 'success': False,
#                 'error': '未选择文件',
#                 'details': '文件名为空'
#             }), 400
        
#         # 检查文件类型
#         allowed_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff'}
#         file_ext = Path(file.filename).suffix.lower()
#         if file_ext not in allowed_extensions:
#             print(f"❌ 错误: 不支持的文件格式: {file_ext}")
#             return jsonify({
#                 'success': False,
#                 'error': '不支持的文件格式',
#                 'details': f'仅支持以下格式: {", ".join(allowed_extensions)}'
#             }), 400
        
#         # 保存上传的文件
#         timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#         filename = f"image_{timestamp}{file_ext}"
#         upload_path = os.path.join('uploads', filename)
#         file.save(upload_path)

#         print(f"💾 文件已保存: {upload_path}")

#         # 创建百度图片翻译器实例
#         baidu_translator = BaiduImageTranslationTester(api_key=api_key, secret_key=secret_key)

#         # 检查运行环境
#         if not baidu_translator.get_access_token():
#             print("❌ 环境检查失败")
#             # 清理上传的文件
#             try:
#                 os.remove(upload_path)
#             except:
#                 pass
#             return jsonify({
#                 'success': False,
#                 'error': '百度API密钥未配置或无效',
#                 'details': '请检查API密钥配置'
#             }), 500

#         # 设置翻译方向和贴图类型
#         from_lang = request.form.get('from_lang', 'en')
#         to_lang = request.form.get('to_lang', 'zh')
#         save_image = request.form.get('save_image', 'true').lower() == 'true'

#         print(f"🎯 翻译方向: {from_lang} -> {to_lang}")
#         print(f"📸 贴图类型: {'保存' if save_image else '不保存'}")

#         # 使用完整的图片翻译流程
#         result = baidu_translator.translate_image_complete(
#             image_path=upload_path,
#             from_lang=from_lang,
#             to_lang=to_lang,
#             save_image=save_image
#         )

#         # 保存原图到输出目录而不是删除
#         original_saved_path = None
#         try:
#             original_filename = f"original_{timestamp}{file_ext}"
#             original_saved_path = os.path.join('image_translation_output', original_filename)
            
#             # 复制原图到输出目录
#             import shutil
#             shutil.copy2(upload_path, original_saved_path)
#             print(f"📁 原图已保存到: {original_saved_path}")
            
#             # 删除临时上传文件
#             os.remove(upload_path)
#             print(f"🧹 已清理临时文件: {upload_path}")
#         except Exception as e:
#             print(f"⚠️ 处理原图时出错: {e}")
#             original_saved_path = None

#         if result['success']:
#             print("🎉 百度图片翻译完成成功!")
            
#             # 准备下载URL
#             download_url = None
#             original_image_url = None
            
#             if result['translated_image']:
#                 filename = os.path.basename(result['translated_image'])
#                 download_url = f'/download/image/{filename}'
            
#             if original_saved_path:
#                 original_filename = os.path.basename(original_saved_path)
#                 original_image_url = f'/download/image/{original_filename}'
            
#             response_data = {
#                 'success': True,
#                 'message': '百度图片翻译完成',
#                 'original_image': result['original_image'],
#                 'original_image_url': original_image_url,
#                 'translated_image': result['translated_image'],
#                 'text_info': result['text_info'],
#                 'translation_direction': result['translation_direction'],
#                 'has_translated_image': result['has_translated_image'],
#                 'file_size': os.path.getsize(result['translated_image']) if result['translated_image'] else 0,
#                 'download_url': download_url,
#                 'translated_filename': os.path.basename(result['translated_image']) if result['translated_image'] else None,
#                 'original_filename': os.path.basename(original_saved_path) if original_saved_path else None
#             }
            
#             print(f"📄 生成文件:")
#             print(f"   - 原始图片: {response_data['original_image']}")
#             print(f"   - 翻译图片: {response_data['translated_image']}")
#             print(f"   - 文本信息: {json.dumps(response_data['text_info'], ensure_ascii=False)}")
#             print(f"   - 翻译方向: {response_data['translation_direction']}")
#             print(f"   - 是否包含翻译图片: {response_data['has_translated_image']}")
#             print(f"   - 翻译图片文件大小: {response_data['file_size']:,} bytes")

#             return jsonify(response_data)
            
#         else:
#             print(f"❌ 百度图片翻译失败: {result['error']}")
            
#             return jsonify({
#                 'success': False,
#                 'error': '百度图片翻译失败',
#                 'details': result['error']
#             }), 500
        
#     except Exception as e:
#         print(f"❌ 百度图片翻译API发生异常: {str(e)}")
        
#         # 清理可能的临时文件
#         try:
#             if 'upload_path' in locals() and os.path.exists(upload_path):
#                 os.remove(upload_path)
#         except:
#             pass
        
#         return jsonify({
#             'success': False,
#             'error': f'百度图片翻译失败: {str(e)}',
#             'details': '处理过程中发生异常'
#         }), 500


@app.route('/api/image-translate', methods=['POST'])
def image_translate():
    """百度图片翻译API"""
    try:
        print("\n" + "="*50)
        print("🚀 开始百度图片翻译API请求处理")

        if 'image' not in request.files:
            print("❌ 错误: 未找到上传的图像文件")
            return jsonify({
                'success': False,
                'error': '请上传图像文件',
                'details': '表单中缺少image字段'
            }), 400

        file = request.files['image']

        # --- START: 这是我们修改的核心部分 ---
        print(f"📄 接收文件: {file.filename}")
        print("🔑 API密钥: 强制从服务器配置文件加载")
        print("🔑 Secret密钥: 强制从服务器配置文件加载")

        if file.filename == '':
            print("❌ 错误: 文件名为空")
            return jsonify({
                'success': False,
                'error': '未选择文件',
                'details': '文件名为空'
            }), 400

        # 检查文件类型
        allowed_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff'}
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in allowed_extensions:
            print(f"❌ 错误: 不支持的文件格式: {file_ext}")
            return jsonify({
                'success': False,
                'error': '不支持的文件格式',
                'details': f'仅支持以下格式: {", ".join(allowed_extensions)}'
            }), 400

        # 保存上传的文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"image_{timestamp}{file_ext}"
        upload_path = os.path.join('uploads', filename)
        file.save(upload_path)

        print(f"💾 文件已保存: {upload_path}")

        # 创建百度图片翻译器实例 (不传递任何参数)
        # 这会强制 __init__ 方法去调用 _load_key_from_file
        baidu_translator = BaiduImageTranslationTester()
        # --- END: 这是我们修改的核心部分 ---

        # 检查运行环境
        if not baidu_translator.get_access_token():
            print("❌ 环境检查失败")
            # 清理上传的文件
            try:
                os.remove(upload_path)
            except:
                pass
            return jsonify({
                'success': False,
                'error': '百度API密钥未配置或无效',
                'details': '请检查API密钥配置'
            }), 500

        # 设置翻译方向和贴图类型
        from_lang = request.form.get('from_lang', 'en')
        to_lang = request.form.get('to_lang', 'zh')
        save_image = request.form.get('save_image', 'true').lower() == 'true'

        print(f"🎯 翻译方向: {from_lang} -> {to_lang}")
        print(f"📸 贴图类型: {'保存' if save_image else '不保存'}")

        # 使用完整的图片翻译流程
        result = baidu_translator.translate_image_complete(
            image_path=upload_path,
            from_lang=from_lang,
            to_lang=to_lang,
            save_image=save_image
        )

        # 保存原图到输出目录而不是删除
        original_saved_path = None
        try:
            original_filename = f"original_{timestamp}{file_ext}"
            original_saved_path = os.path.join('image_translation_output', original_filename)

            # 复制原图到输出目录
            import shutil
            shutil.copy2(upload_path, original_saved_path)
            print(f"📁 原图已保存到: {original_saved_path}")

            # 删除临时上传文件
            os.remove(upload_path)
            print(f"🧹 已清理临时文件: {upload_path}")
        except Exception as e:
            print(f"⚠️ 处理原图时出错: {e}")
            original_saved_path = None

        if result['success']:
            print("🎉 百度图片翻译完成成功!")

            # 准备下载URL
            download_url = None
            original_image_url = None

            if result['translated_image']:
                filename = os.path.basename(result['translated_image'])
                download_url = f'/download/image/{filename}'

            if original_saved_path:
                original_filename = os.path.basename(original_saved_path)
                original_image_url = f'/download/image/{original_filename}'

            response_data = {
                'success': True,
                'message': '百度图片翻译完成',
                'original_image': result['original_image'],
                'original_image_url': original_image_url,
                'translated_image': result['translated_image'],
                'text_info': result['text_info'],
                'translation_direction': result['translation_direction'],
                'has_translated_image': result['has_translated_image'],
                'file_size': os.path.getsize(result['translated_image']) if result['translated_image'] else 0,
                'download_url': download_url,
                'translated_filename': os.path.basename(result['translated_image']) if result['translated_image'] else None,
                'original_filename': os.path.basename(original_saved_path) if original_saved_path else None
            }

            print(f"📄 生成文件:")
            print(f"   - 原始图片: {response_data['original_image']}")
            print(f"   - 翻译图片: {response_data['translated_image']}")
            print(f"   - 文本信息: {json.dumps(response_data['text_info'], ensure_ascii=False)}")
            print(f"   - 翻译方向: {response_data['translation_direction']}")
            print(f"   - 是否包含翻译图片: {response_data['has_translated_image']}")
            print(f"   - 翻译图片文件大小: {response_data['file_size']:,} bytes")

            return jsonify(response_data)

        else:
            print(f"❌ 百度图片翻译失败: {result['error']}")

            return jsonify({
                'success': False,
                'error': '百度图片翻译失败',
                'details': result['error']
            }), 500

    except Exception as e:
        print(f"❌ 百度图片翻译API发生异常: {str(e)}")

        # 清理可能的临时文件
        try:
            if 'upload_path' in locals() and os.path.exists(upload_path):
                os.remove(upload_path)
        except:
            pass

        return jsonify({
            'success': False,
            'error': f'百度图片翻译失败: {str(e)}',
            'details': '处理过程中发生异常'
        }), 500

# ========== 下载端点 ==========

@app.route('/download/<filename>')
def download_file(filename):
    """文件下载端点（downloads文件夹）"""
    try:
        file_path = os.path.join('downloads', filename)
        if not os.path.exists(file_path):
            return jsonify({'error': '文件不存在'}), 404
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
    except Exception as e:
        print(f"下载文件时出错: {str(e)}")
        return jsonify({'error': '下载失败'}), 500

@app.route('/download/translated/<filename>')
def download_translated_file(filename):
    """翻译文件下载端点（translated_snapshot文件夹）"""
    try:
        file_path = os.path.join('translated_snapshot', filename)
        if not os.path.exists(file_path):
            return jsonify({'error': '文件不存在'}), 404
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
    except Exception as e:
        print(f"下载翻译文件时出错: {str(e)}")
        return jsonify({'error': '下载失败'}), 500

@app.route('/preview/translated/<filename>')
def preview_translated_file(filename):
    """Google翻译PDF预览端点（用于iframe嵌入）"""
    try:
        file_path = os.path.join('translated_snapshot', filename)
        if not os.path.exists(file_path):
            return jsonify({'error': '文件不存在'}), 404
        
        # 设置响应头以支持iframe嵌入
        response = send_file(
            file_path,
            as_attachment=False,  # 关键：不强制下载
            mimetype='application/pdf',
            conditional=True  # 支持断点续传
        )
        
        # 完全移除所有可能阻止iframe的响应头
        response.headers['Content-Disposition'] = 'inline; filename=' + filename
        response.headers['Cache-Control'] = 'public, max-age=3600'
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = '*'
        
        # 移除所有可能的frame限制
        headers_to_remove = ['X-Frame-Options', 'Content-Security-Policy', 'X-Content-Type-Options']
        for header in headers_to_remove:
            if header in response.headers:
                del response.headers[header]
        
        print(f"📄 Google翻译PDF预览请求: {filename}")
        print(f"📄 响应头: {dict(response.headers)}")
        return response
        
    except Exception as e:
        print(f"Google翻译PDF预览时出错: {str(e)}")
        return jsonify({'error': 'PDF预览失败'}), 500

@app.route('/download/poster/<filename>')
def download_poster_file(filename):
    """海报文件下载端点"""
    try:
        file_path = os.path.join('poster_output', filename)
        if not os.path.exists(file_path):
            return jsonify({'error': '文件不存在'}), 404
        
        # 根据文件扩展名确定MIME类型
        file_ext = Path(filename).suffix.lower()
        if file_ext == '.pdf':
            mimetype = 'application/pdf'
        elif file_ext == '.tex':
            mimetype = 'text/plain'
        else:
            mimetype = 'application/octet-stream'
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype=mimetype
        )
    except Exception as e:
        print(f"下载海报文件时出错: {str(e)}")
        return jsonify({'error': '下载失败'}), 500

@app.route('/preview/poster/<filename>')
def preview_poster_file(filename):
    """海报PDF预览端点（用于iframe嵌入）"""
    try:
        print(f"🔍 海报PDF预览请求详情:")
        print(f"  - 请求文件名: {filename}")
        print(f"  - 请求方法: {request.method}")
        print(f"  - 请求URL: {request.url}")
        print(f"  - User-Agent: {request.headers.get('User-Agent', 'Unknown')}")
        
        file_path = os.path.join('poster_output', filename)
        print(f"  - 目标文件路径: {file_path}")
        print(f"  - 文件是否存在: {os.path.exists(file_path)}")
        
        if not os.path.exists(file_path):
            print(f"❌ 文件不存在: {file_path}")
            return jsonify({'error': '文件不存在', 'path': file_path}), 404
        
        # 检查文件扩展名
        file_ext = Path(filename).suffix.lower()
        if file_ext != '.pdf':
            print(f"❌ 文件类型错误: {file_ext}")
            return jsonify({'error': '只支持PDF文件预览'}), 400
        
        # 设置响应头以支持iframe嵌入
        response = send_file(
            file_path,
            as_attachment=False,  # 关键：不强制下载
            mimetype='application/pdf',
            conditional=True  # 支持断点续传
        )
        
        # 完全移除所有可能阻止iframe的响应头
        response.headers['Content-Disposition'] = 'inline; filename=' + filename
        response.headers['Cache-Control'] = 'public, max-age=3600'
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = '*'
        
        # 移除所有可能的frame限制
        headers_to_remove = ['X-Frame-Options', 'Content-Security-Policy', 'X-Content-Type-Options']
        for header in headers_to_remove:
            if header in response.headers:
                del response.headers[header]
        
        print(f"📄 海报PDF预览请求: {filename}")
        print(f"📄 响应头: {dict(response.headers)}")
        return response
        
    except Exception as e:
        print(f"PDF预览时出错: {str(e)}")
        return jsonify({'error': 'PDF预览失败'}), 500

@app.route('/download/workflow/<folder_name>/<filename>')
def download_workflow_file(folder_name, filename):
    """工作流程文件下载端点"""
    try:
        file_path = os.path.join('web_translation_output', folder_name, 'original_snapshot', filename)
        print(f"🔍 下载请求: folder={folder_name}, file={filename}")
        print(f"🔍 查找文件路径: {file_path}")
        print(f"🔍 文件是否存在: {os.path.exists(file_path)}")
        
        if not os.path.exists(file_path):
            # 列出目录内容以帮助调试
            dir_path = os.path.join('web_translation_output', folder_name, 'original_snapshot')
            if os.path.exists(dir_path):
                files_in_dir = os.listdir(dir_path)
                print(f"🔍 目录中的文件: {files_in_dir}")
            else:
                print(f"🔍 目录不存在: {dir_path}")
            return jsonify({'error': f'文件不存在: {file_path}'}), 404
        
        # 根据文件扩展名确定MIME类型
        file_ext = Path(filename).suffix.lower()
        if file_ext == '.pdf':
            mimetype = 'application/pdf'
        elif file_ext == '.html':
            mimetype = 'text/html'
        else:
            mimetype = 'application/octet-stream'
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype=mimetype
        )
    except Exception as e:
        print(f"下载工作流程文件时出错: {str(e)}")
        return jsonify({'error': '下载失败'}), 500

@app.route('/preview/workflow/<folder_name>/<filename>')
def preview_workflow_file(folder_name, filename):
    """工作流程PDF预览端点（用于iframe嵌入）"""
    try:
        file_path = os.path.join('web_translation_output', folder_name, 'original_snapshot', filename)
        print(f"🔍 预览请求: folder={folder_name}, file={filename}")
        print(f"🔍 查找文件路径: {file_path}")
        
        if not os.path.exists(file_path):
            return jsonify({'error': '文件不存在'}), 404
        
        # 检查文件扩展名
        file_ext = Path(filename).suffix.lower()
        if file_ext != '.pdf':
            return jsonify({'error': '只支持PDF文件预览'}), 400
        
        # 设置响应头以支持iframe嵌入
        response = send_file(
            file_path,
            as_attachment=False,  # 关键：不强制下载
            mimetype='application/pdf',
            conditional=True  # 支持断点续传
        )
        
        # 完全移除所有可能阻止iframe的响应头
        response.headers['Content-Disposition'] = 'inline; filename=' + filename
        response.headers['Cache-Control'] = 'public, max-age=3600'
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = '*'
        
        # 移除所有可能的frame限制
        headers_to_remove = ['X-Frame-Options', 'Content-Security-Policy', 'X-Content-Type-Options']
        for header in headers_to_remove:
            if header in response.headers:
                del response.headers[header]
        
        print(f"📄 工作流程PDF预览请求: {filename}")
        print(f"📄 响应头: {dict(response.headers)}")
        return response
        
    except Exception as e:
        print(f"网页PDF预览时出错: {str(e)}")
        return jsonify({'error': 'PDF预览失败'}), 500

@app.route('/download/image/<filename>')
def download_image_file(filename):
    """图片翻译文件下载端点"""
    try:
        file_path = os.path.join('image_translation_output', filename)
        if not os.path.exists(file_path):
            return jsonify({'error': '文件不存在'}), 404
        
        # 根据文件扩展名确定MIME类型
        file_ext = Path(filename).suffix.lower()
        if file_ext in ['.jpg', '.jpeg']:
            mimetype = 'image/jpeg'
        elif file_ext == '.png':
            mimetype = 'image/png'
        elif file_ext == '.gif':
            mimetype = 'image/gif'
        elif file_ext == '.bmp':
            mimetype = 'image/bmp'
        elif file_ext == '.tiff':
            mimetype = 'image/tiff'
        else:
            mimetype = 'application/octet-stream'
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype=mimetype
        )
    except Exception as e:
        print(f"下载图片翻译文件时出错: {str(e)}")
        return jsonify({'error': '下载失败'}), 500

@app.route('/api/test', methods=['GET'])
def test_api():
    """测试API端点"""
    return jsonify({
        'success': True,
        'message': '后端API正常运行',
        'timestamp': datetime.now().isoformat(),
        'chrome_available': check_chrome_availability(),
        'pyppeteer_available': PYPPETEER_AVAILABLE,
        'features': {
            'google_translate': True,
            'gpt_translate': True,
            'poster_translate': True,
            'baidu_image_translate': True,
            'pdf_preview': True
        }
    })

@app.route('/api/test/poster-environment', methods=['GET', 'POST'])
def test_poster_environment():
    """测试海报翻译环境检查端点"""
    try:
        print("\n" + "🧪" * 20 + " 环境测试 " + "🧪" * 20)
        
        # 获取API密钥（如果通过POST提供）
        api_key = None
        if request.method == 'POST':
            data = request.get_json()
            if data:
                api_key = data.get('api_key')
        
        # 创建海报翻译器实例进行测试
        translator = PosterTranslator(api_key=api_key)
        
        # 执行详细环境检查
        check_result = translator.check_requirements_with_details()
        
        if check_result['success']:
            print("🎉 环境测试通过!")
            return jsonify({
                'success': True,
                'message': '海报翻译环境检查通过',
                'timestamp': datetime.now().isoformat(),
                'environment_status': 'healthy'
            })
        else:
            print("❌ 环境测试失败")
            return jsonify({
                'success': False,
                'message': '海报翻译环境检查失败',
                'error': check_result['error_summary'],
                'diagnostic_info': check_result['details'],
                'solutions': check_result['solutions'],
                'timestamp': datetime.now().isoformat(),
                'environment_status': 'unhealthy'
            })
            
    except Exception as e:
        print(f"❌ 环境测试异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '环境测试过程中发生异常',
            'error': str(e),
            'timestamp': datetime.now().isoformat(),
            'environment_status': 'error'
        }), 500

@app.route('/api/debug/pdf-files')
def debug_pdf_files():
    """调试端点：列出所有可用的PDF文件"""
    try:
        files = {}
        
        # 检查海报输出目录
        poster_dir = 'poster_output'
        if os.path.exists(poster_dir):
            poster_files = [f for f in os.listdir(poster_dir) if f.endswith('.pdf')]
            files['poster'] = poster_files
        
        # 检查翻译快照目录
        translated_dir = 'translated_snapshot'
        if os.path.exists(translated_dir):
            translated_files = [f for f in os.listdir(translated_dir) if f.endswith('.pdf')]
            files['translated'] = translated_files
        
        # 检查工作流程输出目录
        workflow_base = 'web_translation_output'
        if os.path.exists(workflow_base):
            workflow_files = {}
            for folder in os.listdir(workflow_base):
                folder_path = os.path.join(workflow_base, folder, 'original_snapshot')
                if os.path.exists(folder_path):
                    pdf_files = [f for f in os.listdir(folder_path) if f.endswith('.pdf')]
                    if pdf_files:
                        workflow_files[folder] = pdf_files
            files['workflow'] = workflow_files
        
        return jsonify({
            'success': True,
            'files': files,
            'message': '文件列表获取成功'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/test/pdf-preview')
def test_pdf_preview():
    """测试PDF预览功能"""
    try:
        # 创建一个简单的测试PDF响应
        from flask import make_response
        
        # 返回一个简单的PDF测试内容
        test_content = """<!DOCTYPE html>
<html>
<head><title>PDF预览测试</title></head>
<body>
<h1>PDF预览测试页面</h1>
<p>如果您看到这个页面，说明预览端点工作正常。</p>
<p>时间戳: %s</p>
</body>
</html>""" % datetime.now().isoformat()
        
        response = make_response(test_content)
        response.headers['Content-Type'] = 'text/html'
        response.headers['Content-Disposition'] = 'inline'
        
        # 移除所有可能的frame限制
        headers_to_remove = ['X-Frame-Options', 'Content-Security-Policy', 'X-Content-Type-Options']
        for header in headers_to_remove:
            if header in response.headers:
                del response.headers[header]
        
        return response
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def check_chrome_availability():
    """检查Chrome是否可用"""
    try:
        driver = setup_chrome()
        driver.quit()
        return True
    except Exception as e:
        print(f"Chrome检查失败: {str(e)}")
        return False

if __name__ == '__main__':
    print("🚀 启动翻译平台后端服务 - 增强版 v2.1...")
    print("✨ 新增功能: PDF预览支持、智能图片布局、详细状态日志")
    print("📋 API端点:")
    print("   - GET  /               主页和API信息")
    print("   - GET  /health         健康检查")
    print("   - POST /api/webpage-google-translate  Google网页翻译")
    print("   - POST /api/webpage-gpt-translate     GPT网页翻译（增强版）")
    print("   - POST /api/poster-translate          海报翻译")
    print("   - POST /api/image-translate          百度图片翻译")
    print("   - GET  /api/test       测试API")
    print("   - GET/POST /api/test/poster-environment  测试海报翻译环境")
    print()
    print("📥 下载端点:")
    print("   - GET  /download/<filename>           通用文件下载")
    print("   - GET  /download/translated/<filename> Google翻译文件下载")
    print("   - GET  /download/poster/<filename>    海报翻译文件下载")
    print("   - GET  /download/workflow/<folder>/<file> GPT翻译文件下载")
    print("   - GET  /download/image/<filename>     图片翻译文件下载")
    print()
    print("👁️ PDF预览端点:")
    print("   - GET  /preview/poster/<filename>     海报PDF预览")
    print("   - GET  /preview/translated/<filename> Google翻译PDF预览")
    print("   - GET  /preview/workflow/<folder>/<file> GPT翻译PDF预览")
    print()
    print("🌐 前端页面请访问: integrated_translation_app copy.html")
    print("💡 确保Chrome浏览器已安装并可用")
    print("🔑 对于GPT翻译和海报翻译，请设置OpenAI API密钥")
    print("📄 PDF缩放比例: 90% (更紧凑的页面显示)")
    print("🎨 图片预览: 智能布局优化，自适应容器尺寸")
    print("🔧 增强功能: PDF iframe预览、自动重试、详细日志")
    print()
    
    app.run(debug=True, host='0.0.0.0', port=5000) 