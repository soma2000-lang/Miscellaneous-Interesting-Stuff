import boto3
from src.app.services.notification_interface import NotificationInterface
from botocore.exceptions import ClientError


class EmailNotification(NotificationInterface):

    def __init__(self):
        self.client = boto3.client('ses', region_name='us-east-1')

    def send(self, message: str, recipient: str) -> bool:

        try:
            response = self.client.send_email(
                Source='test@example.com',
                Destination={'ToAddresses': [recipient]},
                Message={
                    'Subject': {
                        'Data': 'Notification',
                    },
                    'Body': {
                        'Text': {
                            'Data': message,
                        },
                    },
                }
            )
            print(f"Email sent! Message ID: {response['MessageId']}")

            return True
        except ClientError as e:
            print(e)
            return False
