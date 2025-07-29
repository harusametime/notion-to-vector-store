#!/usr/bin/env python3
"""
Script to retrieve all data from Notion using NOTION_CONNECTION and NOTION_SECRET from .env file
"""

import os
import sys
import json
from datetime import datetime
from dotenv import load_dotenv
from notion_client import Client

def load_environment():
    """Load environment variables from .env file"""
    load_dotenv()
    notion_secret = os.getenv('NOTION_SECRET')
    notion_connection = os.getenv('NOTION_CONNECTION')
    
    if not notion_secret:
        print("❌ NOTION_SECRET not found in .env file")
        print("Please create a .env file with your Notion integration token:")
        print("NOTION_SECRET=your_notion_integration_token_here")
        return None, None
    
    if not notion_connection:
        print("❌ NOTION_CONNECTION not found in .env file")
        print("Please add NOTION_CONNECTION to your .env file:")
        print("NOTION_CONNECTION=your_notion_connection_id_here")
        return notion_secret, None
    
    return notion_secret, notion_connection

def get_all_pages(notion_secret):
    """Retrieve all pages accessible to the integration"""
    try:
        notion = Client(auth=notion_secret)
        
        print("🔍 Searching for pages...")
        
        # Search for pages
        response = notion.search(
            filter={
                "property": "object",
                "value": "page"
            }
        )
        
        pages = response.get('results', [])
        
        if not pages:
            print("📝 No pages found accessible to this integration")
            print("Please check:")
            print("   - Your integration has the correct permissions")
            print("   - The integration has been added to your workspace")
            print("   - There is content in your Notion workspace")
            return []
        
        print(f"📄 Found {len(pages)} page(s)")
        return pages
        
    except Exception as e:
        print(f"❌ Error retrieving pages: {e}")
        print("This might indicate an authentication issue. Please check your NOTION_SECRET.")
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
        'properties': {}
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
    
    # Extract block content
    page_info['content'] = []
    for block in blocks:
        block_type = block.get('type')
        block_data = {
            'id': block['id'],
            'type': block_type,
            'content': ''
        }
        
        if block_type == 'paragraph':
            rich_text = block[block_type].get('rich_text', [])
            block_data['content'] = ''.join([text.get('plain_text', '') for text in rich_text])
        elif block_type == 'heading_1':
            rich_text = block[block_type].get('rich_text', [])
            block_data['content'] = ''.join([text.get('plain_text', '') for text in rich_text])
        elif block_type == 'heading_2':
            rich_text = block[block_type].get('rich_text', [])
            block_data['content'] = ''.join([text.get('plain_text', '') for text in rich_text])
        elif block_type == 'heading_3':
            rich_text = block[block_type].get('rich_text', [])
            block_data['content'] = ''.join([text.get('plain_text', '') for text in rich_text])
        elif block_type == 'bulleted_list_item':
            rich_text = block[block_type].get('rich_text', [])
            block_data['content'] = ''.join([text.get('plain_text', '') for text in rich_text])
        elif block_type == 'numbered_list_item':
            rich_text = block[block_type].get('rich_text', [])
            block_data['content'] = ''.join([text.get('plain_text', '') for text in rich_text])
        elif block_type == 'to_do':
            rich_text = block[block_type].get('rich_text', [])
            block_data['content'] = ''.join([text.get('plain_text', '') for text in rich_text])
            block_data['checked'] = block[block_type].get('checked', False)
        elif block_type == 'code':
            rich_text = block[block_type].get('rich_text', [])
            block_data['content'] = ''.join([text.get('plain_text', '') for text in rich_text])
            block_data['language'] = block[block_type].get('language', '')
        elif block_type == 'quote':
            rich_text = block[block_type].get('rich_text', [])
            block_data['content'] = ''.join([text.get('plain_text', '') for text in rich_text])
        elif block_type == 'callout':
            rich_text = block[block_type].get('rich_text', [])
            block_data['content'] = ''.join([text.get('plain_text', '') for text in rich_text])
        elif block_type == 'image':
            block_data['url'] = block[block_type].get('file', {}).get('url', '')
        elif block_type == 'file':
            block_data['url'] = block[block_type].get('file', {}).get('url', '')
        elif block_type == 'video':
            block_data['url'] = block[block_type].get('video', {}).get('url', '')
        elif block_type == 'bookmark':
            block_data['url'] = block[block_type].get('url', '')
        elif block_type == 'table_of_contents':
            block_data['content'] = 'Table of Contents'
        elif block_type == 'divider':
            block_data['content'] = '---'
        elif block_type == 'column_list':
            block_data['content'] = 'Column Layout'
        elif block_type == 'column':
            block_data['content'] = 'Column'
        else:
            block_data['content'] = f'Unsupported block type: {block_type}'
        
        page_info['content'].append(block_data)
    
    return page_info

def get_all_notion_data(notion_secret, notion_connection=None):
    """Get all data from Notion"""
    print("🔍 Retrieving all Notion data...")
    print("=" * 50)
    
    # Get all pages
    pages = get_all_pages(notion_secret)
    
    if not pages:
        print("❌ No pages found or accessible")
        return None
    
    all_data = {
        'metadata': {
            'exported_at': datetime.now().isoformat(),
            'total_pages': len(pages),
            'notion_connection': notion_connection
        },
        'pages': []
    }
    
    total_pages_processed = 0
    
    # Process pages
    for i, page in enumerate(pages, 1):
        page_id = page['id']
        page_title = "Untitled"
        
        # Extract page title
        if 'properties' in page:
            for prop_name, prop_value in page['properties'].items():
                if prop_value.get('type') == 'title':
                    title_parts = prop_value.get('title', [])
                    page_title = ''.join([part.get('plain_text', '') for part in title_parts])
                    break
        
        print(f"\n📄 Processing page {i}/{len(pages)}: {page_title}")
        print(f"   Page ID: {page_id}")
        
        # Get detailed content for this page
        page_content = get_page_content(notion_secret, page_id)
        if page_content:
            extracted_data = extract_page_data(page_content)
            all_data['pages'].append(extracted_data)
            total_pages_processed += 1
    
    all_data['metadata']['total_pages_processed'] = total_pages_processed
    
    print(f"\n✅ Export completed!")
    print(f"📄 Total pages found: {len(pages)}")
    print(f"📄 Total pages processed: {total_pages_processed}")
    
    return all_data

def save_data_to_file(data, filename=None):
    """Save the exported data to a JSON file"""
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"notion_export_{timestamp}.json"
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Data saved to: {filename}")
        return filename
    except Exception as e:
        print(f"❌ Error saving data: {e}")
        return None

def main():
    """Main function"""
    print("🚀 Notion Data Exporter")
    print("=" * 30)
    
    # Load environment variables
    notion_secret, notion_connection = load_environment()
    if not notion_secret:
        sys.exit(1)
    
    # Get all data
    all_data = get_all_notion_data(notion_secret, notion_connection)
    
    if all_data:
        # Save to file
        filename = save_data_to_file(all_data)
        
        if filename:
            print(f"\n🎉 Export completed successfully!")
            print(f"📁 File saved as: {filename}")
            print(f"📊 Summary:")
            print(f"   - Pages found: {all_data['metadata']['total_pages']}")
            print(f"   - Pages processed: {all_data['metadata']['total_pages_processed']}")
            print(f"   - Export time: {all_data['metadata']['exported_at']}")
        else:
            print("❌ Failed to save data to file")
    else:
        print("❌ No data to export")

if __name__ == "__main__":
    main() 