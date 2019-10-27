import json


def create_event_from_request(req):
    data = req.get_data()
    key = req.headers['X-Event-Key']

    if key == 'repo:push':
        return PushRepoEvent(data)
    elif key == 'pullrequest:updated':
        return PullRequestUpdatedEvent(data)
    else:
        print(RuntimeError('Ignoring webhook event'))
        return


class IrrelevantEvent(Exception):
    pass


class Event:
    def __init__(self, data):
        self.data = json.loads(data)


    def validate(self, headers):
        return headers['User-Agent'] == 'Bitbucket-Webhooks/2.0'


    @property
    def repo(self):
        return self.data['repository']['name']


    @property
    def clone_url(self):
        return self.data['repository']['links']['html']['href']


class PushRepoEvent(Event):
    @property
    def commit(self):
        return self.data['push']['changes'][0]['commits'][0]['hash']


    @property
    def branch(self):
        return self.data['push']['changes'][0]['new']['name']


class PullRequestUpdatedEvent(Event):
    @property
    def full_name(self):
        return self.data['pullrequest']['source']['repository']['full_name']


    @property
    def commit(self):
        return self.data['pullrequest']['source']['commit']['hash']


    @property
    def branch(self):
        return self.data['pullrequest']['source']['branch']['name']


