"""
監控 API Views
提供 Agent 執行狀態、工作流、Neo4j 查詢結果等數據
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import sqlite3
import json
import os
from pathlib import Path


class AgentStatusView(APIView):
    """
    獲取 Agent 當前執行狀態（從記憶體追蹤器）
    GET /api/monitoring/agents/status
    GET /api/monitoring/agents/status?thread_id=xxx (特定 Thread)
    """
    def get(self, request):
        try:
            # 嘗試從記憶體追蹤器獲取數據
            try:
                from graph_rag_agent.agent_tracker import tracker

                thread_id = request.GET.get('thread_id')

                if thread_id:
                    # 獲取特定 Thread
                    execution = tracker.get_execution(thread_id)
                    if execution:
                        return Response({
                            "status": "success",
                            "source": "memory_tracker",
                            "execution": execution
                        })
                    else:
                        return Response({
                            "error": "Thread not found",
                            "thread_id": thread_id
                        }, status=status.HTTP_404_NOT_FOUND)
                else:
                    # 獲取最近的 Threads
                    recent_threads = tracker.get_recent_threads(limit=10)
                    return Response({
                        "status": "success",
                        "source": "memory_tracker",
                        "thread_count": len(recent_threads),
                        "threads": recent_threads
                    })
            except ImportError:
                # 追蹤器不可用，回退到 checkpoint 資料庫
                pass

            # 備援：從 checkpoint 資料庫讀取
            checkpoint_db = Path(__file__).resolve().parent.parent / "graph_rag_agent" / "agent_checkpoint_new.sqlite"

            if not checkpoint_db.exists():
                return Response({
                    "error": "Checkpoint database not found and tracker unavailable",
                    "path": str(checkpoint_db)
                }, status=status.HTTP_404_NOT_FOUND)

            conn = sqlite3.connect(str(checkpoint_db))
            cursor = conn.cursor()

            # 查詢最近的 checkpoint 記錄
            cursor.execute("""
                SELECT thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id, type, checkpoint
                FROM checkpoints
                ORDER BY checkpoint_id DESC
                LIMIT 10
            """)

            checkpoints = []
            for row in cursor.fetchall():
                checkpoints.append({
                    "thread_id": row[0],
                    "checkpoint_ns": row[1],
                    "checkpoint_id": row[2],
                    "parent_checkpoint_id": row[3],
                    "type": row[4],
                    "checkpoint_size": len(row[5]) if row[5] else 0
                })

            conn.close()

            return Response({
                "status": "success",
                "source": "checkpoint_database",
                "checkpoint_count": len(checkpoints),
                "recent_checkpoints": checkpoints
            })

        except Exception as e:
            import traceback
            return Response({
                "error": str(e),
                "traceback": traceback.format_exc()
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AgentFlowView(APIView):
    """
    獲取特定對話的工作流節點數據（升級版：包含詳細的 Agent、工具資訊）
    GET /api/monitoring/agents/flow?thread_id=xxx
    """
    def get(self, request):
        thread_id = request.GET.get('thread_id')

        if not thread_id:
            return Response({
                "error": "thread_id parameter is required"
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            from .utils.checkpoint_parser import CheckpointParser

            checkpoint_db = Path(__file__).resolve().parent.parent / "graph_rag_agent" / "agent_checkpoint_new.sqlite"

            if not checkpoint_db.exists():
                return Response({
                    "error": "Checkpoint database not found"
                }, status=status.HTTP_404_NOT_FOUND)

            conn = sqlite3.connect(str(checkpoint_db))
            cursor = conn.cursor()

            # 查詢特定 thread 的所有 checkpoint
            cursor.execute("""
                SELECT checkpoint_id, checkpoint_ns, type, checkpoint, metadata
                FROM checkpoints
                WHERE thread_id = ?
                ORDER BY checkpoint_id ASC
            """, (thread_id,))

            checkpoints_data = cursor.fetchall()
            conn.close()

            if not checkpoints_data:
                return Response({
                    "thread_id": thread_id,
                    "nodes": [],
                    "edges": [],
                    "message": "No checkpoints found for this thread"
                })

            # 使用 CheckpointParser 建立工作流圖
            workflow_graph = CheckpointParser.build_workflow_graph(checkpoints_data)

            return Response({
                "thread_id": thread_id,
                "node_count": len(workflow_graph['nodes']),
                "edge_count": len(workflow_graph['edges']),
                "nodes": workflow_graph['nodes'],
                "edges": workflow_graph['edges']
            })

        except Exception as e:
            import traceback
            return Response({
                "error": str(e),
                "traceback": traceback.format_exc()
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class Neo4jQueryResultView(APIView):
    """
    獲取 Neo4j 查詢結果（用於 NeoVis 視覺化）
    GET /api/monitoring/neo4j/query?cypher=xxx
    GET /api/monitoring/neo4j/sample (取得範例子圖)
    """
    def get(self, request):
        from neo4j import GraphDatabase
        import os

        # 獲取 Neo4j 連接資訊
        neo4j_uri = os.getenv("NEO4J_URI")
        neo4j_username = os.getenv("NEO4J_USERNAME")
        neo4j_password = os.getenv("NEO4J_PASSWORD")
        neo4j_database = os.getenv("NEO4J_CHRONIC", "neo4j")

        if not all([neo4j_uri, neo4j_username, neo4j_password]):
            return Response({
                "error": "Neo4j connection not configured",
                "message": "Please set NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD in .env"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 獲取查詢參數
        cypher_query = request.GET.get('cypher')
        sample = request.GET.get('sample', 'false').lower() == 'true'

        # 如果請求範例數據
        if sample or not cypher_query:
            cypher_query = """
            MATCH (n)-[r]->(m)
            RETURN n, r, m
            LIMIT 50
            """

        try:
            driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_username, neo4j_password))

            with driver.session(database=neo4j_database) as session:
                result = session.run(cypher_query)

                # 轉換結果為 NeoVis 格式
                nodes = {}
                relationships = []

                for record in result:
                    # 處理節點
                    for key in record.keys():
                        value = record[key]

                        # 如果是節點
                        if hasattr(value, 'id') and hasattr(value, 'labels'):
                            node_id = value.id
                            if node_id not in nodes:
                                nodes[node_id] = {
                                    "id": node_id,
                                    "labels": list(value.labels),
                                    "properties": dict(value)
                                }

                        # 如果是關係
                        elif hasattr(value, 'type') and hasattr(value, 'start_node'):
                            relationships.append({
                                "id": value.id,
                                "type": value.type,
                                "startNode": value.start_node.id,
                                "endNode": value.end_node.id,
                                "properties": dict(value)
                            })

            driver.close()

            return Response({
                "nodes": list(nodes.values()),
                "relationships": relationships,
                "count": {
                    "nodes": len(nodes),
                    "relationships": len(relationships)
                }
            })

        except Exception as e:
            return Response({
                "error": str(e),
                "query": cypher_query
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AgentHistoryView(APIView):
    """
    獲取所有 Thread ID 的歷史記錄
    GET /api/monitoring/agents/history
    """
    def get(self, request):
        try:
            checkpoint_db = Path(__file__).resolve().parent.parent / "graph_rag_agent" / "agent_checkpoint_new.sqlite"

            if not checkpoint_db.exists():
                return Response({
                    "error": "Checkpoint database not found"
                }, status=status.HTTP_404_NOT_FOUND)

            conn = sqlite3.connect(str(checkpoint_db))
            cursor = conn.cursor()

            # 查詢所有唯一的 thread_id 及其統計信息
            cursor.execute("""
                SELECT
                    thread_id,
                    COUNT(*) as checkpoint_count,
                    MIN(checkpoint_id) as first_checkpoint,
                    MAX(checkpoint_id) as last_checkpoint,
                    SUM(LENGTH(checkpoint)) as total_size
                FROM checkpoints
                GROUP BY thread_id
                ORDER BY last_checkpoint DESC
                LIMIT 100
            """)

            threads = []
            for row in cursor.fetchall():
                threads.append({
                    "thread_id": row[0],
                    "checkpoint_count": row[1],
                    "first_checkpoint": row[2],
                    "last_checkpoint": row[3],
                    "total_size": row[4] or 0
                })

            conn.close()

            return Response({
                "threads": threads,
                "total": len(threads)
            })

        except Exception as e:
            return Response({
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GraphRAGTraceView(APIView):
    """
    獲取 GraphRAG 查詢追蹤記錄
    GET /api/monitoring/graphrag-trace?thread_id=xxx
    """
    def get(self, request):
        thread_id = request.GET.get('thread_id')

        if not thread_id:
            return Response({
                "error": "thread_id parameter is required"
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            from .utils.checkpoint_parser import CheckpointParser

            checkpoint_db = Path(__file__).resolve().parent.parent / "graph_rag_agent" / "agent_checkpoint_new.sqlite"

            if not checkpoint_db.exists():
                return Response({
                    "error": "Checkpoint database not found"
                }, status=status.HTTP_404_NOT_FOUND)

            conn = sqlite3.connect(str(checkpoint_db))
            cursor = conn.cursor()

            # 查詢特定 thread 的所有 checkpoint
            cursor.execute("""
                SELECT checkpoint_id, checkpoint
                FROM checkpoints
                WHERE thread_id = ?
                ORDER BY checkpoint_id ASC
            """, (thread_id,))

            all_queries = []
            for row in cursor.fetchall():
                checkpoint_id, blob = row
                queries = CheckpointParser.extract_graphrag_queries(blob)

                for query in queries:
                    query['checkpoint_id'] = checkpoint_id
                    all_queries.append(query)

            conn.close()

            return Response({
                "thread_id": thread_id,
                "query_count": len(all_queries),
                "queries": all_queries
            })

        except Exception as e:
            import traceback
            return Response({
                "error": str(e),
                "traceback": traceback.format_exc()
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class Neo4jAgentTraceView(APIView):
    """
    獲取 Agent 使用 Neo4j 的追蹤記錄（從記憶體追蹤器）
    GET /api/monitoring/neo4j/agent-trace?thread_id=xxx

    返回特定對話中 Agent 調用 Neo4j GraphRAG 工具的詳細記錄，
    包括查詢的節點、關係、文本塊等完整圖譜數據
    """
    def get(self, request):
        thread_id = request.GET.get('thread_id')

        if not thread_id:
            return Response({
                "error": "thread_id parameter is required"
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            # 從記憶體追蹤器獲取數據
            from graph_rag_agent.agent_tracker import tracker

            execution = tracker.get_execution(thread_id)

            if not execution:
                return Response({
                    "error": "Thread not found",
                    "thread_id": thread_id
                }, status=status.HTTP_404_NOT_FOUND)

            # 提取所有 GraphRAG 工具調用
            neo4j_traces = []

            for agent in execution.get('agents', []):
                agent_name = agent.get('name', '')

                for tool in agent.get('tools_used', []):
                    tool_name = tool.get('tool', '')

                    # 只收集 Neo4j 相關工具
                    if tool_name in ['chronic_search', 'cardiovascular_search']:
                        graph_data = tool.get('graph_data')

                        if graph_data:
                            neo4j_traces.append({
                                'agent_name': agent_name,
                                'agent_display_name': agent.get('display_name', agent_name),
                                'tool_name': tool_name,
                                'timestamp': tool.get('timestamp'),
                                'query_args': tool.get('args', ''),
                                'answer_summary': tool.get('result_summary', ''),
                                'graph_data': {
                                    'database': graph_data.get('database', 'unknown'),
                                    'nodes': graph_data.get('nodes', []),
                                    'relationships': graph_data.get('relationships', []),
                                    'chunks': graph_data.get('chunks', []),
                                    'statistics': {
                                        'node_count': graph_data.get('node_count', 0),
                                        'relationship_count': graph_data.get('relationship_count', 0),
                                        'chunk_count': graph_data.get('chunk_count', 0)
                                    }
                                },
                                'status': tool.get('status', 'unknown')
                            })

            return Response({
                "thread_id": thread_id,
                "query": execution.get('query', ''),
                "started_at": execution.get('started_at'),
                "status": execution.get('status', 'unknown'),
                "trace_count": len(neo4j_traces),
                "traces": neo4j_traces
            })

        except Exception as e:
            import traceback
            return Response({
                "error": str(e),
                "traceback": traceback.format_exc()
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class HealthCheckView(APIView):
    """
    健康檢查端點
    GET /api/monitoring/health
    """
    def get(self, request):
        return Response({
            "status": "healthy",
            "service": "monitoring-api",
            "version": "1.0.0"
        })
