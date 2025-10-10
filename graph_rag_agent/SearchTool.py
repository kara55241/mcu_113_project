import googlemaps
import os
import json
from langchain_community.utilities import GoogleSerperAPIWrapper

class SearchTools:
    """MCP風格的地圖與搜尋工具，使用 Google Maps API 與 Google Search API 本地查詢地點與網頁資訊"""

    @staticmethod
    def Google_Map(input: str, location_info: dict = None) -> str:
        """
        使用 Google Maps API 查詢地點附近的醫療設施。

        Args:
            input: 查詢字串，例如「台北醫院」、「新竹診所」
            location_info: 可選的精確位置資訊 (來自前端地圖點選)
                格式: {"name": "地點名稱", "coordinates": "lat,lng"}

        Returns:
            混合格式字串：人類可讀文字 + JSON 結構化數據
        """
        try:
            gmaps_key = os.getenv("GOOGLE_MAPS_API_KEY")
            if not gmaps_key:
                return "❌ 未設定 GOOGLE_MAPS_API_KEY"

            gmaps = googlemaps.Client(key=gmaps_key)

            # 預設搜尋類別
            search_type = 'hospital'
            keyword = input.strip()
            query_type = "text"  # 預設為文字查詢

            # 類別判斷
            if "診所" in keyword:
                search_type = 'doctor'
            elif "藥局" in keyword:
                search_type = 'pharmacy'

            # 判斷使用精確座標還是文字地名
            if location_info and 'coordinates' in location_info:
                # 模式 A: 使用前端提供的精確座標
                try:
                    coords = location_info['coordinates'].split(',')
                    lat, lng = float(coords[0].strip()), float(coords[1].strip())
                    latlng = (lat, lng)
                    keyword = location_info.get('name', keyword)
                    query_type = "coordinates"
                except (ValueError, IndexError) as e:
                    # 座標解析失敗，回退到文字地名模式
                    pass

            # 模式 B: 使用文字地名進行 geocoding
            if query_type == "text":
                # 清除描述詞，只留下地名
                for word in ['醫院', '診所', '藥局', '附近', '哪裡', '哪里']:
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

            # 過濾結果：移除動物醫院和無效結果
            filtered_results = []
            for place in results[:8]:  # 多取一些以防過濾後不足
                name = place.get("name", "")

                # 排除條件
                is_animal_hospital = any(term in name for term in ['動物', '寵物', '獸醫'])
                is_generic = name in ['藥局', 'Pharmacy', '藥房', '醫院', 'Hospital']
                has_invalid_types = 'veterinary_care' in place.get('types', [])

                if not (is_animal_hospital or is_generic or has_invalid_types) and name:
                    filtered_results.append(place)

                if len(filtered_results) >= 5:  # 只取前5筆
                    break

            if not filtered_results:
                return f"❗在「{keyword}」附近找不到合適的醫療設施（已排除動物醫院）"

            # 建立 AI 可讀的文字回應
            reply = f"## 🏥 在「{keyword}」附近找到以下醫療設施\n\n"

            # 建立結構化數據
            structured_results = []

            for i, place in enumerate(filtered_results):
                name = place.get("name", "無名稱")
                address = place.get("vicinity", "無地址")
                rating = place.get("rating", None)
                place_id = place.get("place_id", "")
                lat = place['geometry']['location']['lat']
                lng = place['geometry']['location']['lng']

                # 生成 Google Maps 連結
                maps_url = f"https://www.google.com/maps/place/?q=place_id:{place_id}" if place_id else ""

                # 文字部分（給 AI 看的）
                rating_str = f"{rating}/5.0" if rating else "無評分"
                reply += f"**{i+1}. {name}**\n"
                reply += f"   - 地址：{address}\n"
                reply += f"   - 評分：{rating_str}\n"
                if maps_url:
                    reply += f"   - [Google Maps 連結]({maps_url})\n"
                reply += "\n"

                # 結構化數據（給前端用的）
                structured_results.append({
                    "name": name,
                    "address": address,
                    "rating": rating,
                    "lat": lat,
                    "lng": lng,
                    "place_id": place_id,
                    "maps_url": maps_url
                })

            # 組合 JSON 數據
            json_data = {
                "type": "hospital_search",
                "location": keyword,
                "query_type": query_type,
                "coordinates": f"{latlng[0]},{latlng[1]}",
                "results": structured_results
            }

            # 混合格式：文字 + JSON（用特殊標記包裹）
            final_response = reply + f"\n[HOSPITAL_DATA]{json.dumps(json_data, ensure_ascii=False)}[/HOSPITAL_DATA]"

            return final_response

        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            return f"🚨 Google Maps 查詢錯誤：{str(e)}\n詳細錯誤：{error_detail}"

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