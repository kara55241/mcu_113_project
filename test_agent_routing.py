"""
測試代理路由識別功能
驗證新的 extract_transferred_agent_from_messages 函數是否正確識別代理
"""
import sys
import os

# 添加專案路徑
sys.path.insert(0, os.path.dirname(__file__))

from graph_rag_agent.multi_agent import extract_transferred_agent_from_messages, AGENT_DISPLAY_NAMES

def test_new_workflow_routing():
    """測試新任務指派型 workflow 的路由識別"""
    print("=" * 60)
    print("測試 1: 新 Workflow - 單一 Agent (心血管)")
    print("=" * 60)

    test_result = {
        'agent_responses': {
            'cardiovascular_agent': '根據圖譜資料，高血壓需要...'
        },
        'messages': [],
        'subtasks': {
            'cardiovascular_agent': {
                'task_id': 'test-123',
                'query': '高血壓如何預防？',
                'status': 'completed'
            }
        }
    }

    agent = extract_transferred_agent_from_messages(test_result)
    display_name = AGENT_DISPLAY_NAMES.get(agent, agent)

    print(f"[OK] 識別結果: {display_name} ({agent})")
    assert agent == 'cardiovascular_agent', f"預期 'cardiovascular_agent', 得到 '{agent}'"
    print("[OK] 測試通過\n")

def test_multi_agent_routing():
    """測試多代理協作的路由識別"""
    print("=" * 60)
    print("測試 2: 新 Workflow - 多 Agent 協作")
    print("=" * 60)

    test_result = {
        'agent_responses': {
            'chronic_agent': '糖尿病管理建議...',
            'cardiovascular_agent': '心血管風險評估...'
        },
        'messages': []
    }

    # 應該返回第一個有回應的 agent（按優先順序）
    agent = extract_transferred_agent_from_messages(test_result)
    display_name = AGENT_DISPLAY_NAMES.get(agent, agent)

    print(f"[OK] 識別結果: {display_name} ({agent})")
    assert agent == 'chronic_agent', f"預期 'chronic_agent' (優先順序), 得到 '{agent}'"
    print("[OK] 測試通過\n")

def test_old_workflow_routing():
    """測試舊轉交型 workflow 的路由識別（向後兼容）"""
    print("=" * 60)
    print("測試 3: 舊 Workflow - 轉交訊息識別")
    print("=" * 60)

    from langchain_core.messages import ToolMessage

    test_messages = [
        ToolMessage(
            content="Successfully transferred to chronic_agent",
            tool_call_id="test-123"
        )
    ]

    agent = extract_transferred_agent_from_messages(test_messages)
    display_name = AGENT_DISPLAY_NAMES.get(agent, agent)

    print(f"[OK] 識別結果: {display_name} ({agent})")
    assert agent == 'chronic_agent', f"預期 'chronic_agent', 得到 '{agent}'"
    print("[OK] 測試通過\n")

def test_fast_path_routing():
    """測試 Fast-Path 處理（無 agent 轉交）"""
    print("=" * 60)
    print("測試 4: Fast-Path - 簡單問候")
    print("=" * 60)

    test_result = {
        'agent_responses': {},  # 空的，因為是 fast-path
        'messages': []
    }

    agent = extract_transferred_agent_from_messages(test_result)

    print(f"[OK] 識別結果: {agent}")
    assert agent is None, f"預期 None (無 agent), 得到 '{agent}'"
    print("[OK] 測試通過 - 正確識別為無需 agent 處理\n")

def main():
    print("\n" + "=" * 60)
    print("開始測試代理路由識別功能")
    print("=" * 60 + "\n")

    try:
        test_new_workflow_routing()
        test_multi_agent_routing()
        test_old_workflow_routing()
        test_fast_path_routing()

        print("=" * 60)
        print("[SUCCESS] 所有測試通過！")
        print("=" * 60)
        print("\n修復總結:")
        print("• 新 workflow 能正確識別 agent_responses")
        print("• 多代理協作按優先順序識別")
        print("• 舊 workflow 向後兼容正常")
        print("• Fast-path 處理正確（返回 None）")

    except AssertionError as e:
        print(f"\n[FAILED] 測試失敗: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] 執行錯誤: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
