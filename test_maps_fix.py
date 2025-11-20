"""
測試地圖搜尋路由修正 - 完整流程測試
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from graph_rag_agent.multi_agent import _calculate_intent_similarities, _determine_task_type_and_agents

def test_maps_routing():
    """測試地圖查詢是否正確路由"""

    test_cases = [
        {
            "query": "幫我找台北市的心臟科診所",
            "expected_type": "simple_maps",
            "description": "包含「找」+ 地點名稱 + 醫療機構"
        },
        {
            "query": "幫我找離桃園夜市近的骨科診所",
            "expected_type": "simple_maps",
            "description": "包含「找」+ 地標 + 醫療機構"
        },
        {
            "query": "台北車站附近有什麼醫院",
            "expected_type": "simple_maps",
            "description": "包含「附近」+ 地點"
        },
        {
            "query": "最近的藥局在哪裡",
            "expected_type": "simple_maps",
            "description": "包含「最近」+ 「在哪」"
        },
        {
            "query": "糖尿病患者可以吃什麼水果",
            "expected_type": "single_expert",
            "description": "純醫療諮詢，無地點查詢"
        },
        {
            "query": "高血壓的症狀有哪些",
            "expected_type": "single_expert",
            "description": "純醫療知識查詢"
        }
    ]

    print("=" * 80)
    print("地圖路由修正測試 - 完整流程")
    print("=" * 80)

    passed = 0
    failed = 0

    for i, case in enumerate(test_cases, 1):
        query = case["query"]
        expected = case["expected_type"]
        desc = case["description"]

        print(f"\n測試 {i}: {query}")
        print(f"說明: {desc}")
        print(f"預期: {expected}")

        try:
            # 計算相似度
            similarities = _calculate_intent_similarities(query)

            # 判斷任務類型
            result = _determine_task_type_and_agents(similarities, query, query)

            actual = result['type']
            print(f"實際: {actual}")

            # 顯示相似度分數
            print(f"相似度: maps={similarities.get('simple_maps', 0):.3f}, "
                  f"chronic={similarities.get('chronic_disease', 0):.3f}, "
                  f"cardio={similarities.get('cardiovascular', 0):.3f}")

            if actual == expected:
                print("結果: [PASS]")
                passed += 1
            else:
                print(f"結果: [FAIL] (預期 {expected}, 實際 {actual})")
                failed += 1

        except Exception as e:
            print(f"結果: [ERROR] - {str(e)}")
            failed += 1

    print("\n" + "=" * 80)
    print(f"測試總結: {passed} 通過, {failed} 失敗, 總計 {passed + failed}")
    print("=" * 80)

    return failed == 0

if __name__ == "__main__":
    success = test_maps_routing()
    sys.exit(0 if success else 1)
