#!/usr/bin/env python3
"""
清理 multi_agent.py 的舊程式碼
刪除以下區塊:
1. workflow_legacy (約行 2204-2216)
2. supervisor_decomposition_node (約行 1535-1729)
3. integration_node (約行 1732-1851)
4. create_agent_task_node 及相關 (約行 1850-1967)
5. route_after_task_analysis, route_after_decomposition, parallel_join_node, route_after_join (約行 2012-2173)
"""

# 讀取檔案
with open('graph_rag_agent/multi_agent.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"原始行數: {len(lines)}")

# 要刪除的函數和變數名
items_to_remove = [
    ('def supervisor_decomposition_node', 'return state'),
    ('def integration_node', 'return state'),
    ('def create_agent_task_node', 'return agent_task_node'),
    ('chronic_agent_task_node =', '\n'),
    ('cardiovascular_agent_task_node =', '\n'),
    ('fact_check_agent_task_node =', '\n'),
    ('def route_after_task_analysis', 'return "chronic_agent"'),
    ('def route_after_decomposition', 'return send_list'),
    ('def parallel_join_node', 'return state'),
    ('def route_after_join', 'return "integration"'),
    ('workflow_legacy=(', ')'),
    ('# 預設使用新的任務指派型 workflow', '\n'),
]

# 標記要刪除的行
lines_to_keep = [True] * len(lines)
i = 0
while i < len(lines):
    line = lines[i].strip()

    # 檢查是否是要刪除的函數/變數的開始
    for start_pattern, end_pattern in items_to_remove:
        if start_pattern in lines[i]:
            print(f"找到 '{start_pattern}' 在行 {i+1}")
            # 標記這行及後續直到找到 end_pattern
            j = i
            while j < len(lines):
                lines_to_keep[j] = False
                if end_pattern in lines[j] and j > i:
                    print(f"  結束於行 {j+1}")
                    break
                j += 1
            i = j
            break
    i += 1

# 生成新檔案
new_lines = [lines[i] for i in range(len(lines)) if lines_to_keep[i]]

print(f"清理後行數: {len(new_lines)}")
print(f"刪除了: {len(lines) - len(new_lines)} 行")

# 寫回檔案
with open('graph_rag_agent/multi_agent.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("清理完成!")
