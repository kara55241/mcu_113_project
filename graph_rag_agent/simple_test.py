#!/usr/bin/env python3
"""
簡單測試net_search工具直接調用
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from multi_agent import net_search

def test_simple():
    print("直接測試net_search工具")
    print("=" * 40)

    # 測試地點查詢
    print("\n測試1: 地點查詢")
    print("-" * 20)
    try:
        result = net_search("台北心臟科醫院")
        print("結果:")
        print(result)
        print()
    except Exception as e:
        print(f"錯誤: {e}")

    # 測試一般查詢
    print("\n測試2: 一般查詢")
    print("-" * 20)
    try:
        result = net_search("老人補助申請")
        print("結果:")
        print(result)
        print()
    except Exception as e:
        print(f"錯誤: {e}")

if __name__ == "__main__":
    test_simple()