"""初始化neo4j"""
from dotenv import load_dotenv
import os
from langchain_neo4j import Neo4jGraph
# Connect to Neo4j
load_dotenv()
graph = Neo4jGraph(
    url=os.getenv("NEO4J_URI"),
    username=os.getenv("NEO4J_USERNAME"),
    password=os.getenv("NEO4J_PASSWORD"),
    database=os.getenv("NEO4J_DATABASE"),
    enhanced_schema=True,
    timeout=10
)