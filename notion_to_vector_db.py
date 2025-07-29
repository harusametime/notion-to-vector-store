#!/usr/bin/env python3
"""
Script to extract Notion data, generate embeddings, and store in DataStax Astra DB vector database
"""

import os
import sys
import json
import boto3
from datetime import datetime
from dotenv import load_dotenv
from notion_client import Client
from botocore.exceptions import ClientError, NoCredentialsError
from astrapy.db import AstraDB

def load_environment():
    """Load environment variables from .env file"""
    load_dotenv()
    
    # Notion credentials
    notion_secret = os.getenv('NOTION_SECRET')
    notion_connection = os.getenv('NOTION_CONNECTION')
    
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
    if not notion_secret:
        print("❌ NOTION_SECRET not found in .env file")
        return None, None, None, None, None, None, None, None, None, None
    
    if not aws_access_key or not aws_secret_key:
        print("❌ AWS credentials not found in .env file")
        return None, None, None, None, None, None, None, None, None, None
    
    if not astra_db_endpoint or not astra_db_keyspace or not astra_db_application_token:
        print("❌ Astra DB credentials not found in .env file")
        print("Please add: ASTRA_DB_ENDPOINT, ASTRA_DB_KEYSPACE, ASTRA_DB_APPLICATION_TOKEN")
        return None, None, None, None, None, None, None, None, None, None
    
    return (notion_secret, notion_connection, aws_access_key, aws_secret_key, 
            aws_region, bedrock_model_id, astra_db_endpoint, astra_db_keyspace, 
            astra_db_application_token, astra_db_name, vector_collection_name)

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

def get_all_notion_pages(notion_secret):
    """Retrieve all pages from Notion"""
    try:
        notion = Client(auth=notion_secret)
        
        print("🔍 Searching for Notion pages...")
        
        response = notion.search(
            filter={
                "property": "object",
                "value": "page"
            }
        )
        
        pages = response.get('results', [])
        
        if not pages:
            print("📝 No pages found accessible to this integration")
            return []
        
        print(f"📄 Found {len(pages)} page(s)")
        return pages
        
    except Exception as e:
        print(f"❌ Error retrieving Notion pages: {e}")
        return []

def get_page_content(notion_secret, page_id):
    """Get detailed content of a specific page"""
    try:
        notion = Client(auth=notion_secret)
        
        # Get page details
        page = notion.pages.retrieve(page_id=page_id)
        
        # Get page blocks
        blocks = notion.blocks.children.list(block_id=page_id)
        all_blocks = blocks.get('results', [])
        
        # Handle pagination for blocks
        while blocks.get('has_more'):
            blocks = notion.blocks.children.list(
                block_id=page_id,
                start_cursor=blocks.get('next_cursor')
            )
            all_blocks.extend(blocks.get('results', []))
        
        return {
            'page': page,
            'blocks': all_blocks
        }
        
    except Exception as e:
        print(f"❌ Error retrieving page content: {e}")
        return None

def extract_page_data(page_data):
    """Extract relevant data from a page"""
    page = page_data['page']
    blocks = page_data['blocks']
    
    # Extract page properties
    properties = page.get('properties', {})
    page_info = {
        'id': page['id'],
        'url': page['url'],
        'created_time': page['created_time'],
        'last_edited_time': page['last_edited_time'],
        'archived': page['archived'],
        'properties': {},
        'content_text': '',
        'content_blocks': []
    }
    
    # Extract property values
    for prop_name, prop_value in properties.items():
        prop_type = prop_value.get('type')
        if prop_type == 'title':
            title_parts = prop_value.get('title', [])
            page_info['properties'][prop_name] = ''.join([part.get('plain_text', '') for part in title_parts])
        elif prop_type == 'rich_text':
            rich_text_parts = prop_value.get('rich_text', [])
            page_info['properties'][prop_name] = ''.join([part.get('plain_text', '') for part in rich_text_parts])
        elif prop_type == 'number':
            page_info['properties'][prop_name] = prop_value.get('number')
        elif prop_type == 'select':
            select_value = prop_value.get('select')
            page_info['properties'][prop_name] = select_value.get('name') if select_value else None
        elif prop_type == 'multi_select':
            multi_select_values = prop_value.get('multi_select', [])
            page_info['properties'][prop_name] = [item.get('name') for item in multi_select_values]
        elif prop_type == 'date':
            date_value = prop_value.get('date')
            page_info['properties'][prop_name] = date_value.get('start') if date_value else None
        elif prop_type == 'checkbox':
            page_info['properties'][prop_name] = prop_value.get('checkbox')
        elif prop_type == 'url':
            page_info['properties'][prop_name] = prop_value.get('url')
        elif prop_type == 'email':
            page_info['properties'][prop_name] = prop_value.get('email')
        elif prop_type == 'phone_number':
            page_info['properties'][prop_name] = prop_value.get('phone_number')
        else:
            page_info['properties'][prop_name] = str(prop_value)
    
    # Extract block content for embedding
    content_parts = []
    for block in blocks:
        block_type = block.get('type')
        block_data = {
            'id': block['id'],
            'type': block_type,
            'content': ''
        }
        
        if block_type == 'paragraph':
            rich_text = block[block_type].get('rich_text', [])
            text_content = ''.join([text.get('plain_text', '') for text in rich_text])
            block_data['content'] = text_content
            content_parts.append(text_content)
        elif block_type in ['heading_1', 'heading_2', 'heading_3']:
            rich_text = block[block_type].get('rich_text', [])
            text_content = ''.join([text.get('plain_text', '') for text in rich_text])
            block_data['content'] = text_content
            content_parts.append(text_content)
        elif block_type in ['bulleted_list_item', 'numbered_list_item']:
            rich_text = block[block_type].get('rich_text', [])
            text_content = ''.join([text.get('plain_text', '') for text in rich_text])
            block_data['content'] = text_content
            content_parts.append(text_content)
        elif block_type == 'to_do':
            rich_text = block[block_type].get('rich_text', [])
            text_content = ''.join([text.get('plain_text', '') for text in rich_text])
            block_data['content'] = text_content
            content_parts.append(text_content)
        elif block_type == 'code':
            rich_text = block[block_type].get('rich_text', [])
            text_content = ''.join([text.get('plain_text', '') for text in rich_text])
            block_data['content'] = text_content
            content_parts.append(text_content)
        elif block_type == 'quote':
            rich_text = block[block_type].get('rich_text', [])
            text_content = ''.join([text.get('plain_text', '') for text in rich_text])
            block_data['content'] = text_content
            content_parts.append(text_content)
        elif block_type == 'callout':
            rich_text = block[block_type].get('rich_text', [])
            text_content = ''.join([text.get('plain_text', '') for text in rich_text])
            block_data['content'] = text_content
            content_parts.append(text_content)
        
        page_info['content_blocks'].append(block_data)
    
    # Combine all text content for embedding
    page_info['content_text'] = ' '.join(content_parts)
    
    return page_info

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

