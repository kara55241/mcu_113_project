
from langchain_google_genai import GoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from neo4j import GraphDatabase

class Def_relationships:
    def __init__(self, uri, user, password,database):
        self.driver = GraphDatabase.driver(uri, auth=(user, password),database=database)
        self.llm = GoogleGenerativeAI(model="gemini-1.5-flash")

    def save_entities_and_relationships_batch(self, relationships):
        with self.driver.session() as session:
            with session.begin_transaction() as tx:
                for entity1, relationship, entity2 in relationships:
                    query = (
                        "MERGE (e1:Entity {name: $entity1}) "
                        "MERGE (e2:Entity {name: $entity2}) "
                        "MERGE (e1)-[r:RELATIONSHIP {type: $relationship}]->(e2)"
                    )
                    tx.run(query, entity1=entity1, entity2=entity2, relationship=relationship)


    def extract_entities_and_relationships(self, text):
        try:
            template = ChatPromptTemplate.from_messages([
                ("system", "從以下文本中提取關係，格式為 '實體1 @@ 關係 @@ 實體2'?"),
                ("user", "{input}")
            ])
            response = self.llm.invoke(template.format(input=text))  # 使用同步調用
            if isinstance(response, str):
                print(f"LLM Response: {response}")  # 如果是字符串，直接输出
                return response
            else:
                print(f"Unexpected response format: {response}")
                return ""
        except Exception as e:
            print(f"An error occurred: {e}")
        return ""
    
    def close(self):
        self.driver.close()