"""
測試對話連續性 - 檢查檢查點恢復機制是否正常工作
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from multi_agent import generate_response
import time

def test_conversation_continuity():
    """測試對話是否能夠保持連續性"""

    # 使用新的 session_id 測試改進後的提示詞
    session_id = "test_improved_prompts_002"

    print("=== 測試改進後的對話連續性 ===")
    print(f"使用 session_id: {session_id}")
    print()

    # 第一個問題
    print("[USER] 第一個問題：")
    question1 = "我最近有點喘不過氣"
    print(f"用戶: {question1}")

    response1 = generate_response(question1, session_id)
    print(f"AI回應: {response1.get('output', '')[:200]}...")
    print()

    # 等待一下，模擬真實對話間隔
    time.sleep(2)

    # 第二個問題 - 應該能夠參考第一個問題的上下文
    print("[USER] 第二個問題（應該能參考前面的喘不過氣）：")
    question2 = "我有抽菸 跟這個有關嗎"
    print(f"用戶: {question2}")

    response2 = generate_response(question2, session_id)
    print(f"AI回應: {response2.get('output', '')}")
    print()

    # 檢查第二個回應是否包含對第一個問題的參考
    response_text = response2.get('output', '').lower()
    continuity_indicators = [
        '喘不過氣', '呼吸', '前面', '剛才', '之前', '您提到', '您說的', '抽菸', '吸菸'
    ]

    found_indicators = [indicator for indicator in continuity_indicators if indicator in response_text]

    print("=== 連續性分析 ===")
    if found_indicators:
        print(f"[OK] 檢測到連續性指標: {found_indicators}")
        print("[OK] 對話具有連續性")
    else:
        print("[ERROR] 未檢測到連續性指標")
        print("[ERROR] 對話可能缺乏連續性")

    print("\n=== 詳細回應內容 ===")
    print("第二個回應完整內容:")
    print(response2.get('output', ''))

if __name__ == "__main__":
    test_conversation_continuity()