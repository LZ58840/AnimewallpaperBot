import os

from celery import Celery

from acr_worker.matcher import get_group_matcher, match_descriptors_to_group, get_showdown_matcher, sigmoid, \
    match_descriptors_to_descriptors
from utils import get_rabbitmq_auth, get_mysql_auth, database_ctx

# Due to running Celery via CLI, set Docker variable in CLI beforehand
docker = bool(os.environ.get('RUN_DOCKER'))
rabbitmq_auth = get_rabbitmq_auth(docker)
mysql_auth = get_mysql_auth(docker=docker, as_root=True)

# Initialize main Celery app
app = Celery('acr_worker',
             backend=f'db+mysql://root:{mysql_auth["password"]}@{mysql_auth["host"]}/celery',
             broker=f'pyamqp://{rabbitmq_auth["login"]}:{rabbitmq_auth["password"]}@{rabbitmq_auth["host"]}//')


# Define tasks here
@app.task(name='get_similarity', ignore_result=False)
def get_submission_similarity(submission_id: str, subreddit: str, threshold=.75):
    query_descriptors_rows = fetch_submission_descriptors(submission_id)
    if len(query_descriptors_rows) == 0:
        return {}
    subreddit_descriptors_rows = fetch_subreddit_descriptors(subreddit, submission_id)
    image_idx_map = [image_row['id'] for image_row in subreddit_descriptors_rows]
    group_matcher = get_group_matcher(subreddit_descriptors_rows)
    group_results = {
        query_row['id']: match_descriptors_to_group(query_row['sift'], group_matcher)
        for query_row in query_descriptors_rows
    }
    del group_matcher
    showdown_matcher = get_showdown_matcher()
    showdown_results = {
        query_row['id']: [
            (image_idx_map[idx], pct)
            for idx, _ in group_results[query_row['id']]
            if (pct := sigmoid(match_descriptors_to_descriptors(
                    query_row['sift'], subreddit_descriptors_rows[idx]['sift'], showdown_matcher
                ))) > threshold]
        for query_row in query_descriptors_rows
    }
    return showdown_results


def fetch_submission_descriptors(submission_id: str):
    with database_ctx(mysql_auth) as db:
        db.execute('SELECT id, sift FROM images WHERE submission_id=%s', submission_id)
        descriptors_rows = db.fetchall()
    return descriptors_rows


def fetch_subreddit_descriptors(subreddit: str, except_submission_id: str = None):
    sql_except_submission = ' AND i.submission_id!=%s' if except_submission_id is not None else ''
    sql_stmt = ('SELECT i.id, i.sift '
                'FROM images i JOIN submissions s ON i.submission_id = s.id '
                'WHERE s.subreddit=%s AND NOT s.removed AND NOT s.deleted AND i.sift IS NOT NULL')
    sql_args = (except_submission_id, subreddit) if except_submission_id is not None else (subreddit,)

    with database_ctx(mysql_auth) as db:
        db.execute(sql_stmt + sql_except_submission, sql_args)
        descriptors_rows = db.fetchall()

    return descriptors_rows
