#!/usr/bin/env python3
"""
精確清理 multi_agent.py - 基於行號直接刪除
"""

# 讀取檔案
with open('graph_rag_agent/multi_agent.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"原始行數: {len(lines)}")

# 需要刪除的行範圍 (基於分析):
# 1. supervisor_decomposition_node: 約 1535-1729
# 2. integration_node: 約 1732-1849
# 3. create_agent_task_node 及相關: 約 1850-1967
# 4. route_after_task_analysis: 約 2012-2039
# 5. route_after_decomposition: 約 2043-2086
# 6. parallel_join_node: 約 2090-2139
# 7. route_after_join: 約 2143-2163
# 8. workflow_legacy: 約 2201-2219

# 找到關鍵標記
new_workflow_line = None
for i, line in enumerate(lines):
    if 'new_workflow = (' in line and i > 1800:  # 修正搜尋範圍
        new_workflow_line = i
        print(f"找到 new_workflow 在行 {i+1}")
        break

if not new_workflow_line:
    print("錯誤: 找不到 new_workflow")
    exit(1)

# 找到 supervisor_decomposition_node 開始
decomp_start = None
for i in range(1500, 1600):
    if 'def supervisor_decomposition_node' in lines[i]:
        decomp_start = i
        print(f"找到 supervisor_decomposition_node 在行 {i+1}")
        break

# 策略: 保留 1-decomp_start, 刪除 decomp_start到new_workflow之間的所有東西
# 然後保留 new_workflow 到結尾,並刪除 workflow_legacy

if decomp_start:
    # 找到 workflow_legacy
    legacy_start = None
    legacy_end = None
    for i in range(new_workflow_line, len(lines)):
        if 'workflow_legacy=(' in lines[i]:
            legacy_start = i
            print(f"找到 workflow_legacy 在行 {i+1}")
            # 找結尾
            for j in range(i+1, min(i+20, len(lines))):
                if lines[j].strip() == ')':
                    legacy_end = j
                    print(f"  結束於行 {j+1}")
                    break
            break

    # 組合新檔案
    new_lines = []
    new_lines.extend(lines[:decomp_start])  # 保留開頭
    new_lines.append('\n')
    new_lines.append('# ============================================================================\n')
    new_lines.append('# Workflow 定義 - Supervisor → Agent → Supervisor 架構\n')
    new_lines.append('# ============================================================================\n')
    new_lines.append('\n')

    if legacy_start:
        # 從 new_workflow 到 legacy_start
        new_lines.extend(lines[new_workflow_line:legacy_start])
        # 跳過 legacy, 保留剩餘
        if legacy_end:
            new_lines.extend(lines[legacy_end+2:])  # +2 跳過空行
        else:
            new_lines.extend(lines[legacy_start+15:])  # 估算
    else:
        new_lines.extend(lines[new_workflow_line:])

    print(f"新行數: {len(new_lines)}")
    print(f"刪除了: {len(lines) - len(new_lines)} 行")

    # 寫回
    with open('graph_rag_agent/multi_agent.py', 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

    print("清理完成!")
else:
    print("錯誤: 找不到 supervisor_decomposition_node")
