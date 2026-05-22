import boto3
from config.settings import (
    SUPABASE_ENDPOINT, SUPABASE_ACCESS_KEY_ID, SUPABASE_SECRET_ACCESS_KEY,
    SUPABASE_REGION, SUPABASE_BUCKET_NAME
)

def reset_s3():
    print("[WARNING] This will DELETE ALL objects in your S3 bucket. Continue? (y/n)")
    if input().strip().lower() != 'y':
        print("Aborted.")
        return

    client = boto3.client(
        's3',
        endpoint_url=SUPABASE_ENDPOINT,
        aws_access_key_id=SUPABASE_ACCESS_KEY_ID,
        aws_secret_access_key=SUPABASE_SECRET_ACCESS_KEY,
        region_name=SUPABASE_REGION,
        config=boto3.session.Config(signature_version='s3v4', s3={'addressing_style': 'path'})
    )

    paginator = client.get_paginator('list_objects_v2')
    total_deleted = 0
    for page in paginator.paginate(Bucket=SUPABASE_BUCKET_NAME):
        if 'Contents' in page:
            for obj in page['Contents']:
                key = obj['Key']
                client.delete_object(Bucket=SUPABASE_BUCKET_NAME, Key=key)
                total_deleted += 1
                print(f"Deleted: {key}")
    print(f"[OK] S3 bucket cleared. Total deleted: {total_deleted}")

if __name__ == "__main__":
    reset_s3()