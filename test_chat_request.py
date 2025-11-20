"""
測試實際的聊天請求，觸發多代理系統
"""

import requests
import json
import time

# Django 服務器地址
BASE_URL = "http://127.0.0.1:8000"

def test_chat_request():
    """發送聊天請求並監控執行"""

    # 1. 獲取 CSRF Token
    session = requests.Session()
    response = session.get(f"{BASE_URL}/")
    csrf_token = session.cookies.get('csrftoken')

    print("=" * 60)
    print("測試聊天請求與監控顯示")
    print("=" * 60)

    # 2. 發送聊天請求
    chat_data = {
        "message": "糖尿病患者可以吃蜂蜜嗎？",
        "chatId": f"test-chat-{int(time.time())}"
    }

    print(f"\n發送聊天請求...")
    print(f"訊息: {chat_data['message']}")
    print(f"Chat ID: {chat_data['chatId']}")

    headers = {
        'X-CSRFToken': csrf_token,
        'Content-Type': 'application/json'
    }

    try:
        response = session.post(
            f"{BASE_URL}/chat/",
            json=chat_data,
            headers=headers,
            timeout=60
        )

        print(f"\n回應狀態碼: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print(f"回應訊息: {result.get('response', '')[:200]}...")

            # 3. 查詢監控 API，獲取執行詳情
            print("\n" + "=" * 60)
            print("查詢監控 API...")
            print("=" * 60)

            time.sleep(2)  # 等待追蹤器更新

            # 獲取最近的 threads
            monitor_response = session.get(f"{BASE_URL}/api/monitoring/agents/status")
            monitor_data = monitor_response.json()

            print(f"\n資料來源: {monitor_data.get('source')}")
            print(f"Thread 總數: {monitor_data.get('thread_count', 0)}")

            threads = monitor_data.get('threads', [])
            if threads:
                latest_thread = threads[0]
                thread_id = latest_thread['thread_id']

                print(f"\n最新 Thread ID: {thread_id}")
                print(f"狀態: {latest_thread.get('status')}")
                print(f"查詢: {latest_thread.get('query', '')[:60]}...")
                print(f"代理數量: {len(latest_thread.get('agents', []))}")

                # 顯示分組資訊
                grouped = latest_thread.get('grouped_agents', {})
                if grouped:
                    print("\n邏輯層分組:")
                    print(f"  Supervisor 層: {len(grouped.get('supervisor', []))} 個代理")
                    for agent in grouped.get('supervisor', []):
                        print(f"    - {agent.get('display_name')}")

                    print(f"  專家代理層: {len(grouped.get('expert', []))} 個代理")
                    for agent in grouped.get('expert', []):
                        print(f"    - {agent.get('display_name')}")

                    print(f"  整合層: {len(grouped.get('integration', []))} 個代理")
                    for agent in grouped.get('integration', []):
                        print(f"    - {agent.get('display_name')}")

                print("\n" + "=" * 60)
                print("監控儀表板鏈接:")
                print("=" * 60)
                print(f"http://localhost:5174/workflow")
                print(f"\n可以在儀表板中選擇 Thread ID 查看視覺化流程圖")

            else:
                print("\n尚無活動的 Thread")

        else:
            print(f"請求失敗: {response.text}")

    except Exception as e:
        print(f"錯誤: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_chat_request()
