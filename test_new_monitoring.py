"""
測試新架構監控功能
驗證任務指派型 Supervisor 架構的追蹤是否正常
"""

import sys
import time
from graph_rag_agent.multi_agent import generate_response
from graph_rag_agent.agent_tracker import tracker

def test_monitoring():
    """測試監控追蹤功能"""

    print("=" * 70)
    print("測試新架構監控功能")
    print("=" * 70)

    # 測試案例
    test_cases = [
        {
            "name": "簡單問候 (應該走 fast_path)",
            "message": "你好",
            "session_id": "test_greeting_001"
        },
        {
            "name": "單一專家問題 (慢性疾病)",
            "message": "糖尿病患者應該注意什麼飲食？",
            "session_id": "test_chronic_001"
        },
        {
            "name": "單一專家問題 (心血管)",
            "message": "心臟病患者可以運動嗎？",
            "session_id": "test_cardio_001"
        }
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'=' * 70}")
        print(f"測試案例 {i}/{len(test_cases)}: {test_case['name']}")
        print(f"{'=' * 70}")
        print(f"問題: {test_case['message']}")
        print(f"Session ID: {test_case['session_id']}")
        print()

        try:
            # 發送查詢
            print("⏳ 正在執行查詢...")
            start_time = time.time()
            result = generate_response(
                message=test_case['message'],
                session_id=test_case['session_id']
            )
            elapsed = time.time() - start_time

            print(f"✅ 查詢完成 (耗時: {elapsed:.2f}秒)")

            # 從 tracker 獲取執行記錄
            execution = tracker.get_execution(test_case['session_id'])

            if execution:
                print(f"\n📊 追蹤記錄:")
                print(f"  - Thread ID: {execution.get('thread_id')}")
                print(f"  - 狀態: {execution.get('status')}")
                print(f"  - 開始時間: {execution.get('started_at')}")
                print(f"  - 執行的 Agents:")

                for agent in execution.get('agents', []):
                    agent_name = agent.get('name')
                    display_name = agent.get('display_name')
                    status = agent.get('status')
                    tools_count = len(agent.get('tools_used', []))

                    print(f"\n    🤖 {display_name} ({agent_name})")
                    print(f"       狀態: {status}")
                    print(f"       工具調用: {tools_count} 次")

                    # 顯示工具調用詳情
                    for tool in agent.get('tools_used', []):
                        tool_name = tool.get('tool')
                        tool_status = tool.get('status')

                        # 檢查是否有圖譜數據
                        graph_data = tool.get('graph_data')
                        if graph_data:
                            node_count = graph_data.get('node_count', 0)
                            rel_count = graph_data.get('relationship_count', 0)
                            chunk_count = graph_data.get('chunk_count', 0)
                            print(f"         - {tool_name}: {tool_status}")
                            print(f"           圖譜數據: {node_count} 節點, {rel_count} 關係, {chunk_count} 文本塊")
                        else:
                            print(f"         - {tool_name}: {tool_status}")

                    # 顯示轉交訊息
                    handoff_msg = agent.get('handoff_message')
                    if handoff_msg:
                        print(f"       轉交訊息: {handoff_msg[:100]}")

                print(f"\n📝 回應預覽:")
                output = result.get('output', '')
                preview = output[:200] + "..." if len(output) > 200 else output
                print(f"  {preview}")
            else:
                print(f"\n⚠️  警告: 沒有找到追蹤記錄")

        except KeyboardInterrupt:
            print("\n\n⏸️  測試被用戶中斷")
            sys.exit(0)
        except Exception as e:
            print(f"\n❌ 測試失敗: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'=' * 70}")
    print("測試完成")
    print(f"{'=' * 70}")

    # 顯示所有追蹤記錄摘要
    all_threads = tracker.get_recent_threads(limit=10)
    print(f"\n📊 所有追蹤記錄 (最近 {len(all_threads)} 個):")
    for thread in all_threads:
        thread_id = thread.get('thread_id', '')[:20]
        agent_count = len(thread.get('agents', []))
        status = thread.get('status')
        print(f"  - {thread_id}: {agent_count} agents, 狀態: {status}")

if __name__ == "__main__":
    test_monitoring()
