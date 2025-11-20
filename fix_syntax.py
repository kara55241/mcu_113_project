#!/usr/bin/env python3
"""
修復語法錯誤 - 直接刪除 1599-1921 行之間的廢棄程式碼
"""

with open('graph_rag_agent/multi_agent.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"原始行數: {len(lines)}")

# 保留 1-1598 行
new_lines = lines[:1598]

# 跳到 1923 行 (new_workflow開始)
# 注意: Python 列表索引從 0 開始，所以第 1923 行是 lines[1922]
new_lines.extend(lines[1922:])

print(f"新行數: {len(new_lines)}")
print(f"刪除了: {len(lines) - len(new_lines)} 行")

with open('graph_rag_agent/multi_agent.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("修復完成!")
