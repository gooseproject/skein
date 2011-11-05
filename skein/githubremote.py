import os
import sys
import re
import time
import tempfile
import subprocess

# GitPython
import git
from git import InvalidGitRepositoryError, NoSuchPathError, GitCommandError

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
        self.github = self._login()

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

            tmp_file.write(self.cfgs['github']['initial_message'])
            tmp_file.flush()

            cmd = [editor, tmp_file.name]

            try:
                p = subprocess.check_call(cmd)
                f = open(tmp_file.name, 'r')
                reason = f.read()

#                print "r: %s" % reason
#                print "i: %s" % self.cfgs['github']['initial_message']

                if not reason:
                    raise SkeinError("Description required.")
                elif reason == self.cfgs['github']['initial_message']:
                    raise SkeinError("Description has not changed.")

            except subprocess.CalledProcessError:
                raise SkeinError("Action cancelled by user.")

        try:

            for i in self.github.issues.list_by_label(self.cfgs['github']['issue_project'], 'new repo'):
                if i.title.lower().find(pkg) != -1:
                    print "Possible conflict with package: '%s'" % i.title
                    print "%s/%s/%s/%d." % (self.cfgs['github']['url'], self.cfgs['github']['issue_project'], self.cfgs['github']['issues_uri'], i.number)
                    raise SkeinError("Please file this request at %s/%s/%s if you are sure this is not a conflict."
                            % (self.cfgs['github']['url'], self.cfgs['github']['issue_project'], self.cfgs['github']['issues_uri'] ))

            req = self.github.issues.open(u"%s" % self.cfgs['github']['issue_project'], self.cfgs['github']['issue_title'] % pkg, reason)
            self.github.issues.add_label(u"%s" % (self.cfgs['github']['issue_project']), req.number, self.cfgs['github']['new_repo_issue_label'])

            if req:
                print "Issue %d created for new repo: %s." % (req.number, pkg)
                print "Visit https://github.com/%s/issues/%d to assign or view the issue." % (self.cfgs['github']['issue_project'], req.number)

            self.logger.info("  Request for '%s/%s' complete" % (self.org, pkg))
        except RuntimeError, e:
            # assume repo already exists if this is thrown
            self.logger.debug("  error: %s" %e)

    def search_repo_requests(self, state='open'):
        self.logger.info("== Searching '%s' github repository requests from '%s' ==" % (state, self.org))

        newrepo = []
        try:
            issues = self.github.issues.list(self.cfgs['github']['issue_project'], state=state)

            [newrepo.append(i) for i in issues if 'new repo' in i.labels]
            self.logger.info("  Grabbed %d new repo requests" % (len(newrepo)))
        except RuntimeError, e:
            # assume repo already exists if this is thrown
            self.logger.debug("  github error: %s" %e)

        print u"#\tDescription\t\t\t\tRequestor\tURL"
        print u"-------------------------------------------------------------------"
        for r in newrepo:
            print u"%d\t%s\t\t%s\t\t%s/%s/%s/%d" % ( r.number, r.title.ljust(25), r.user, self.cfgs['github']['url'], self.cfgs['github']['issue_project'], self.cfgs['github']['issues_uri'], r.number)
        print

    def _get_request_detail(self, request):

        details = []

        title = request.title
        details.append(title[title.find(":")+1:].strip())

        lines = request.body.split('\n')

        for l in lines:
            if l.lower().startswith("summary:") or l.lower().startswith("package description:"):
                details.append(l[l.find(":")+1:].strip())
            if l.lower().startswith("url:") or l.lower().startswith("upstream url:"):
                details.append(l[l.find(":")+1:].strip())

        details.append(request.user)

        return details

    def show_request_by_id(self, request_id):
        try:
            request = self.github.issues.show(self.cfgs['github']['issue_project'], request_id)

            return self._get_request_detail(request)

        except RuntimeError, e:
            # assume repo already exists if this is thrown
            self.logger.debug("  github error: %s" %e)
            raise SkeinError("Request %s doesn't exist for %s" % (request_id, self.cfgs['github']['issue_project']))
    
    def create_remote_repo(self, name, summary, url):
        self.logger.info("== Creating github repository '%s/%s' ==" % (self.org, name))

        try:
            repo = self.github.repos.create(u"%s/%s" % (self.org, name), summary, url)
        except (KeyError, RuntimeError) as e:
            # assume repo already exists if this is thrown
            self.logger.debug("  github error: %s" %e)
            self.logger.info("  Remote '%s/%s' already exists" % (self.org, name))
            print "Remote repo '%s/%s' already exists, skipping" % (self.org, name)

        try:
            for team in self.cfgs['github']['repo_teams'].split(","):
                self.github.teams.add_project(team.strip(), u"%s/%s" % (self.org, name))

        except RuntimeError, e:
            # assume repo already exists if this is thrown
            self.logger.debug("  couldn't add teams: %s" %e)
            print "Couldn't add teams to '%s/%s'" % (self.org, name)

        self.logger.info("  Remote '%s/%s' created" % (self.org, name))

    def create_team(self, name, permission, repos):

        try:
            value = self.github.organizations.add_team(self.org, name, permission, repos)
            team = value['team']
            self.logger.info("  Team '%s' created with id: '%s'" % (team['name'], team['id']))
        except (KeyError, RuntimeError) as e:
            # assume team already exists if this is thrown
            self.logger.debug("  github error: %s" %e)
            self.logger.info("  Team '%s' already exists" % name)
            print "Team '%s' already exists, skipping" % name

    def close_repo_request(self, request_id, name):

        try:
            self.github.issues.comment(self.cfgs['github']['issue_project'], request_id, self.cfgs['github']['closing_comment_text'] % name)
            self.github.issues.close(self.cfgs['github']['issue_project'], request_id)
        except (KeyError, RuntimeError) as e:
            self.logger.debug("  github error: %s" %e)
            print "Ticket id '%s' could not be closed automatically, please close by hand" % request_id


