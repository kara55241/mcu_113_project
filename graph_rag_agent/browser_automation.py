"""
瀏覽器自動化模組 - 原生 Playwright + LLM 引導實現

使用原生 Playwright API 配合 LLM 智能引導，替換 browser-use 架構
解決 EventBus 死鎖、初始化超時、Unicode 編碼等問題
"""

import os
import asyncio
import logging
import time
import json
import base64
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv
from playwright.async_api import async_playwright, Browser, Page, Playwright
from io import BytesIO

# 載入環境變數
load_dotenv()

# 設置日誌 - 簡化版，無需複雜的 Unicode 處理
browser_logger = logging.getLogger('browser_automation')
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
if not browser_logger.handlers:
    browser_logger.addHandler(handler)
browser_logger.setLevel(logging.INFO)

class LLMOperationEngine:
    """LLM 驅動的操作生成和執行引擎"""
    
    def __init__(self, llm_model=None):
        self.llm_model = llm_model
        # 如果沒有提供 LLM 模型，嘗試初始化預設模型
        if not self.llm_model:
            try:
                from .llm import llm_gemini
                self.llm_model = llm_gemini
                browser_logger.info("LLM 操作引擎使用 Gemini 模型")
            except ImportError:
                try:
                    from llm import llm_gemini
                    self.llm_model = llm_gemini
                    browser_logger.info("LLM 操作引擎使用 Gemini 模型")
                except ImportError:
                    browser_logger.warning("無法導入 LLM 模型，將使用備用策略")
        
    async def analyze_page(self, page: Page, task_description: str) -> Dict[str, Any]:
        """分析頁面內容，生成操作策略"""
        try:
            # 獲取頁面基本信息
            url = page.url
            title = await page.title()
            
            # 獲取頁面截圖（用於視覺分析）
            screenshot = await page.screenshot()
            
            # 獲取可互動元素
            interactive_elements = await self._get_interactive_elements(page)
            
            # 獲取頁面文本內容（前 2000 字符）
            page_text = await page.evaluate('() => document.body.innerText')
            page_text = page_text[:2000] if page_text else ""
            
            return {
                "url": url,
                "title": title,
                "screenshot": screenshot,
                "interactive_elements": interactive_elements,
                "page_text": page_text,
                "task": task_description
            }
        except Exception as e:
            browser_logger.warning(f"頁面分析失敗: {str(e)}")
            return {"error": str(e)}
    
    async def _get_interactive_elements(self, page: Page) -> List[Dict]:
        """獲取頁面可互動元素"""
        try:
            # 獲取常見的互動元素
            elements = []
            
            # 鏈接
            links = await page.query_selector_all('a[href]')
            for i, link in enumerate(links[:10]):  # 限制數量
                text = await link.inner_text()
                href = await link.get_attribute('href')
                if text.strip():
                    elements.append({
                        "type": "link", 
                        "text": text.strip()[:50], 
                        "href": href,
                        "selector": f"a:nth-child({i+1})"
                    })
            
            # 按鈕
            buttons = await page.query_selector_all('button, input[type="submit"], input[type="button"]')
            for i, button in enumerate(buttons[:10]):
                text = await button.inner_text()
                if not text.strip():
                    text = await button.get_attribute('value') or await button.get_attribute('aria-label') or "Button"
                elements.append({
                    "type": "button", 
                    "text": text.strip()[:50],
                    "selector": f"button:nth-child({i+1})"
                })
            
            # 輸入框
            inputs = await page.query_selector_all('input[type="text"], input[type="search"], textarea')
            for i, input_elem in enumerate(inputs[:10]):
                placeholder = await input_elem.get_attribute('placeholder') or "Input field"
                name = await input_elem.get_attribute('name') or f"input_{i}"
                elements.append({
                    "type": "input", 
                    "placeholder": placeholder[:50],
                    "name": name,
                    "selector": f"input:nth-child({i+1})"
                })
            
            return elements
        except Exception as e:
            browser_logger.warning(f"獲取互動元素失敗: {str(e)}")
            return []
    
    async def generate_operations(self, page_analysis: Dict, llm_model=None) -> List[Dict]:
        """使用 LLM 生成操作序列"""
        try:
            # 使用傳入的模型或實例化的模型
            model_to_use = llm_model or self.llm_model
            
            if not model_to_use:
                return await self._fallback_operations(page_analysis)
            
            # 構建 LLM prompt
            prompt = self._build_operation_prompt(page_analysis)
            
            # 調用 LLM
            try:
                # 處理異步和同步調用
                if hasattr(model_to_use, 'ainvoke'):
                    response = await model_to_use.ainvoke(prompt)
                else:
                    response = model_to_use.invoke(prompt)
                    
                operations_text = response.content if hasattr(response, 'content') else str(response)
                browser_logger.info(f"LLM 操作生成回應長度: {len(operations_text)} 字符")
                
                # 解析 LLM 回應中的操作序列
                operations = self._parse_operations(operations_text)
                
                if operations:
                    browser_logger.info(f"成功生成 {len(operations)} 個操作序列")
                    return operations
                else:
                    browser_logger.warning("LLM 未生成有效操作序列，使用備用策略")
                    return await self._fallback_operations(page_analysis)
                
            except Exception as llm_error:
                browser_logger.warning(f"LLM 操作生成失敗: {str(llm_error)}")
                return await self._fallback_operations(page_analysis)
                
        except Exception as e:
            browser_logger.error(f"操作生成失敗: {str(e)}")
            return await self._fallback_operations(page_analysis)
    
    def _build_operation_prompt(self, analysis: Dict) -> str:
        """構建 LLM 操作生成 prompt"""
        task = analysis.get("task", "")
        url = analysis.get("url", "")
        title = analysis.get("title", "")
        page_text = analysis.get("page_text", "")[:1000]
        elements = analysis.get("interactive_elements", [])
        
        elements_text = "\n".join([
            f"- {elem['type']}: {elem.get('text', elem.get('placeholder', 'Unknown'))}"
            for elem in elements[:20]
        ])
        
        return f"""
任務: {task}

當前頁面信息:
- URL: {url}
- 標題: {title}
- 頁面內容摘要: {page_text}

可用的互動元素:
{elements_text}

請分析這個頁面，並生成完成任務所需的操作序列。請以 JSON 格式返回操作列表，每個操作包含:
- action: "click", "type", "scroll", "wait", "extract"
- target: 元素選擇器或描述
- value: 如果是輸入操作，提供輸入值
- description: 操作描述

範例:
[
  {{"action": "click", "target": "搜索按鈕", "description": "點擊搜索按鈕"}},
  {{"action": "type", "target": "搜索框", "value": "搜索關鍵詞", "description": "輸入搜索內容"}},
  {{"action": "extract", "target": "結果區域", "description": "提取搜索結果"}}
]

請生成操作序列:
"""
    
    def _parse_operations(self, operations_text: str) -> List[Dict]:
        """解析 LLM 生成的操作序列"""
        try:
            # 嘗試從回應中提取 JSON
            import re
            json_match = re.search(r'\[.*\]', operations_text, re.DOTALL)
            if json_match:
                operations_json = json_match.group()
                operations = json.loads(operations_json)
                return operations
            else:
                # 如果沒有找到 JSON，使用備用解析
                return []
        except Exception as e:
            browser_logger.warning(f"操作序列解析失敗: {str(e)}")
            return []
    
    async def _fallback_operations(self, analysis: Dict) -> List[Dict]:
        """備用操作序列生成（基於規則）"""
        task = analysis.get("task", "").lower()
        url = analysis.get("url", "")
        elements = analysis.get("interactive_elements", [])
        
        operations = []
        
        # 基於任務類型和頁面內容生成基本操作
        if "google.com" in url and ("搜索" in task or "search" in task):
            # Google 搜索
            search_inputs = [e for e in elements if e['type'] == 'input']
            if search_inputs:
                operations.append({
                    "action": "type",
                    "target": "input[name='q']",
                    "value": "提取的搜索詞",
                    "description": "在搜索框輸入關鍵詞"
                })
                operations.append({
                    "action": "click", 
                    "target": "input[type='submit']",
                    "description": "點擊搜索按鈕"
                })
        
        # 添加通用的內容提取操作
        operations.append({
            "action": "extract",
            "target": "body",
            "description": "提取頁面主要內容"
        })
        
        return operations
    
    async def execute_operations(self, page: Page, operations: List[Dict]) -> Dict[str, Any]:
        """執行 LLM 生成的操作序列"""
        results = {
            "executed_operations": 0,
            "successful_operations": 0,
            "failed_operations": 0,
            "extracted_content": "",
            "errors": []
        }
        
        for i, operation in enumerate(operations):
            try:
                action = operation.get("action", "").lower()
                target = operation.get("target", "")
                value = operation.get("value", "")
                description = operation.get("description", f"Operation {i+1}")
                
                browser_logger.info(f"執行操作 {i+1}/{len(operations)}: {description}")
                
                # 執行不同類型的操作
                if action == "click":
                    await self._execute_click(page, target)
                elif action == "type" or action == "fill":
                    await self._execute_type(page, target, value)
                elif action == "scroll":
                    await self._execute_scroll(page, target)
                elif action == "wait":
                    await self._execute_wait(page, value)
                elif action == "extract":
                    content = await self._execute_extract(page, target)
                    results["extracted_content"] += f"\n{content}"
                else:
                    browser_logger.warning(f"未知操作類型: {action}")
                    continue
                
                results["executed_operations"] += 1
                results["successful_operations"] += 1
                
                # 短暫等待以避免操作過快
                await asyncio.sleep(0.5)
                
            except Exception as e:
                error_msg = f"操作 {i+1} 失敗: {str(e)}"
                browser_logger.warning(error_msg)
                
                # 嘗試智能錯誤恢復
                try:
                    browser_logger.info(f"嘗試智能錯誤恢復...")
                    recovery_plan = await self.diagnose_and_recover(
                        page, e, operation, {"task": "執行操作序列"}
                    )
                    
                    if recovery_plan and recovery_plan.get("operations"):
                        recovery_result = await self.execute_recovery(page, recovery_plan)
                        
                        if recovery_result.get("success"):
                            browser_logger.info("智能錯誤恢復成功，繼續執行原操作")
                            # 重新嘗試原操作
                            try:
                                if action == "click":
                                    await self._execute_click(page, target)
                                elif action == "type" or action == "fill":
                                    await self._execute_type(page, target, value)
                                elif action == "extract":
                                    content = await self._execute_extract(page, target)
                                    results["extracted_content"] += f"\n恢復後提取: {content}"
                                
                                results["successful_operations"] += 1
                                browser_logger.info(f"操作 {i+1} 在錯誤恢復後成功執行")
                            except Exception as retry_error:
                                browser_logger.warning(f"錯誤恢復後重試仍失敗: {str(retry_error)}")
                                results["errors"].append(f"恢復後重試失敗: {str(retry_error)}")
                                results["failed_operations"] += 1
                        else:
                            browser_logger.warning("智能錯誤恢復失敗")
                            results["errors"].append(error_msg)
                            results["failed_operations"] += 1
                    else:
                        results["errors"].append(error_msg)
                        results["failed_operations"] += 1
                        
                except Exception as recovery_error:
                    browser_logger.warning(f"錯誤恢復過程異常: {str(recovery_error)}")
                    results["errors"].append(f"原錯誤: {error_msg}, 恢復異常: {str(recovery_error)}")
                    results["failed_operations"] += 1
                
                results["executed_operations"] += 1
        
        browser_logger.info(f"操作執行完成: {results['successful_operations']}/{results['executed_operations']} 成功")
        return results
    
    async def _execute_click(self, page: Page, target: str):
        """執行點擊操作"""
        try:
            # 嘗試多種選擇器策略
            selectors = self._generate_selectors(target)
            
            for selector in selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        await element.click()
                        browser_logger.debug(f"點擊成功: {selector}")
                        return
                except Exception:
                    continue
            
            # 如果所有選擇器都失敗，嘗試文本匹配
            await page.click(f"text='{target}'")
            
        except Exception as e:
            raise Exception(f"無法點擊目標 '{target}': {str(e)}")
    
    async def _execute_type(self, page: Page, target: str, value: str):
        """執行輸入操作"""
        try:
            selectors = self._generate_selectors(target)
            
            for selector in selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        await element.fill(value)
                        browser_logger.debug(f"輸入成功: {selector} = {value}")
                        return
                except Exception:
                    continue
            
            # 嘗試通用輸入框選擇器
            await page.fill("input[type='text'], input[type='search'], textarea", value)
            
        except Exception as e:
            raise Exception(f"無法在 '{target}' 輸入內容: {str(e)}")
    
    async def _execute_scroll(self, page: Page, target: str):
        """執行滾動操作"""
        try:
            if target.lower() in ['down', 'bottom']:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            elif target.lower() in ['up', 'top']:
                await page.evaluate("window.scrollTo(0, 0)")
            else:
                # 滾動到特定元素
                selectors = self._generate_selectors(target)
                for selector in selectors:
                    try:
                        element = await page.query_selector(selector)
                        if element:
                            await element.scroll_into_view_if_needed()
                            return
                    except Exception:
                        continue
        except Exception as e:
            raise Exception(f"滾動操作失敗: {str(e)}")
    
    async def _execute_wait(self, page: Page, value: str):
        """執行等待操作"""
        try:
            # 解析等待時間（秒）
            wait_time = float(value) if value.replace('.', '').isdigit() else 2.0
            await asyncio.sleep(wait_time)
        except Exception as e:
            await asyncio.sleep(2.0)  # 默認等待2秒
    
    async def _execute_extract(self, page: Page, target: str) -> str:
        """執行內容提取操作"""
        try:
            if target.lower() in ['body', 'page', 'content']:
                # 提取整個頁面內容
                return await page.evaluate("() => document.body.innerText")
            else:
                # 提取特定元素內容
                selectors = self._generate_selectors(target)
                for selector in selectors:
                    try:
                        element = await page.query_selector(selector)
                        if element:
                            return await element.inner_text()
                    except Exception:
                        continue
                
                # 如果找不到特定元素，返回頁面標題和摘要
                title = await page.title()
                content = await page.evaluate("() => document.body.innerText")
                return f"頁面標題: {title}\n內容摘要: {content[:500]}..."
                
        except Exception as e:
            return f"內容提取失敗: {str(e)}"
    
    def _generate_selectors(self, target: str) -> List[str]:
        """生成多種選擇器策略"""
        selectors = []
        
        # 如果目標已經是有效選擇器
        if any(char in target for char in ['#', '.', '[', '>', ' ']):
            selectors.append(target)
        
        # 生成基於文本的選擇器
        selectors.extend([
            f"[aria-label*='{target}']",
            f"[title*='{target}']", 
            f"[placeholder*='{target}']",
            f"[name*='{target}']",
            f"button:has-text('{target}')",
            f"a:has-text('{target}')",
            f"input[name='{target}']",
            f"#{target}",
            f".{target}",
        ])
        
        return selectors
    
    async def diagnose_and_recover(self, page: Page, error: Exception, failed_operation: Dict, page_context: Dict) -> Dict[str, Any]:
        """使用 LLM 診斷錯誤並生成恢復策略"""
        try:
            if not self.llm_model:
                return await self._fallback_recovery(page, error, failed_operation)
            
            # 獲取當前頁面狀態
            current_state = await self._get_current_page_state(page)
            
            # 構建診斷 prompt
            diagnosis_prompt = self._build_diagnosis_prompt(error, failed_operation, page_context, current_state)
            
            # 調用 LLM 進行診斷
            try:
                if hasattr(self.llm_model, 'ainvoke'):
                    response = await self.llm_model.ainvoke(diagnosis_prompt)
                else:
                    response = self.llm_model.invoke(diagnosis_prompt)
                
                diagnosis_text = response.content if hasattr(response, 'content') else str(response)
                browser_logger.info(f"LLM 錯誤診斷回應長度: {len(diagnosis_text)} 字符")
                
                # 解析診斷結果和恢復策略
                recovery_plan = self._parse_recovery_plan(diagnosis_text)
                
                if recovery_plan:
                    browser_logger.info(f"LLM 生成了 {len(recovery_plan.get('operations', []))} 個恢復操作")
                    return recovery_plan
                else:
                    browser_logger.warning("LLM 未生成有效恢復策略，使用備用恢復")
                    return await self._fallback_recovery(page, error, failed_operation)
                    
            except Exception as llm_error:
                browser_logger.warning(f"LLM 錯誤診斷失敗: {str(llm_error)}")
                return await self._fallback_recovery(page, error, failed_operation)
                
        except Exception as e:
            browser_logger.error(f"錯誤恢復診斷失敗: {str(e)}")
            return await self._fallback_recovery(page, error, failed_operation)
    
    async def _get_current_page_state(self, page: Page) -> Dict[str, Any]:
        """獲取當前頁面狀態用於診斷 - 增強版本，包含完整異常保護"""
        try:
            # 檢查頁面是否仍然有效
            if not page or page.is_closed():
                browser_logger.warning("頁面已關閉，返回錯誤狀態")
                return {
                    "error": "頁面已關閉",
                    "timestamp": time.time(),
                    "ready_state": "closed",
                    "is_loading": True,
                    "has_content": False
                }
            
            # 首先等待基本 DOM 載入，使用更短的超時時間
            try:
                await page.wait_for_load_state('domcontentloaded', timeout=2000)
            except Exception as load_error:
                browser_logger.debug(f"DOM 載入等待超時: {str(load_error)}")
                # 繼續執行，不讓等待阻止狀態檢查
            
            # 獲取詳細頁面狀態，添加異常保護
            page_info = {}
            try:
                page_info = await page.evaluate('''() => {
                    try {
                        const state = {
                            readyState: document.readyState || 'unknown',
                            isLoading: document.readyState !== 'complete',
                            hasErrors: !!(document.querySelector && document.querySelector('.error, .warning, .alert, [class*="error"], [id*="error"]')),
                            hasContent: !!(document.body && document.body.innerText && document.body.innerText.trim().length > 0),
                            contentLength: document.body ? (document.body.innerText ? document.body.innerText.trim().length : 0) : 0,
                            
                            // 搜索相關狀態
                            hasSearchBox: !!(document.querySelector && document.querySelector('input[name="q"], #sb_form_q, textarea[name="q"], .gLFyf')),
                            isGooglePage: window.location && window.location.hostname && window.location.hostname.includes('google'),
                            isBingPage: window.location && window.location.hostname && window.location.hostname.includes('bing'),
                            
                            // 網頁載入狀態
                            imageCount: document.images ? document.images.length : 0,
                            loadedImages: document.images ? Array.from(document.images).filter(img => img.complete && img.naturalHeight > 0).length : 0,
                            linkCount: document.links ? document.links.length : 0,
                            
                            // JavaScript 錯誤
                            jsErrors: window.jsErrors || [],
                            
                            // 頁面內容分析
                            hasMainContent: !!(
                                (document.querySelector && document.querySelector('main, article, .content, #content, .main')) ||
                                (document.body && document.body.innerText && document.body.innerText.trim().length > 200)
                            ),
                            
                            // 互動元素檢測
                            hasButtons: document.querySelectorAll ? document.querySelectorAll('button, input[type="button"], input[type="submit"]').length : 0,
                            hasInputs: document.querySelectorAll ? document.querySelectorAll('input, textarea, select').length : 0,
                            hasLinks: document.querySelectorAll ? document.querySelectorAll('a[href]').length : 0,
                            
                            timestamp: Date.now()
                        };
                        
                        return state;
                    } catch (e) {
                        return {
                            error: 'JavaScript evaluation failed: ' + e.message,
                            readyState: 'error',
                            isLoading: false,
                            hasContent: false,
                            timestamp: Date.now()
                        };
                    }
                }''')
            except Exception as eval_error:
                browser_logger.warning(f"頁面 JavaScript 評估失敗: {str(eval_error)}")
                page_info = {
                    "error": f"頁面評估失敗: {str(eval_error)}",
                    "readyState": "unknown",
                    "isLoading": True,
                    "hasContent": False,
                    "timestamp": time.time()
                }
            
            # 檢查網絡活動狀態，添加異常保護
            network_idle = False
            try:
                network_idle = await self._check_network_activity(page)
            except Exception as network_error:
                browser_logger.debug(f"網絡活動檢查失敗: {str(network_error)}")
                network_idle = False
            
            # 獲取互動元素（如果需要），添加異常保護
            interactive_elements = []
            try:
                if not page.is_closed():
                    interactive_elements = await self._get_interactive_elements(page)
            except Exception as elements_error:
                browser_logger.debug(f"獲取互動元素失敗: {str(elements_error)}")
                # 非關鍵信息，失敗不影響整體狀態檢測
            
            # 安全獲取頁面基本信息
            page_url = "unknown"
            page_title = "unknown"
            page_text_sample = ""
            
            try:
                page_url = page.url if not page.is_closed() else "page_closed"
                page_title = await page.title() if not page.is_closed() else "page_closed"
            except Exception as basic_error:
                browser_logger.debug(f"獲取基本頁面信息失敗: {str(basic_error)}")
                
            try:
                if not page.is_closed():
                    page_text_sample = (await page.evaluate("() => document.body ? document.body.innerText : ''"))[:500]
            except Exception as text_error:
                browser_logger.debug(f"獲取頁面文本失敗: {str(text_error)}")
                page_text_sample = ""

            return {
                "url": page_url,
                "title": page_title,
                "ready_state": page_info.get('readyState', 'unknown'),
                "is_loading": page_info.get('isLoading', True),
                "has_errors": page_info.get('hasErrors', False),
                "has_content": page_info.get('hasContent', False),
                "content_length": page_info.get('contentLength', 0),
                "has_main_content": page_info.get('hasMainContent', False),
                
                # 搜索引擎特定狀態
                "search_ready": page_info.get('hasSearchBox', False) if (page_info.get('isGooglePage', False) or page_info.get('isBingPage', False)) else True,
                "is_google_page": page_info.get('isGooglePage', False),
                "is_bing_page": page_info.get('isBingPage', False),
                
                # 載入狀態
                "images_loaded_ratio": page_info.get('loadedImages', 0) / max(page_info.get('imageCount', 1), 1),
                "network_idle": network_idle,
                
                # 互動性檢測
                "interactive_elements_count": len(interactive_elements),
                "has_buttons": page_info.get('hasButtons', 0) > 0,
                "has_inputs": page_info.get('hasInputs', 0) > 0,
                "has_links": page_info.get('hasLinks', 0) > 0,
                
                # JavaScript 錯誤
                "js_errors": page_info.get('jsErrors', []),
                
                # 頁面內容樣本
                "page_text_sample": page_text_sample,
                
                "timestamp": time.time(),
                "page_info_error": page_info.get('error')  # 保留錯誤信息用於調試
            }
            
        except Exception as e:
            browser_logger.warning(f"詳細頁面狀態檢測失敗: {str(e)}")
            # 回退到基本狀態檢查
            try:
                return {
                    "url": page.url,
                    "title": await page.title(),
                    "ready_state": await page.evaluate("() => document.readyState"),
                    "is_loading": await page.evaluate("() => document.readyState !== 'complete'"),
                    "has_errors": False,
                    "has_content": await page.evaluate("() => document.body && document.body.innerText.length > 0"),
                    "error": f"部分狀態檢測失敗: {str(e)}",
                    "timestamp": time.time()
                }
            except Exception as fallback_error:
                return {
                    "error": f"頁面狀態檢測完全失敗: {str(fallback_error)}", 
                    "timestamp": time.time()
                }
    
    async def _check_network_activity(self, page: Page) -> bool:
        """檢查頁面網絡活動是否結束"""
        try:
            # 等待網絡空閒狀態，最多等待 3 秒
            await page.wait_for_load_state('networkidle', timeout=3000)
            return True
        except Exception:
            # 如果等待超時或失敗，檢查頁面載入狀態
            try:
                ready_state = await page.evaluate('() => document.readyState')
                return ready_state == 'complete'
            except Exception:
                return False  # 假設網絡活動仍在進行
    
    async def _wait_for_page_ready(self, page: Page, task_type: str = "general", max_wait_time: int = 15) -> bool:
        """智能等待頁面準備就緒，根據任務類型調整等待策略"""
        start_time = time.time()
        browser_logger.info(f"等待頁面準備就緒，任務類型: {task_type}")
        
        try:
            # 基本 DOM 載入等待
            await page.wait_for_load_state('domcontentloaded', timeout=5000)
            
            # 根據任務類型採用不同的準備狀態檢查
            while (time.time() - start_time) < max_wait_time:
                state = await self._get_current_page_state(page)
                
                # 檢查基本載入狀態
                if state.get('error'):
                    browser_logger.warning(f"頁面狀態檢測錯誤: {state['error']}")
                    await asyncio.sleep(1)
                    continue
                
                # 基本準備條件
                basic_ready = (
                    state.get('ready_state') == 'complete' and
                    state.get('has_content', False) and
                    not state.get('is_loading', True)
                )
                
                # 根據任務類型的特定準備條件
                task_ready = True
                
                if task_type in ['search_and_analyze', 'verify_medical_claim', 'extract_hospital_info']:
                    # 搜索相關任務需要搜索框可用
                    if state.get('is_google_page') or state.get('is_bing_page'):
                        task_ready = state.get('search_ready', False)
                        browser_logger.debug(f"搜索頁面準備狀態: {task_ready}")
                
                elif task_type == 'navigate_and_extract':
                    # 內容提取任務需要主要內容載入
                    task_ready = (
                        state.get('has_main_content', False) and
                        state.get('content_length', 0) > 100 and
                        state.get('images_loaded_ratio', 0) > 0.5
                    )
                    browser_logger.debug(f"內容提取準備狀態: 主內容={state.get('has_main_content')}, 長度={state.get('content_length')}")
                
                # 檢查是否準備就緒
                if basic_ready and task_ready:
                    wait_time = time.time() - start_time
                    browser_logger.info(f"頁面準備就緒，等待時間: {wait_time:.2f}秒")
                    return True
                
                # 如果有 JavaScript 錯誤，記錄但不阻止
                js_errors = state.get('js_errors', [])
                if js_errors:
                    browser_logger.warning(f"檢測到 {len(js_errors)} 個 JS 錯誤")
                
                # 短暫等待後重新檢查
                await asyncio.sleep(0.5)
            
            # 超時但記錄最終狀態
            final_state = await self._get_current_page_state(page)
            browser_logger.warning(f"頁面準備等待超時 ({max_wait_time}秒)")
            browser_logger.info(f"最終狀態: ready={final_state.get('ready_state')}, "
                              f"content={final_state.get('has_content')}, "
                              f"search_ready={final_state.get('search_ready')}")
            
            # 即使超時，如果基本狀態OK就返回True
            return (final_state.get('ready_state') == 'complete' and 
                   final_state.get('has_content', False))
            
        except Exception as e:
            browser_logger.error(f"頁面準備狀態檢查失敗: {str(e)}")
            return False
    
    def _build_diagnosis_prompt(self, error: Exception, failed_operation: Dict, page_context: Dict, current_state: Dict) -> str:
        """構建錯誤診斷 prompt"""
        error_msg = str(error)
        operation_desc = failed_operation.get("description", "Unknown operation")
        operation_action = failed_operation.get("action", "unknown")
        operation_target = failed_operation.get("target", "unknown")
        
        return f"""
錯誤診斷和恢復策略生成

發生的錯誤:
- 錯誤訊息: {error_msg}
- 失敗操作: {operation_desc}
- 操作類型: {operation_action}
- 操作目標: {operation_target}

頁面當前狀態:
- URL: {current_state.get('url', 'Unknown')}
- 標題: {current_state.get('title', 'Unknown')}
- 是否加載中: {current_state.get('is_loading', False)}
- 是否有錯誤元素: {current_state.get('has_errors', False)}
- 頁面內容摘要: {current_state.get('page_text_sample', '')}

原始頁面上下文:
- 任務: {page_context.get('task', 'Unknown')}
- 頁面標題: {page_context.get('title', 'Unknown')}

請分析錯誤原因並提供恢復策略。回應格式：

{{
  "diagnosis": "錯誤原因分析",
  "recovery_strategy": "恢復策略說明",
  "operations": [
    {{"action": "操作類型", "target": "目標", "value": "值", "description": "描述"}}
  ]
}}

常見恢復策略:
1. 如果元素未找到，嘗試等待頁面加載完成
2. 如果點擊失敗，嘗試使用不同的選擇器
3. 如果輸入失敗，先清空輸入框再重新輸入
4. 如果頁面超時，嘗試刷新頁面
5. 如果彈窗阻擋，先處理彈窗

請生成具體的恢復操作序列:
"""
    
    def _parse_recovery_plan(self, diagnosis_text: str) -> Dict[str, Any]:
        """解析 LLM 生成的恢復計劃"""
        try:
            # 嘗試從回應中提取 JSON
            import re
            json_match = re.search(r'\{.*\}', diagnosis_text, re.DOTALL)
            if json_match:
                recovery_json = json_match.group()
                recovery_plan = json.loads(recovery_json)
                return recovery_plan
            else:
                return {}
        except Exception as e:
            browser_logger.warning(f"恢復計劃解析失敗: {str(e)}")
            return {}
    
    async def _fallback_recovery(self, page: Page, error: Exception, failed_operation: Dict) -> Dict[str, Any]:
        """備用恢復策略（基於規則）"""
        error_msg = str(error).lower()
        operation_action = failed_operation.get("action", "").lower()
        
        recovery_operations = []
        
        # 基於錯誤類型的恢復策略
        if "timeout" in error_msg:
            recovery_operations.extend([
                {"action": "wait", "value": "3", "description": "等待頁面加載"},
                {"action": "scroll", "target": "top", "description": "滾動到頁面頂部"},
            ])
        elif "not found" in error_msg or "no such element" in error_msg:
            recovery_operations.extend([
                {"action": "wait", "value": "2", "description": "等待元素出現"},
                {"action": "scroll", "target": "down", "description": "向下滾動尋找元素"},
            ])
        elif "click" in operation_action and ("not clickable" in error_msg or "obscured" in error_msg):
            recovery_operations.extend([
                {"action": "scroll", "target": failed_operation.get("target", ""), "description": "滾動到目標元素"},
                {"action": "wait", "value": "1", "description": "短暫等待"},
            ])
        elif "type" in operation_action or "fill" in operation_action:
            recovery_operations.extend([
                {"action": "click", "target": failed_operation.get("target", ""), "description": "重新點擊輸入框"},
                {"action": "wait", "value": "1", "description": "等待輸入框激活"},
            ])
        
        # 通用恢復操作
        if not recovery_operations:
            recovery_operations = [
                {"action": "wait", "value": "2", "description": "等待頁面穩定"},
                {"action": "extract", "target": "body", "description": "重新提取頁面內容"},
            ]
        
        return {
            "diagnosis": f"檢測到 {error_msg} 錯誤",
            "recovery_strategy": "使用基於規則的恢復策略",
            "operations": recovery_operations
        }
    
    async def execute_recovery(self, page: Page, recovery_plan: Dict[str, Any]) -> Dict[str, Any]:
        """執行錯誤恢復計劃"""
        recovery_operations = recovery_plan.get("operations", [])
        
        if not recovery_operations:
            return {"success": False, "message": "沒有恢復操作可執行"}
        
        browser_logger.info(f"執行錯誤恢復: {recovery_plan.get('recovery_strategy', 'Unknown strategy')}")
        
        try:
            # 執行恢復操作
            results = await self.execute_operations(page, recovery_operations)
            
            if results["successful_operations"] > 0:
                browser_logger.info(f"錯誤恢復成功: {results['successful_operations']}/{results['executed_operations']} 操作成功")
                return {"success": True, "message": "錯誤恢復成功", "results": results}
            else:
                browser_logger.warning("錯誤恢復失敗: 沒有成功的恢復操作")
                return {"success": False, "message": "錯誤恢復失敗", "results": results}
                
        except Exception as e:
            browser_logger.error(f"執行錯誤恢復時發生異常: {str(e)}")
            return {"success": False, "message": f"錯誤恢復異常: {str(e)}"}