def create_vector_collection(db, collection_name):
    """Create vector collection in Astra DB"""
    try:
        # First, try to get the collection to see if it exists
        try:
            collection = db.collection(collection_name)
            # Test if collection exists by trying to access it
            collection.find_one()
            print(f"✅ Vector collection '{collection_name}' already exists")
            return collection
        except Exception:
            # Collection doesn't exist, create it
            print(f"📝 Creating new vector collection '{collection_name}'...")
            collection = db.create_collection(
                collection_name,
                dimension=1024,  # Amazon Titan embedding dimension
                metric="cosine"
            )
            print(f"✅ Vector collection '{collection_name}' created successfully")
            return collection
        
    except Exception as e:
        print(f"❌ Error with vector collection: {e}")
        return None

def insert_page_embedding(db, collection_name, page_data, embedding, model_id):
    """Insert a page with its embedding into Astra DB"""
    try:
        # Extract title from properties
        page_title = "Untitled"
        if 'properties' in page_data:
            for prop_name, prop_value in page_data['properties'].items():
                if prop_name.lower() in ['title', 'name']:
                    page_title = str(prop_value) if prop_value else "Untitled"
                    break
        
        # Prepare document for insertion
        document = {
            "page_id": page_data['id'],
            "page_title": page_title,
            "page_url": page_data['url'],
            "created_time": page_data['created_time'],
            "last_edited_time": page_data['last_edited_time'],
            "archived": page_data['archived'],
            "properties": page_data['properties'],
            "content_text": page_data['content_text'],
            "content_blocks": page_data['content_blocks'],
            "embedding_model": model_id,
            "created_at": datetime.now().isoformat(),
            "$vector": embedding
        }
        
        # Insert document into collection
        result = db.collection(collection_name).insert_one(document)
        
        return True
        
    except Exception as e:
        print(f"❌ Error inserting page embedding: {e}")
        return False

def process_notion_to_vector_db():
    """Main function to process Notion data and store in vector database"""
    print("🚀 Notion to Vector Database Pipeline")
    print("=" * 50)
    
    # Load environment variables
    (notion_secret, notion_connection, aws_access_key, aws_secret_key, 
     aws_region, bedrock_model_id, astra_db_endpoint, astra_db_keyspace, 
     astra_db_application_token, astra_db_name, vector_collection_name) = load_environment()
    
    if not all([notion_secret, aws_access_key, aws_secret_key, astra_db_endpoint, 
                astra_db_keyspace, astra_db_application_token]):
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
    
    # Create vector collection
    collection = create_vector_collection(db, vector_collection_name)
    if not collection:
        print("❌ Failed to create or access vector collection")
        sys.exit(1)
    
    # Get all Notion pages
    pages = get_all_notion_pages(notion_secret)
    if not pages:
        print("❌ No pages found to process")
        sys.exit(1)
    
    # Process each page
    successful_inserts = 0
    total_pages = len(pages)
    
    for i, page in enumerate(pages, 1):
        page_id = page['id']
        print(f"\n📄 Processing page {i}/{total_pages}: {page_id}")
        
        # Get detailed page content
        page_content = get_page_content(notion_secret, page_id)
        if not page_content:
            print(f"   ⚠️  Failed to get content for page {page_id}")
            continue
        
        # Extract page data
        page_data = extract_page_data(page_content)
        
        # Generate embedding if there's content
        if page_data['content_text'].strip():
            print(f"   🔍 Generating embedding for content...")
            embedding = get_embedding(bedrock_client, page_data['content_text'], bedrock_model_id)
            
            if embedding:
                print(f"   💾 Storing in vector database...")
                if insert_page_embedding(db, vector_collection_name, page_data, embedding, bedrock_model_id):
                    successful_inserts += 1
                    print(f"   ✅ Successfully stored page {i}/{total_pages}")
                else:
                    print(f"   ❌ Failed to store page {i}/{total_pages}")
            else:
                print(f"   ⚠️  Failed to generate embedding for page {i}/{total_pages}")
        else:
            print(f"   ⚠️  No content to embed for page {i}/{total_pages}")
    
    # Summary
    print(f"\n🎉 Processing completed!")
    print(f"📊 Summary:")
    print(f"   - Total pages found: {total_pages}")
    print(f"   - Successfully processed: {successful_inserts}")
    print(f"   - Failed: {total_pages - successful_inserts}")
    
    return successful_inserts

def main():
    """Main function"""
    process_notion_to_vector_db()

if __name__ == "__main__":
    main() 