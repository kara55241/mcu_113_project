import os
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

print("BASE_DIR:", settings.BASE_DIR)
print("STATIC_URL:", settings.STATIC_URL)
print("STATICFILES_DIRS:", settings.STATICFILES_DIRS)
print("DEBUG:", settings.DEBUG)

# 檢查靜態文件是否存在
import pathlib
static_dir = settings.STATICFILES_DIRS[0]
print(f"Static directory exists: {pathlib.Path(static_dir).exists()}")
print(f"sw.js exists: {(pathlib.Path(static_dir) / 'sw.js').exists()}")

# 列出靜態目錄內容
if pathlib.Path(static_dir).exists():
    print("Static directory contents:")
    for item in pathlib.Path(static_dir).iterdir():
        print(f"  {item.name}")