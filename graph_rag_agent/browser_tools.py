"""
瀏覽器工具函數

將瀏覽器自動化功能包裝為 LangGraph 工具
"""

import asyncio
import logging
import time
from langchain_core.tools import tool
from typing import Annotated

# 設置日誌
browser_tools_logger = logging.getLogger('browser_tools')

try:
    from .browser_automation import browser_automation
except ImportError:
    from browser_automation import browser_automation

@tool(name_or_callable='browser_navigate_and_extract')
def browser_navigate_and_extract(url: str, extraction_goal: str) -> str:
    """
    Navigate to a specific URL and extract information from the webpage.
    
    Use this tool when you need to:
    - Visit a specific website or webpage
    - Extract specific information from a known URL
    - Get content from medical institutions or health authority websites
    - Verify information on official websites
    
    Args:
        url: The URL to navigate to (must be a valid HTTP/HTTPS URL)
        extraction_goal: What specific information to extract from the page
        
    Returns:
        Extracted information from the webpage in a structured format
    """
    browser_tools_logger.info(f"[TOOL] BROWSER_NAVIGATE_AND_EXTRACT 啟動")
    browser_tools_logger.info(f"    目標 URL: {url}")
    browser_tools_logger.info(f"    提取目標: {extraction_goal[:100]}...")
    
    start_time = time.time()
    
    try:
        # 使用官方建議的 asyncio.run() 模式 
        def async_main():
            return asyncio.run(browser_automation.navigate_and_extract(url, extraction_goal))
        
        # 檢查是否在現有的事件循環中
        try:
            loop = asyncio.get_running_loop()
            # 在新線程中執行，避免嵌套事件循環問題
            import concurrent.futures
            import threading
            result = None
            exception = None
            
            def run_in_thread():
                nonlocal result, exception
                try:
                    result = asyncio.run(browser_automation.navigate_and_extract(url, extraction_goal))
                except Exception as e:
                    exception = e
            
            thread = threading.Thread(target=run_in_thread)
            thread.start()
            thread.join(timeout=180)  # 3分鐘超時
            
            if thread.is_alive():
                raise TimeoutError("Browser task timed out")
            if exception:
                raise exception
                
        except RuntimeError:
            # 沒有運行中的事件循環，直接使用 asyncio.run
            result = asyncio.run(browser_automation.navigate_and_extract(url, extraction_goal))
        
        end_time = time.time()
        browser_tools_logger.info(f"[TOOL] BROWSER_NAVIGATE_AND_EXTRACT 完成 | 耗時: {end_time - start_time:.2f}秒")
        
        if result.get("success", False):
            response_text = result.get("result", "未能提取資訊")
            browser_tools_logger.info(f"    提取成功，內容長度: {len(response_text)} 字符")
            return f"網頁資訊提取成功：\n\n{response_text}"
        else:
            error_msg = result.get("error", "未知錯誤")
            browser_tools_logger.error(f"    提取失敗: {error_msg}")
            return f"無法從 {url} 提取資訊。錯誤: {error_msg}"
            
    except Exception as e:
        end_time = time.time()
        browser_tools_logger.error(f"[TOOL] BROWSER_NAVIGATE_AND_EXTRACT 錯誤 | 耗時: {end_time - start_time:.2f}秒")
        browser_tools_logger.error(f"    錯誤詳情: {str(e)}")
        return f"瀏覽器導航過程中發生錯誤: {str(e)}"

