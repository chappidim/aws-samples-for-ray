
import subprocess
import sys
subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'sagemaker', 'ray', 'modin[ray]', 'pydantic==1.10.10'])

from sagemaker.feature_store.feature_group import FeatureGroup
import time
import argparse
import os
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import time
import datetime
import sagemaker
import boto3
import glob
import modin.pandas as pd
import ray

########### BEGIN ACTOR #############

@ray.remote(num_cpus=0.5)
class Featurestore:
    
    def __init__(self):
        pass
    
    def ingest_features(self,feature_group_name, df, region):
        """
        Ingest features to Feature Store Group
        Args:
            feature_group_name (str): Feature Group Name
            data_path (str): Path to the train/validation/test data in CSV format.
        """
        featurestore_runtime_client = boto3.client('sagemaker-featurestore-runtime', region_name=region)
        for index, row in df.iterrows(): 
            try:
                featurestore_runtime_client.put_record(
                    FeatureGroupName=feature_group_name,
                    Record=[
                        {
                            'FeatureName': 'record_id',
                            'ValueAsString': str(int(row['record_id']))
                        },
                        {
                            'FeatureName': 'event_time',
                            'ValueAsString': str(row['event_time'])
                        },
                        {
                            'FeatureName': 'NUM_BATHROOMS',
                            'ValueAsString': str(row['NUM_BATHROOMS'])
                        },
                        {
                            'FeatureName': 'NUM_BEDROOMS',
                            'ValueAsString': str(row['NUM_BEDROOMS'])
                        },
                        {
                            'FeatureName': 'FRONT_PORCH',
                            'ValueAsString': str(row['FRONT_PORCH'])
                        },
                        {
                            'FeatureName': 'LOT_ACRES',
                            'ValueAsString': str(row['LOT_ACRES'])
                        },
                        {
                            'FeatureName': 'DECK',
                            'ValueAsString': str(row['DECK'])
                        },
                        {
                            'FeatureName': 'SQUARE_FEET',
                            'ValueAsString': str(row['SQUARE_FEET'])
                        },
                        {
                            'FeatureName': 'YEAR_BUILT',
                            'ValueAsString': str(row['YEAR_BUILT'])
                        },
                        {
                            'FeatureName': 'GARAGE_SPACES',
                            'ValueAsString': str(row['GARAGE_SPACES'])
                        },
                        {
                            'FeatureName': 'PRICE',
                            'ValueAsString': str(int(row['PRICE']))
                        },
                    ],
                    TargetStores=[
                        'OfflineStore'
                    ]
                )
            except Exception as e:
                print(f"An error occurred: {e}\nFailed to process record number {index} for feature group {feature_group_name}");

        return
    
########### END ACTOR #############


def wait_for_feature_group_creation_complete(feature_group):
    """
    Function that waits for feature group to be created in SageMaker Feature Store
    Args:
        feature_group (sagemaker.feature_store.feature_group.FeatureGroup): Feature Group
    """
    status = feature_group.describe().get('FeatureGroupStatus')
    print(f'Initial status: {status}')
    while status == 'Creating':
        print(f'Waiting for feature group: {feature_group.name} to be created ...')
        time.sleep(5)
        status = feature_group.describe().get('FeatureGroupStatus')
    if status != 'Created':
        raise SystemExit(f'Failed to create feature group {feature_group.name}: {status}')
    print(f'FeatureGroup {feature_group.name} was successfully created.')

