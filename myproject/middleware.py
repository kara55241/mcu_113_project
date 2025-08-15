# myproject/middleware.py
from django.middleware.security import SecurityMiddleware

class CustomSecurityMiddleware(SecurityMiddleware):
    """自定義安全中間件，添加必要的安全標頭"""
    
    def process_request(self, request):
        """處理HTTPS重定向"""
        if request.headers.get('x-forwarded-proto') == 'https':
            request.is_secure = lambda: True
        return None
    
    def process_response(self, request, response):
        # 先執行父類的處理
        response = super().process_response(request, response)
        
        # 添加必要的安全標頭
        
        # 添加 X-Content-Type-Options
        if 'X-Content-Type-Options' not in response:
            response['X-Content-Type-Options'] = 'nosniff'
        
        # 使用 Cache-Control 代替 Expires
        if 'Expires' in response:
            del response['Expires']
        
        # 確保 Cache-Control 存在
        if 'Cache-Control' not in response:
            # 靜態資源使用長期緩存
            if request.path.startswith('/static/'):
                response['Cache-Control'] = 'max-age=31536000, immutable'
            else:
                response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        
        # 添加 Content-Security-Policy 替代 X-Frame-Options
        if 'X-Frame-Options' in response:
            del response['X-Frame-Options']
        
        # 設置全面但安全的 CSP
        response['Content-Security-Policy'] = "frame-ancestors 'self'; default-src 'self'; script-src 'self' https://maps.googleapis.com https://cdnjs.cloudflare.com https://ajax.googleapis.com 'unsafe-inline' 'unsafe-eval'; connect-src 'self' https://*.googleapis.com; img-src 'self' data: https://*.googleapis.com https://*.gstatic.com https://*.ggpht.com; style-src 'self' https://fonts.googleapis.com https://cdnjs.cloudflare.com 'unsafe-inline'; font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com;"
        
        # 移除 X-XSS-Protection 標頭，因為現代瀏覽器不再需要它
        if 'X-XSS-Protection' in response:
            del response['X-XSS-Protection']
        
        return response