@tool(name_or_callable='browser_search_and_analyze')
def browser_search_and_analyze(search_query: str, analysis_goal: str) -> str:
    """
    Search for information on the internet and analyze the results.
    
    Use this tool when you need to:
    - Search for current medical information or research
    - Find multiple sources about a health topic
    - Analyze search results for specific insights
    - Get up-to-date information not available in knowledge graphs
    
    Args:
        search_query: The search terms or question to search for
        analysis_goal: What specific analysis or insights you want from the search results
        
    Returns:
        Analyzed information from search results with key findings
    """
    browser_tools_logger.info(f"[TOOL] BROWSER_SEARCH_AND_ANALYZE 啟動")
    browser_tools_logger.info(f"    搜尋查詢: {search_query}")
    browser_tools_logger.info(f"    分析目標: {analysis_goal[:100]}...")
    
    start_time = time.time()
    
    try:
        # 使用官方建議的 asyncio.run() 模式 
        # 檢查是否在現有的事件循環中
        try:
            loop = asyncio.get_running_loop()
            # 在新線程中執行，避免嵌套事件循環問題
            import threading
            result = None
            exception = None
            
            def run_in_thread():
                nonlocal result, exception
                try:
                    result = asyncio.run(browser_automation.search_and_analyze(search_query, analysis_goal))
                except Exception as e:
                    exception = e
            
            thread = threading.Thread(target=run_in_thread)
            thread.start()
            thread.join(timeout=180)  # 3分鐘超時
            
            if thread.is_alive():
                raise TimeoutError("Browser search task timed out")
            if exception:
                raise exception
                
        except RuntimeError:
            # 沒有運行中的事件循環，直接使用 asyncio.run
            result = asyncio.run(browser_automation.search_and_analyze(search_query, analysis_goal))
        
        end_time = time.time()
        browser_tools_logger.info(f"[TOOL] BROWSER_SEARCH_AND_ANALYZE 完成 | 耗時: {end_time - start_time:.2f}秒")
        
        if result.get("success", False):
            response_text = result.get("result", "未能分析搜尋結果")
            browser_tools_logger.info(f"    搜尋分析成功，內容長度: {len(response_text)} 字符")
            return f"搜尋分析結果：\n\n{response_text}"
        else:
            error_msg = result.get("error", "未知錯誤")
            browser_tools_logger.error(f"    搜尋分析失敗: {error_msg}")
            return f"無法完成搜尋分析。搜尋查詢: {search_query}。錯誤: {error_msg}"
            
    except Exception as e:
        end_time = time.time()
        browser_tools_logger.error(f"[TOOL] BROWSER_SEARCH_AND_ANALYZE 錯誤 | 耗時: {end_time - start_time:.2f}秒")
        browser_tools_logger.error(f"    錯誤詳情: {str(e)}")
        return f"瀏覽器搜尋過程中發生錯誤: {str(e)}"

@tool(name_or_callable='browser_verify_medical_claim')
def browser_verify_medical_claim(claim: str, specific_sources: str = "") -> str:
    """
    Verify a medical claim by searching for evidence from authoritative sources.
    
    Use this tool when you need to:
    - Verify the accuracy of medical statements or claims
    - Find evidence-based information about health claims
    - Cross-check medical information against reliable sources
    - Investigate potentially false or misleading health information
    
    Args:
        claim: The medical claim or statement to verify
        specific_sources: Optional specific sources or websites to check (comma-separated URLs)
        
    Returns:
        Verification analysis with evidence from authoritative medical sources
    """
    browser_tools_logger.info(f"[TOOL] BROWSER_VERIFY_MEDICAL_CLAIM 啟動")
    browser_tools_logger.info(f"    待驗證聲明: {claim[:100]}...")
    browser_tools_logger.info(f"    指定來源: {specific_sources}")
    
    start_time = time.time()
    
    try:
        # 解析指定來源
        source_urls = []
        if specific_sources.strip():
            source_urls = [url.strip() for url in specific_sources.split(",") if url.strip()]
        
        # 在新的事件循環中執行異步操作
        loop = None
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        if loop.is_running():
            # 如果循環正在運行，使用 run_coroutine_threadsafe
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    lambda: asyncio.run(browser_automation.verify_medical_claim(claim, source_urls))
                )
                result = future.result(timeout=90)
        else:
            # 循環未運行，直接使用 run
            result = loop.run_until_complete(
                browser_automation.verify_medical_claim(claim, source_urls)
            )
        
        end_time = time.time()
        browser_tools_logger.info(f"[TOOL] BROWSER_VERIFY_MEDICAL_CLAIM 完成 | 耗時: {end_time - start_time:.2f}秒")
        
        if result.get("success", False):
            response_text = result.get("result", "未能完成驗證")
            browser_tools_logger.info(f"    醫療聲明驗證成功，內容長度: {len(response_text)} 字符")
            return f"醫療聲明驗證結果：\n\n{response_text}"
        else:
            error_msg = result.get("error", "未知錯誤")
            browser_tools_logger.error(f"    醫療聲明驗證失敗: {error_msg}")
            return f"無法完成醫療聲明驗證。聲明: {claim[:50]}...。錯誤: {error_msg}"
            
    except Exception as e:
        end_time = time.time()
        browser_tools_logger.error(f"[TOOL] BROWSER_VERIFY_MEDICAL_CLAIM 錯誤 | 耗時: {end_time - start_time:.2f}秒")
        browser_tools_logger.error(f"    錯誤詳情: {str(e)}")
        return f"醫療聲明驗證過程中發生錯誤: {str(e)}"

