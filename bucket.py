import boto3
from os import environ
from dotenv import load_dotenv
from botocore.client import Config

load_dotenv()

class Bucket:
    def __init__(self):
        self.DO_REGION = environ.get('DO_REGION')
        self.DO_ACCESS_KEY = environ.get('DO_ACCESS_KEY')
        self.DO_SECRET_KEY = environ.get('DO_SECRET_KEY')
        self.DO_BUCKET_NAME = environ.get('DO_BUCKET_NAME')
        self.DO_BUCKET_ENDPOINT = environ.get('DO_BUCKET_ENDPOINT')

        self.client = boto3.client(
            's3',
            region_name=self.DO_REGION,
            endpoint_url=self.DO_BUCKET_ENDPOINT,
            aws_access_key_id=self.DO_ACCESS_KEY,
            aws_secret_access_key=self.DO_SECRET_KEY,
            config=Config(s3={'addressing_style': 'virtual'})
        )

    def loadByType(self, types: list):
        response = self.client.list_objects_v2(Bucket=self.DO_BUCKET_NAME)

        # Filter files by type
        files = [
            obj['Key'] for obj in response.get('Contents', []) if obj['Key'].split('.')[-1] in types
        ]

        return files

    def downloadFile(self, file_path, local_path):
        self.client.download_file(
            self.DO_BUCKET_NAME,
            file_path,
            local_path
        )

    def uploadFile(self, file_key, local_path):
        self.client.upload_file(
            local_path,
            self.DO_BUCKET_NAME,
            f"songs/{file_key}"
        )