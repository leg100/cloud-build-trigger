import tempfile
import os
import uuid
import yaml

from google.cloud import storage
from googleapiclient import discovery
from sh import git

from cloud_build_trigger.event import create_event_from_request


def upload(tarball, bucket):
    storage_client = storage.Client()

    try:
        b = storage_client.get_bucket(bucket)
    except exceptions.NotFound:
        raise RuntimeError(f"Could not find bucket {bucket}")
    else:
        blob = b.blob(os.path.basename(tarball))
        blob.upload_from_filename(tarball)


def submit(project, config):
    cloudbuild_client = discovery.build('cloudbuild', 'v1', cache_discovery=False)

    cloudbuild_client.projects() \
            .builds() \
            .create(projectId=project, body=config) \
            .execute()


def trigger(req):
    e = create_event_from_request(req)

    try:
        e.validate(req.headers)
    except Exception:
        print(RuntimeError("Ignoring webhook event"))
        return

    bucket = os.environ['BUCKET']
    project = os.environ['GCP_PROJECT']

    config = {
            'source': {
                'bucket': bucket
                },
            'substitutions': {
                'REPO_NAME': e.repo,
                'BRANCH_NAME': e.branch,
                'REVISION_ID': e.commit,
                'COMMIT_SHA': e.commit,
                'SHORT_SHA': e.commit[0:7]
                }
            }

    with tempfile.TemporaryDirectory() as tmpdir:
        #git.clone('--branch', e.base_branch, '--single-branch', e.base_clone_url, tmpdir)
        #git.remote('add', 'head', e.head_clone_url, _cwd=tmpdir)
        #git.fetch('head', f'+refs/heads/{e.head_branch}', _cwd=tmpdir)
        #git.merge('-q', '--no-ff', '-m', 'trigger-merge', 'FETCH_HEAD', _cwd=tmpdir)
        git.clone('--branch', e.branch, '--depth=1', '--single-branch', e.clone_url, tmpdir)

        cloudbuild_config_path = os.path.join(tmpdir, 'cloudbuild.yaml')
        config.update(yaml.safe_load(open(cloudbuild_config_path)))

        suffix = uuid.uuid1()
        tarball = os.path.join(tmpdir, f'{e.commit}-{suffix}.tar.gz')

        config['source']['object'] = tarball

        git.archive('-o', tarball, 'HEAD', _cwd=tmpdir)

        upload(tarball, bucket)

    submit(project, config)
