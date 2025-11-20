#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
檢查任務指派型 Supervisor 實施狀態
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

print("正在檢查任務指派型 Supervisor 實施...")
print("="*80)

try:
    from graph_rag_agent import multi_agent
    print("✅ multi_agent 模組導入成功")

    # 檢查核心節點函數是否存在
    nodes_to_check = [
        'supervisor_task_analysis_node',
        'supervisor_fast_path_node',
        'supervisor_decomposition_node',
        'integration_node',
        'create_agent_task_node'
    ]

    print("\n檢查核心節點函數:")
    for node_name in nodes_to_check:
        if hasattr(multi_agent, node_name):
            print(f"  ✅ {node_name}")
        else:
            print(f"  ❌ {node_name} 缺失")

    # 檢查路由函數
    routes_to_check = [
        'route_after_task_analysis',
        'route_after_decomposition',
        'route_after_agent_execution'
    ]

    print("\n檢查路由函數:")
    for route_name in routes_to_check:
        if hasattr(multi_agent, route_name):
            print(f"  ✅ {route_name}")
        else:
            print(f"  ❌ {route_name} 缺失")

    # 檢查 workflows
    print("\n檢查 Workflows:")
    if hasattr(multi_agent, 'new_workflow'):
        print(f"  ✅ new_workflow 存在")
        print(f"     節點數: {len(multi_agent.new_workflow.nodes)}")
    else:
        print(f"  ❌ new_workflow 缺失")

    if hasattr(multi_agent, 'workflow_legacy'):
        print(f"  ✅ workflow_legacy 存在 (舊架構備用)")
    else:
        print(f"  ❌ workflow_legacy 缺失")

    if hasattr(multi_agent, 'workflow'):
        print(f"  ✅ workflow 變數存在")
        # 檢查是否指向新 workflow
        if multi_agent.workflow == multi_agent.new_workflow:
            print(f"     ✅ workflow 指向 new_workflow (任務指派型)")
        else:
            print(f"     ⚠️ workflow 指向其他 workflow")
    else:
        print(f"  ❌ workflow 變數缺失")

    # 檢查 State 結構
    print("\n檢查 State 結構:")
    if hasattr(multi_agent, 'State'):
        state_class = multi_agent.State
        expected_fields = ['task_analysis', 'subtasks', 'agent_responses', 'fast_path_handled', 'needs_integration']
        for field in expected_fields:
            # Python 3.7+ dataclass 檢查
            if hasattr(state_class, '__annotations__') and field in state_class.__annotations__:
                print(f"  ✅ {field}")
            else:
                print(f"  ❌ {field} 缺失")
    else:
        print("  ❌ State 類別缺失")

    # 檢查工具
    print("\n檢查新增工具:")
    if hasattr(multi_agent, 'google_map_search'):
        print(f"  ✅ google_map_search 工具")
    else:
        print(f"  ❌ google_map_search 工具缺失")

    # 檢查 Agent Wrappers
    print("\n檢查 Agent Wrappers:")
    wrappers = [
        'chronic_agent_task_node',
        'cardiovascular_agent_task_node',
        'fact_check_agent_task_node'
    ]
    for wrapper_name in wrappers:
        if hasattr(multi_agent, wrapper_name):
            print(f"  ✅ {wrapper_name}")
        else:
            print(f"  ❌ {wrapper_name} 缺失")

    print("\n" + "="*80)
    print("✅ 任務指派型 Supervisor 實施檢查完成!")
    print("\n建議:")
    print("1. 運行 'venv\\Scripts\\python test_task_assigning.py' 進行功能測試")
    print("2. 運行 'python manage.py runserver' 啟動 Django 服務")
    print("3. 檢查 agent_debug.log 查看詳細運行日誌")

except ImportError as e:
    print(f"❌ 導入失敗: {e}")
    print("請確保已安裝所有依賴: pip install -r requirements.txt")
except Exception as e:
    print(f"❌ 檢查過程出錯: {e}")
    import traceback
    traceback.print_exc()
