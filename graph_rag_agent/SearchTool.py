import googlemaps
import os
from langchain_community.utilities import GoogleSerperAPIWrapper

class SearchTools:
    """MCP風格的地圖與搜尋工具，使用 Google Maps API 與 Google Search API 本地查詢地點與網頁資訊"""

    @staticmethod
    def Google_Map(input: str) -> str:
        """
        使用 Google Maps API 查詢地點附近的醫療設施。
        輸入應為地名，例如「台北醫院」、「新竹診所」。
        """
        try:
            gmaps_key = os.getenv("GOOGLE_MAPS_API_KEY")
            if not gmaps_key:
                return "❌ 未設定 GOOGLE_MAPS_API_KEY"

            gmaps = googlemaps.Client(key=gmaps_key)

            # 預設搜尋類別
            search_type = 'hospital'
            keyword = input.strip()

            # 類別判斷
            if "診所" in keyword:
                search_type = 'doctor'
            elif "藥局" in keyword:
                search_type = 'pharmacy'

            # 清除描述詞，只留下地名
            for word in ['醫院', '診所', '藥局', '附近', '哪裡']:
                keyword = keyword.replace(word, '')
            keyword = keyword.strip()

            # 地理編碼
            geocode = gmaps.geocode(keyword, language='zh-TW')
            if not geocode:
                return f"❌ 找不到「{keyword}」這個地點"

            loc = geocode[0]['geometry']['location']
            latlng = (loc['lat'], loc['lng'])

            # 查詢附近地點
            results = gmaps.places_nearby(
                location=latlng,
                radius=3000,
                type=search_type,
                language='zh-TW'
            ).get('results', [])

            if not results:
                return f"❗在「{keyword}」附近找不到相關醫療設施"

            # 回傳前5筆
            reply = f"在「{keyword}」附近找到以下醫療設施：\n"
            for i, place in enumerate(results[:5]):
                name = place.get("name", "無名稱")
                address = place.get("vicinity", "無地址")
                rating = place.get("rating", "無評分")
                reply += f"{i+1}. {name}｜地址：{address}｜評分：{rating}/5\n"

            return reply

        except Exception as e:
            return f"🚨 Google Maps 查詢錯誤：{str(e)}"

    @staticmethod
    def Google_Search(input: str) -> str:
        """
        使用 Google Search 查詢網頁資訊，回傳摘要結果。
        """
        try:
            G_serper = GoogleSerperAPIWrapper(gl='tw', hl='zh-tw', type='search', k=5)
            result = G_serper.run(input)
            return f"🔍 Google 搜尋結果如下：\n\n{result}"
        except Exception as e:
            return f"❌ Google 搜尋錯誤：{str(e)}"