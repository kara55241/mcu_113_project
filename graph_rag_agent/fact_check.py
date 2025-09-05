import requests
import json
import os
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

# 從環境變數獲取 API 金鑰
API_KEY = os.getenv("GOOGLE_FACT_CHECK_API_KEY")
if not API_KEY:
    raise ValueError("GOOGLE_FACT_CHECK_API_KEY 環境變數未設定！請在 .env 檔案中設定此金鑰。")

# Base URL for the Fact Check Tools API
BASE_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"

def search_fact_checks(query: str, language_code='zh-TW', review_publisher_site_filter=None,
                       max_age_days=None, page_size=None, page_token=None, offset=None):
    
    params = {
        "query": query,
        "key": API_KEY,
    }

    if language_code:
        params["languageCode"] = language_code
    if review_publisher_site_filter:
        params["reviewPublisherSiteFilter"] = review_publisher_site_filter
    if max_age_days is not None:
        params["maxAgeDays"] = max_age_days
    if page_size is not None:
        params["pageSize"] = page_size
    if page_token:
        params["pageToken"] = page_token
    if offset is not None:
        params["offset"] = offset

    try:
        # 檢查 API 金鑰是否可用
        if not API_KEY:
            print("錯誤：Google Fact Check API 金鑰未設定")
            return None
            
        response = requests.get(BASE_URL, params=params, timeout=30)
        response.raise_for_status()  # 拋出 HTTP 錯誤異常 (4xx or 5xx)
        
        result = response.json()
        
        # 記錄成功的查詢
        if result.get('claims'):
            print(f"Fact check 查詢成功：找到 {len(result['claims'])} 筆結果")
        else:
            print("Fact check 查詢完成：未找到相關結果")
            
        return result
        
    except requests.exceptions.HTTPError as errh:
        print(f"HTTP 錯誤: {errh}")
        # 如果是 API 金鑰問題，提供更詳細的錯誤信息
        if response.status_code == 403:
            print("可能是 API 金鑰無效或配額不足")
    except requests.exceptions.ConnectionError as errc:
        print(f"連線錯誤: {errc}")
    except requests.exceptions.Timeout as errt:
        print(f"請求逾時: {errt}")
    except requests.exceptions.RequestException as err:
        print(f"請求發生未預期錯誤: {err}")
    except json.JSONDecodeError as json_err:
        print(f"JSON 解析錯誤: {json_err}")
    except Exception as e:
        print(f"其他錯誤: {e}")
        
    return None

if __name__ == "__main__":
    print("--- Simple Search ---")
    results = search_fact_checks("老人宜多吃豬腳，常吃可長壽")
    
    if results:
        if 'claims' in results:
            print(f"Found {len(results['claims'])} claims:")
            for claim in results['claims']:
                print(f"- Claim: {claim.get('text')}")
                if 'claimReview' in claim and claim['claimReview']:
                    for review in claim['claimReview']:
                        print(f"  Review Publisher: {review.get('publisher', {}).get('name')}")
                        print(f"  Review Rating: {review.get('textualRating')}")
                        print(f"  Review URL: {review.get('url')}")
                print("-" * 20)
        else:
            print("No claims found for the query.")

    print("\n" + "="*50 + "\n")
    

