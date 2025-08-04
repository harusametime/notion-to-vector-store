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
from langchain_text_splitters import RecursiveCharacterTextSplitter

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
    
    # Chunking configuration
    chunk_size = int(os.getenv('CHUNK_SIZE', '1000'))  # Default 1000 tokens
    
    # Validate required credentials
    if not notion_secret:
        print("❌ NOTION_SECRET not found in .env file")
        return None, None, None, None, None, None, None, None, None, None, None
    
    if not aws_access_key or not aws_secret_key:
        print("❌ AWS credentials not found in .env file")
        return None, None, None, None, None, None, None, None, None, None, None
    
    if not astra_db_endpoint or not astra_db_keyspace or not astra_db_application_token:
        print("❌ Astra DB credentials not found in .env file")
        print("Please add: ASTRA_DB_ENDPOINT, ASTRA_DB_KEYSPACE, ASTRA_DB_APPLICATION_TOKEN")
        return None, None, None, None, None, None, None, None, None, None, None
    
    return (notion_secret, notion_connection, aws_access_key, aws_secret_key, 
            aws_region, bedrock_model_id, astra_db_endpoint, astra_db_keyspace, 
            astra_db_application_token, astra_db_name, vector_collection_name, chunk_size)

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

def chunk_text(text, chunk_size, overlap=200):
    """
    Split text into chunks of specified size with overlap using RecursiveCharacterTextSplitter.
    
    Args:
        text (str): Text to chunk
        chunk_size (int): Maximum tokens per chunk (approximate)
        overlap (int): Number of characters to overlap between chunks
    
    Returns:
        list: List of text chunks
    """
    if not text or len(text) <= chunk_size:
        return [text] if text else []
    
    # Create text splitter with intelligent chunking
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", "! ", "? ", " ", ""]  # Priority order for splitting
    )
    
    # Split the text
    chunks = text_splitter.split_text(text)
    
    return chunks

