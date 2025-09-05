"""
瀏覽器自動化模組

直接整合 browser-use 功能，無需 MCP 服務器
使用本地 browser-use 實例處理瀏覽器操作
"""

import os
import asyncio
import logging
import time
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv
import json
import base64
from io import BytesIO

# 載入環境變數
load_dotenv()

# 設置日誌 - 配置 UTF-8 編碼處理
browser_logger = logging.getLogger('browser_automation')

# 自定義日誌格式器，處理 Unicode 字符
class SafeFormatter(logging.Formatter):
    """安全的日誌格式器，處理 Unicode 編碼問題"""
    def format(self, record):
        try:
            # 先嘗試正常格式化
            result = super().format(record)
            # 過濾或替換有問題的 Unicode 字符
            result = result.encode('utf-8', errors='ignore').decode('utf-8')
            return result
        except UnicodeEncodeError:
            # 如果仍有問題，使用安全的 ASCII 替換
            safe_msg = str(record.getMessage()).encode('ascii', errors='ignore').decode('ascii')
            return f"{record.levelname}: {safe_msg}"

# 配置瀏覽器日誌處理器
def configure_browser_logging():
    """配置瀏覽器相關的日誌處理，避免 Unicode 錯誤"""
    # 完全禁用 browser-use 相關的所有日誌記錄器
    loggers_to_disable = [
        'browser_use',
        'bubus',
        'browser_use.agent',
        'browser_use.agent.service',
        'browser_use.sync.service',
        'cdp_use.client',
        'httpcore',
        'httpx'
    ]
    
    for logger_name in loggers_to_disable:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.CRITICAL + 1)  # 設置到最高級別以上，徹底禁用
        logger.disabled = True
        # 清除現有的處理器
        logger.handlers.clear()
        logger.propagate = False
    
    # 為 browser_automation 設置安全的處理器
    if not browser_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(SafeFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        browser_logger.addHandler(handler)
    
    browser_logger.info("瀏覽器日誌配置完成，已完全禁用 browser-use 日誌輸出")

# 設置環境變量禁用遙測和詳細日誌
os.environ.setdefault('BROWSER_USE_DISABLE_TELEMETRY', 'true')
os.environ.setdefault('BROWSER_USE_LOG_LEVEL', 'ERROR')
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

# 初始化安全日誌配置
configure_browser_logging()

class BrowserAutomation:
    """瀏覽器自動化管理類"""
    
    def __init__(self):
        self.headless = os.getenv("BROWSER_USE_HEADLESS", "false").lower() == "true"
        self.executable_path = os.getenv("BROWSER_USE_EXECUTABLE_PATH", "")
        self.timeout = int(os.getenv("MCP_BROWSER_TIMEOUT", "30"))
        self.retry_count = int(os.getenv("MCP_BROWSER_RETRY_COUNT", "3"))
        self.max_session_time = int(os.getenv("BROWSER_SESSION_MAX_TIME", "300"))
        
        self._agent = None
        self._session_start_time = None
        
        browser_logger.info("瀏覽器自動化模組初始化完成")
        browser_logger.info(f"配置: headless={self.headless}, timeout={self.timeout}s")
    
    async def _ensure_agent(self):
        """確保 browser-use agent 已初始化 - 增強穩定性"""
        try:
            if self._agent is None or self._is_session_expired():
                browser_logger.info("初始化新的 browser-use agent")
                
                # 確保先清理舊的資源
                await self._cleanup_agent()
                
                # 動態導入 browser-use - 延遲導入避免日誌問題
                from browser_use import Agent, Browser, ChatGoogle
                
                # 使用 Google Gemini 避免 ChatOpenAI 兼容性問題
                llm = ChatGoogle(
                    model="gemini-2.5-flash",
                    temperature=0.1,
                    api_key=os.getenv("GOOGLE_API_KEY")
                )
                
                # 創建瀏覽器配置 - 使用官方支持的參數
                browser_config = {
                    'headless': self.headless,
                    # 設定瀏覽器視窗大小
                    'window_size': {'width': 1280, 'height': 720}
                }
                
                # 添加可選配置
                if self.executable_path:
                    browser_config['user_data_dir'] = os.path.dirname(self.executable_path)
                
                # 創建瀏覽器實例，使用官方推薦的簡化配置
                try:
                    browser = Browser(**browser_config)
                except Exception as browser_error:
                    browser_logger.warning(f"使用配置創建瀏覽器失敗: {str(browser_error)}")
                    # 回退到最基本配置
                    browser = Browser(headless=self.headless)
                
                # 創建 agent，使用官方推薦的配置
                self._agent = Agent(
                    task="Browser automation agent ready",
                    llm=llm,
                    browser=browser,
                    # 使用官方推薦的穩定性參數
                    max_failures=3,  # 官方預設值
                    step_timeout=120  # 官方推薦的步驟超時（秒）
                )
                
                # 禁用 agent 內部的一些日誌記錄器
                if hasattr(self._agent, 'logger'):
                    self._agent.logger.setLevel(logging.CRITICAL + 1)
                    self._agent.logger.disabled = True
                
                self._session_start_time = time.time()
                browser_logger.info("Browser agent 使用 Gemini 初始化成功")
                
        except Exception as e:
            error_msg = str(e)
            browser_logger.error(f"初始化 browser agent 失敗: {error_msg}")
            
            if "GOOGLE_API_KEY" in error_msg:
                browser_logger.error("請確保 GOOGLE_API_KEY 環境變數已正確設置")
            elif "chrome" in error_msg.lower() or "browser" in error_msg.lower():
                browser_logger.error("請確保系統已安裝 Chrome 瀏覽器或正確設置瀏覽器路徑")
            
            # 清理失敗的初始化嘗試
            self._agent = None
            raise
    
    def _is_session_expired(self) -> bool:
        """檢查會話是否過期"""
        if self._session_start_time is None:
            return True
        return (time.time() - self._session_start_time) > self.max_session_time
    
    async def _execute_with_retry(self, task: str, operation_type: str = "general") -> Dict[str, Any]:
        """執行瀏覽器任務並重試 - 增強錯誤處理"""
        last_error = None
        
        for attempt in range(self.retry_count):
            try:
                browser_logger.info(f"執行瀏覽器任務 (嘗試 {attempt + 1}/{self.retry_count}): {operation_type}")
                browser_logger.info(f"任務描述: {task[:100]}...")
                
                await self._ensure_agent()
                
                # 更新 agent 的任務
                self._agent.task = task
                
                # 執行任務，使用官方推薦的 AsyncIO 模式
                start_time = time.time()
                try:
                    # 使用官方推薦的 agent.run() 方法
                    result = await self._agent.run()
                except asyncio.TimeoutError:
                    raise TimeoutError(f"Browser task timed out after step_timeout")
                except Exception as e:
                    # 將其他異常重新拋出，讓外層錯誤處理器處理
                    raise
                
                end_time = time.time()
                browser_logger.info(f"瀏覽器任務完成，耗時: {end_time - start_time:.2f}秒")
                
                # 提取結果
                response_text = ""
                if hasattr(result, 'messages') and result.messages:
                    # 從消息歷史中提取最後的 AI 回應
                    for msg in reversed(result.messages):
                        if hasattr(msg, 'type') and msg.type == 'ai' and hasattr(msg, 'content'):
                            response_text = msg.content
                            break
                elif hasattr(result, 'content'):
                    response_text = result.content
                else:
                    response_text = str(result)
                
                return {
                    "success": True,
                    "result": response_text,
                    "operation_type": operation_type,
                    "execution_time": end_time - start_time,
                    "attempt": attempt + 1
                }
                
            except (RuntimeError, OSError, ConnectionError, TimeoutError) as e:
                error_msg = str(e)
                last_error = e
                
                # 基於官方建議的錯誤分類和處理
                if "cannot schedule new futures after shutdown" in error_msg:
                    browser_logger.warning(f"AsyncIO 事件循環錯誤，重新創建 agent")
                elif "max_failures" in error_msg.lower() or "consecutive failures" in error_msg.lower():
                    browser_logger.warning(f"達到最大失敗次數限制，重新初始化 agent")
                elif "step_timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                    browser_logger.warning(f"步驟超時，調整任務描述或增加具體性")
                elif "navigation" in error_msg.lower() or "page" in error_msg.lower():
                    browser_logger.warning(f"頁面導航問題，嘗試使用鍵盤導航作為備選")
                elif any(net_err in error_msg.lower() for net_err in ['connection', 'network', 'dns']):
                    browser_logger.warning(f"網絡連接問題: {error_msg}")
                else:
                    browser_logger.warning(f"嘗試 {attempt + 1} 失敗: {error_msg}")
                
                # 徹底清理 agent 和相關資源
                await self._cleanup_agent()
                
                if attempt < self.retry_count - 1:
                    wait_time = min(2 ** attempt, 10)  # 最大等待 10 秒
                    browser_logger.info(f"等待 {wait_time} 秒後重試...")
                    await asyncio.sleep(wait_time)
                    
            except Exception as e:
                last_error = e
                error_msg = str(e)
                browser_logger.warning(f"未預期的錯誤 (嘗試 {attempt + 1}): {error_msg}")
                
                # 對於其他錯誤也進行清理
                await self._cleanup_agent()
                
                if attempt < self.retry_count - 1:
                    await asyncio.sleep(2 ** attempt)
        
        # 所有重試都失敗
        browser_logger.error(f"瀏覽器任務執行失敗，已重試 {self.retry_count} 次")
        browser_logger.error(f"最後錯誤: {str(last_error)}")
        
        return {
            "success": False,
            "error": str(last_error),
            "operation_type": operation_type,
            "attempts": self.retry_count
        }
    
    async def _cleanup_agent(self):
        """徹底清理 agent 和相關資源"""
        try:
            if self._agent:
                # 嘗試關閉瀏覽器會話
                if hasattr(self._agent, 'browser') and self._agent.browser:
                    try:
                        await self._agent.browser.close()
                    except Exception:
                        pass  # 忽略清理過程中的錯誤
                
                # 清理 agent 實例
                self._agent = None
            
            # 重置會話時間
            self._session_start_time = None
            
        except Exception as e:
            browser_logger.warning(f"清理 agent 時發生錯誤: {str(e)}")
        
        # 等待一小段時間讓系統清理
        await asyncio.sleep(0.5)
    
    async def navigate_and_extract(self, url: str, extraction_goal: str) -> Dict[str, Any]:
        """導航到指定 URL 並提取資訊"""
        task = f"""
Navigate to {url} and extract the following information: {extraction_goal}

DETAILED INSTRUCTIONS:
1. Go directly to the URL: {url}
2. Wait for the page to fully load (check that all main content is visible)
3. Extract the requested information: {extraction_goal}
4. Structure your findings clearly with headers and bullet points
5. Include relevant links or contact information if available

ERROR RECOVERY STRATEGIES:
- If the page doesn't load, try refreshing once
- If links don't work, use keyboard navigation (Tab key)
- If content is blocked, look for alternative sections
- If images don't load, focus on text content
- Report any technical issues you encounter

EXPECTED OUTPUT:
Provide a clear, structured summary of the extracted information with specific details found on the page.
"""
        return await self._execute_with_retry(task, "navigate_and_extract")
    
    async def search_and_analyze(self, search_query: str, analysis_goal: str) -> Dict[str, Any]:
        """執行搜尋並分析結果"""
        task = f"""
Search for "{search_query}" and analyze the results for: {analysis_goal}

STEP-BY-STEP INSTRUCTIONS:
1. Go to Google (www.google.com)
2. Enter the search query: "{search_query}"
3. Press Enter or click the Search button
4. Wait for results to load completely
5. Review the first 5-10 search results
6. Click on 2-3 relevant links to gather detailed information
7. Analyze findings according to: {analysis_goal}

ERROR RECOVERY STRATEGIES:
- If Google doesn't load, try a different search engine
- If search doesn't work, type query manually in address bar
- If links don't open, use right-click "Open in new tab"
- If pages are slow, wait longer before moving on
- Use keyboard navigation (Tab, Enter) if mouse clicks fail

ANALYSIS REQUIREMENTS:
- Focus specifically on: {analysis_goal}
- Provide key findings with sources
- Include relevant URLs for verification
- Structure information with clear headers
- Highlight the most important insights

EXPECTED OUTPUT:
A comprehensive analysis addressing the analysis goal with supporting evidence from multiple sources.
"""
        return await self._execute_with_retry(task, "search_and_analyze")
    
    async def verify_medical_claim(self, claim: str, source_urls: Optional[List[str]] = None) -> Dict[str, Any]:
        """驗證醫療聲明"""
        task = f"""
Verify the medical claim: "{claim}"

Please:
1. Search for reliable medical sources about this claim
2. Visit authoritative medical websites (like medical institutions, government health agencies)
3. Compare the claim against established medical evidence
4. Look for any contradictory information
5. Provide a balanced assessment of the claim's accuracy

If specific source URLs were provided: {source_urls if source_urls else "None specified"}

Focus on providing evidence-based verification from credible medical sources.
"""
        return await self._execute_with_retry(task, "verify_medical_claim")
    
    async def extract_hospital_info(self, hospital_name: str, location: str = "") -> Dict[str, Any]:
        """提取醫院或診所資訊"""
        location_info = f" in {location}" if location else ""
        task = f"""
Find information about "{hospital_name}"{location_info}

Please:
1. Search for the hospital/clinic website or official information
2. Extract key details like:
   - Full name and address
   - Contact information (phone, website)
   - Available departments/specialties
   - Operating hours
   - Any special services or facilities
3. Verify the information from multiple sources if possible
4. Report if the facility is currently operational

Provide comprehensive, accurate information about this medical facility.
"""
        return await self._execute_with_retry(task, "extract_hospital_info")
    
    async def close_session(self):
        """關閉瀏覽器會話"""
        try:
            if self._agent and hasattr(self._agent, 'browser'):
                await self._agent.browser.close()
                browser_logger.info("瀏覽器會話已關閉")
            self._agent = None
            self._session_start_time = None
        except Exception as e:
            browser_logger.warning(f"關閉瀏覽器會話時發生錯誤: {str(e)}")

# 全域瀏覽器自動化實例
browser_automation = BrowserAutomation()

async def cleanup_browser():
    """清理瀏覽器資源"""
    await browser_automation.close_session()