import os
import django
from django.conf import settings
from django.urls import reverse, resolve
from django.test import RequestFactory
from django.views.static import serve

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

# 測試靜態文件路徑
print(f"BASE_DIR: {settings.BASE_DIR}")
print(f"STATICFILES_DIRS: {settings.STATICFILES_DIRS}")
print(f"DEBUG: {settings.DEBUG}")

# 檢查文件是否存在
import pathlib
static_dir = settings.BASE_DIR / 'static'
print(f"Static dir exists: {static_dir.exists()}")
print(f"sw.js exists: {(static_dir / 'sw.js').exists()}")

# 測試直接serve
from django.http import HttpRequest
request = HttpRequest()
request.method = 'GET'

try:
    response = serve(request, 'sw.js', document_root=static_dir)
    print(f"Direct serve response: {response.status_code}")
    print(f"Content type: {response.get('Content-Type', 'Not set')}")
except Exception as e:
    print(f"Direct serve error: {e}")

# 檢查URL配置
from django.urls import get_resolver
resolver = get_resolver()
print(f"URL patterns: {len(resolver.url_patterns)}")
for pattern in resolver.url_patterns[:5]:  # 只顯示前5個
    print(f"  {pattern}")