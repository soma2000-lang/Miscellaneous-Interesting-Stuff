# AWS Two-Person Review System for Production Resources

## 1. Overview

This system implements a two-person review process for critical AWS actions, particularly those affecting production databases. It ensures that no single person can make changes to sensitive resources without approval from a second authorized individual.

## 2. System Components

1. AWS Identity and Access Management (IAM)
2. AWS CloudTrail
3. AWS Lambda
4. Amazon SNS (Simple Notification Service)
5. Amazon DynamoDB (for tracking approval requests)
6. Custom web interface for approvals

## 3. Implementation Steps

### 3.1 IAM Configuration

1. Create two IAM groups: "Requesters" and "Approvers"
2. Set up IAM policies:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:DescribeTable",
        "dynamodb:ListTables"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/prod-*"
    },
    {
      "Effect": "Deny",
      "Action": [
        "dynamodb:DeleteTable",
        "dynamodb:UpdateTable"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/prod-*"
    }
  ]
}
```

3. Assign users to appropriate groups

### 3.2 CloudTrail Configuration

1. Ensure CloudTrail is enabled and logging all DynamoDB events
2. Create a CloudWatch rule to trigger on specific DynamoDB events:

```json
{
  "source": ["aws.dynamodb"],
  "detail-type": ["AWS API Call via CloudTrail"],
  "detail": {
    "eventSource": ["dynamodb.amazonaws.com"],
    "eventName": ["DeleteTable", "UpdateTable"]
  }
}
```

### 3.3 Lambda Function for Processing Events

```python
import boto3
import json

dynamodb = boto3.resource('dynamodb')
sns = boto3.client('sns')
approval_table = dynamodb.Table('ApprovalRequests')

def lambda_handler(event, context):
    detail = event['detail']
    event_name = detail['eventName']
    request_parameters = detail['requestParameters']
    user_identity = detail['userIdentity']['arn']
    
    # Check if the affected table is a production table
    if not request_parameters['tableName'].startswith('prod-'):
        return
    
    # Create approval request
    approval_id = str(uuid.uuid4())
    approval_table.put_item(
        Item={
            'ApprovalId': approval_id,
            'EventName': event_name,
            'RequestParameters': json.dumps(request_parameters),
            'Requester': user_identity,
            'Status': 'Pending'
        }
    )
    
    # Send notification for approval
    sns.publish(
        TopicArn='arn:aws:sns:region:account-id:ApprovalNotifications',
        Message=json.dumps({
            'ApprovalId': approval_id,
            'EventName': event_name,
            'Requester': user_identity,
            'Resource': request_parameters['tableName']
        }),
        Subject='Action Approval Required'
    )
    
    # Respond to the original request
    return {
        'statusCode': 202,
        'body': json.dumps('Action requires approval. Request ID: ' + approval_id)
    }
```

### 3.4 Approval Web Interface

Create a simple web application for approvers to review and approve/deny requests:

```python
from flask import Flask, request, jsonify
import boto3

app = Flask(__name__)
dynamodb = boto3.resource('dynamodb')
approval_table = dynamodb.Table('ApprovalRequests')

@app.route('/approvals', methods=['GET'])
def list_approvals():
    response = approval_table.scan(FilterExpression=Attr('Status').eq('Pending'))
    return jsonify(response['Items'])

@app.route('/approve', methods=['POST'])
def approve_request():
    approval_id = request.json['ApprovalId']
    approver = request.json['Approver']
    
    # Update approval status
    approval_table.update_item(
        Key={'ApprovalId': approval_id},
        UpdateExpression='SET Status = :status, Approver = :approver',
        ExpressionAttributeValues={
            ':status': 'Approved',
            ':approver': approver
        }
    )
    
    # Trigger the approved action (implement this based on your requirements)
    trigger_approved_action(approval_id)
    
    return jsonify({'message': 'Action approved and executed'})

@app.route('/deny', methods=['POST'])
def deny_request():
    approval_id = request.json['ApprovalId']
    approver = request.json['Approver']
    
    approval_table.update_item(
        Key={'ApprovalId': approval_id},
        UpdateExpression='SET Status = :status, Approver = :approver',
        ExpressionAttributeValues={
            ':status': 'Denied',
            ':approver': approver
        }
    )
    
    return jsonify({'message': 'Action denied'})

if __name__ == '__main__':
    app.run(debug=True)
```

### 3.5 Execution of Approved Actions

Create another Lambda function to execute approved actions:

```python
import boto3

dynamodb = boto3.client('dynamodb')

def lambda_handler(event, context):
    approval_id = event['ApprovalId']
    
    # Retrieve approval details
    approval = get_approval_details(approval_id)
    
    if approval['Status'] != 'Approved':
        return {
            'statusCode': 400,
            'body': 'Action not approved'
        }
    
    # Execute the approved action
    if approval['EventName'] == 'DeleteTable':
        dynamodb.delete_table(TableName=approval['RequestParameters']['tableName'])
    elif approval['EventName'] == 'UpdateTable':
        # Implement update logic based on the specific update parameters
        pass
    
    return {
        'statusCode': 200,
        'body': 'Action executed successfully'
    }

def get_approval_details(approval_id):
    # Implement this function to retrieve approval details from DynamoDB
    pass
```

## 4. Security Considerations

1. **Least Privilege**: Ensure IAM policies adhere to the principle of least privilege.
2. **Encryption**: Use AWS KMS to encrypt sensitive data at rest and in transit.
3. **Logging**: Enable detailed logging for all components, especially approval actions.
4. **Authentication**: Implement strong authentication for the approval web interface, possibly using AWS Cognito.
5. **Audit Trail**: Maintain a comprehensive audit trail of all requests and approvals.

## 5. Implementation Strategy

1. Set up IAM groups and policies
2. Configure CloudTrail and CloudWatch rules
3. Implement the Lambda function for processing events
4. Create the DynamoDB table for storing approval requests
5. Develop and deploy the approval web interface
6. Implement the Lambda function for executing approved actions
7. Set up SNS for notifications
8. Conduct thorough testing in a staging environment
9. Gradually roll out to production, starting with non-critical resources
10. Provide training to both requesters and approvers
11. Regularly review and audit the system

## 6. Best Practices

1. Regularly rotate IAM credentials
2. Implement MFA for all IAM users, especially those in the Approvers group
3. Use AWS Organizations to manage multiple accounts if applicable
4. Regularly review and update the list of resources requiring dual control
5. Implement alerting for any bypasses or failures in the approval system
6. Conduct regular security audits and penetration testing
7. Keep all systems and dependencies up to date