def create_feature_group(feature_group_name, prefix, role_arn, region):
    """
    Create Feature Store Group
    Args:
        feature_group_name (str): Feature Store Group Name
        sagemaker_session (sagemaker.session.Session): sagemaker session
        df (pandas.DataFrame): dataframe to injest used to create features definition
        prefix (str): geature group prefix (train/validation or test)
        role_arn (str): role arn to create feature store
    Returns:
        fs_group (sagemaker.feature_store.feature_group.FeatureGroup): Feature Group
    """
    sm_client = boto3.client('sagemaker', region_name=region)
    sagemaker_session = sagemaker.Session(boto3.Session(region_name=region))

    default_bucket = sagemaker_session.default_bucket()

    # Search to see if the Feature Group already exists
    results = sm_client.search(
        Resource="FeatureGroup",
        SearchExpression={
            'Filters': [
                {
                    'Name': 'FeatureGroupName',
                    'Operator': 'Equals',
                    'Value': feature_group_name
                },
            ]
        }
    )

    # If a FeatureGroup was not found with the name, create one
    if not results['Results']:
        sm_client.create_feature_group(
            FeatureGroupName=feature_group_name,
            RecordIdentifierFeatureName='record_id',
            EventTimeFeatureName='event_time',
            OnlineStoreConfig={
                "EnableOnlineStore": False
            },
            OfflineStoreConfig={
                "S3StorageConfig": {
                    "S3Uri": f's3://{default_bucket}/{prefix}', 
                }, 
            },
            FeatureDefinitions=[
                {
                    'FeatureName': 'record_id',
                    'FeatureType': 'Integral'
                },
                {
                    'FeatureName': 'event_time',
                    'FeatureType': 'Fractional'
                },
                {
                    'FeatureName': 'NUM_BATHROOMS',
                    'FeatureType': 'Fractional'
                },
                {
                    'FeatureName': 'NUM_BEDROOMS',
                    'FeatureType': 'Fractional'
                },
                {
                    'FeatureName': 'FRONT_PORCH',
                    'FeatureType': 'Fractional'
                },
                {
                    'FeatureName': 'LOT_ACRES',
                    'FeatureType': 'Fractional'
                },
                {
                    'FeatureName': 'DECK',
                    'FeatureType': 'Fractional'
                },
                {
                    'FeatureName': 'SQUARE_FEET',
                    'FeatureType': 'Fractional'
                },
                {
                    'FeatureName': 'YEAR_BUILT',
                    'FeatureType': 'Fractional'
                },
                {
                    'FeatureName': 'GARAGE_SPACES',
                    'FeatureType': 'Fractional'
                },
                {
                    'FeatureName': 'PRICE',
                    'FeatureType': 'Integral'
                },
            ],
            RoleArn=role_arn
        )

    fs_group = FeatureGroup(
        name=feature_group_name, 
        sagemaker_session=sagemaker_session
    )

    wait_for_feature_group_creation_complete(fs_group)
    return fs_group


def prepare_df_for_feature_store(df):
    """
    Add event time and record id to df in order to store it in SageMaker Feature Store
    Args:
        df (pandas.DataFrame): data to be prepared
    Returns:
        df (pandas.DataFrame): dataframe with event time and record id
    """
    print(f'Preparing data for Feature Store..')
    current_time_sec = int(round(time.time()))
    # create event time
    df['event_time'] = pd.Series([current_time_sec]*len(df), dtype="float64")
    # create record id from index
    df['record_id'] = df.reset_index().index
    return df

def read_csv(path, num_actors):
    """
    Read all the CSV files with in a given directory
    IMPORTANT: All CSVs should have the same schema
    Args:
        path: the path in which the input file exist
    Returns:
        df (pandas.DataFrame): dataframe with CSV data
    """
    
    csv_files = glob.glob(os.path.join(path, "*.csv"))
    print(f"found {len(csv_files)} files")
    frames = []
    # loop over the list of csv files
    for f in csv_files:
        # read the csv file
        df = pd.read_csv(f)
        frames.append(df)

    data = pd.concat(frames)
    data = prepare_df_for_feature_store(data)
    # Split into partitions
    partitions = [ray.put(part) for part in np.array_split(data, num_actors)]
    return partitions
    

def read_parameters():
    """
    Read job parameters
    Returns:
        (Namespace): read parameters
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--feature_group_name', type=str, default='fs-ray-synthetic-house-price')
    parser.add_argument('--bucket_prefix', type=str, default='aws-ray-mlops-workshop/feature-store')
    parser.add_argument('--num_actors', type=int, default=4)
    parser.add_argument('--region', type=str, default='us-east-1')
    parser.add_argument('--role_arn', type=str)
    params, _ = parser.parse_known_args()
    return params

start = time.time()      
print(f"===========================================================")
print(f"Starting Feature Store Ingestion")
print(f"Reading parameters")

ray.init(runtime_env={'env_vars': {'__MODIN_AUTOIMPORT_PANDAS__': '1'}})

# reading job parameters
args = read_parameters()
print(f"Parameters read: {args}")


create_feature_group(
            args.feature_group_name, 
            f'{args.bucket_prefix}/synthetic-housing-price-data',
            args.role_arn,
            args.region
        )


# set input path
input_data_path = "/opt/ml/processing/input/"

input_partitions = read_csv(input_data_path, args.num_actors)


# Start actors and assign partitions in a loop
actors = [Featurestore.remote() for _ in range(args.num_actors)]
results = []
for actor, partition in zip(actors, input_partitions):
    results.append(actor.ingest_features.remote(args.feature_group_name, partition, args.region))
    
#for actor_state in ray.util.state.list_actors():
#    print(actor_state.node_id, actor_state.pid, actor_state.name, actor_state.state)

ray.get(results)

taken = time.time() - start
print(f"Ending Feature Store Ingestion")
print(f"TOTAL TIME TAKEN: {taken:.2f} seconds")
print(f"===========================================================")
