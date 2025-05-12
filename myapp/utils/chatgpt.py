import openai
import os
from dotenv import load_dotenv

load_dotenv()

def get_chatgpt_response(question):
    try:
        response = openai.ChatCompletion.acreate(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "你是AI助理。"},
                {"role": "user", "content": question}
            ]
        )
        return response.choices[0].message["content"]
    except openai.error.OpenAIError as e:
        print(f"OpenAI API 發生錯誤：{e}")
        return "抱歉，我無法生成回應。"