class BrowserAutomation:
    """瀏覽器自動化管理類 - 原生 Playwright 實現"""
    
    def __init__(self):
        self.headless = os.getenv("BROWSER_USE_HEADLESS", "false").lower() == "true"
        self.executable_path = os.getenv("BROWSER_USE_EXECUTABLE_PATH", "")
        # 優化超時設置：從 120 秒降至 20 秒，更快失敗轉備選
        self.timeout = int(os.getenv("MCP_BROWSER_TIMEOUT", "20")) * 1000  # Playwright 使用毫秒
        # 增加重試次數：從 3 次增至 5 次，提高成功率
        self.retry_count = int(os.getenv("MCP_BROWSER_RETRY_COUNT", "5"))
        self.max_session_time = int(os.getenv("BROWSER_SESSION_MAX_TIME", "300"))
        
        # 新增細粒度超時控制
        self.page_load_timeout = 15000  # 頁面載入超時 15 秒
        self.element_timeout = 5000     # 元素等待超時 5 秒
        self.operation_timeout = 10000  # 單個操作超時 10 秒
        
        self._playwright = None
        self._browser = None
        self._session_start_time = None
        
        # 添加異步鎖，防止競態條件
        self._browser_lock = asyncio.Lock()
        self._operation_lock = asyncio.Lock()
        
        # 初始化 LLM 操作引擎
        self.operation_engine = LLMOperationEngine()
        
        browser_logger.info("原生 Playwright 瀏覽器自動化模組初始化完成")
        browser_logger.info(f"配置: headless={self.headless}, timeout={self.timeout/1000}s")
    
    async def _ensure_browser(self):
        """確保瀏覽器已初始化 - 增強穩定性和錯誤恢復，包含異步鎖保護"""
        # 使用異步鎖防止並發初始化
        async with self._browser_lock:
            max_init_attempts = 3
            
            for attempt in range(max_init_attempts):
                try:
                    # 檢查瀏覽器是否需要重新初始化
                    need_init = await self._check_browser_health()
                
                    if need_init:
                        browser_logger.info(f"初始化新的 Playwright 瀏覽器 (嘗試 {attempt + 1}/{max_init_attempts})")
                    
                    # 確保完全清理舊的資源
                    await self._cleanup_browser()
                    
                    # 等待清理完成
                    await asyncio.sleep(0.5)
                    
                    # 啟動新的 Playwright 實例
                    try:
                        self._playwright = await async_playwright().start()
                        browser_logger.debug("Playwright 實例啟動成功")
                    except Exception as playwright_error:
                        browser_logger.warning(f"Playwright 啟動失敗: {str(playwright_error)}")
                        if attempt < max_init_attempts - 1:
                            await asyncio.sleep(1)  # 等待後重試
                            continue
                        else:
                            raise
                    
                    # 瀏覽器啟動配置 - 更保守的設置
                    browser_config = {
                        'headless': self.headless,
                        'args': [
                            '--no-sandbox',
                            '--disable-blink-features=AutomationControlled',
                            '--disable-dev-shm-usage',
                            '--disable-web-security',
                            '--disable-features=VizDisplayCompositor',
                            '--disable-background-timer-throttling',
                            '--disable-backgrounding-occluded-windows',
                            '--disable-renderer-backgrounding',
                            '--disable-extensions',
                            '--no-first-run'
                        ],
                        'timeout': 30000  # 30秒啟動超時
                    }
                    
                    # 如果指定了執行路徑
                    if self.executable_path:
                        browser_config['executable_path'] = self.executable_path
                    
                    # 啟動瀏覽器
                    try:
                        browser_logger.debug("啟動 Chromium 瀏覽器...")
                        self._browser = await self._playwright.chromium.launch(**browser_config)
                        browser_logger.debug("Chromium 瀏覽器啟動成功")
                    except Exception as browser_error:
                        browser_logger.warning(f"瀏覽器啟動失敗: {str(browser_error)}")
                        if attempt < max_init_attempts - 1:
                            await self._cleanup_browser()
                            await asyncio.sleep(2)  # 更長的等待時間
                            continue
                        else:
                            raise
                    
                    # 驗證瀏覽器是否正常工作
                    if self._browser is None:
                        raise RuntimeError("瀏覽器實例創建失敗")
                    
                    # 測試瀏覽器連接
                    try:
                        test_page = await self._browser.new_page()
                        await test_page.close()
                        browser_logger.debug("瀏覽器連接測試成功")
                    except Exception as test_error:
                        browser_logger.warning(f"瀏覽器連接測試失敗: {str(test_error)}")
                        if attempt < max_init_attempts - 1:
                            await self._cleanup_browser()
                            await asyncio.sleep(2)
                            continue
                        else:
                            raise RuntimeError(f"瀏覽器連接測試失敗: {str(test_error)}")
                    
                        self._session_start_time = time.time()
                        browser_logger.info(f"Playwright 瀏覽器初始化成功 (嘗試 {attempt + 1})")
                        return  # 成功，退出循環
                    else:
                        browser_logger.debug("瀏覽器實例健康，無需重新初始化")
                        return
                
                except Exception as e:
                    error_msg = str(e)
                    browser_logger.error(f"初始化瀏覽器失敗 (嘗試 {attempt + 1}/{max_init_attempts}): {error_msg}")
                    
                    # 確保清理失敗的初始化嘗試
                    await self._cleanup_browser()
                    
                    if attempt < max_init_attempts - 1:
                        wait_time = (attempt + 1) * 2  # 遞增等待時間
                        browser_logger.info(f"等待 {wait_time} 秒後重試瀏覽器初始化...")
                        await asyncio.sleep(wait_time)
                    else:
                        # 最後一次嘗試失敗，提供詳細錯誤信息
                        if "chrome" in error_msg.lower() or "chromium" in error_msg.lower():
                            browser_logger.error("可能的解決方案: 安裝 Chrome/Chromium 瀏覽器或檢查執行路徑")
                        elif "timeout" in error_msg.lower():
                            browser_logger.error("可能的解決方案: 增加超時時間或檢查系統資源")
                        elif "connection" in error_msg.lower():
                            browser_logger.error("可能的解決方案: 檢查網絡連接和防火牆設置")
                        
                        raise RuntimeError(f"瀏覽器初始化失敗，已重試 {max_init_attempts} 次: {error_msg}")
    
    async def _check_browser_health(self) -> bool:
        """檢查瀏覽器健康狀態，決定是否需要重新初始化"""
        try:
            # 基本存在性檢查
            if self._browser is None or self._playwright is None:
                browser_logger.debug("瀏覽器實例不存在，需要初始化")
                return True
            
            # 會話過期檢查
            if self._is_session_expired():
                browser_logger.debug("瀏覽器會話過期，需要重新初始化")
                return True
            
            # 瀏覽器連接狀態檢查
            try:
                # 嘗試獲取瀏覽器版本信息
                version = await self._browser.version()
                if not version:
                    browser_logger.debug("無法獲取瀏覽器版本，可能連接已斷開")
                    return True
            except Exception as version_error:
                browser_logger.debug(f"瀏覽器版本檢查失敗: {str(version_error)}")
                return True
            
            # 如果所有檢查都通過，瀏覽器健康
            return False
            
        except Exception as e:
            browser_logger.debug(f"瀏覽器健康檢查失敗: {str(e)}")
            return True  # 出錯時選擇重新初始化
    
    def _is_session_expired(self) -> bool:
        """檢查會話是否過期"""
        if self._session_start_time is None:
            return True
        return (time.time() - self._session_start_time) > self.max_session_time
    
    def _classify_error(self, error_msg: str) -> str:
        """智能錯誤分類，用於決定恢復策略 - 增強版本"""
        error_msg_lower = error_msg.lower()
        
        # 瀏覽器連接和會話相關錯誤（優先檢查）
        if any(keyword in error_msg_lower for keyword in ['connection closed', 'browser has been closed', 'target closed']):
            return 'browser_connection_lost'
        elif any(keyword in error_msg_lower for keyword in ['browser', 'context', 'session', 'closed']):
            return 'browser_session_error'
        
        # 頁面狀態相關錯誤
        elif any(keyword in error_msg_lower for keyword in ['page.is_closed', 'page closed', 'page has been closed']):
            return 'page_closed_error'
        
        # 超時相關錯誤（細分類型）
        elif any(keyword in error_msg_lower for keyword in ['timeout', 'timed out', '120000ms exceeded', '30000ms exceeded']):
            if 'locator' in error_msg_lower or 'selector' in error_msg_lower:
                return 'element_timeout'
            elif 'navigation' in error_msg_lower or 'goto' in error_msg_lower:
                return 'navigation_timeout'
            elif 'wait_for' in error_msg_lower:
                return 'wait_timeout'
            elif 'page.evaluate' in error_msg_lower:
                return 'javascript_timeout'
            else:
                return 'general_timeout'
        
        # 元素選擇器和頁面交互錯誤
        elif any(keyword in error_msg_lower for keyword in ['locator', 'selector', 'element']):
            if 'not found' in error_msg_lower or 'no such element' in error_msg_lower:
                return 'element_not_found'
            elif 'not clickable' in error_msg_lower or 'obscured' in error_msg_lower:
                return 'element_not_clickable'
            elif 'not visible' in error_msg_lower or 'not attached' in error_msg_lower:
                return 'element_not_accessible'
            else:
                return 'element_interaction_error'
        
        # 網絡連接相關錯誤
        elif any(keyword in error_msg_lower for keyword in ['connection', 'network', 'dns', 'refused', 'unreachable']):
            if 'dns' in error_msg_lower:
                return 'dns_error'
            elif 'refused' in error_msg_lower or 'unreachable' in error_msg_lower:
                return 'connection_refused'
            else:
                return 'network_error'
        
        # 頁面導航相關錯誤
        elif any(keyword in error_msg_lower for keyword in ['navigation', 'navigate', 'goto']):
            if 'ssl' in error_msg_lower or 'certificate' in error_msg_lower:
                return 'ssl_certificate_error'
            elif 'net::err_name_not_resolved' in error_msg_lower:
                return 'dns_resolution_error'
            else:
                return 'navigation_error'
        
        # JavaScript 執行錯誤
        elif any(keyword in error_msg_lower for keyword in ['evaluate', 'javascript', 'script']):
            if 'evaluation failed' in error_msg_lower:
                return 'javascript_evaluation_error'
            else:
                return 'javascript_error'
        
        # 權限和安全相關錯誤
        elif any(keyword in error_msg_lower for keyword in ['permission', 'security', 'blocked', 'cors']):
            return 'permission_error'
        
        # 搜索引擎特定錯誤
        elif any(keyword in error_msg_lower for keyword in ['input[name="q"]', 'search box', 'google search']):
            return 'search_element_error'
        elif 'google.com' in error_msg_lower and 'failed' in error_msg_lower:
            return 'google_access_error'
        
        # 資源和記憶體相關錯誤
        elif any(keyword in error_msg_lower for keyword in ['out of memory', 'memory', 'resource']):
            return 'resource_error'
        
        # Playwright 特定錯誤
        elif any(keyword in error_msg_lower for keyword in ['playwright', 'chromium.launch']):
            return 'playwright_launch_error'
        
        # 頁面內容相關錯誤
        elif any(keyword in error_msg_lower for keyword in ['_get_current_page_state', 'page state']):
            return 'page_state_error'
        
        return 'unknown_error'
    
    async def _determine_recovery_action(self, error_category: str, attempt: int, operation_type: str) -> Dict[str, Any]:
        """根據錯誤類型和嘗試次數決定恢復策略 - 增強版本"""
        base_wait_time = min(2 ** attempt, 10)  # 指數回退，最大 10 秒
        
        recovery_strategies = {
            # 瀏覽器連接相關錯誤（高優先級）
            'browser_connection_lost': {
                'strategy': '立即重新建立瀏覽器連接',
                'wait_time': base_wait_time + 1,
                'cleanup_browser': True,
                'fallback_search': False,
                'priority': 'high'
            },
            
            'browser_session_error': {
                'strategy': '重新初始化瀏覽器會話',
                'wait_time': base_wait_time + 2,
                'cleanup_browser': True,
                'fallback_search': False,
                'priority': 'high'
            },
            
            'page_closed_error': {
                'strategy': '創建新頁面並重新執行任務',
                'wait_time': base_wait_time * 0.5,
                'cleanup_browser': False,
                'fallback_search': False,
                'priority': 'medium'
            },
            
            'page_state_error': {
                'strategy': '跳過頁面狀態檢查，繼續執行',
                'wait_time': base_wait_time * 0.5,
                'cleanup_browser': False,
                'fallback_search': False,
                'priority': 'low'
            },
            
            # 超時相關錯誤
            'element_timeout': {
                'strategy': '增加元素等待時間並嘗試多種選擇器',
                'wait_time': base_wait_time,
                'cleanup_browser': attempt >= 4,
                'fallback_search': operation_type in ['search_and_analyze', 'verify_medical_claim', 'extract_hospital_info'],
                'priority': 'medium'
            },
            
            'navigation_timeout': {
                'strategy': '降低頁面載入要求並增加超時時間',
                'wait_time': base_wait_time * 1.5,
                'cleanup_browser': attempt >= 2,
                'fallback_search': False,
                'priority': 'medium'
            },
            
            'wait_timeout': {
                'strategy': '調整等待策略並跳過非關鍵等待',
                'wait_time': base_wait_time,
                'cleanup_browser': attempt >= 3,
                'fallback_search': False,
                'priority': 'low'
            },
            
            'javascript_timeout': {
                'strategy': '簡化 JavaScript 執行並增加超時',
                'wait_time': base_wait_time,
                'cleanup_browser': attempt >= 3,
                'fallback_search': False,
                'priority': 'medium'
            },
            
            'general_timeout': {
                'strategy': '增加超時時間並優化執行策略',
                'wait_time': base_wait_time,
                'cleanup_browser': attempt >= 3,
                'fallback_search': False,
                'priority': 'medium'
            },
            
            # 元素交互錯誤
            'element_not_found': {
                'strategy': '使用多重選擇器策略和頁面滾動',
                'wait_time': base_wait_time * 0.5,
                'cleanup_browser': False,
                'fallback_search': operation_type.startswith('search'),
                'priority': 'medium'
            },
            
            'element_not_clickable': {
                'strategy': '滾動到元素並等待元素可點擊',
                'wait_time': base_wait_time * 0.5,
                'cleanup_browser': False,
                'fallback_search': False,
                'priority': 'low'
            },
            
            'element_not_accessible': {
                'strategy': '等待元素載入並檢查頁面狀態',
                'wait_time': base_wait_time,
                'cleanup_browser': attempt >= 3,
                'fallback_search': False,
                'priority': 'medium'
            },
            
            'element_interaction_error': {
                'strategy': '使用替代交互方式',
                'wait_time': base_wait_time * 0.5,
                'cleanup_browser': False,
                'fallback_search': False,
                'priority': 'low'
            },
            
            # 網絡相關錯誤
            'network_error': {
                'strategy': '重新建立網絡連接並重啟瀏覽器',
                'wait_time': base_wait_time * 2,
                'cleanup_browser': True,
                'fallback_search': False,
                'priority': 'high'
            },
            
            'dns_error': {
                'strategy': '等待 DNS 解析並重試',
                'wait_time': base_wait_time * 2,
                'cleanup_browser': attempt >= 2,
                'fallback_search': False,
                'priority': 'high'
            },
            
            'connection_refused': {
                'strategy': '檢查網絡連通性並重試',
                'wait_time': base_wait_time * 2,
                'cleanup_browser': attempt >= 2,
                'fallback_search': False,
                'priority': 'high'
            },
            
            'dns_resolution_error': {
                'strategy': '使用備選 DNS 並重試',
                'wait_time': base_wait_time * 2,
                'cleanup_browser': attempt >= 3,
                'fallback_search': False,
                'priority': 'high'
            },
            
            # 導航相關錯誤
            'navigation_error': {
                'strategy': '簡化頁面載入策略',
                'wait_time': base_wait_time,
                'cleanup_browser': attempt >= 2,
                'fallback_search': False,
                'priority': 'medium'
            },
            
            'ssl_certificate_error': {
                'strategy': '忽略 SSL 錯誤並重試',
                'wait_time': base_wait_time,
                'cleanup_browser': True,
                'fallback_search': False,
                'priority': 'medium'
            },
            
            # JavaScript 相關錯誤
            'javascript_error': {
                'strategy': '簡化頁面操作並避免複雜 JS',
                'wait_time': base_wait_time,
                'cleanup_browser': attempt >= 3,
                'fallback_search': False,
                'priority': 'low'
            },
            
            'javascript_evaluation_error': {
                'strategy': '使用備選頁面檢查方式',
                'wait_time': base_wait_time * 0.5,
                'cleanup_browser': False,
                'fallback_search': False,
                'priority': 'low'
            },
            
            # 搜索相關錯誤
            'search_element_error': {
                'strategy': '嘗試備選搜索元素選擇器',
                'wait_time': base_wait_time * 0.5,
                'cleanup_browser': False,
                'fallback_search': True,
                'priority': 'medium'
            },
            
            'google_access_error': {
                'strategy': '切換到備選搜索引擎',
                'wait_time': base_wait_time,
                'cleanup_browser': False,
                'fallback_search': True,
                'priority': 'medium'
            },
            
            # 系統資源相關錯誤
            'resource_error': {
                'strategy': '清理資源並降低並發度',
                'wait_time': base_wait_time * 3,
                'cleanup_browser': True,
                'fallback_search': False,
                'priority': 'high'
            },
            
            'playwright_launch_error': {
                'strategy': '調整 Playwright 啟動參數',
                'wait_time': base_wait_time * 2,
                'cleanup_browser': True,
                'fallback_search': False,
                'priority': 'high'
            },
            
            # 權限相關錯誤
            'permission_error': {
                'strategy': '調整瀏覽器權限設置',
                'wait_time': base_wait_time,
                'cleanup_browser': True,
                'fallback_search': False,
                'priority': 'medium'
            }
        }
        
        # 如果錯誤類型未知，使用默認策略
        default_strategy = {
            'strategy': '基本重試策略',
            'wait_time': base_wait_time,
            'cleanup_browser': attempt >= 2,
            'fallback_search': False,
            'priority': 'low'
        }
        
        strategy = recovery_strategies.get(error_category, default_strategy)
        
        # 根據嘗試次數調整策略強度
        if attempt >= 3:
            strategy['cleanup_browser'] = True
            strategy['wait_time'] = min(strategy['wait_time'] * 1.5, 15)
        
        return strategy
    
    async def _execute_error_recovery(self, recovery_action: Dict[str, Any], attempt: int):
        """執行具體的錯誤恢復動作 - 增強版本"""
        strategy = recovery_action['strategy']
        priority = recovery_action.get('priority', 'medium')
        
        browser_logger.info(f"執行錯誤恢復策略: {strategy} (嘗試 {attempt + 1}, 優先級: {priority})")
        
        # 高優先級恢復動作立即執行
        if priority == 'high':
            browser_logger.warning(f"高優先級恢復動作: {strategy}")
        
        # 是否需要清理瀏覽器
        if recovery_action.get('cleanup_browser', False):
            browser_logger.info("執行瀏覽器清理和重新初始化")
            try:
                await self._cleanup_browser()
                browser_logger.debug("瀏覽器清理完成")
            except Exception as cleanup_error:
                browser_logger.warning(f"瀏覽器清理過程中發生錯誤: {str(cleanup_error)}")
        
        # 特定的恢復動作
        if recovery_action.get('fallback_search', False):
            browser_logger.info("準備在下次重試時使用備選搜索引擎")
        
        # 根據策略類型執行特定動作
        await self._apply_recovery_adjustments(strategy, attempt)
        
        # 記錄恢復動作完成
        browser_logger.debug(f"恢復策略執行完成: {strategy}")
    
    async def _apply_recovery_adjustments(self, strategy: str, attempt: int):
        """根據恢復策略應用特定調整"""
        try:
            if 'timeout' in strategy.lower():
                # 動態調整超時時間
                self.timeout = min(self.timeout * 1.2, 60000)  # 增加 20%，最大 60 秒
                browser_logger.debug(f"調整超時配置為 {self.timeout/1000}秒")
                
            elif 'browser' in strategy.lower() and 'connection' in strategy.lower():
                # 瀏覽器連接問題，調整啟動參數
                browser_logger.debug("準備使用更穩定的瀏覽器配置")
                
            elif 'javascript' in strategy.lower():
                # JavaScript 問題，準備使用簡化模式
                browser_logger.debug("準備使用簡化的頁面交互模式")
                
            elif 'network' in strategy.lower():
                # 網絡問題，記錄網絡狀態
                browser_logger.debug("網絡恢復策略：將在重試時檢查網絡連接")
                
        except Exception as adjustment_error:
            browser_logger.debug(f"應用恢復調整時發生錯誤: {str(adjustment_error)}")
    
    
    async def _execute_with_retry(self, task: str, operation_type: str = "general") -> Dict[str, Any]:
        """執行瀏覽器任務並重試 - 智能錯誤處理"""
        last_error = None
        
        for attempt in range(self.retry_count):
            try:
                browser_logger.info(f"執行瀏覽器任務 (嘗試 {attempt + 1}/{self.retry_count}): {operation_type}")
                browser_logger.info(f"任務描述: {task[:100]}...")
                
                await self._ensure_browser()
                
                # 創建新的頁面
                page = await self._browser.new_page()
                
                try:
                    # 設置優化的頁面超時
                    page.set_default_timeout(self.timeout)
                    page.set_default_navigation_timeout(self.page_load_timeout)
                    
                    # 執行任務
                    start_time = time.time()
                    result = await self._execute_task(page, task, operation_type)
                    end_time = time.time()
                    
                    browser_logger.info(f"瀏覽器任務完成，耗時: {end_time - start_time:.2f}秒")
                    
                    return {
                        "success": True,
                        "result": result,
                        "operation_type": operation_type,
                        "execution_time": end_time - start_time,
                        "attempt": attempt + 1
                    }
                    
                finally:
                    # 確保頁面關閉
                    try:
                        await page.close()
                    except Exception:
                        pass
                        
            except Exception as e:
                error_msg = str(e)
                last_error = e
                
                browser_logger.warning(f"嘗試 {attempt + 1} 失敗: {error_msg}")
                
                # 智能錯誤分析和處理策略
                error_category = self._classify_error(error_msg)
                recovery_action = await self._determine_recovery_action(error_category, attempt, operation_type)
                
                browser_logger.info(f"錯誤分類: {error_category}, 恢復策略: {recovery_action['strategy']}")
                
                # 執行錯誤恢復動作
                await self._execute_error_recovery(recovery_action, attempt)
                
                if attempt < self.retry_count - 1:
                    wait_time = recovery_action['wait_time']
                    browser_logger.info(f"等待 {wait_time} 秒後重試...")
                    await asyncio.sleep(wait_time)
        
        # 所有重試都失敗
        browser_logger.error(f"瀏覽器任務執行失敗，已重試 {self.retry_count} 次")
        browser_logger.error(f"最後錯誤: {str(last_error)}")
        
        return {
            "success": False,
            "error": str(last_error),
            "operation_type": operation_type,
            "attempts": self.retry_count
        }
    
    async def _execute_task(self, page: Page, task: str, operation_type: str) -> str:
        """執行具體的瀏覽器任務"""
        try:
            # 根據操作類型執行不同的策略
            if operation_type == "navigate_and_extract":
                return await self._execute_navigate_and_extract(page, task)
            elif operation_type == "search_and_analyze":
                return await self._execute_search_and_analyze(page, task)
            elif operation_type == "verify_medical_claim":
                return await self._execute_verify_medical_claim(page, task)
            elif operation_type == "extract_hospital_info":
                return await self._execute_extract_hospital_info(page, task)
            else:
                return await self._execute_general_task(page, task)
                
        except Exception as e:
            browser_logger.error(f"任務執行失敗: {str(e)}")
            raise
    
    async def _execute_navigate_and_extract(self, page: Page, task: str) -> str:
        """執行導航和資訊提取任務"""
        # 解析任務中的 URL 和提取目標
        lines = task.strip().split('\n')
        url = None
        extraction_goal = ""
        
        for line in lines:
            if line.startswith('Navigate to'):
                # 提取 URL
                import re
                url_match = re.search(r'https?://[^\s]+', line)
                if url_match:
                    url = url_match.group()
            elif line.startswith('extract') or '提取' in line:
                extraction_goal = line
        
        if not url:
            raise ValueError("無法從任務中提取 URL")
        
        # 導航到目標 URL - 使用優化的超時設置
        browser_logger.info(f"導航到: {url}")
        await page.goto(url, wait_until='domcontentloaded', timeout=self.page_load_timeout)
        
        # 等待頁面準備就緒 - 針對內容提取任務優化
        page_ready = await self._wait_for_page_ready(page, task_type='navigate_and_extract', max_wait_time=15)
        if not page_ready:
            browser_logger.warning("目標頁面可能未完全載入，但繼續執行內容提取")
        
        # 分析頁面並生成操作
        page_analysis = await self.operation_engine.analyze_page(page, extraction_goal)
        
        # 使用 LLM 生成智能操作序列（如果可用）
        llm_extracted_content = ""
        if self.operation_engine.llm_model:
            try:
                operations = await self.operation_engine.generate_operations(page_analysis)
                if operations:
                    browser_logger.info(f"LLM 生成了 {len(operations)} 個操作")
                    
                    # 執行 LLM 生成的操作序列
                    operation_results = await self.operation_engine.execute_operations(page, operations)
                    
                    if operation_results["successful_operations"] > 0:
                        browser_logger.info(f"成功執行 {operation_results['successful_operations']} 個操作")
                        llm_extracted_content = operation_results.get("extracted_content", "")
                    
                    if operation_results["errors"]:
                        for error in operation_results["errors"]:
                            browser_logger.warning(f"操作錯誤: {error}")
                            
            except Exception as e:
                browser_logger.warning(f"LLM 操作執行失敗: {str(e)}")
        
        # 提取頁面內容（傳統方法）
        traditional_result = await self._extract_page_content(page, extraction_goal)
        
        # 結合 LLM 和傳統結果
        if llm_extracted_content:
            result = f"{traditional_result}\n\n--- LLM 智能提取內容 ---\n{llm_extracted_content}"
        else:
            result = traditional_result
        
        return result
    
    async def _execute_search_and_analyze(self, page: Page, task: str) -> str:
        """執行搜索和分析任務"""
        # 解析搜索查詢和分析目標
        lines = task.strip().split('\n')
        search_query = ""
        analysis_goal = ""
        
        for line in lines:
            if 'Search for' in line or '搜索' in line:
                # 提取搜索查詢
                import re
                query_match = re.search(r'"([^"]+)"', line)
                if query_match:
                    search_query = query_match.group(1)
            elif 'analyze' in line or '分析' in line:
                analysis_goal = line
        
        if not search_query:
            raise ValueError("無法從任務中提取搜索查詢")
        
        # 導航到 Google - 使用優化的超時設置
        browser_logger.info("導航到 Google 搜索")
        await page.goto('https://www.google.com', wait_until='domcontentloaded', timeout=self.page_load_timeout)
        
        # 等待頁面準備就緒 - 針對搜索任務優化
        page_ready = await self._wait_for_page_ready(page, task_type='search_and_analyze', max_wait_time=10)
        if not page_ready:
            browser_logger.warning("Google 頁面可能未完全載入，但繼續執行搜索")
        
        # 執行搜索 - 使用多種選擇器策略
        search_success = await self._smart_search_input(page, search_query)
        if not search_success:
            raise Exception("無法在 Google 頁面找到搜索框")
        
        # 等待搜索結果載入
        await self._wait_for_page_ready(page, task_type='search_and_analyze', max_wait_time=8)
        
        # 分析搜索結果
        result = await self._analyze_search_results(page, analysis_goal)
        
        return result
    
    async def _execute_verify_medical_claim(self, page: Page, task: str) -> str:
        """執行醫療聲明驗證任務"""
        # 解析聲明內容
        lines = task.strip().split('\n')
        claim = ""
        
        for line in lines:
            if 'Verify the medical claim:' in line or '驗證醫療聲明:' in line:
                # 提取聲明
                import re
                claim_match = re.search(r'"([^"]+)"', line)
                if claim_match:
                    claim = claim_match.group(1)
        
        if not claim:
            raise ValueError("無法從任務中提取醫療聲明")
        
        # 搜索相關的醫療資訊
        search_query = f"醫療 {claim} 科學證據"
        
        await page.goto('https://www.google.com', wait_until='domcontentloaded', timeout=self.page_load_timeout)
        
        # 等待頁面準備就緒 - 針對醫療驗證任務優化  
        page_ready = await self._wait_for_page_ready(page, task_type='verify_medical_claim', max_wait_time=10)
        if not page_ready:
            browser_logger.warning("Google 頁面可能未完全載入，但繼續執行醫療驗證搜索")
        
        # 執行搜索 - 使用智能搜索輸入
        search_success = await self._smart_search_input(page, search_query)
        if not search_success:
            raise Exception("無法在醫療聲明驗證頁面找到搜索框")
        
        # 等待搜索結果載入
        await self._wait_for_page_ready(page, task_type='verify_medical_claim', max_wait_time=8)
        
        # 分析驗證結果
        result = await self._verify_claim_from_results(page, claim)
        
        return result
    
    async def _execute_extract_hospital_info(self, page: Page, task: str) -> str:
        """執行醫院資訊提取任務"""
        # 解析醫院名稱和位置
        lines = task.strip().split('\n')
        hospital_name = ""
        location = ""
        
        for line in lines:
            if 'Find information about' in line or '查找' in line:
                # 提取醫院名稱
                import re
                name_match = re.search(r'"([^"]+)"', line)
                if name_match:
                    hospital_name = name_match.group(1)
                if 'in ' in line:
                    location = line.split('in ')[-1].strip()
        
        if not hospital_name:
            raise ValueError("無法從任務中提取醫院名稱")
        
        # 搜索醫院資訊
        search_query = f"{hospital_name} {location} 醫院 資訊"
        
        await page.goto('https://www.google.com', wait_until='domcontentloaded', timeout=self.page_load_timeout)
        
        # 等待頁面準備就緒 - 針對醫院資訊提取任務優化
        page_ready = await self._wait_for_page_ready(page, task_type='extract_hospital_info', max_wait_time=10)
        if not page_ready:
            browser_logger.warning("Google 頁面可能未完全載入，但繼續執行醫院資訊搜索")
        
        # 執行搜索 - 使用智能搜索輸入
        search_success = await self._smart_search_input(page, search_query)
        if not search_success:
            raise Exception("無法在醫院資訊提取頁面找到搜索框")
        
        await page.wait_for_load_state('networkidle')
        
        # 提取醫院資訊
        result = await self._extract_hospital_details(page, hospital_name)
        
        return result
    
    async def _smart_search_input(self, page: Page, search_query: str) -> bool:
        """智能搜索輸入 - 支持多種搜索框選擇器和搜索引擎"""
        # Google 搜索框的多種選擇器（按優先級排序）
        google_selectors = [
            'input[name="q"]',           # 標準桌面版
            'textarea[name="q"]',        # 新版 Google 搜索框
            '[aria-label*="搜尋"]',      # 繁體中文介面
            '[aria-label*="搜索"]',      # 簡體中文介面  
            '[aria-label*="Search"]',    # 英文介面
            '#searchboxinput',           # 移動版或特殊版本
            '.gLFyf',                    # Google 搜索框的 CSS 類名
            'input[type="text"][title*="搜"]',  # 基於 title 屬性
            'textarea[jsaction*="search"]',     # 基於 JavaScript 事件
        ]
        
        browser_logger.info(f"開始智能搜索輸入: {search_query}")
        
        # 首先等待頁面穩定 - 使用優化的超時時間
        try:
            await page.wait_for_load_state('domcontentloaded', timeout=self.element_timeout)
            await page.wait_for_load_state('networkidle', timeout=self.page_load_timeout)
        except Exception as e:
            browser_logger.warning(f"頁面載入等待超時: {str(e)}")
        
        # 嘗試多種選擇器
        for i, selector in enumerate(google_selectors):
            try:
                browser_logger.debug(f"嘗試選擇器 {i+1}/{len(google_selectors)}: {selector}")
                
                # 等待元素出現，使用較短的超時時間
                element = await page.wait_for_selector(selector, timeout=self.element_timeout)
                
                if element:
                    # 確保元素可見和可互動
                    await element.scroll_into_view_if_needed()
                    await page.wait_for_timeout(500)  # 短暫等待動畫完成
                    
                    # 清空並輸入搜索內容
                    await element.click()
                    await element.clear()
                    await element.fill(search_query)
                    
                    browser_logger.info(f"成功使用選擇器 {selector} 輸入搜索內容")
                    
                    # 提交搜索
                    try:
                        await element.press('Enter')
                        browser_logger.info("搜索提交成功")
                        return True
                    except Exception as e:
                        browser_logger.warning(f"使用 Enter 鍵提交失敗: {str(e)}")
                        # 嘗試點擊搜索按鈕
                        try:
                            search_button = await page.query_selector('input[type="submit"], button[type="submit"], .FPdoLc center input[name="btnK"]')
                            if search_button:
                                await search_button.click()
                                browser_logger.info("點擊搜索按鈕成功")
                                return True
                        except Exception:
                            pass
                        
                        browser_logger.warning("搜索提交失敗，嘗試下一個選擇器")
                        continue
                        
            except Exception as e:
                browser_logger.debug(f"選擇器 {selector} 失敗: {str(e)}")
                continue
        
        # 如果 Google 完全失敗，嘗試備選搜索引擎
        browser_logger.warning("Google 搜索失敗，嘗試備選搜索引擎")
        return await self._fallback_search_engine(page, search_query)
    
    async def _fallback_search_engine(self, page: Page, search_query: str) -> bool:
        """備選搜索引擎 - Bing 搜索"""
        try:
            browser_logger.info("嘗試使用 Bing 作為備選搜索引擎")
            await page.goto('https://www.bing.com', wait_until='networkidle', timeout=self.page_load_timeout)
            
            # Bing 搜索框選擇器
            bing_selectors = [
                'input#sb_form_q',
                'input[name="q"]',
                '[aria-label*="搜"]',
                '[aria-label*="Search"]',
                '#sb_form_q'
            ]
            
            for selector in bing_selectors:
                try:
                    element = await page.wait_for_selector(selector, timeout=self.element_timeout)
                    if element:
                        await element.click()
                        await element.clear()
                        await element.fill(search_query)
                        await element.press('Enter')
                        
                        browser_logger.info(f"Bing 搜索成功，選擇器: {selector}")
                        return True
                        
                except Exception as e:
                    browser_logger.debug(f"Bing 選擇器 {selector} 失敗: {str(e)}")
                    continue
            
        except Exception as e:
            browser_logger.error(f"備選搜索引擎失敗: {str(e)}")
        
        return False
    
    async def _execute_general_task(self, page: Page, task: str) -> str:
        """執行一般任務"""
        # 分析頁面並生成操作
        page_analysis = await self.operation_engine.analyze_page(page, task)
        
        # 提取頁面基本內容
        title = await page.title()
        content = await page.evaluate('() => document.body.innerText')
        
        return f"頁面標題: {title}\n\n頁面內容摘要: {content[:1000]}..."
    
    async def _extract_page_content(self, page: Page, extraction_goal: str) -> str:
        """提取頁面內容"""
        try:
            # 獲取頁面基本信息
            title = await page.title()
            url = page.url
            
            # 提取主要內容
            content = await page.evaluate('''() => {
                // 移除腳本和樣式標籤
                const scripts = document.querySelectorAll('script, style');
                scripts.forEach(el => el.remove());
                
                // 獲取主要內容區域
                const mainContent = document.querySelector('main, article, .content, #content, .main') 
                    || document.body;
                
                return mainContent.innerText;
            }''')
            
            # 提取鏈接
            links = await page.evaluate('''() => {
                const links = Array.from(document.querySelectorAll('a[href]'));
                return links.slice(0, 10).map(link => ({
                    text: link.innerText.trim(),
                    href: link.href
                })).filter(link => link.text);
            }''')
            
            # 格式化結果
            result = f"""
頁面標題: {title}
頁面 URL: {url}

主要內容:
{content[:2000]}

重要鏈接:
{chr(10).join([f"- {link['text']}: {link['href']}" for link in links])}

提取目標: {extraction_goal}
"""
            
            return result.strip()
            
        except Exception as e:
            browser_logger.warning(f"內容提取失敗: {str(e)}")
            return f"頁面內容提取遇到問題: {str(e)}"
    
    async def _analyze_search_results(self, page: Page, analysis_goal: str) -> str:
        """分析搜索結果"""
        try:
            # 提取搜索結果
            results = await page.evaluate('''() => {
                const results = Array.from(document.querySelectorAll('div.g, .result'));
                return results.slice(0, 5).map(result => {
                    const titleElement = result.querySelector('h3, .title');
                    const linkElement = result.querySelector('a[href]');
                    const snippetElement = result.querySelector('.VwiC3b, .snippet, .s');
                    
                    return {
                        title: titleElement ? titleElement.innerText : '',
                        link: linkElement ? linkElement.href : '',
                        snippet: snippetElement ? snippetElement.innerText : ''
                    };
                }).filter(result => result.title);
            }''')
            
            # 格式化分析結果
            analysis = f"""
搜索結果分析 (針對: {analysis_goal})

找到 {len(results)} 個相關結果:

"""
            
            for i, result in enumerate(results, 1):
                analysis += f"""
{i}. {result['title']}
   連結: {result['link']}
   摘要: {result['snippet'][:200]}...

"""
            
            analysis += f"\n分析目標: {analysis_goal}\n"
            analysis += "建議: 基於以上搜索結果，可以進一步查看具體鏈接獲取更詳細的資訊。"
            
            return analysis.strip()
            
        except Exception as e:
            browser_logger.warning(f"搜索結果分析失敗: {str(e)}")
            return f"搜索結果分析遇到問題: {str(e)}"
    
    async def _verify_claim_from_results(self, page: Page, claim: str) -> str:
        """從搜索結果驗證醫療聲明"""
        try:
            # 提取相關的搜索結果
            results = await page.evaluate('''() => {
                const results = Array.from(document.querySelectorAll('div.g, .result'));
                return results.slice(0, 5).map(result => {
                    const titleElement = result.querySelector('h3, .title');
                    const linkElement = result.querySelector('a[href]');
                    const snippetElement = result.querySelector('.VwiC3b, .snippet, .s');
                    
                    return {
                        title: titleElement ? titleElement.innerText : '',
                        link: linkElement ? linkElement.href : '',
                        snippet: snippetElement ? snippetElement.innerText : ''
                    };
                }).filter(result => result.title);
            }''')
            
            # 分析驗證結果
            verification = f"""
醫療聲明驗證: "{claim}"

基於搜索結果的分析:

"""
            
            authoritative_sources = 0
            for i, result in enumerate(results, 1):
                verification += f"{i}. {result['title']}\n"
                verification += f"   來源: {result['link']}\n"
                verification += f"   內容: {result['snippet'][:150]}...\n\n"
                
                # 檢查權威來源
                if any(domain in result['link'] for domain in ['.gov.tw', '.edu.tw', 'mohw.gov.tw', 'who.int', 'nih.gov']):
                    authoritative_sources += 1
            
            # 提供驗證總結
            verification += f"""
驗證總結:
- 找到 {len(results)} 個相關結果
- 其中 {authoritative_sources} 個來自權威機構
- 建議: 請參考權威醫療機構的資訊進行進一步確認

注意: 此為初步搜索分析，具體的醫療建議請諮詢專業醫療人員。
"""
            
            return verification.strip()
            
        except Exception as e:
            browser_logger.warning(f"醫療聲明驗證失敗: {str(e)}")
            return f"醫療聲明驗證遇到問題: {str(e)}"
    
    async def _extract_hospital_details(self, page: Page, hospital_name: str) -> str:
        """提取醫院詳細資訊"""
        try:
            # 提取搜索結果中的醫院資訊
            results = await page.evaluate('''() => {
                const results = Array.from(document.querySelectorAll('div.g, .result'));
                return results.slice(0, 5).map(result => {
                    const titleElement = result.querySelector('h3, .title');
                    const linkElement = result.querySelector('a[href]');
                    const snippetElement = result.querySelector('.VwiC3b, .snippet, .s');
                    
                    return {
                        title: titleElement ? titleElement.innerText : '',
                        link: linkElement ? linkElement.href : '',
                        snippet: snippetElement ? snippetElement.innerText : ''
                    };
                }).filter(result => result.title);
            }''')
            
            hospital_info = f"""
醫院資訊: {hospital_name}

找到以下相關資訊:

"""
            
            for i, result in enumerate(results, 1):
                hospital_info += f"""
{i}. {result['title']}
   網站: {result['link']}
   資訊: {result['snippet'][:200]}...

"""
            
            hospital_info += """
建議事項:
- 請直接聯繫醫院確認最新資訊
- 可通過官方網站查看更詳細的科別和服務資訊
- 建議在前往前先電話預約確認
"""
            
            return hospital_info.strip()
            
        except Exception as e:
            browser_logger.warning(f"醫院資訊提取失敗: {str(e)}")
            return f"醫院資訊提取遇到問題: {str(e)}"
    
    async def _cleanup_browser(self):
        """清理瀏覽器資源 - 增強版本，確保完全清理"""
        cleanup_timeout = 10  # 10秒清理超時
        
        try:
            browser_logger.debug("開始清理瀏覽器資源...")
            
            # 清理瀏覽器實例
            if self._browser:
                try:
                    # 首先嘗試獲取所有打開的頁面並關閉
                    try:
                        contexts = self._browser.contexts
                        for context in contexts:
                            try:
                                pages = context.pages
                                for page in pages:
                                    try:
                                        if not page.is_closed():
                                            await asyncio.wait_for(page.close(), timeout=2)
                                    except Exception as page_error:
                                        browser_logger.debug(f"關閉頁面失敗: {str(page_error)}")
                                
                                # 關閉上下文
                                await asyncio.wait_for(context.close(), timeout=2)
                            except Exception as context_error:
                                browser_logger.debug(f"關閉上下文失敗: {str(context_error)}")
                    except Exception as pages_error:
                        browser_logger.debug(f"處理頁面清理時錯誤: {str(pages_error)}")
                    
                    # 關閉瀏覽器主實例
                    browser_logger.debug("關閉瀏覽器主實例...")
                    await asyncio.wait_for(self._browser.close(), timeout=cleanup_timeout)
                    browser_logger.debug("瀏覽器主實例關閉成功")
                    
                except asyncio.TimeoutError:
                    browser_logger.warning("瀏覽器關閉超時，強制清理")
                except Exception as browser_error:
                    browser_logger.warning(f"關閉瀏覽器時發生錯誤: {str(browser_error)}")
                finally:
                    self._browser = None
            
            # 清理 Playwright 實例
            if self._playwright:
                try:
                    browser_logger.debug("停止 Playwright 實例...")
                    await asyncio.wait_for(self._playwright.stop(), timeout=cleanup_timeout)
                    browser_logger.debug("Playwright 實例停止成功")
                except asyncio.TimeoutError:
                    browser_logger.warning("Playwright 停止超時，強制清理")
                except Exception as playwright_error:
                    browser_logger.warning(f"停止 Playwright 時發生錯誤: {str(playwright_error)}")
                finally:
                    self._playwright = None
            
            # 重置會話時間
            self._session_start_time = None
            
            browser_logger.debug("瀏覽器資源清理完成")
            
        except Exception as e:
            browser_logger.warning(f"清理瀏覽器時發生意外錯誤: {str(e)}")
            # 強制重置所有引用
            self._browser = None
            self._playwright = None
            self._session_start_time = None
        
        # 等待清理完成，給系統時間釋放資源
        await asyncio.sleep(1.0)
    
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
    
    async def _check_network_activity(self, page: Page) -> bool:
        """檢查頁面網絡活動是否結束"""
        try:
            # 等待網絡空閒狀態，最多等待 3 秒
            await page.wait_for_load_state('networkidle', timeout=3000)
            return True
        except Exception:
            # 如果等待超時或失敗，檢查頁面載入狀態
            try:
                ready_state = await page.evaluate('() => document.readyState')
                return ready_state == 'complete'
            except Exception:
                return False  # 假設網絡活動仍在進行
    
    async def _wait_for_page_ready(self, page: Page, task_type: str = "general", max_wait_time: int = 15) -> bool:
        """智能等待頁面準備就緒，根據任務類型調整等待策略"""
        start_time = time.time()
        browser_logger.info(f"等待頁面準備就緒，任務類型: {task_type}")
        
        try:
            # 基本 DOM 載入等待
            await page.wait_for_load_state('domcontentloaded', timeout=5000)
            
            # 根據任務類型採用不同的準備狀態檢查
            while (time.time() - start_time) < max_wait_time:
                state = await self._get_current_page_state(page)
                
                # 檢查基本載入狀態
                if state.get('error'):
                    browser_logger.warning(f"頁面狀態檢測錯誤: {state['error']}")
                    await asyncio.sleep(1)
                    continue
                
                # 基本準備條件
                basic_ready = (
                    state.get('ready_state') == 'complete' and
                    state.get('has_content', False) and
                    not state.get('is_loading', True)
                )
                
                # 根據任務類型的特定準備條件
                task_ready = True
                
                if task_type in ['search_and_analyze', 'verify_medical_claim', 'extract_hospital_info']:
                    # 搜索相關任務需要搜索框可用
                    if state.get('is_google_page') or state.get('is_bing_page'):
                        task_ready = state.get('search_ready', False)
                        browser_logger.debug(f"搜索頁面準備狀態: {task_ready}")
                
                elif task_type == 'navigate_and_extract':
                    # 內容提取任務需要主要內容載入
                    task_ready = (
                        state.get('has_main_content', False) and
                        state.get('content_length', 0) > 100 and
                        state.get('images_loaded_ratio', 0) > 0.5
                    )
                    browser_logger.debug(f"內容提取準備狀態: 主內容={state.get('has_main_content')}, 長度={state.get('content_length')}")
                
                # 檢查是否準備就緒
                if basic_ready and task_ready:
                    wait_time = time.time() - start_time
                    browser_logger.info(f"頁面準備就緒，等待時間: {wait_time:.2f}秒")
                    return True
                
                # 如果有 JavaScript 錯誤，記錄但不阻止
                js_errors = state.get('js_errors', [])
                if js_errors:
                    browser_logger.warning(f"檢測到 {len(js_errors)} 個 JS 錯誤")
                
                # 短暫等待後重新檢查
                await asyncio.sleep(0.5)
            
            # 超時但記錄最終狀態
            final_state = await self._get_current_page_state(page)
            browser_logger.warning(f"頁面準備等待超時 ({max_wait_time}秒)")
            browser_logger.info(f"最終狀態: ready={final_state.get('ready_state')}, "
                              f"content={final_state.get('has_content')}, "
                              f"search_ready={final_state.get('search_ready')}")
            
            # 即使超時，如果基本狀態OK就返回True
            return (final_state.get('ready_state') == 'complete' and 
                   final_state.get('has_content', False))
            
        except Exception as e:
            browser_logger.error(f"頁面準備狀態檢查失敗: {str(e)}")
            return False
    
    async def close_session(self):
        """關閉瀏覽器會話"""
        try:
            await self._cleanup_browser()
            browser_logger.info("瀏覽器會話已關閉")
        except Exception as e:
            browser_logger.warning(f"關閉瀏覽器會話時發生錯誤: {str(e)}")

# 全域瀏覽器自動化實例
browser_automation = BrowserAutomation()

async def cleanup_browser():
    """清理瀏覽器資源"""
    await browser_automation.close_session()