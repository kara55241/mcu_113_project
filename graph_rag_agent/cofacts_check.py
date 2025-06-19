import requests
import json

url = "https://api.cofacts.tw/graphql"

def make_graphql_request(query, variables=None):
    """
    統一發送 GraphQL 請求的函式
    """
    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()

        data = response.json()

        if "errors" in data:
            print("GraphQL 請求發生錯誤:")
            for error in data["errors"]:
                print(error)
            return None
        else:
            return data["data"]
    except requests.exceptions.RequestException as e:
        print(f"請求 Cofacts API 時發生網路或 HTTP 錯誤: {e}")
        return None
    except json.JSONDecodeError:
        print("無法解析 API 回應的 JSON 格式。")
        return None

# --- 查詢文章及其回覆的 GraphQL 語法 ---
query_article_with_replies = """
query GetArticleTruthStatus($id: String!) {
  GetArticle(id: $id) {
    id
    text
    articleReplies(statuses: [NORMAL]) { # 只查詢正常狀態的文章回覆
      reply {
        id
        text
        type # 關鍵：回覆類型 (RUMOR, NOT_RUMOR, etc.)
      }
      positiveFeedbackCount # 關鍵：正面回饋數
      negativeFeedbackCount # 關鍵：負面回饋數
    }
  }
}
"""

def analyze_article_truthfulness(article_id):
    """
    分析指定文章的真偽狀態
    """
    print(f"\n--- 分析文章 ID: {article_id} 的真偽狀態 ---")
    variables = {"id": article_id}
    result = make_graphql_request(query_article_with_replies, variables)

    if not result or not result["GetArticle"]:
        print(f"找不到 ID 為 {article_id} 的文章或請求失敗。")
        return

    article = result["GetArticle"]
    print(f"文章內容: {article['text'][:100]}...")

    if not article["articleReplies"]:
        print("沒有相關回覆，無法判斷真偽。")
        return

    # 初始化計數器
    rumor_replies = []
    not_rumor_replies = []
    other_replies = []

    for ar in article["articleReplies"]:
        reply_type = ar["reply"]["type"]
        positive_feedback = ar["positiveFeedbackCount"]
        negative_feedback = ar["negativeFeedbackCount"]
        feedback_diff = positive_feedback - negative_feedback

        # 優先考慮有較多正面回饋的回覆
        if reply_type == "RUMOR" and feedback_diff > 0:
            rumor_replies.append((ar["reply"]["text"], feedback_diff))
        elif reply_type == "NOT_RUMOR" and feedback_diff > 0:
            not_rumor_replies.append((ar["reply"]["text"], feedback_diff))
        else:
            other_replies.append((ar["reply"]["text"], reply_type, feedback_diff))

    # 簡單的判斷邏輯：
    # 如果有高可信度的 RUMOR 回覆，判定為假
    if rumor_replies:
        rumor_replies.sort(key=lambda x: x[1], reverse=True) # 按回饋數排序
        print(f"\n**判斷結果: 假新聞/謠言 (基於 {len(rumor_replies)} 個支持度較高的『RUMOR』回覆)**")
        print("主要理由 (回覆內容):")
        for text, _ in rumor_replies:
            print(f"- {text[:70]}...")
    # 如果有高可信度的 NOT_RUMOR 回覆，判定為真
    elif not_rumor_replies:
        not_rumor_replies.sort(key=lambda x: x[1], reverse=True)
        print(f"\n**判斷結果: 正確資訊/非謠言 (基於 {len(not_rumor_replies)} 個支持度較高的『NOT_RUMOR』回覆)**")
        print("主要理由 (回覆內容):")
        for text, _ in not_rumor_replies:
            print(f"- {text[:70]}...")
    else:
        # 如果沒有明確的 RUMOR 或 NOT_RUMOR，或回饋數不高
        print("\n**判斷結果: 狀態不明確或無主要事實查核結果。**")
        if other_replies:
            print("其他回覆類型:")
            for text, r_type, _ in other_replies:
                print(f"- 類型: {r_type}, 內容: {text[:70]}...")

# --- 實際呼叫範例 ---
# 為了測試，我們先查詢最新的文章，然後取第一篇文章來分析
keyword = ""  # 你想搜尋的關鍵字
query_search_by_keyword = """
query SearchArticles($keyword: String!) {
  ListArticles(
    filter: { moreLikeThis: { like: $keyword } }
    orderBy: [{createdAt: DESC}]
    first: 5
  ) {
    edges {
      node {
        id
        text
      }
    }
  }
}
"""
variables = {"keyword": keyword}
latest_article_result = make_graphql_request(query_search_by_keyword,variables)
if latest_article_result and latest_article_result["ListArticles"]["edges"]:
    sample_article_id = latest_article_result["ListArticles"]["edges"][0]["node"]["id"]
    analyze_article_truthfulness(sample_article_id)
else:
    print("無法取得文章 ID，請手動提供一個文章 ID 進行分析。")
    # 例如：analyze_article_truthfulness("CoP7h4yB") # 你可以替換為一個已知的文章 ID
    
    
keyword = "疫苗"  # 你想搜尋的關鍵字
query_search_by_keyword = """
query SearchArticles($keyword: String!) {
  ListArticles(
    filter: { moreLikeThis: { like: $keyword } }
    orderBy: [{createdAt: DESC}]
    first: 5
  ) {
    edges {
      node {
        id
        text
      }
    }
  }
}
"""

