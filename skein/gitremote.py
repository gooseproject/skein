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

    def request_remote_repo(self, name):
        return self.remote.request_remote_repo(name)

    def search_repo_requests(self, state='open'):
        return self.remote.search_repo_requests(state)

    def show_request_by_id(self, request_id):
        return self.remote.show_request_by_id(request_id)

    def create_remote_repo(self, name, summary, url):
        return self.remote.create_remote_repo(name, summary, url)

    def create_team(self, name, permission, gitowner, repos):
        return self.remote.create_team(name, permission, gitowner, repos)

    def request_is_open(self, request_id):
        return self.remote.request_is_open(request_id)

    def close_repo_request(self, request_id, name):
        return self.remote.close_repo_request(request_id, name)

    def get_scm_url(self, name):
        return self.remote.get_scm_url(name)

    def revoke_repo_request(self, request_id, name):
        return self.remote.revoke_repo_request(request_id, name)
