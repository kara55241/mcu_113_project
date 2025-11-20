"""
Agent 執行追蹤器
用於記錄 LangGraph Multi-Agent 系統的執行狀態
"""

import json
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

class AgentExecutionTracker:
    """追蹤 Agent 執行狀態"""

    def __init__(self):
        self.executions: Dict[str, Dict] = {}  # {thread_id: execution_data}
        logger.info("AgentExecutionTracker initialized")

    def start_agent(self, thread_id: str, agent_name: str, query: str = "") -> None:
        """
        記錄 Agent 開始執行

        Args:
            thread_id: Thread ID
            agent_name: Agent 名稱
            query: 用戶查詢內容
        """
        # 如果是新的 thread，初始化執行記錄
        if thread_id not in self.executions:
            self.executions[thread_id] = {
                'thread_id': thread_id,
                'started_at': datetime.now().isoformat(),
                'query': query,
                'agents': [],
                'current_agent': None,
                'status': 'running'
            }
            logger.info(f"[TRACKER] New thread started: {thread_id}")

        # 創建 Agent 執行記錄
        agent_data = {
            'name': agent_name,
            'display_name': self._get_agent_display_name(agent_name),
            'role': self._get_agent_role(agent_name),
            'started_at': datetime.now().isoformat(),
            'completed_at': None,
            'status': 'running',
            'tools_used': [],
            'handoff_message': None
        }

        self.executions[thread_id]['agents'].append(agent_data)
        self.executions[thread_id]['current_agent'] = agent_name

        logger.info(f"[TRACKER] Agent started: {agent_name} in thread {thread_id}")

    def log_tool_call(
        self,
        thread_id: str,
        agent_name: str,
        tool_name: str,
        args: Any,
        result: Any = None,
        error: Any = None
    ) -> None:
        """
        記錄工具調用

        Args:
            thread_id: Thread ID
            agent_name: Agent 名稱
            tool_name: 工具名稱
            args: 工具參數
            result: 工具返回結果（可以是字符串或包含 graph_data 的字典）
            error: 錯誤信息
        """
        if thread_id not in self.executions:
            logger.warning(f"[TRACKER] Thread {thread_id} not found for tool logging")
            return

        # 找到當前 Agent
        agents = self.executions[thread_id]['agents']
        current_agent = next(
            (a for a in agents if a['name'] == agent_name and a['status'] == 'running'),
            None
        )

        if not current_agent:
            logger.warning(f"[TRACKER] Agent {agent_name} not found in thread {thread_id}")
            return

        # 處理結果數據
        result_summary = None
        graph_data = None

        if result:
            # 檢查 result 是否包含 graph_data（來自 GraphRAG 工具）
            if isinstance(result, dict):
                # 如果是字典，可能包含 answer 和 graph_data
                if 'graph_data' in result:
                    # 這是 GraphRAG 結果
                    answer = result.get('answer', '')
                    result_summary = self._truncate_string(str(answer), 500)

                    # 保存完整的圖譜數據（不截斷）
                    graph_data = {
                        'nodes': result['graph_data'].get('nodes', []),
                        'relationships': result['graph_data'].get('relationships', []),
                        'chunks': result['graph_data'].get('chunks', []),
                        'database': result.get('database', 'unknown'),
                        'node_count': len(result['graph_data'].get('nodes', [])),
                        'relationship_count': len(result['graph_data'].get('relationships', [])),
                        'chunk_count': len(result['graph_data'].get('chunks', []))
                    }
                else:
                    # 普通字典結果
                    result_summary = self._truncate_string(str(result), 500)
            else:
                # 字符串結果
                result_summary = self._truncate_string(str(result), 500)

        # 創建工具調用記錄
        tool_data = {
            'tool': tool_name,
            'timestamp': datetime.now().isoformat(),
            'args': self._truncate_string(str(args), 200),
            'result_summary': result_summary,
            'graph_data': graph_data,  # 新增：圖譜數據字段
            'error': str(error) if error else None,
            'status': 'error' if error else 'success'
        }

        current_agent['tools_used'].append(tool_data)

        status_text = '[ERROR]' if error else '[SUCCESS]'
        graph_info = f" | Graph: {graph_data['node_count']}N, {graph_data['relationship_count']}R" if graph_data else ""
        logger.info(f"[TRACKER] {status_text} Tool called: {tool_name} by {agent_name}{graph_info}")

    def complete_agent(
        self,
        thread_id: str,
        agent_name: str,
        handoff_message: Optional[str] = None
    ) -> None:
        """
        記錄 Agent 完成

        Args:
            thread_id: Thread ID
            agent_name: Agent 名稱
            handoff_message: 轉交訊息
        """
        if thread_id not in self.executions:
            logger.warning(f"[TRACKER] Thread {thread_id} not found for agent completion")
            return

        # 找到當前 Agent
        agents = self.executions[thread_id]['agents']
        current_agent = next(
            (a for a in agents if a['name'] == agent_name and a['status'] == 'running'),
            None
        )

        if not current_agent:
            logger.warning(f"[TRACKER] Agent {agent_name} not found for completion")
            return

        # 更新 Agent 狀態
        current_agent['completed_at'] = datetime.now().isoformat()
        current_agent['status'] = 'completed'
        current_agent['handoff_message'] = handoff_message

        logger.info(f"[TRACKER] Agent completed: {agent_name}")

    def complete_thread(self, thread_id: str) -> None:
        """
        標記 Thread 完成

        Args:
            thread_id: Thread ID
        """
        if thread_id in self.executions:
            self.executions[thread_id]['status'] = 'completed'
            self.executions[thread_id]['current_agent'] = None
            logger.info(f"[TRACKER] Thread completed: {thread_id}")

    def get_execution(self, thread_id: str) -> Optional[Dict]:
        """
        獲取執行狀態

        Args:
            thread_id: Thread ID

        Returns:
            執行狀態數據，如果不存在返回 None
        """
        execution = self.executions.get(thread_id)
        if not execution:
            return None

        # 新增邏輯層分組（按角色分組代理）
        grouped_agents = {
            'supervisor': [],
            'expert': [],
            'integration': [],
            'unknown': []
        }

        for agent in execution.get('agents', []):
            role = agent.get('role', 'unknown')
            grouped_agents[role].append(agent)

        # 添加 grouped_agents 欄位
        execution['grouped_agents'] = grouped_agents

        return execution

    def get_all_threads(self) -> List[str]:
        """
        獲取所有 Thread ID

        Returns:
            Thread ID 列表
        """
        return list(self.executions.keys())

    def get_recent_threads(self, limit: int = 10) -> List[Dict]:
        """
        獲取最近的 Thread

        Args:
            limit: 返回數量限制

        Returns:
            Thread 列表（按時間降序）
        """
        threads = list(self.executions.values())
        threads.sort(key=lambda x: x['started_at'], reverse=True)
        return threads[:limit]

    def clear_old_threads(self, keep_count: int = 100) -> None:
        """
        清理舊的 Thread 數據（保留最近的 N 個）

        Args:
            keep_count: 保留數量
        """
        if len(self.executions) > keep_count:
            threads = sorted(
                self.executions.items(),
                key=lambda x: x[1]['started_at'],
                reverse=True
            )
            self.executions = dict(threads[:keep_count])
            logger.info(f"[TRACKER] Cleared old threads, kept {keep_count}")

    def _get_agent_display_name(self, agent_name: str) -> str:
        """獲取 Agent 顯示名稱"""
        display_names = {
            # 舊架構節點
            "supervisor": "SUPERVISOR",
            # 新架構 supervisor 節點
            "supervisor_analysis": "任務分析節點",
            "supervisor_fast_path": "快速回應節點",
            "supervisor_decomposition": "任務拆解節點",
            # Agent 節點
            "chronic_agent": "CHRONIC AGENT",
            "cardiovascular_agent": "CARDIOVASCULAR AGENT",
            "fact_check_agent": "FACT-CHECK AGENT",
            # 整合節點
            "integration": "結果整合節點"
        }
        return display_names.get(agent_name, agent_name)

    def _get_agent_role(self, agent_name: str) -> str:
        """獲取 Agent 角色類型（用於邏輯層分組）"""
        role_map = {
            # Supervisor 層（決策和分析）
            "supervisor": "supervisor",
            "supervisor_analysis": "supervisor",
            "supervisor_fast_path": "supervisor",
            "supervisor_decomposition": "supervisor",
            # 專家代理層（並行執行）
            "chronic_agent": "expert",
            "cardiovascular_agent": "expert",
            "fact_check_agent": "expert",
            # 整合層（結果整合）
            "integration": "integration"
        }
        return role_map.get(agent_name, "unknown")

    def _truncate_string(self, text: str, max_length: int) -> str:
        """截斷字符串到指定長度"""
        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."


# 創建全局追蹤器實例
tracker = AgentExecutionTracker()


# 輔助函數：從 state 提取 thread_id
def get_thread_id(state: Dict) -> str:
    """從 state 中提取 thread_id"""
    # LangGraph 的 thread_id 通常在 configurable 中
    config = state.get('configurable', {})
    thread_id = config.get('thread_id')

    if not thread_id:
        # 如果沒有 thread_id，使用默認值
        thread_id = 'default'

    return str(thread_id)


# 輔助函數：從 state 提取用戶查詢
def get_user_query(state: Dict) -> str:
    """從 state 中提取用戶查詢"""
    messages = state.get('messages', [])
    if messages:
        last_message = messages[-1]
        if hasattr(last_message, 'content'):
            return str(last_message.content)[:200]
    return ""