def get_chunk_embeddings(bedrock_client, text, model_id, chunk_size):
    """
    Get embeddings for text chunks.
    
    Args:
        bedrock_client: Bedrock client
        text (str): Text to embed
        model_id (str): Bedrock model ID
        chunk_size (int): Maximum tokens per chunk
    
    Returns:
        list: List of tuples (chunk_text, embedding)
    """
    if not text or not text.strip():
        return []
    
    # Calculate adaptive overlap (20% of chunk size, but at least 10 and at most 200)
    overlap = max(10, min(200, chunk_size // 5))
    
    # Split text into chunks
    chunks = chunk_text(text, chunk_size, overlap)
    
    if not chunks:
        return []
    
    print(f"   📄 Split content into {len(chunks)} chunk(s) (chunk_size: {chunk_size}, overlap: {overlap})")
    
    chunk_embeddings = []
    for i, chunk in enumerate(chunks, 1):
        print(f"   🔍 Generating embedding for chunk {i}/{len(chunks)}...")
        embedding = get_embedding(bedrock_client, chunk, model_id)
        
        if embedding:
            chunk_embeddings.append((chunk, embedding))
        else:
            print(f"   ⚠️  Failed to generate embedding for chunk {i}")
    
    return chunk_embeddings

def get_all_notion_pages(notion_secret):
    """Retrieve all pages from Notion with pagination support"""
    try:
        notion = Client(auth=notion_secret)
        
        print("🔍 Searching for Notion pages...")
        
        all_pages = []
        has_more = True
        start_cursor = None
        page_count = 0
        
        while has_more:
            page_count += 1
            print(f"   📄 Fetching page {page_count}...")
            
            # Prepare search parameters
            search_params = {
                "filter": {
                    "property": "object",
                    "value": "page"
                }
            }
            
            # Add cursor for pagination (except for first page)
            if start_cursor:
                search_params["start_cursor"] = start_cursor
            
            # Perform search
            response = notion.search(**search_params)
            
            # Get results from this page
            pages = response.get('results', [])
            all_pages.extend(pages)
            
            # Check if there are more pages
            has_more = response.get('has_more', False)
            start_cursor = response.get('next_cursor')
            
            print(f"   📄 Found {len(pages)} pages on page {page_count}")
        
        if not all_pages:
            print("📝 No pages found accessible to this integration")
            return []
        
        print(f"📄 Total pages found: {len(all_pages)} across {page_count} API calls")
        return all_pages
        
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

def check_page_exists(db, collection_name, page_id):
    """Check if a page already exists in the collection and return its data"""
    try:
        # Find all chunks for this page
        result = db.collection(collection_name).find({"page_id": page_id})
        chunks = list(result)
        
        if chunks:
            # Return the first chunk as representative of the page
            # All chunks should have the same page metadata
            return chunks[0]
        else:
            return None
    except Exception as e:
        print(f"❌ Error checking if page exists: {e}")
        return None

def should_update_page(existing_page, page_data):
    """Check if page needs updating based on last modified time"""
    if not existing_page:
        return True  # New page, needs insertion
    
    # Get last updated time from existing page
    # Handle different data structures that might be returned
    existing_updated_time = None
    
    try:
        if isinstance(existing_page, dict):
            if 'data' in existing_page and isinstance(existing_page['data'], dict) and 'document' in existing_page['data']:
                # Old format
                existing_doc = existing_page['data']['document']
                existing_updated_time = existing_doc.get('last_updated_time')
            elif 'last_updated_time' in existing_page:
                # New chunked format - document is directly in the result
                existing_updated_time = existing_page.get('last_updated_time')
            else:
                # Unknown format, update to be safe
                return True
        else:
            # Not a dict, update to be safe
            return True
    except Exception as e:
        print(f"   ⚠️  Error parsing existing page data: {e}")
        return True  # Update to be safe
    
    if not existing_updated_time:
        return True  # No timestamp, update to be safe
    
    # Compare with current page's last edited time
    current_edited_time = page_data.get('last_edited_time')
    if not current_edited_time:
        return True  # No current timestamp, update to be safe
    
    # Update if current page is newer
    return current_edited_time > existing_updated_time

def update_page_embedding(db, collection_name, page_data, embedding, model_id):
    """Update an existing page with new data and embedding"""
    try:
        # Extract title from properties
        page_title = "Untitled"
        if 'properties' in page_data:
            for prop_name, prop_value in page_data['properties'].items():
                if prop_name.lower() in ['title', 'name']:
                    page_title = str(prop_value) if prop_value else "Untitled"
                    break
        
        # Prepare document for update
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
            "updated_at": datetime.now().isoformat(),
            "last_updated_time": datetime.now().isoformat(),  # Track when we last updated
            "$vector": embedding
        }
        
        # Update document in collection
        result = db.collection(collection_name).update_one(
            {"page_id": page_data['id']},
            {"$set": document}
        )
        
        return True
        
    except Exception as e:
        print(f"❌ Error updating page embedding: {e}")
        return False

def update_page_chunks(db, collection_name, page_data, chunk_embeddings, model_id):
    """Update an existing page with new chunked data and embeddings"""
    try:
        # Extract title from properties
        page_title = "Untitled"
        if 'properties' in page_data:
            for prop_name, prop_value in page_data['properties'].items():
                if prop_name.lower() in ['title', 'name']:
                    page_title = str(prop_value) if prop_value else "Untitled"
                    break
        
        # First, delete all existing chunks for this page
        delete_result = db.collection(collection_name).delete_many({"page_id": page_data['id']})
        
        # Handle different possible return formats from Astra DB
        deleted_count = 0
        if hasattr(delete_result, 'deleted_count'):
            deleted_count = delete_result.deleted_count
        elif isinstance(delete_result, dict) and 'deletedCount' in delete_result:
            deleted_count = delete_result['deletedCount']
        elif isinstance(delete_result, dict) and 'deleted_count' in delete_result:
            deleted_count = delete_result['deleted_count']
        
        print(f"   🗑️  Deleted {deleted_count} existing chunk(s)")
        
        # Insert new chunks
        inserted_count = 0
        for i, (chunk_text, embedding) in enumerate(chunk_embeddings, 1):
            # Prepare document for each chunk
            document = {
                "page_id": page_data['id'],
                "chunk_id": f"{page_data['id']}_chunk_{i}",
                "chunk_index": i,
                "page_title": page_title,
                "page_url": page_data['url'],
                "created_time": page_data['created_time'],
                "last_edited_time": page_data['last_edited_time'],
                "archived": page_data['archived'],
                "properties": page_data['properties'],
                "content_text": page_data['content_text'],  # Full content for reference
                "chunk_text": chunk_text,  # This chunk's text
                "content_blocks": page_data['content_blocks'],
                "embedding_model": model_id,
                "updated_at": datetime.now().isoformat(),
                "last_updated_time": datetime.now().isoformat(),
                "$vector": embedding
            }
            
            # Insert chunk document
            result = db.collection(collection_name).insert_one(document)
            
            # Handle different possible return formats from Astra DB
            if hasattr(result, 'inserted_id') and result.inserted_id:
                inserted_count += 1
            elif isinstance(result, dict) and ('insertedId' in result or 'inserted_id' in result):
                inserted_count += 1
            elif result:  # If result exists but we can't determine the format, assume success
                inserted_count += 1
        
        print(f"   💾 Inserted {inserted_count} new chunk(s)")
        return inserted_count > 0
        
    except Exception as e:
        print(f"❌ Error updating page chunks: {e}")
        return False

def insert_page_chunks(db, collection_name, page_data, chunk_embeddings, model_id):
    """Insert a page with its chunked embeddings into Astra DB"""
    try:
        # Extract title from properties
        page_title = "Untitled"
        if 'properties' in page_data:
            for prop_name, prop_value in page_data['properties'].items():
                if prop_name.lower() in ['title', 'name']:
                    page_title = str(prop_value) if prop_value else "Untitled"
                    break
        
        # Insert all chunks
        inserted_count = 0
        for i, (chunk_text, embedding) in enumerate(chunk_embeddings, 1):
            # Prepare document for each chunk
            document = {
                "page_id": page_data['id'],
                "chunk_id": f"{page_data['id']}_chunk_{i}",
                "chunk_index": i,
                "page_title": page_title,
                "page_url": page_data['url'],
                "created_time": page_data['created_time'],
                "last_edited_time": page_data['last_edited_time'],
                "archived": page_data['archived'],
                "properties": page_data['properties'],
                "content_text": page_data['content_text'],  # Full content for reference
                "chunk_text": chunk_text,  # This chunk's text
                "content_blocks": page_data['content_blocks'],
                "embedding_model": model_id,
                "created_at": datetime.now().isoformat(),
                "last_updated_time": datetime.now().isoformat(),
                "$vector": embedding
            }
            
            # Insert chunk document
            result = db.collection(collection_name).insert_one(document)
            
            # Handle different possible return formats from Astra DB
            if hasattr(result, 'inserted_id') and result.inserted_id:
                inserted_count += 1
            elif isinstance(result, dict) and ('insertedId' in result or 'inserted_id' in result):
                inserted_count += 1
            elif result:  # If result exists but we can't determine the format, assume success
                inserted_count += 1
        
        print(f"   💾 Inserted {inserted_count} chunk(s)")
        return inserted_count > 0
        
    except Exception as e:
        print(f"❌ Error inserting page chunks: {e}")
        return False

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
            "last_updated_time": datetime.now().isoformat(),  # Track when we last updated
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
     astra_db_application_token, astra_db_name, vector_collection_name, chunk_size) = load_environment()
    
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
    updated_pages = 0
    skipped_pages = 0
    unchanged_pages = 0
    total_pages = len(pages)
    
    for i, page in enumerate(pages, 1):
        page_id = page['id']
        print(f"\n📄 Processing page {i}/{total_pages}: {page_id}")
        
        # Check if page already exists and get its data
        existing_page = check_page_exists(db, vector_collection_name, page_id)
        
        # Get detailed page content
        page_content = get_page_content(notion_secret, page_id)
        if not page_content:
            print(f"   ⚠️  Failed to get content for page {page_id}")
            continue
        
        # Extract page data
        page_data = extract_page_data(page_content)
        
        # Check if page needs updating
        needs_update = should_update_page(existing_page, page_data)
        
        # Debug: Show what's happening
        if existing_page is not None:
            # Handle different data structures that might be returned
            existing_time = 'None'
            try:
                if isinstance(existing_page, dict):
                    if 'data' in existing_page and isinstance(existing_page['data'], dict) and 'document' in existing_page['data']:
                        # Old format
                        existing_doc = existing_page['data']['document']
                        existing_time = existing_doc.get('last_updated_time', 'None')
                    elif 'last_updated_time' in existing_page:
                        # New chunked format
                        existing_time = existing_page.get('last_updated_time', 'None')
                    else:
                        existing_time = 'Unknown format'
                else:
                    existing_time = 'Non-dict format'
            except Exception as e:
                existing_time = f'Error: {e}'
            
            current_time = page_data.get('last_edited_time', 'None')
            print(f"      📅 Existing: {existing_time}")
            print(f"      📅 Current: {current_time}")
            print(f"      🔍 Needs update: {needs_update}")
        else:
            print(f"      📅 New page, will insert")
        
        if needs_update and page_data['content_text'].strip():
            print(f"   🔍 Generating embeddings for content...")
            chunk_embeddings = get_chunk_embeddings(bedrock_client, page_data['content_text'], bedrock_model_id, chunk_size)
            
            if chunk_embeddings:
                if existing_page is not None:
                    print(f"   🔄 Page changed, updating chunks...")
                    if update_page_chunks(db, vector_collection_name, page_data, chunk_embeddings, bedrock_model_id):
                        updated_pages += 1
                        print(f"   ✅ Successfully updated page {i}/{total_pages}")
                    else:
                        print(f"   ❌ Failed to update page {i}/{total_pages}")
                else:
                    print(f"   💾 Storing new page chunks in vector database...")
                    if insert_page_chunks(db, vector_collection_name, page_data, chunk_embeddings, bedrock_model_id):
                        successful_inserts += 1
                        print(f"   ✅ Successfully stored page {i}/{total_pages}")
                    else:
                        print(f"   ❌ Failed to store page {i}/{total_pages}")
            else:
                print(f"   ⚠️  Failed to generate embeddings for page {i}/{total_pages}")
        elif not needs_update:
            print(f"   ⏭️  Page unchanged, skipping...")
            unchanged_pages += 1
        else:
            print(f"   ⚠️  No content to embed for page {i}/{total_pages}")
            skipped_pages += 1
    
    # Summary
    print(f"\n🎉 Processing completed!")
    print(f"📊 Summary:")
    print(f"   - Total pages found: {total_pages}")
    print(f"   - New pages inserted: {successful_inserts}")
    print(f"   - Existing pages updated: {updated_pages}")
    print(f"   - Pages unchanged (skipped): {unchanged_pages}")
    print(f"   - Pages skipped (no content): {skipped_pages}")
    print(f"   - Failed: {total_pages - successful_inserts - updated_pages - unchanged_pages - skipped_pages}")
    
    return successful_inserts + updated_pages

def main():
    """Main function"""
    process_notion_to_vector_db()

if __name__ == "__main__":
    main() 