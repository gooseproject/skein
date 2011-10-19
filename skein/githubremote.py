import os
import sys
import re
import time
import tempfile
import subprocess

# GitPython
import git
from git.errors import InvalidGitRepositoryError, NoSuchPathError, GitCommandError

# settings, including lookaside uri and temporary paths
import skein_settings as sks
from pyskein import SkeinError

# github api and token should be kept secret
#import github_settings as ghs
from github2.client import Github

from gitremote import GitRemote


class GithubRemote(GitRemote):

    def __init__(self, cfgs, logger):
        self.name = 'GithubRemote'
        self.logger = logger
        self.cfgs = cfgs
        self.org = self.cfgs['github']['org']

    def __str__(self):
        return self.name

    def _login(self):

        return Github(username=self.cfgs['github']['username'], api_token=self.cfgs['github']['api_token'])

    def request_remote_repo(self, pkg, reason):

        self.logger.info("== Requesting github repository for '%s/%s' ==" % (self.org, pkg))

        # if the description isn't passed, open an editor for the user
        if not reason:
            editor = os.environ.get('EDITOR') if os.environ.get('EDITOR') else sks.editor

            tmp_file = tempfile.NamedTemporaryFile(suffix=".tmp")

            tmp_file.write(sks.initial_message)
            tmp_file.flush()

            cmd = [editor, tmp_file.name]
            p = subprocess.call(cmd)
            f = open(tmp_file.name, 'r')
            reason = f.read()[0:-1]

            if not reason:
                raise SkeinError("Description required.")

        try:
            github = self._login()

            for i in github.issues.list_by_label(self.cfgs['github']['issue_project'], 'new repo'):
                if i.title.lower().find(pkg) != -1:
                    print "Possible conflict with package: '%s'" % i.title
                    print "%s/%s/%s/%d." % (self.cfgs['github']['url'], self.cfgs['github']['issue_project'], self.cfgs['github']['issues_uri'], i.number)
                    raise SkeinError("Please file this request at %s/%s/%s if you are sure this is not a conflict."
                            % (self.cfgs['github']['url'], self.cfgs['github']['issue_project'], self.cfgs['github']['issues_uri'] ))

            req = github.issues.open(u"%s" % self.cfgs['github']['issue_project'], self.cfgs['github']['issue_title'] % pkg, reason)
            github.issues.add_label(u"%s" % (self.cfgs['github']['issue_project']), req.number, self.cfgs['github']['new_repo_issue_label'])

            if req:
                print "Issue %d created for new repo: %s." % (req.number, pkg)
                print "Visit https://github.com/%s/issues/%d to assign or view the issue." % (self.cfgs['github']['issue_project'], req.number)

            self.logger.info("  Request for '%s/%s' complete" % (self.org, pkg))
        except RuntimeError, e:
            # assume repo already exists if this is thrown
            self.logger.debug("  error: %s" %e)

    def search_repo_requests(self, state='open'):
        self.logger.info("== Searching %s github repository requests from '%s' ==" % (state, self.org))

        newrepo = []
        try:
            github = self._login()
            issues = github.issues.list(self.cfgs['github']['issue_project'])

            [newrepo.append(i) for i in issues if 'new repo' in i.labels]
            self.logger.info("  Grabbed %d new repo requests" % (len(newrepo)))
        except RuntimeError, e:
            # assume repo already exists if this is thrown
            self.logger.debug("  github error: %s" %e)

        print u"#\tDescription\t\tRequestor\tURL"
        print u"---------------------------------------------------"
        for r in newrepo:
            print u"%d\t%s\t\t%s\t\t%s/%s/%s/%d" % ( r.number, r.title[:25], r.user, self.cfgs['github']['url'], self.cfgs['github']['issue_project'], self.cfgs['github']['issues_uri'], r.number)
        print
    
    def create_remote_repo(self):
        self.logger.info("== Creating github repository '%s/%s' ==" % (self.org, self.name))
        try:
            github = self._login()
            repo = github.repos.create(u"%s/%s" % (self.org, self.name), self.summary, self.url)
            for team in ghs.repo_teams:
                github.teams.add_project(team, u"%s/%s" % (self.org, self.name))

            self.logger.info("  Remote '%s/%s' created" % (self.org, repo.name))
        except RuntimeError, e:
            # assume repo already exists if this is thrown
            self.logger.debug("  github error: %s" %e)
            self.logger.info("  Remote '%s/%s' already exists" % (self.org, self.name))
            #print str(e.message)
            pass

