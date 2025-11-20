"""
測試監控顯示的代理追蹤功能
模擬一個完整的多代理執行流程
"""

import sys
import os

# 添加專案根目錄到路徑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from graph_rag_agent.agent_tracker import tracker

def simulate_agent_execution():
    """模擬一個完整的代理執行流程"""

    thread_id = "test-thread-001"
    query = "糖尿病患者可以吃蜂蜜嗎？"

    print(f"\n開始模擬代理執行流程...")
    print(f"Thread ID: {thread_id}")
    print(f"查詢: {query}\n")

    # 1. Supervisor 分析
    print("1. SUPERVISOR 開始分析...")
    tracker.start_agent(thread_id, "supervisor_analysis", query)
    tracker.complete_agent(thread_id, "supervisor_analysis")

    # 2. Supervisor 任務拆解
    print("2. SUPERVISOR 進行任務拆解...")
    tracker.start_agent(thread_id, "supervisor_decomposition", query)
    tracker.log_tool_call(
        thread_id,
        "supervisor_decomposition",
        "task_decomposition",
        {"query": query},
        {"tasks": ["慢性病查詢", "事實查核"]}
    )
    tracker.complete_agent(thread_id, "supervisor_decomposition")

    # 3. 慢性病專家代理
    print("3. CHRONIC AGENT 開始執行...")
    tracker.start_agent(thread_id, "chronic_agent", "")
    tracker.log_tool_call(
        thread_id,
        "chronic_agent",
        "chronic_search",
        {"query": "糖尿病 飲食 蜂蜜"},
        {
            "answer": "糖尿病患者應謹慎食用蜂蜜，因為蜂蜜含有大量單糖...",
            "graph_data": {
                "nodes": [
                    {"id": "糖尿病", "label": "Disease", "name": "糖尿病"},
                    {"id": "飲食控制", "label": "Treatment", "name": "飲食控制"}
                ],
                "relationships": [
                    {"type": "需要", "start": "糖尿病", "end": "飲食控制"}
                ],
                "chunks": ["糖尿病患者需要嚴格控制血糖..."]
            },
            "database": "diseases-tw"
        }
    )
    tracker.complete_agent(thread_id, "chronic_agent")

    # 4. 事實查核代理
    print("4. FACT-CHECK AGENT 開始執行...")
    tracker.start_agent(thread_id, "fact_check_agent", "")
    tracker.log_tool_call(
        thread_id,
        "fact_check_agent",
        "google_fact_check_tool",
        {"query": "糖尿病患者吃蜂蜜"},
        "根據搜尋結果，多數醫學資料指出糖尿病患者應該避免或限制蜂蜜攝取..."
    )
    tracker.complete_agent(thread_id, "fact_check_agent")

    # 5. 整合節點
    print("5. INTEGRATION 開始整合結果...")
    tracker.start_agent(thread_id, "integration", "")
    tracker.complete_agent(thread_id, "integration")

    # 6. 完成整個 Thread
    print("6. Thread 執行完成！\n")
    tracker.complete_thread(thread_id)

    # 取得執行結果
    execution = tracker.get_execution(thread_id)

    print("=" * 60)
    print("執行結果摘要:")
    print("=" * 60)
    print(f"Thread ID: {execution['thread_id']}")
    print(f"狀態: {execution['status']}")
    print(f"代理總數: {len(execution['agents'])}")

    print("\n按時間序排列的代理:")
    for i, agent in enumerate(execution['agents'], 1):
        print(f"  {i}. {agent['display_name']} ({agent['name']}) - {agent['role']}")

    print("\n按邏輯層分組的代理:")
    grouped = execution['grouped_agents']
    print(f"  Supervisor層: {len(grouped['supervisor'])} 個代理")
    for agent in grouped['supervisor']:
        print(f"    - {agent['display_name']}")

    print(f"  專家代理層: {len(grouped['expert'])} 個代理")
    for agent in grouped['expert']:
        print(f"    - {agent['display_name']}")

    print(f"  整合層: {len(grouped['integration'])} 個代理")
    for agent in grouped['integration']:
        print(f"    - {agent['display_name']}")

    print("\n=" * 60)
    print("測試完成！")
    print("=" * 60)
    print(f"\n請訪問監控儀表板查看視覺化效果:")
    print(f"http://localhost:5174/workflow")
    print(f"\n或透過 API 查看:")
    print(f"http://127.0.0.1:8000/api/monitoring/agents/status?thread_id={thread_id}")
    print()

if __name__ == "__main__":
    simulate_agent_execution()
