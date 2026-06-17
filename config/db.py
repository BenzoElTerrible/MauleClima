from pymongo import MongoClient
from neo4j import GraphDatabase
from django.conf import settings

_mongo_client = None
_neo4j_driver = None

def get_mongo_db():
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = MongoClient(settings.MONGO_URI, serverSelectionTimeoutMS=5000)
    return _mongo_client[settings.MONGO_DB]

def get_neo4j_driver():
    global _neo4j_driver
    if _neo4j_driver is None:
        _neo4j_driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )
    return _neo4j_driver

def neo4j_session():
    return get_neo4j_driver().session()
