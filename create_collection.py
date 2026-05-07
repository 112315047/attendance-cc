import boto3

def create_collection():
    client = boto3.client('rekognition', region_name='us-east-1')
    collection_id = 'attendance_collection'
    
    try:
        print(f"Creating collection: {collection_id}")
        response = client.create_collection(CollectionId=collection_id)
        print("Collection created successfully!")
        print(f"Collection ARN: {response['CollectionArn']}")
    except client.exceptions.ResourceAlreadyExistsException:
        print("Collection already exists!")
    except Exception as e:
        print(f"Error creating collection: {e}")

if __name__ == '__main__':
    create_collection()
