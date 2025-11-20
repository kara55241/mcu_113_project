#!/usr/bin/env python
"""
測試並行執行多專家協作功能

測試場景：
1. 單一疾病問題（應該派發給單一 agent）
2. 多疾病複合問題（應該並行派發給多個 agents）
3. 簡單問候（應該使用 Fast-Path）
"""

import sys
import os

# 添加項目路徑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 設置環境變數（如果需要）
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")

# Django setup
import django
django.setup()

from graph_rag_agent.multi_agent import generate_response
import time

def print_separator(title=""):
    print("\n" + "=" * 80)
    if title:
        print(f"  {title}")
        print("=" * 80)

def test_query(query: str, description: str):
    """測試單一查詢"""
    print_separator(description)
    print(f"[QUERY] {query}\n")

    start_time = time.time()
    try:
        response = generate_response(query, session_id=f"test_{int(time.time())}")
        elapsed = time.time() - start_time

        print(f"[SUCCESS] 回應成功 (耗時: {elapsed:.2f}秒)")
        print(f"\n[METADATA]")
        print(f"   - 處理時間: {response['data']['processing_time']}秒")
        print(f"   - 處理 Agent: {response['data']['transferred_agent']}")
        print(f"   - 回應長度: {response['data']['response_length']} 字符")

        print(f"\n[RESPONSE]")
        print("-" * 80)
        print(response['output'][:500])  # 只顯示前 500 字符
        if len(response['output']) > 500:
            print(f"\n... (省略 {len(response['output']) - 500} 字符)")
        print("-" * 80)

        return response

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"[ERROR] 錯誤 (耗時: {elapsed:.2f}秒)")
        print(f"   錯誤訊息: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def main():
    print_separator("[TEST] 並行多專家協作系統測試")
    print("測試新架構：Task Analysis → Parallel Dispatch → Integration")

    # 測試 1: 單一疾病問題（慢性病）
    test_query(
        "糖尿病患者應該如何控制血糖？",
        "測試 1: 單一慢性疾病問題（預期: chronic_agent）"
    )

    time.sleep(2)

    # 測試 2: 單一疾病問題（心血管）
    test_query(
        "高血壓會導致哪些併發症？",
        "測試 2: 單一心血管疾病問題（預期: cardiovascular_agent）"
    )

    time.sleep(2)

    # 測試 3: 多疾病複合問題（關鍵測試！）
    test_query(
        "我有糖尿病和高血壓，會影響心臟嗎？應該怎麼保養？",
        "測試 3: 多疾病複合問題（預期: chronic_agent + cardiovascular_agent 並行）"
    )

    time.sleep(2)

    # 測試 4: 另一個多疾病場景
    test_query(
        "糖尿病併發心血管疾病怎麼辦？",
        "測試 4: 併發症問題（預期: 多專家並行）"
    )

    time.sleep(2)

    # 測試 5: 簡單問候（Fast-Path）
    test_query(
        "你好",
        "測試 5: 簡單問候（預期: Fast-Path 直接回應）"
    )

    print_separator("[DONE] 測試完成")
    print("\n請檢查以下日誌文件以查看詳細執行流程：")
    print("  - agent_debug.log (多代理系統日誌)")
    print("\n建議使用以下命令查看並行執行日誌：")
    print('  findstr /C:"ROUTE" /C:"PARALLEL" /C:"INTEGRATION" /C:"TASK_ANALYSIS" agent_debug.log')

if __name__ == "__main__":
    main()
