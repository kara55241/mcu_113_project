"""
簡單測試 Django 靜態文件配置
"""
import os
import django
from django.conf import settings
from django.core.management import execute_from_command_line

# 設置 Django 環境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

# 檢查設置
print("=== Django 靜態文件配置檢查 ===")
print(f"DEBUG: {settings.DEBUG}")
print(f"STATIC_URL: {settings.STATIC_URL}")
print(f"STATICFILES_DIRS: {settings.STATICFILES_DIRS}")

# 檢查文件是否存在
import pathlib
static_dir = settings.STATICFILES_DIRS[0]
print(f"\n=== 靜態文件目錄檢查 ===")
print(f"Static directory: {static_dir}")
print(f"Directory exists: {pathlib.Path(static_dir).exists()}")

test_files = ['test.txt', 'css/styles.css', 'js/app-core.js', 'sw.js']
for file in test_files:
    file_path = pathlib.Path(static_dir) / file
    print(f"{file}: {file_path.exists()}")

# 檢查URL配置
from django.urls import get_resolver
resolver = get_resolver()
print(f"\n=== URL配置檢查 ===")
print(f"Total URL patterns: {len(resolver.url_patterns)}")

# 檢查是否有靜態文件URL
static_patterns = []
for pattern in resolver.url_patterns:
    pattern_str = str(pattern)
    if 'static' in pattern_str.lower():
        static_patterns.append(pattern_str)

print(f"Static URL patterns found: {len(static_patterns)}")
for pattern in static_patterns:
    print(f"  {pattern}")

# 測試 URL 解析
from django.urls import reverse, resolve, NoReverseMatch
try:
    # 嘗試解析靜態文件 URL
    from django.test import RequestFactory
    factory = RequestFactory()
    request = factory.get('/static/test.txt')
    
    try:
        match = resolve('/static/test.txt')
        print(f"\n=== URL解析測試 ===")
        print(f"URL '/static/test.txt' resolved to: {match.func}")
        print(f"URL name: {match.url_name}")
        print(f"Args: {match.args}")
        print(f"Kwargs: {match.kwargs}")
    except:
        print(f"\n=== URL解析測試 ===")
        print("ERROR: Could not resolve '/static/test.txt'")
        
except Exception as e:
    print(f"Error during URL testing: {e}")

print("\n=== 完成 ===")