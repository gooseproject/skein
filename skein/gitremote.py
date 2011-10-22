import os
import sys
import re
import time

# GitPython
import git
from git.errors import InvalidGitRepositoryError, NoSuchPathError, GitCommandError

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
