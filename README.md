# QuickStart

1. Prepare two AWS accounts, one for Worldwide and one for China.
2. Build the AMI in your Worldwide account by the standard instructions, after that an available AMI will in your Worldwide AWS account.
3. To execute the tool with the certain parameters. It will copy the AMI from your Worldwide account to your China account.<br>
   The tool is based on the [Boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html) Python SDK. You can install the dependencies by the following command:

   ```bash
   pip install -r requirements.txt
   ```

   The tool supports the following parameters:

   | Name                    | Description                                                                                                                                                                                                                                                                                                           | Date type | Required | Default value               | Example values        |
   |-------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------|----------|-----------------------------|-----------------------|
   | SRC\_AWS\_PROFILE         | The AWS profile name of your Worldwide account. You can configure the profile name by ~/.aws/credentials amd ~/.aws/config file. If you want to do that by AWS CLI commandline, you can check the guide at [here](https://awscli.amazonaws.com/v2/documentation/api/latest/reference/configure/index.html#configure). | String    | No       | ww                          | Worldwide             |
   | DST\_AWS\_PROFILE         | The AWS profile name of your China account. You can configure the profile name by ~/.aws/credentials amd ~/.aws/config file. If you want to do that by AWS CLI commandline, you can check the guide at [here](https://awscli.amazonaws.com/v2/documentation/api/latest/reference/configure/index.html#configure).     | String    | No       | cn                          | china                 |
   | AMI\_ID                  | The AMI ID of the AMI you want to copy. It in your Worldwide account.                                                                                                                                                                                                                                                 | String    | Yes      |                             | ami-0123456789abcdefg |
   | SRC\_BUCKET\_NAME         | The name of the S3 bucket used to store the temporary AMI binary file in your Worldwide account. If the bucket is not existing, a temprary one will be used.                                                                                                                                                          | String    | No       | my-temp-bucket-*{time-now}* | my-src-bucket         |
   | DST\_BUCKET\_NAME         | The name of the S3 bucket used to store the temporary AMI binary file in your China account. If the bucket is not existing, a temprary one will be used.                                                                                                                                                              | String    | No       | my-temp-bucket-*{time-now}* | my-dst-bucket         |
   | TEMP\_BUCKET\_NAME\_PREFIX | The prefix of the S3 bucket name used to store the temporary files for your Worldwide and China AWS accounts. The Bucket will be automatically crated, and deleted after use.                                                                                                                                         | String    | No       | my-temp-bucket-             | ami-copy-temp-        |

   For example, you can execute the tool by the following command to copy the AMI *ami-0123456789abcdefg* from your Worldwide account to your China account:

   ```bash
    AMI_ID=ami-0123456789abcdefg python ami_copy.py
    ```
    After the tool is executed successfully, you will see the AMI in your China account. The similar logs will be printed as following:

   ```base
   Executing, started at 2023-07-27 16:02:05.
   Bucket my-temp-bucket-1690473726 created (region ap-southeast-1).
   AMI ami-0123456789abcdefg stored to my-temp-bucket-1690473726/ami-0123456789abcdefg.bin in region ap-southeast-1.
   Object my-temp-bucket-1690473726/ami-0123456789abcdefg.bin downloaded to /tmp/tmpkxldmshq (auto delete later).
   Bucket my-temp-bucket-1690474663 created (region cn-north-1).
   Stored AMI /tmp/tmpkxldmshq uploaded to my-temp-bucket-1690474663/ami-0123456789abcdefg.bin.
   Snapshot snap-0c7e05a710089da04 restored for AMI ami-0132c59633dd28339 in region cn-north-1.
   Encrypted snapshot snap-0875b74f2f9b59c6e duplicated from snap-0c7e05a710089da04 in region cn-north-1.
   AMI ami-0123456789abcdefg restored in region cn-north-1. New AMI ID: ami-0e95e9a116aa6f348
   Bucket my-temp-bucket-1690474663 deleted (region cn-north-1).
   Bucket my-temp-bucket-1690473726 deleted (region ap-southeast-1).
   Done, ended at 2023-07-27 16:44:26.
   ```

   In this example, the AMI ami-0e95e9a116aa6f348 in your China AWS account is ready to serve.

>> **Note:**
>> 
>> Technically this tool should support copy the AMI from China AWS account to Worldwide account, howevery I didn't test it yet.
