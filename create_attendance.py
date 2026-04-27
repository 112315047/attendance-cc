import boto3
import time

try:
    dynamodb = boto3.client('dynamodb', region_name='us-east-1')
    
    print("Creating DynamoDB table 'Attendance'...")
    response = dynamodb.create_table(
        TableName='Attendance',
        KeySchema=[
            {'AttributeName': 'roll', 'KeyType': 'HASH'},
            {'AttributeName': 'date', 'KeyType': 'RANGE'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'roll', 'AttributeType': 'S'},
            {'AttributeName': 'date', 'AttributeType': 'S'}
        ],
        BillingMode='PAY_PER_REQUEST'
    )
    
    waiter = dynamodb.get_waiter('table_exists')
    waiter.wait(TableName='Attendance')
    print("Table 'Attendance' created successfully!")
except dynamodb.exceptions.ResourceInUseException:
    print("Table already exists!")
except Exception as e:
    print(f"Error: {e}")
