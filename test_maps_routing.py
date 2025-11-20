"""
測試地圖路由邏輯修正
"""
import sys
import os

# 添加項目路徑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 模擬測試（不實際調用 API）
def test_routing_logic():
    test_queries = [
        "幫我找台北市的心臟科診所",
        "幫我找離桃園夜市近的骨科診所",
        "找附近的藥局",
        "台北車站附近有什麼醫院",
        "糖尿病患者可以吃什麼水果？",  # 應該是醫療專家
        "高血壓的症狀有哪些？"  # 應該是醫療專家
    ]

    print("=" * 60)
    print("地圖路由邏輯測試")
    print("=" * 60)

    for query in test_queries:
        print(f"\n查詢: {query}")

        # 模擬關鍵字檢測
        location_keywords = ["在哪", "找", "附近", "最近", "位置", "地點", "地址", "導航", "路線", "幫我找", "搜尋"]
        has_keyword = any(kw in query for kw in location_keywords)

        print(f"  包含地點關鍵字: {has_keyword}")

        if has_keyword:
            print(f"  [OK] 預期路由: simple_maps (Google Maps 搜尋)")
        else:
            print(f"  [WARN] 預期路由: 醫療專家代理")

    print("\n" + "=" * 60)
    print("修正說明:")
    print("1. 增強關鍵字: 添加「找」「幫我找」「搜尋」等動詞")
    print("2. 放寬條件: maps_advantage > -0.05 (原本 > 0.1)")
    print("3. 關鍵字輔助: maps_score > 0.65 + 包含關鍵字即可路由")
    print("=" * 60)

if __name__ == "__main__":
    test_routing_logic()
