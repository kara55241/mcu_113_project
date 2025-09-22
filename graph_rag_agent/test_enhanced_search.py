#!/usr/bin/env python3
"""
測試增強後的net_search功能
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from multi_agent import generate_response

async def test_enhanced_search():
    """測試不同類型查詢的網址返回功能"""

    test_cases = [
        ("地點查詢", "台北有哪些心臟科醫院？"),         # 應該包含地圖連結
        ("政府補助", "老人長照補助申請資格"),          # 應該找到政府網站
        ("疾病資訊", "最新COVID-19疫苗資訊"),         # 應該找到健康資訊網站
    ]

    print("測試增強後的NET_SEARCH功能")
    print("=" * 50)

    for category, question in test_cases:
        print(f"\n[{category}] {question}")
        print("-" * 30)

        try:
            session_id = f"test_{category}"
            response = await generate_response(question, session_id)

            print(f"回應長度: {len(response)} 字符")

            # 檢查回應是否包含網址
            if "http" in response:
                print("✓ 包含網址連結")
            else:
                print("✗ 沒有網址連結")

            # 檢查是否包含地圖連結（對地點查詢）
            if category == "地點查詢" and "maps.google.com" in response:
                print("✓ 包含Google Maps連結")

            print(f"回應預覽: {response[:200]}...")

        except Exception as e:
            print(f"測試失敗: {str(e)}")

        print()

if __name__ == "__main__":
    asyncio.run(test_enhanced_search())