import boto3
import time

try:
    dynamodb = boto3.client('dynamodb', region_name='us-east-1')
    
    print("Creating DynamoDB table 'Users'...")
    response = dynamodb.create_table(
        TableName='Users',
        KeySchema=[
            {'AttributeName': 'roll', 'KeyType': 'HASH'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'roll', 'AttributeType': 'S'}
        ],
        BillingMode='PAY_PER_REQUEST'
    )
    
    print("Waiting for table to become active...")
    waiter = dynamodb.get_waiter('table_exists')
    waiter.wait(TableName='Users')
    print("Table created successfully!")
except dynamodb.exceptions.ResourceInUseException:
    print("Table already exists!")
except Exception as e:
    print(f"Error: {e}")
