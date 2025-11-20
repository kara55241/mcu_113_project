"""調試孤立節點的根本原因"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, 'graph_rag_agent')
from graph_rag import graphrag_chronic
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

# 執行查詢獲取孤立節點
result = graphrag_chronic('糖尿病可以吃甜食嗎?', return_graph_data=True)
graph_data = result.get('graph_data', {})
nodes = graph_data.get('nodes', [])
rels = graph_data.get('relationships', [])

# 找出孤立節點
node_degrees = {}
for node in nodes:
    node_degrees[node['id']] = 0

for rel in rels:
    if rel['startNode'] in node_degrees:
        node_degrees[rel['startNode']] += 1
    if rel['endNode'] in node_degrees:
        node_degrees[rel['endNode']] += 1

isolated = [nid for nid, degree in node_degrees.items() if degree == 0]

print(f'發現 {len(isolated)} 個孤立節點')
print('=' * 80)

# 連接 Neo4j 直接查詢這些節點的原始數據
driver = GraphDatabase.driver(
    os.getenv('NEO4J_URI'),
    auth=(os.getenv('NEO4J_USERNAME'), os.getenv('NEO4J_PASSWORD'))
)

for node_id in isolated:
    node = next((n for n in nodes if n['id'] == node_id), None)
    if not node:
        continue

    name = node.get('properties', {}).get('name', 'N/A')
    labels = ','.join(node.get('labels', []))

    print(f'\n【孤立節點】: {name} ({labels})')
    print(f'  Element ID: {node_id}')

    # 在 Neo4j 中查詢這個節點的實際連接情況
    query = """
    MATCH (n)
    WHERE elementId(n) = $node_id

    // 查詢所有連接到這個節點的關係
    OPTIONAL MATCH (n)-[r]-(other)

    RETURN
      n,
      count(r) as total_relationships,
      collect(DISTINCT type(r)) as relationship_types,
      collect(DISTINCT labels(other)) as connected_node_types
    """

    with driver.session(database=os.getenv('NEO4J_CHRONIC')) as session:
        neo4j_result = session.run(query, node_id=node_id)
        record = neo4j_result.single()

        if record:
            print(f'  Neo4j 中的實際度數: {record["total_relationships"]}')
            print(f'  關係類型: {record["relationship_types"]}')
            print(f'  連接的節點類型: {record["connected_node_types"]}')

            # 如果 Neo4j 中有關係，但在返回結果中沒有，說明被過濾了
            if record["total_relationships"] > 0:
                print(f'  ⚠️  警告: 這個節點在 Neo4j 中有 {record["total_relationships"]} 個關係，但在查詢結果中被過濾掉了！')

                # 查詢為什麼被過濾
                detail_query = """
                MATCH (n)
                WHERE elementId(n) = $node_id
                MATCH (n)-[r]-(other)

                RETURN
                  type(r) as rel_type,
                  labels(other) as other_labels,
                  other.name as other_name,
                  other:Chunk as is_chunk
                LIMIT 5
                """

                detail_result = session.run(detail_query, node_id=node_id)
                print(f'\n  關係詳情（前 5 個）：')
                for detail_record in detail_result:
                    rel_type = detail_record['rel_type']
                    other_name = detail_record['other_name']
                    other_labels = ','.join(detail_record['other_labels'])
                    is_chunk = detail_record['is_chunk']

                    status = ''
                    if rel_type == 'FROM_CHUNK':
                        status = ' [被過濾: FROM_CHUNK 關係]'
                    elif is_chunk:
                        status = ' [被過濾: 連接到 Chunk 節點]'

                    print(f'    - {rel_type} -> {other_name} ({other_labels}){status}')

driver.close()

print('\n' + '=' * 80)
print('分析總結：')
print('孤立節點的原因可能是：')
print('1. 該節點的所有關係都是 FROM_CHUNK 類型（被過濾）')
print('2. 該節點只連接到 Chunk 節點（被過濾）')
print('3. 該節點在圖譜中的度數本來就 < 2（被度數過濾）')
print('4. 該節點的連接節點在其他查詢步驟中被過濾掉，導致變成孤立')
