"""
監控 API URL 路由配置
"""
from django.urls import path
from . import views

app_name = 'monitoring_api'

urlpatterns = [
    # 健康檢查
    path('health', views.HealthCheckView.as_view(), name='health'),

    # Agent 相關端點
    path('agents/status', views.AgentStatusView.as_view(), name='agent_status'),
    path('agents/flow', views.AgentFlowView.as_view(), name='agent_flow'),
    path('agents/history', views.AgentHistoryView.as_view(), name='agent_history'),

    # Neo4j 相關端點
    path('neo4j/query', views.Neo4jQueryResultView.as_view(), name='neo4j_query'),
    path('neo4j/agent-trace', views.Neo4jAgentTraceView.as_view(), name='neo4j_agent_trace'),

    # GraphRAG 追蹤端點
    path('graphrag-trace', views.GraphRAGTraceView.as_view(), name='graphrag_trace'),
]
