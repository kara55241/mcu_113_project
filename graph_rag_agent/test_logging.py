#!/usr/bin/env python3
"""
測試代理轉交日誌記錄功能
Test agent transfer logging functionality
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from multi_agent import generate_response

async def test_agent_transfers():
    """測試不同類型的查詢來驗證代理轉交日誌"""

    test_cases = [
        "我有糖尿病，應該注意什麼飲食？",  # Should go to chronic_agent
        "我的血壓高，有什麼運動建議？",    # Should go to cardiovascular_agent
        "最新的流感疫苗資訊是什麼？",      # Should go to fact_check_agent with net_search
        "台北有哪些心臟科醫院？"          # Should go to cardiovascular_agent then maybe fact_check for maps
    ]

    print("開始測試代理轉交日誌記錄功能...")
    print("=" * 60)

    for i, question in enumerate(test_cases, 1):
        print(f"\n測試案例 {i}: {question}")
        print("-" * 40)

        try:
            # 使用固定的 session_id 來測試
            session_id = f"test_session_{i}"

            response = await generate_response(question, session_id)

            print(f"回應長度: {len(response)} 字符")
            print(f"回應摘要: {response[:100]}...")

        except Exception as e:
            print(f"測試失敗: {str(e)}")

        print("\n" + "=" * 60)

    print("測試完成！請檢查日誌文件查看代理轉交記錄。")

if __name__ == "__main__":
    asyncio.run(test_agent_transfers())