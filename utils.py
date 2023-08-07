import os
import threading
import time

from botocore.exceptions import ClientError


class EnsureS3Bucket:
    def __init__(self, s3_client, bucket_name, tmp_bucket_name_prefix, region):
        self._s3_client = s3_client
        self._remove = False
        self._bucket_name = str(bucket_name).strip() if bucket_name is not None else ""
        self._tmp_bucket_name_prefix = str(tmp_bucket_name_prefix).strip() if tmp_bucket_name_prefix is not None else ""
        self._region = str(region).strip() if region is not None else ""

    def _delete_all_objects(self):
        objects = self._s3_client.list_objects(Bucket=self._bucket_name)
        if 'Contents' in objects:
            for obj in objects['Contents']:
                self._s3_client.delete_object(Bucket=self._bucket_name, Key=obj['Key'])

    def __enter__(self):
        if not self._bucket_name or len(self._bucket_name) == 0:
            self._bucket_name = self._tmp_bucket_name_prefix + str(int(time.time()))

        try:
            bucket_create_config = {}
            if self._region != "us-east-1":
                bucket_create_config["LocationConstraint"] = self._region

            self._s3_client.create_bucket(
                Bucket=self._bucket_name,
                CreateBucketConfiguration=bucket_create_config)
            self._remove = True
            print(f'Bucket {self._bucket_name} created (region {self._region}).')
        except ClientError as e:
            if e.response['Error']['Code'] == 'BucketAlreadyOwnedByYou':
                print(f'Bucket {self._bucket_name} already exists (region {self._region}).')
            else:
                raise

        return self._bucket_name

    def __exit__(self, type, value, traceback):
        if self._remove:
            self._delete_all_objects()
            self._s3_client.delete_bucket(Bucket=self._bucket_name)
            print(f'Bucket {self._bucket_name} deleted (region {self._region}).')


class DownloadProgressPercentage:
    def __init__(self, s3_client, bucket_name, object_key, filename):
        self._bucket_name = bucket_name
        self._object_key = object_key
        self._filename = filename
        self._seen_so_far = 0
        self._lock = threading.Lock()

        obj_metadata = s3_client.head_object(Bucket=self._bucket_name, Key=self._object_key)
        self._size = float(obj_metadata['ContentLength'])

    def __call__(self, bytes_amount):
        with self._lock:
            self._seen_so_far += bytes_amount
            progress = (self._seen_so_far / self._size) * 100 // 0.01 * 0.01
            print(f"\rObject {self._bucket_name}/{self._object_key} is being downloaded to {self._filename} ... "
                  f"{progress:.2f}% ({(self._seen_so_far / 1024 / 1024):.2f}MB / {(self._size / 1024 / 1024):.2f}MB)",
                  end="", flush=False)


class UploadProgressPercentage:
    def __init__(self, bucket_name, filename):
        self._bucket = bucket_name
        self._filename = filename
        self._size = float(os.path.getsize(filename))
        self._seen_so_far = 0
        self._lock = threading.Lock()

    def __call__(self, bytes_amount):
        with self._lock:
            self._seen_so_far += bytes_amount
            progress = (self._seen_so_far / self._size) * 100 // 0.01 * 0.01
            print(f"\rStored AMI {self._filename} is being uploaded to {self._bucket} ... "
                  f"{progress:.2f}% ({(self._seen_so_far / 1024 / 1024):.2f}MB / {(self._size / 1024 / 1024):.2f}MB)",
                  end="", flush=False)
