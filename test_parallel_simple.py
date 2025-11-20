#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""簡化的並行測試"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")

import django
django.setup()

from graph_rag_agent.multi_agent import generate_response

print("\n" + "="*80)
print("測試：多疾病並行查詢")
print("="*80 + "\n")

query = "我有糖尿病和高血壓，會影響心臟嗎？"
print(f"查詢: {query}\n")

try:
    response = generate_response(query, session_id="parallel_test_001")

    print(f"處理 Agent: {response['data']['transferred_agent']}")
    print(f"處理時間: {response['data']['processing_time']}秒")
    print(f"\n回應內容（前300字）:")
    print("-" * 80)
    print(response['output'][:300])
    print("\n" + "="*80)
    print("測試完成！請檢查 agent_debug.log 查看並行執行詳情")

except Exception as e:
    print(f"錯誤: {e}")
    import traceback
    traceback.print_exc()
