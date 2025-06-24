from sentence_transformers import SentenceTransformer, util
from cofacts_check import search_cofacts
from llm import word_transformer

model = word_transformer
def find_most_similar_cofacts_article(query_text):
    cofacts_result = search_cofacts(query_text)
    articles = []
    nodes = []
    edges = cofacts_result['data']['ListArticles']['edges']
    for edge in edges:
        articles.append(edge['node']['text'])
        nodes.append(edge['node'])
    if not articles:
        return None, None
    sentences = [query_text] + articles
    embeddings = model.encode(sentences)
    query_embedding = embeddings[0]
    article_embeddings = embeddings[1:]
    similarities = util.cos_sim(query_embedding, article_embeddings)[0]
    max_idx = similarities.argmax()
    most_similar_node = nodes[max_idx]
    similarity_score = similarities[max_idx].item()
    return most_similar_node, similarity_score

# 範例呼叫
if __name__ == "__main__":
    query = "台灣加入聯合國"
    node, score = find_most_similar_cofacts_article(query)
    if node:
        print("最相關的文章內容：", node['text'])
        print("AI 回覆：", node.get('aiReplies', []))
        print("人工回覆：", node.get('articleReplies', []))
        print("相似度：", score)
    else:
        print("查無相關文章")