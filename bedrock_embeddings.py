#!/usr/bin/env python3
"""
Script to access Amazon Bedrock embeddings model using environment variables
"""

import os
import sys
import json
import boto3
from dotenv import load_dotenv
from botocore.exceptions import ClientError, NoCredentialsError

def load_environment():
    """Load environment variables from .env file"""
    load_dotenv()
    
    # AWS credentials
    aws_access_key_id = os.getenv('AWS_ACCESS_KEY')
    aws_secret_access_key = os.getenv('AWS_SECRET_KEY')
    aws_region = os.getenv('AWS_REGION', 'us-east-1')
    
    # Bedrock specific settings
    bedrock_model_id = os.getenv('BEDROCK_MODEL_ID', 'amazon.titan-embed-text-v1')
    
    if not aws_access_key_id:
        print("❌ AWS_ACCESS_KEY not found in .env file")
        print("Please add your AWS access key to your .env file:")
        print("AWS_ACCESS_KEY=your_aws_access_key_here")
        return None, None, None, None
    
    if not aws_secret_access_key:
        print("❌ AWS_SECRET_KEY not found in .env file")
        print("Please add your AWS secret key to your .env file:")
        print("AWS_SECRET_KEY=your_aws_secret_key_here")
        return None, None, None, None
    
    return aws_access_key_id, aws_secret_access_key, aws_region, bedrock_model_id

def create_bedrock_client(aws_access_key_id, aws_secret_access_key, aws_region):
    """Create and configure Bedrock client"""
    try:
        bedrock_client = boto3.client(
            service_name='bedrock-runtime',
            region_name=aws_region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key
        )
        
        print(f"✅ Bedrock client created successfully")
        print(f"   Region: {aws_region}")
        return bedrock_client
        
    except NoCredentialsError:
        print("❌ AWS credentials not found or invalid")
        return None
    except ClientError as e:
        print(f"❌ Error creating Bedrock client: {e}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error creating Bedrock client: {e}")
        return None

def get_embedding(bedrock_client, text, model_id):
    """Get embedding for a given text using Bedrock"""
    try:
        # Prepare the request body
        request_body = {
            "inputText": text
        }
        
        # Convert to JSON
        body = json.dumps(request_body)
        
        # Make the API call
        response = bedrock_client.invoke_model(
            modelId=model_id,
            body=body
        )
        
        # Parse the response
        response_body = json.loads(response['body'].read())
        embedding = response_body.get('embedding', [])
        
        return embedding
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'AccessDeniedException':
            print(f"❌ Access denied. Please check your AWS permissions for Bedrock")
        elif error_code == 'ValidationException':
            print(f"❌ Invalid request. Please check your input text and model ID")
        else:
            print(f"❌ AWS Bedrock error: {e}")
        return None
    except Exception as e:
        print(f"❌ Error getting embedding: {e}")
        return None

def test_bedrock_connection(bedrock_client, model_id):
    """Test the Bedrock connection with a simple embedding request"""
    print(f"🧪 Testing Bedrock connection with model: {model_id}")
    
    test_text = "Hello, this is a test message for Amazon Bedrock embeddings."
    
    print(f"   Input text: {test_text}")
    
    embedding = get_embedding(bedrock_client, test_text, model_id)
    
    if embedding:
        print(f"✅ Connection successful!")
        print(f"   Embedding dimensions: {len(embedding)}")
        print(f"   First 5 values: {embedding[:5]}")
        return True
    else:
        print(f"❌ Connection failed")
        return False

def get_embeddings_batch(bedrock_client, texts, model_id):
    """Get embeddings for a batch of texts"""
    embeddings = []
    
    print(f"📊 Processing {len(texts)} texts...")
    
    for i, text in enumerate(texts, 1):
        print(f"   Processing text {i}/{len(texts)}...")
        
        embedding = get_embedding(bedrock_client, text, model_id)
        if embedding:
            embeddings.append({
                'text': text,
                'embedding': embedding,
                'dimensions': len(embedding)
            })
        else:
            print(f"   ⚠️  Failed to get embedding for text {i}")
    
    return embeddings

def save_embeddings_to_file(embeddings, filename=None):
    """Save embeddings to a JSON file"""
    if not filename:
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"bedrock_embeddings_{timestamp}.json"
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(embeddings, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Embeddings saved to: {filename}")
        return filename
    except Exception as e:
        print(f"❌ Error saving embeddings: {e}")
        return None

def main():
    """Main function"""
    print("🚀 Amazon Bedrock Embeddings")
    print("=" * 35)
    
    # Load environment variables
    aws_access_key_id, aws_secret_access_key, aws_region, model_id = load_environment()
    if not aws_access_key_id or not aws_secret_access_key:
        sys.exit(1)
    
    # Create Bedrock client
    bedrock_client = create_bedrock_client(aws_access_key_id, aws_secret_access_key, aws_region)
    if not bedrock_client:
        sys.exit(1)
    
    # Test connection
    if not test_bedrock_connection(bedrock_client, model_id):
        print("❌ Bedrock connection test failed")
        sys.exit(1)
    
    # Example usage
    print(f"\n📝 Example usage:")
    print(f"   Model ID: {model_id}")
    print(f"   Region: {aws_region}")
    
    # Get embeddings for some example texts
    example_texts = [
        "This is the first example text for embedding.",
        "Here is another text to demonstrate the embedding functionality.",
        "Amazon Bedrock provides powerful embedding capabilities.",
        "Embeddings can be used for semantic search and similarity matching."
    ]
    
    embeddings = get_embeddings_batch(bedrock_client, example_texts, model_id)
    
    if embeddings:
        # Save to file
        filename = save_embeddings_to_file(embeddings)
        
        if filename:
            print(f"\n🎉 Successfully processed {len(embeddings)} embeddings!")
            print(f"📁 File saved as: {filename}")
            print(f"📊 Summary:")
            print(f"   - Texts processed: {len(embeddings)}")
            print(f"   - Embedding dimensions: {embeddings[0]['dimensions'] if embeddings else 0}")
        else:
            print("❌ Failed to save embeddings to file")
    else:
        print("❌ No embeddings were generated")

if __name__ == "__main__":
    main() 