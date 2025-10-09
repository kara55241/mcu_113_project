"""
Checkpoint 解析器
解析 SQLite checkpoint blob，提取 Agent 工作流資訊
"""
import pickle
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class CheckpointParser:
    """解析 LangGraph checkpoint 數據"""

    # Agent 工具對應表
    TOOL_AGENT_MAP = {
        'chronic_search': 'chronic_agent',
        'cardiovascular_search': 'cardiovascular_agent',
        'cofacts_check_tool': 'fact_check_agent',
        'google_fact_check_tool': 'fact_check_agent',
        'net_search': 'fact_check_agent',
        'transfer_to_chronic_agent': 'supervisor',
        'transfer_to_cardiovascular_agent': 'supervisor',
        'transfer_to_fact_check_agent': 'supervisor',
    }

    # Agent 顯示名稱
    AGENT_DISPLAY_NAMES = {
        'supervisor': 'Supervisor (路由協調)',
        'chronic_agent': '慢性疾病專家',
        'cardiovascular_agent': '心血管疾病專家',
        'fact_check_agent': '資訊搜尋專家'
    }

    @staticmethod
    def parse_checkpoint_blob(checkpoint_blob: bytes) -> Optional[Dict]:
        """
        解析 checkpoint blob (pickle 格式)

        Args:
            checkpoint_blob: pickle 序列化的 checkpoint 數據

        Returns:
            解析後的 checkpoint 字典，或 None 如果解析失敗
        """
        if not checkpoint_blob:
            return None

        try:
            checkpoint_data = pickle.loads(checkpoint_blob)
            return checkpoint_data
        except Exception as e:
            logger.error(f"Failed to parse checkpoint blob: {e}")
            return None

    @staticmethod
    def extract_messages(checkpoint_data: Dict) -> List[Dict]:
        """
        從 checkpoint 數據提取 messages 列表

        Args:
            checkpoint_data: 解析後的 checkpoint 字典

        Returns:
            messages 列表
        """
        if not checkpoint_data:
            return []

        # LangGraph checkpoint 結構: checkpoint_data['channel_values']['messages']
        try:
            channel_values = checkpoint_data.get('channel_values', {})
            messages = channel_values.get('messages', [])
            return messages
        except Exception as e:
            logger.error(f"Failed to extract messages: {e}")
            return []

    @staticmethod
    def parse_message(msg: Any) -> Dict:
        """
        解析單個 message 對象

        Args:
            msg: LangChain message 對象

        Returns:
            標準化的 message 字典
        """
        result = {
            'type': 'unknown',
            'content': '',
            'role': '',
            'tool_calls': [],
            'tool_call_id': None,
            'name': None
        }

        try:
            # 獲取 message type
            if hasattr(msg, 'type'):
                result['type'] = msg.type

            # 獲取內容
            if hasattr(msg, 'content'):
                result['content'] = msg.content if isinstance(msg.content, str) else str(msg.content)

            # 獲取 role (針對 AIMessage, HumanMessage 等)
            if hasattr(msg, 'role'):
                result['role'] = msg.role
            elif result['type'] == 'human':
                result['role'] = 'user'
            elif result['type'] == 'ai':
                result['role'] = 'assistant'
            elif result['type'] == 'tool':
                result['role'] = 'tool'

            # 獲取 tool calls (AIMessage 可能包含)
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                result['tool_calls'] = []
                for tc in msg.tool_calls:
                    if isinstance(tc, dict):
                        result['tool_calls'].append(tc)
                    else:
                        # 對象轉字典
                        result['tool_calls'].append({
                            'name': getattr(tc, 'name', ''),
                            'args': getattr(tc, 'args', {}),
                            'id': getattr(tc, 'id', '')
                        })

            # 獲取 tool_call_id (ToolMessage 包含)
            if hasattr(msg, 'tool_call_id'):
                result['tool_call_id'] = msg.tool_call_id

            # 獲取 name (ToolMessage 包含工具名稱)
            if hasattr(msg, 'name'):
                result['name'] = msg.name

        except Exception as e:
            logger.error(f"Failed to parse message: {e}")

        return result

    @classmethod
    def extract_workflow_nodes(cls, checkpoint_blob: bytes, checkpoint_id: str,
                               namespace: str, checkpoint_type: str,
                               metadata: Optional[str] = None) -> List[Dict]:
        """
        從 checkpoint 提取工作流節點

        Args:
            checkpoint_blob: pickle blob
            checkpoint_id: checkpoint ID
            namespace: checkpoint namespace
            checkpoint_type: checkpoint type
            metadata: metadata JSON 字串

        Returns:
            節點列表，每個節點包含類型、代理、工具等資訊
        """
        nodes = []

        # 解析 checkpoint
        checkpoint_data = cls.parse_checkpoint_blob(checkpoint_blob)
        if not checkpoint_data:
            # 如果無法解析，返回基礎節點
            return [{
                'checkpoint_id': checkpoint_id,
                'namespace': namespace,
                'type': checkpoint_type,
                'node_type': 'unknown',
                'label': f'Checkpoint {checkpoint_id}',
                'details': '無法解析 checkpoint 數據'
            }]

        # 提取 messages
        messages = cls.extract_messages(checkpoint_data)

        # 解析 metadata
        meta_dict = {}
        if metadata:
            try:
                meta_dict = json.loads(metadata)
            except:
                pass

        # 分析 messages 建立節點
        for idx, msg in enumerate(messages):
            parsed_msg = cls.parse_message(msg)

            # 根據 message type 建立不同類型的節點
            if parsed_msg['type'] == 'human':
                # 用戶輸入節點
                nodes.append({
                    'checkpoint_id': checkpoint_id,
                    'message_index': idx,
                    'node_type': 'user_input',
                    'agent_name': 'user',
                    'label': '用戶輸入',
                    'content': parsed_msg['content'][:100],  # 截斷顯示
                    'full_content': parsed_msg['content'],
                    'timestamp': meta_dict.get('timestamp')
                })

            elif parsed_msg['type'] == 'ai' and parsed_msg['tool_calls']:
                # AI 調用工具節點
                for tool_call in parsed_msg['tool_calls']:
                    tool_name = tool_call.get('name', '')

                    # 判斷是 Supervisor 路由還是 Agent 工具調用
                    if tool_name.startswith('transfer_to_'):
                        # Supervisor 路由決策
                        target_agent = tool_name.replace('transfer_to_', '')
                        nodes.append({
                            'checkpoint_id': checkpoint_id,
                            'message_index': idx,
                            'node_type': 'supervisor_routing',
                            'agent_name': 'supervisor',
                            'label': 'Supervisor 路由決策',
                            'action': f'轉交至 {cls.AGENT_DISPLAY_NAMES.get(target_agent, target_agent)}',
                            'target_agent': target_agent,
                            'tool_name': tool_name,
                            'tool_args': tool_call.get('args', {})
                        })
                    else:
                        # Agent 工具調用
                        agent_name = cls.TOOL_AGENT_MAP.get(tool_name, 'unknown')
                        nodes.append({
                            'checkpoint_id': checkpoint_id,
                            'message_index': idx,
                            'node_type': 'tool_call',
                            'agent_name': agent_name,
                            'label': f'{tool_name} 工具調用',
                            'tool_name': tool_name,
                            'tool_args': tool_call.get('args', {}),
                            'tool_id': tool_call.get('id', '')
                        })

            elif parsed_msg['type'] == 'tool':
                # 工具執行結果節點
                nodes.append({
                    'checkpoint_id': checkpoint_id,
                    'message_index': idx,
                    'node_type': 'tool_result',
                    'agent_name': cls.TOOL_AGENT_MAP.get(parsed_msg.get('name', ''), 'unknown'),
                    'label': f'{parsed_msg.get("name", "工具")} 結果',
                    'tool_name': parsed_msg.get('name'),
                    'content': parsed_msg['content'][:200],  # 截斷
                    'full_content': parsed_msg['content'],
                    'tool_call_id': parsed_msg.get('tool_call_id')
                })

            elif parsed_msg['type'] == 'ai' and not parsed_msg['tool_calls']:
                # AI 最終回應節點
                nodes.append({
                    'checkpoint_id': checkpoint_id,
                    'message_index': idx,
                    'node_type': 'ai_response',
                    'agent_name': 'assistant',
                    'label': 'AI 回應',
                    'content': parsed_msg['content'][:200],
                    'full_content': parsed_msg['content']
                })

        # 如果沒有提取到任何節點，返回基礎節點
        if not nodes:
            nodes.append({
                'checkpoint_id': checkpoint_id,
                'namespace': namespace,
                'type': checkpoint_type,
                'node_type': 'checkpoint',
                'label': f'Checkpoint {checkpoint_id}',
                'message_count': len(messages)
            })

        return nodes

    @classmethod
    def build_workflow_graph(cls, checkpoints_data: List[tuple]) -> Dict:
        """
        從多個 checkpoints 建立完整的工作流圖

        Args:
            checkpoints_data: checkpoints 查詢結果列表
                格式: [(checkpoint_id, namespace, type, checkpoint_blob, metadata), ...]

        Returns:
            {
                'nodes': [...],
                'edges': [...]
            }
        """
        all_nodes = []
        edges = []

        # 處理每個 checkpoint
        for idx, checkpoint_row in enumerate(checkpoints_data):
            checkpoint_id, namespace, cp_type, blob, metadata = checkpoint_row

            # 提取節點
            nodes = cls.extract_workflow_nodes(blob, checkpoint_id, namespace, cp_type, metadata)

            # 為每個節點生成唯一 ID
            for node_idx, node in enumerate(nodes):
                node['id'] = f"{checkpoint_id}_{node.get('message_index', node_idx)}"
                all_nodes.append(node)

        # 建立邊 (簡單的順序連接)
        for i in range(len(all_nodes) - 1):
            edge_label = ""
            current_node = all_nodes[i]
            next_node = all_nodes[i + 1]

            # 根據節點類型添加邊標籤
            if current_node['node_type'] == 'supervisor_routing':
                edge_label = current_node.get('action', '轉交')
            elif current_node['node_type'] == 'tool_call':
                edge_label = f"調用 {current_node.get('tool_name', '工具')}"
            elif current_node['node_type'] == 'tool_result':
                edge_label = "返回結果"

            edges.append({
                'id': f"edge_{i}",
                'from': current_node['id'],
                'to': next_node['id'],
                'label': edge_label
            })

        return {
            'nodes': all_nodes,
            'edges': edges
        }

    @classmethod
    def extract_graphrag_queries(cls, checkpoint_blob: bytes) -> List[Dict]:
        """
        從 checkpoint 提取 GraphRAG 查詢記錄

        Args:
            checkpoint_blob: pickle blob

        Returns:
            GraphRAG 查詢記錄列表
        """
        queries = []

        checkpoint_data = cls.parse_checkpoint_blob(checkpoint_blob)
        if not checkpoint_data:
            return queries

        messages = cls.extract_messages(checkpoint_data)

        for msg in messages:
            parsed_msg = cls.parse_message(msg)

            # 查找 chronic_search 或 cardiovascular_search 工具調用
            if parsed_msg['type'] == 'ai' and parsed_msg['tool_calls']:
                for tool_call in parsed_msg['tool_calls']:
                    tool_name = tool_call.get('name', '')
                    if tool_name in ['chronic_search', 'cardiovascular_search']:
                        queries.append({
                            'tool_name': tool_name,
                            'database': 'diseases-tw',
                            'query': tool_call.get('args', {}).get('query', ''),
                            'args': tool_call.get('args', {})
                        })

            # 查找工具結果
            elif parsed_msg['type'] == 'tool':
                tool_name = parsed_msg.get('name', '')
                if tool_name in ['chronic_search', 'cardiovascular_search']:
                    # 嘗試解析結果中的 Neo4j 節點資訊
                    result_content = parsed_msg.get('full_content', '')
                    queries.append({
                        'tool_name': tool_name,
                        'result_length': len(result_content),
                        'result_preview': result_content[:300]
                    })

        return queries
