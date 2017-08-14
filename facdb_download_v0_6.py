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
    'facdb_download_v0_6',
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
        "db": "af_facdb",
        "db_user": "airflow",
    }

    get = BashOperator(
        task_id='get_' + source,
        bash_command='npm run get {{ params.source }} --prefix=~/airflow/dags/scripts -- --ftp_user={{ params.ftp_user }} --ftp_pass={{ params.ftp_pass }} --download_dir=~/tmp',
        params=params,
        dag=facbdb_download)
    get.set_upstream(email_started)

    push = BashOperator(
        task_id='push_' + source,
        bash_command="npm run push {{ params.source }} --prefix=~/airflow/dags/scripts -- --db={{ params.db }} --db_user={{ params.db_user }} --download_dir=~/tmp",
        params=params,
        dag=facbdb_download)
    push.set_upstream(get)

    after_file_path = "/home/airflow/airflow/dags/scripts/datasets/{0}/after.sql".format(source)
    if os.path.isfile(after_file_path):
        after = SQLOperator(
            task_id='after_' + source,
            postgres_conn_id='postgres_default',
            sql=after_file_path
        )
        after.set_upstream(push)

    # after = BashOperator(
    #     task_id='after_' + source,
    #     bash_command="npm run after {{ params.source }} --prefix=~/airflow/dags/scripts -- --db={{ params.db }} --db_user={{ params.db_user }}",
    #     params=params,
    #     dag=facbdb_download)
    # after.set_upstream(push)
