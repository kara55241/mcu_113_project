import requests
import json

# Replace with your actual API key
API_KEY = "AIzaSyB2PxK_0hv39nQlazmqaGltXOSQKenZS0A"

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
        response = requests.get(BASE_URL, params=params)
        response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
        return response.json()
    except requests.exceptions.HTTPError as errh:
        print(f"HTTP Error: {errh}")
    except requests.exceptions.ConnectionError as errc:
        print(f"Error Connecting: {errc}")
    except requests.exceptions.Timeout as errt:
        print(f"Timeout Error: {errt}")
    except requests.exceptions.RequestException as err:
        print(f"An unexpected error occurred: {err}")
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
    
