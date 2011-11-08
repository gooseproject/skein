import os
import sys
import re
import time

class GitRemote():

    def __init__(self, remote_class, cfgs, logger):
        self.name = 'GitRemote'
        self.remote = remote_class(cfgs, logger)

    def __str__(self):
        return self.name

    def request_remote_repo(self, name, reason):
        return self.remote.request_remote_repo(name, reason)

    def search_repo_requests(self, state='open'):
        return self.remote.search_repo_requests(state)

    def show_request_by_id(self, request_id):
        return self.remote.show_request_by_id(request_id)

    def create_remote_repo(self, name, summary, url):
        return self.remote.create_remote_repo(name, summary, url)

    def create_team(self, name, permission, repos):
        return self.remote.create_team(name, permission, repos)

    def close_repo_request(self, request_id, name):
        return self.remote.close_repo_request(request_id, name)
