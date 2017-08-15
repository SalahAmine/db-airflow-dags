import os

from airflow.models import DAG
from airflow.models import Variable
from airflow.operators.bash_operator import BashOperator
from airflow.operators.email_operator import EmailOperator
from airflow.operators.postgres_operator import PostgresOperator

from datetime import datetime, timedelta

import data_sources

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2017, 7, 1),
    'email': ['jpichot@planning.nyc.gov'],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 0,
    'retry_delay': timedelta(minutes=5),
}

# Data Loading Scripts
facbdb_download = DAG(
    'facdb_download',
    schedule_interval='@monthly',
    default_args=default_args
)

email_started = EmailOperator(
    task_id='email_on_trigger',
    to=['jpichot@planning.nyc.gov'],
    subject='[Airflow] FacDB Download Triggered',
    html_content='FacDB Download DAG triggered',
    dag=facbdb_download
)

for source in data_sources.facdb:
    params = {
        "source": source,
        "ftp_user": Variable.get('FTP_USER'),
        "ftp_pass": Variable.get('FTP_PASS'),
        "download_dir": Variable.get('DOWNLOAD_DIR'),
        "db": "af_facdb",
        "db_user": "airflow",
    }

    get = BashOperator(
        task_id='get_' + source,
        bash_command='npm run get {{ params.source }} --prefix=~/airflow/dags/download -- --ftp_user={{ params.ftp_user }} --ftp_pass={{ params.ftp_pass }} --download_dir={{ params.download_dir }}',
        params=params,
        dag=facbdb_download)
    get.set_upstream(email_started)

    push = BashOperator(
        task_id='push_' + source,
        bash_command="npm run push {{ params.source }} --prefix=~/airflow/dags/download -- --db={{ params.db }} --db_user={{ params.db_user }} --download_dir={{ params.download_dir }}",
        params=params,
        dag=facbdb_download)
    push.set_upstream(get)

    after_file_path = "/home/airflow/airflow/dags/download/datasets/{0}/after.sql".format(source)
    if os.path.isfile(after_file_path):
        with open(after_file_path, 'r') as sql_file:
            sql=sql_file.read().replace('\n', ' ')

        after = PostgresOperator(
            task_id='after_' + source,
            postgres_conn_id='facdb',
            sql=sql,
            dag=facbdb_download
        )
        after.set_upstream(push)
