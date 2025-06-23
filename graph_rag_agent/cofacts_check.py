import requests
import json

url = "https://api.cofacts.tw/graphql"

def make_graphql_request(query, variables=None):
    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    headers = {"Content-Type": "application/json"} #告訴server我們發送的是JSON格式的資料

    
    response = requests.post(url, headers=headers, data=json.dumps(payload))
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError:
        print("API 回傳錯誤：", response.text) 
        raise
    result = response.json()
    return result
  
#查詢function
def search_cofacts(keyword):

    query = """
    query ListArticles($keyword: String!, $first: Int) {
      ListArticles(filter: {moreLikeThis: {like: $keyword}}, first: $first) {
        edges {
          node {
            id
            text
            articleReplies {
              reply {
                text
                type
              }
              createdAt
            }
            aiReplies {
              status
              text
            }
          }
        }
      }
    }
    """
    variables = {"keyword": keyword, "first": 3}
    result = make_graphql_request(query, variables)
    return result

  
# 測試
if __name__ == "__main__":
  print(search_cofacts("新冠肺炎疫苗"))  