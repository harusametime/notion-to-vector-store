#!/usr/bin/env python3
"""
Script to search Notion content stored in Astra DB vector database
"""

import os
import sys
import json
import boto3
from datetime import datetime
from dotenv import load_dotenv
from botocore.exceptions import ClientError, NoCredentialsError
from astrapy.db import AstraDB

def load_environment():
    """Load environment variables from .env file"""
    load_dotenv()
    
    # AWS Bedrock credentials
    aws_access_key = os.getenv('AWS_ACCESS_KEY')
    aws_secret_key = os.getenv('AWS_SECRET_KEY')
    aws_region = os.getenv('AWS_REGION', 'us-east-1')
    bedrock_model_id = os.getenv('BEDROCK_MODEL_ID', 'amazon.titan-embed-text-v1')
    
    # Astra DB credentials
    astra_db_endpoint = os.getenv('ASTRA_DB_ENDPOINT')
    astra_db_keyspace = os.getenv('ASTRA_DB_KEYSPACE')
    astra_db_application_token = os.getenv('ASTRA_DB_APPLICATION_TOKEN')
    astra_db_name = os.getenv('ASTRA_DB_NAME')
    vector_collection_name = os.getenv('VECTOR_COLLECTION_NAME')
    
    # Validate required credentials
    if not aws_access_key or not aws_secret_key:
        print("❌ AWS credentials not found in .env file")
        return None, None, None, None, None, None, None, None, None, None
    
    if not astra_db_endpoint or not astra_db_keyspace or not astra_db_application_token:
        print("❌ Astra DB credentials not found in .env file")
        return None, None, None, None, None, None, None, None, None, None
    
    return (aws_access_key, aws_secret_key, aws_region, bedrock_model_id, 
            astra_db_endpoint, astra_db_keyspace, astra_db_application_token, 
            astra_db_name, vector_collection_name)

def create_bedrock_client(aws_access_key, aws_secret_key, aws_region):
    """Create and configure Bedrock client"""
    try:
        bedrock_client = boto3.client(
            service_name='bedrock-runtime',
            region_name=aws_region,
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key
        )
        print(f"✅ Bedrock client created successfully")
        return bedrock_client
    except Exception as e:
        print(f"❌ Error creating Bedrock client: {e}")
        return None

def get_embedding(bedrock_client, text, model_id):
    """Get embedding for a given text using Bedrock"""
    try:
        request_body = {"inputText": text}
        body = json.dumps(request_body)
        
        response = bedrock_client.invoke_model(
            modelId=model_id,
            body=body
        )
        
        response_body = json.loads(response['body'].read())
        embedding = response_body.get('embedding', [])
        return embedding
        
    except Exception as e:
        print(f"❌ Error getting embedding: {e}")
        return None

def create_astra_client(astra_db_endpoint, astra_db_keyspace, astra_db_application_token, 
                       astra_db_name, vector_collection_name):
    """Create Astra DB client using Astrapy"""
    try:
        # Create Astra DB client
        db = AstraDB(
            token=astra_db_application_token,
            api_endpoint=astra_db_endpoint,
            namespace=astra_db_keyspace
        )
        
        print(f"✅ Astra DB client created successfully")
        print(f"   Endpoint: {astra_db_endpoint}")
        print(f"   Keyspace: {astra_db_keyspace}")
        print(f"   Collection: {vector_collection_name}")
        
        return db
        
    except Exception as e:
        print(f"❌ Error creating Astra DB client: {e}")
        print("Please check your Astra DB credentials and ensure the database is accessible")
        return None

def search_similar_pages(db, collection_name, query_embedding, limit=5):
    """Search for similar pages using vector similarity"""
    try:
        # Search for similar documents using vector similarity
        results = db.collection(collection_name).find(
            {},
            sort={"$vector": query_embedding},
            limit=limit
        )
        
        search_results = []
        for result in results['data']['documents']:
            search_results.append({
                'page_id': result.get('page_id'),
                'page_title': result.get('page_title', 'Untitled'),
                'page_url': result.get('page_url'),
                'content_text': result.get('content_text', '')[:200] + '...' if len(result.get('content_text', '')) > 200 else result.get('content_text', ''),
                'properties': result.get('properties', {}),
                'created_time': result.get('created_time'),
                'last_edited_time': result.get('last_edited_time'),
                'similarity': result.get('$similarity', 0.0)
            })
        
        return search_results
        
    except Exception as e:
        print(f"❌ Error searching similar pages: {e}")
        return []

def search_notion_content():
    """Main function to search Notion content in vector database"""
    print("🔍 Notion Vector Database Search")
    print("=" * 40)
    
    # Load environment variables
    (aws_access_key, aws_secret_key, aws_region, bedrock_model_id, 
     astra_db_endpoint, astra_db_keyspace, astra_db_application_token, 
     astra_db_name, vector_collection_name) = load_environment()
    
    if not all([aws_access_key, aws_secret_key, astra_db_endpoint, astra_db_keyspace, 
                astra_db_application_token]):
        sys.exit(1)
    
    # Create Bedrock client
    bedrock_client = create_bedrock_client(aws_access_key, aws_secret_key, aws_region)
    if not bedrock_client:
        sys.exit(1)
    
    # Create Astra DB client
    db = create_astra_client(astra_db_endpoint, astra_db_keyspace, 
                           astra_db_application_token, astra_db_name, vector_collection_name)
    if not db:
        sys.exit(1)
    
    # Interactive search loop
    while True:
        print(f"\n💬 Enter your search query (or 'quit' to exit):")
        query = input("> ").strip()
        
        if query.lower() in ['quit', 'exit', 'q']:
            break
        
        if not query:
            print("Please enter a search query.")
            continue
        
        print(f"\n🔍 Searching for: '{query}'")
        print("-" * 50)
        
        # Generate embedding for the query
        query_embedding = get_embedding(bedrock_client, query, bedrock_model_id)
        if not query_embedding:
            print("❌ Failed to generate embedding for query")
            continue
        
        # Search for similar pages
        results = search_similar_pages(db, vector_collection_name, query_embedding, limit=5)
        
        if not results:
            print("❌ No results found")
            continue
        
        # Display results
        print(f"📄 Found {len(results)} similar pages:")
        print()
        
        for i, result in enumerate(results, 1):
            print(f"{i}. {result['page_title']}")
            print(f"   URL: {result['page_url']}")
            print(f"   Content: {result['content_text']}")
            if result['similarity']:
                print(f"   Similarity: {result['similarity']:.4f}")
            print(f"   Created: {result['created_time']}")
            print()
    
    print("👋 Search session ended")

def main():
    """Main function"""
    search_notion_content()

if __name__ == "__main__":
    main() 