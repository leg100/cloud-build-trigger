import flask
import os
import pytest
import yaml

from unittest import mock

import main


@pytest.fixture
def req():
    req = mock.MagicMock(spec=flask.Request)
    req.method = 'POST'
    req.remote_addr = '4.3.2.1'
    req.headers = { 'User-Agent': 'Bitbucket-Webhooks/2.0' }

    return req


@pytest.fixture
def push_repo_event(req):
    repo_push = open('tests/push_repo.json', 'r').read()
    req.get_data = mock.MagicMock(return_value=repo_push)
    req.headers['X-Event-Key'] = 'repo:push'

    return req


@pytest.fixture
def pullrequest_updated_event(req):
    pullrequest_updated = open('tests/pullrequest_updated.json', 'r').read()
    req.get_data = mock.MagicMock(return_value=pullrequest_updated)
    req.headers['X-Event-Key'] = 'pullrequest:updated'

    return req


@pytest.fixture
def env_vars(monkeypatch):
    monkeypatch.setenv('GCP_PROJECT', 'my-project')
    monkeypatch.setenv('BUCKET', 'my-bucket')


@pytest.fixture
def tmp_dir(mocker, tmpdir):
    config = {'steps': []}
    config_path = tmpdir.join('cloudbuild.yaml')
    yaml.dump(config, open(config_path, 'w'))

    tmp_dir = mock.Mock()
    tmp_dir.__enter__ = mock.Mock(return_value=tmpdir)
    tmp_dir.__exit__ = mock.Mock(return_value=False)
    mocker.patch('tempfile.TemporaryDirectory', return_value=tmp_dir)

    return tmpdir


@pytest.fixture
def uuid(mocker):
    mocker.patch('uuid.uuid1', return_value='1ccb32b0-77e5-4011-8e6d-106a02d10760')


@pytest.fixture
def patches(mocker):
    mocker.patch('main.upload')
    mocker.patch('main.submit')
    mocker.patch('main.git', create=True)


def test_push_repo(push_repo_event, env_vars, mocker, tmp_dir, uuid, patches):
    tarball = os.path.join(tmp_dir,
            'd2edcfc2b34ebd9244eaa4919aae28661366ca9b-1ccb32b0-77e5-4011-8e6d-106a02d10760.tar.gz')

    main.trigger(push_repo_event)

    main.git.clone.assert_called_with('--branch', 'feature/test-branch',
            '--depth=1', '--single-branch',
            'https://bitbucket.org/garman/test-repo', tmp_dir)

    main.git.archive.assert_called_with('-o', tarball, 'HEAD', _cwd=tmp_dir)
    main.upload.assert_called_with(tarball, 'my-bucket')
    main.submit.assert_called_with('my-project', {
        'source': {
            'bucket': 'my-bucket',
            'object': tarball
            },
        'steps': [],
        'substitutions': {
            'REPO_NAME': 'test-repo',
            'BRANCH_NAME': 'feature/test-branch',
            'REVISION_ID': 'd2edcfc2b34ebd9244eaa4919aae28661366ca9b',
            'COMMIT_SHA': 'd2edcfc2b34ebd9244eaa4919aae28661366ca9b',
            'SHORT_SHA': 'd2edcfc'
            }
        })


def test_pullrequest_updated(pullrequest_updated_event, env_vars, mocker, tmp_dir, uuid, patches):
    tarball = os.path.join(tmp_dir,
            '4d80f7a7d7bd-1ccb32b0-77e5-4011-8e6d-106a02d10760.tar.gz')

    main.trigger(pullrequest_updated_event)

    main.git.clone.assert_called_with('--branch', 'feature/test-branch',
            '--depth=1', '--single-branch',
            'https://bitbucket.org/garman/test-repo', tmp_dir)

    main.git.archive.assert_called_with('-o', tarball, 'HEAD', _cwd=tmp_dir)
    main.upload.asssert_called_with(tarball, 'my-bucket')
    main.submit.assert_called_with('my-project', {
        'source': {
            'bucket': 'my-bucket',
            'object': tarball
            },
        'steps': [],
        'substitutions': {
            'REPO_NAME': 'test-repo',
            'BRANCH_NAME': 'feature/test-branch',
            'REVISION_ID': '4d80f7a7d7bd',
            'COMMIT_SHA': '4d80f7a7d7bd',
            'SHORT_SHA': '4d80f7a'
            }
        })
