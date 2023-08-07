import datetime
import os
import tempfile
import time

import boto3
from boto3.s3.transfer import TransferConfig, S3Transfer
from botocore.exceptions import ClientError

import utils

#########################
# Configurations begin
#########################

# required, according to your ~/.aws/credentials & ~/.aws/config
src_profile_name = os.environ.get("SRC_AWS_PROFILE", "") or "ww"  # required
dst_profile_name = os.environ.get("DST_AWS_PROFILE", "") or "cn"  # required

# required, e.g. ami-0123456789abcdefg
ami_id = os.environ.get("AMI_ID", "")

# required, default value is enough
tmp_bucket_name_prefix = os.environ.get("TEMP_BUCKET_NAME_PREFIX", "") or "my-temp-bucket-"

# optional, will create one with above prefix if not exists
src_bucket_name = os.environ.get("SRC_BUCKET_NAME", "")
dst_bucket_name = os.environ.get("DST_BUCKET_NAME", "")

encrypt_restored_ami = True  # optional, default is True

#########################
# Configurations end
#########################

print("Executing, started at {}.".format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

src_region_name = boto3.Session(profile_name=src_profile_name).region_name
dst_region_name = boto3.Session(profile_name=dst_profile_name).region_name

src_session = boto3.Session(profile_name=src_profile_name, region_name=src_region_name)
dst_session = boto3.Session(profile_name=dst_profile_name, region_name=dst_region_name)

src_ec2 = src_session.client("ec2")
dst_ec2 = dst_session.client("ec2")
src_s3 = src_session.client("s3")
dst_s3 = dst_session.client("s3")

#########################

try:
    src_ec2.describe_images(ImageIds=[ami_id])
except ClientError as e:
    if "InvalidAMIID" in str(e) or "MissingParameter" in str(e):
        print(f"AMI '{ami_id}' is not exists in region {src_region_name}.")
        exit(1)

#########################

with utils.EnsureS3Bucket(src_s3, src_bucket_name, tmp_bucket_name_prefix, src_region_name) as src_bucket_name:
    store_task = src_ec2.create_store_image_task(
        ImageId=ami_id,
        Bucket=src_bucket_name
    )
    object_key = store_task['ObjectKey']

    while True:
        tasks = src_ec2.describe_store_image_tasks(ImageIds=[ami_id])
        state = tasks["StoreImageTaskResults"][0]["StoreTaskState"]
        progress = tasks["StoreImageTaskResults"][0]["ProgressPercentage"]

        print(f"\rAMI {ami_id} is being stored to {src_bucket_name}/{object_key} in region {src_region_name} ... "
              f"{progress}%", end='', flush=True)

        if state == "Completed":
            print(f"\rAMI {ami_id} stored to {src_bucket_name}/{object_key} in region {src_region_name}." + " " * 20)
            break
        elif state == "Failed":
            reason = tasks["StoreImageTaskResults"][0]["StoreTaskFailureReason"]
            print(f"\rAMI {ami_id} store to {src_bucket_name}/{object_key} in region {src_region_name} failed. "
                  f"Reason: {reason}")
            exit(1)
        time.sleep(5)

    #########################

    with tempfile.NamedTemporaryFile(delete=True) as temp_file:
        download_progress_callback = utils.DownloadProgressPercentage(
            src_s3, src_bucket_name, object_key, temp_file.name)
        transfer_config = TransferConfig()  # multipart download will be used by default
        transfer = S3Transfer(src_s3, transfer_config)
        transfer.download_file(src_bucket_name, object_key, temp_file.name, callback=download_progress_callback)

        print(f"\rObject {src_bucket_name}/{object_key} downloaded to {temp_file.name} (auto delete later)." + " " * 40)

        temp_file.flush()
        # close() causes file deletion
        # temp_file.close()

        with utils.EnsureS3Bucket(dst_s3, dst_bucket_name, tmp_bucket_name_prefix, dst_region_name) as dst_bucket_name:
            upload_progress_callback = utils.UploadProgressPercentage(dst_bucket_name, temp_file.name)
            transfer_config = TransferConfig()  # multipart upload will be used by default
            transfer = S3Transfer(dst_s3, transfer_config)
            transfer.upload_file(temp_file.name, dst_bucket_name, object_key, callback=upload_progress_callback)

            print(f"\rStored AMI {temp_file.name} uploaded to {dst_bucket_name}/{object_key}." + " " * 40)

            task = dst_ec2.create_restore_image_task(
                ObjectKey=object_key,
                Bucket=dst_bucket_name)

            ami_id_new = task["ImageId"]

            #########################

            ami_resp = dst_ec2.describe_images(ImageIds=[ami_id_new]).get("Images")
            if not ami_resp:
                print(f"\rAMI {ami_id_new} in region {src_region_name} not found.")
                exit(1)

            ami = ami_resp[0]

            # Assuming the AMI has only one snapshot
            snapshot_id = ami["BlockDeviceMappings"][0]["Ebs"]["SnapshotId"]

            while True:
                snapshot_resp = dst_ec2.describe_snapshots(SnapshotIds=[snapshot_id]).get("Snapshots")
                if not snapshot_resp:
                    print(f"\rAMI {ami_id_new} restored in region {dst_region_name} has no snapshot.")
                    exit(1)

                snapshot = snapshot_resp[0]
                state = snapshot["State"]
                progress = snapshot["Progress"]

                print(f"\rSnapshot {snapshot_id} is being restoring for AMI {ami_id_new} "
                      f"in region {dst_region_name} ... {progress}", end='', flush=True)

                if state == 'completed':
                    print(f"\rSnapshot {snapshot_id} restored for AMI {ami_id_new} in region {dst_region_name}." +
                          " " * 20)
                    break
                elif state == 'error':
                    reason = snapshot["StateMessage"]
                    print(f"\rSnapshot {snapshot_id} restore for AMI {ami_id_new} in region {dst_region_name} failed. "
                          f"Reason: {reason}")
                    exit(1)
                time.sleep(5)  # wait for 5 seconds before the next query

            #########################

            if not encrypt_restored_ami:
                print(f"AMI {ami_id} restored in region {dst_region_name}. New AMI ID: {ami_id_new}")
            else:  # Encrypt the restored snapshot/AMI, to meet the compliance requirement in general cases.
                snapshot_copy_resp = dst_ec2.copy_snapshot(
                    SourceSnapshotId=snapshot_id,
                    SourceRegion=dst_region_name,
                    Description=f"Restored for AMI {ami_id} in region {src_region_name}",
                    Encrypted=True
                )

                snapshot_id_encrypted = snapshot_copy_resp['SnapshotId']

                tags_resp = dst_ec2.describe_tags(
                    Filters=[
                        {
                            "Name": "resource-id",
                            "Values": [snapshot_id]
                        }
                    ]
                )

                tags = tags_resp["Tags"]
                if tags:
                    dst_ec2.create_tags(Resources=[snapshot_id_encrypted],
                                        Tags=[{'Key': tag['Key'], 'Value': tag['Value']} for tag in tags])

                while True:
                    snapshot_encrypted_resp = dst_ec2.describe_snapshots(
                        SnapshotIds=[snapshot_id_encrypted]).get("Snapshots")
                    if not snapshot_encrypted_resp:
                        print(f"\rSnapshot {snapshot_id_encrypted} duplicated from {snapshot_id} "
                              f"in region {dst_region_name} not found.")
                        exit(1)

                    snapshot_encrypted = snapshot_encrypted_resp[0]
                    state = snapshot_encrypted["State"]
                    progress = snapshot_encrypted["Progress"]

                    print(f"\rEncrypted snapshot {snapshot_id_encrypted} is being duplicated from {snapshot_id} "
                          f"in region {dst_region_name} ... {progress}", end="", flush=True)

                    if state == "completed":
                        print(f"\rEncrypted snapshot {snapshot_id_encrypted} duplicated from {snapshot_id} "
                              f"in region {dst_region_name}." + " " * 40)
                        break
                    elif state == "error":
                        reason = snapshot_encrypted["StateMessage"]
                        print(f"\rEncrypted snapshot {snapshot_id_encrypted} duplicate from {snapshot_id} "
                              f"in region {dst_region_name} failed. Reason: {reason}")
                        exit(1)
                    time.sleep(5)  # wait for 5 seconds before the next query

                tags_resp = dst_ec2.describe_tags(
                    Filters=[
                        {
                            "Name": "resource-id",
                            "Values": [ami_id_new]
                        }
                    ]
                )

                tags = tags_resp["Tags"]

                dst_ec2.deregister_image(ImageId=ami_id_new)
                dst_ec2.delete_snapshot(SnapshotId=snapshot_id)

                ami_register_resp = dst_ec2.register_image(
                    Name=ami["Name"],
                    Description=ami.get("Description", ""),
                    Architecture=ami["Architecture"],
                    EnaSupport=ami.get("EnaSupport", True),  # G serials need ENA support
                    SriovNetSupport=ami.get("SriovNetSupport", "simple"),
                    RootDeviceName=ami["RootDeviceName"],
                    BlockDeviceMappings=[
                        {
                            "DeviceName": ami["RootDeviceName"],
                            "Ebs": {
                                "SnapshotId": snapshot_id_encrypted,
                                "DeleteOnTermination": True,
                                "VolumeType": "gp2",
                            },
                        },
                        {
                            "DeviceName": "/dev/sdb",
                            "VirtualName": "ephemeral0",
                        },
                        {
                            "DeviceName": "/dev/sdc",
                            "VirtualName": "ephemeral1"
                        },
                    ],
                )

                ami_id_new_encrypted = ami_register_resp["ImageId"]

                if tags:
                    dst_ec2.create_tags(Resources=[ami_id_new_encrypted],
                                        Tags=[{"Key": tag["Key"], "Value": tag["Value"]} for tag in tags])

                print(f"AMI {ami_id} restored in region {dst_region_name}. New AMI ID: {ami_id_new_encrypted}")

print("Done, ended at {}.".format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
