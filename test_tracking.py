#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""測試 Agent 追蹤功能"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")

import django
django.setup()

from graph_rag_agent.multi_agent import generate_response
from graph_rag_agent.agent_tracker import tracker

print("\n" + "="*80)
print("測試：Agent 追蹤與監控顯示")
print("="*80 + "\n")

query = "我有糖尿病和高血壓，會影響心臟嗎？"
session_id = "tracking_test_001"

print(f"查詢: {query}")
print(f"Session ID: {session_id}\n")

try:
    # 執行查詢
    response = generate_response(query, session_id=session_id)

    print(f"\n處理 Agent: {response['data']['transferred_agent']}")
    print(f"處理時間: {response['data']['processing_time']}秒")

    # 從追蹤器獲取執行資訊
    execution = tracker.get_execution(session_id)

    if execution:
        print("\n" + "="*80)
        print("追蹤器記錄的執行資訊:")
        print("="*80)

        # 顯示所有 agents
        print(f"\n執行的 Agents (共 {len(execution['agents'])} 個):")
        for agent in execution['agents']:
            print(f"\n  - {agent['display_name']}")
            print(f"    角色: {agent['role']}")
            print(f"    狀態: {agent['status']}")
            print(f"    開始: {agent['started_at']}")
            if agent['completed_at']:
                print(f"    完成: {agent['completed_at']}")
            if agent['tools_used']:
                tool_names = []
                for t in agent['tools_used']:
                    if isinstance(t, dict) and 'name' in t:
                        tool_names.append(t['name'])
                if tool_names:
                    print(f"    工具: {', '.join(tool_names)}")

        # 顯示分組資訊
        grouped = execution.get('grouped_agents', {})
        print(f"\n按角色分組:")
        print(f"  - Supervisor 節點: {len(grouped.get('supervisor', []))} 個")
        print(f"  - Expert Agents: {len(grouped.get('expert', []))} 個")

        # 顯示 Expert Agents 詳細資訊
        expert_agents = grouped.get('expert', [])
        if expert_agents:
            print(f"\n並行執行的 Expert Agents:")
            for agent in expert_agents:
                print(f"  ✓ {agent['display_name']}")

    print("\n" + "="*80)
    print("測試完成！")
    print("\n監控儀表板: http://localhost:5173")
    print("  → 您應該可以在儀表板中看到：")
    print("     • SUPERVISOR [分析/路由/整合] 節點")
    print("     • 並行執行的慢性疾病專家 + 心血管專家")
    print("="*80 + "\n")

except Exception as e:
    print(f"\n錯誤: {e}")
    import traceback
    traceback.print_exc()
