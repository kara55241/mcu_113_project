#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""測試單一 Agent 的 Supervisor 總結功能"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")

import django
django.setup()

from graph_rag_agent.multi_agent import generate_response
from graph_rag_agent.agent_tracker import tracker

print("\n" + "="*80)
print("測試：單一 Agent 執行 + Supervisor 總結")
print("="*80 + "\n")

# 測試單一慢性疾病問題（應該只觸發 chronic_agent）
query = "糖尿病患者應該如何控制血糖？"
session_id = "single_agent_test"

print(f"查詢: {query}")
print(f"預期: chronic_agent → integration (總結) → END\n")

try:
    response = generate_response(query, session_id=session_id)

    print(f"\n處理 Agent: {response['data']['transferred_agent']}")
    print(f"處理時間: {response['data']['processing_time']}秒")

    # 從追蹤器獲取執行資訊
    execution = tracker.get_execution(session_id)

    if execution:
        print("\n" + "-"*80)
        print("執行流程追蹤:")
        print("-"*80)

        for idx, agent in enumerate(execution['agents'], 1):
            print(f"\n{idx}. {agent['display_name']}")
            print(f"   狀態: {agent['status']}")

        # 檢查是否有 integration 節點
        has_integration = any(
            'integration' in agent['name'].lower() or '整合' in agent.get('display_name', '')
            for agent in execution['agents']
        )

        print("\n" + "-"*80)
        if has_integration:
            print("✅ 確認：單一 Agent 回應經過 Supervisor 整合節點")
        else:
            print("❌ 警告：單一 Agent 回應未經過整合節點")
        print("-"*80)

    print(f"\n回應內容（前400字）:")
    print("="*80)
    print(response['output'][:400])
    print("="*80)

    print("\n✅ 測試完成！")
    print("監控儀表板: http://localhost:5173")

except Exception as e:
    print(f"\n錯誤: {e}")
    import traceback
    traceback.print_exc()