@tool(name_or_callable='browser_extract_hospital_info')
def browser_extract_hospital_info(hospital_name: str, location: str = "") -> str:
    """
    Extract information about a specific hospital or medical facility.
    
    Use this tool when you need to:
    - Find contact information for hospitals or clinics
    - Get details about medical facility services and departments
    - Verify hospital operating hours and availability
    - Find location and accessibility information for medical facilities
    
    Args:
        hospital_name: The name of the hospital or medical facility
        location: Optional location information (city, district, etc.) to help narrow the search
        
    Returns:
        Comprehensive information about the medical facility
    """
    browser_tools_logger.info(f"[TOOL] BROWSER_EXTRACT_HOSPITAL_INFO 啟動")
    browser_tools_logger.info(f"    醫院名稱: {hospital_name}")
    browser_tools_logger.info(f"    位置資訊: {location}")
    
    start_time = time.time()
    
    try:
        # 使用官方建議的 asyncio.run() 模式 
        # 檢查是否在現有的事件循環中
        try:
            loop = asyncio.get_running_loop()
            # 在新線程中執行，避免嵌套事件循環問題
            import threading
            result = None
            exception = None
            
            def run_in_thread():
                nonlocal result, exception
                try:
                    result = asyncio.run(browser_automation.extract_hospital_info(hospital_name, location))
                except Exception as e:
                    exception = e
            
            thread = threading.Thread(target=run_in_thread)
            thread.start()
            thread.join(timeout=180)  # 3分鐘超時
            
            if thread.is_alive():
                raise TimeoutError("Hospital info extraction timed out")
            if exception:
                raise exception
                
        except RuntimeError:
            # 沒有運行中的事件循環，直接使用 asyncio.run
            result = asyncio.run(browser_automation.extract_hospital_info(hospital_name, location))
        
        end_time = time.time()
        browser_tools_logger.info(f"[TOOL] BROWSER_EXTRACT_HOSPITAL_INFO 完成 | 耗時: {end_time - start_time:.2f}秒")
        
        if result.get("success", False):
            response_text = result.get("result", "未能提取醫院資訊")
            browser_tools_logger.info(f"    醫院資訊提取成功，內容長度: {len(response_text)} 字符")
            return f"醫院資訊：\n\n{response_text}"
        else:
            error_msg = result.get("error", "未知錯誤")
            browser_tools_logger.error(f"    醫院資訊提取失敗: {error_msg}")
            return f"無法找到 {hospital_name} 的資訊。錯誤: {error_msg}"
            
    except Exception as e:
        end_time = time.time()
        browser_tools_logger.error(f"[TOOL] BROWSER_EXTRACT_HOSPITAL_INFO 錯誤 | 耗時: {end_time - start_time:.2f}秒")
        browser_tools_logger.error(f"    錯誤詳情: {str(e)}")
        return f"提取醫院資訊過程中發生錯誤: {str(e)}"

# 清理函數
async def cleanup_browser_tools():
    """清理瀏覽器工具資源"""
    try:
        await browser_automation.close_session()
        browser_tools_logger.info("瀏覽器工具資源清理完成")
    except Exception as e:
        browser_tools_logger.warning(f"清理瀏覽器工具資源時發生錯誤: {str(e)}")