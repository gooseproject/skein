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
from pyskein import SkeinError

# github api and token should be kept secret
from github2.client import Github
from github2.request import HttpError

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

    def _request_by_editor(self, name):
        """ Set request values with the EDITOR value

        :param str name: repository name
        """

        reason = None
        editor = os.environ.get('EDITOR') if os.environ.get('EDITOR') else self.cfgs['skein']['editor']

        tmp_file = tempfile.NamedTemporaryFile(suffix=".tmp")

        initial_message = "%s\n====\n%s\n%s\n%s\n====\n" % (self.cfgs['github']['reason_default'], self.cfgs['github']['summary_default'], self.cfgs['github']['url_default'], self.cfgs['github']['branches_default'])

        tmp_file.write(initial_message)
        tmp_file.flush()

        cmd = [editor, tmp_file.name]

        try:
            p = subprocess.check_call(cmd)
            f = open(tmp_file.name, 'r')
            reason = f.read()

            if not reason:
                raise SkeinError("Description required.")
            elif reason == initial_message:
                raise SkeinError("Description has not changed.")

        except subprocess.CalledProcessError:
            raise SkeinError("Action cancelled by user.")
#         elif summary and not url:

        self.logger.info("== Requesting github repository for '%s/%s' ==" % (self.org, name))

    def _request_from_srpm(self, summary, url, force):
        """ Request a new github repository with values from an srpm

        :param str summary: repository summary
        :param str url: repository url
        :param str force: don't prompt
        """

        if not force:
            print "\nSummary: %s\nURL: %s\n" % (summary, url)
            valid = 'n'
            valid = raw_input("Is the above information correct? (y/N) ")
        else:
            valid = 'y'

        if valid.lower() == 'y':
            initial_message = "%s\n====\n%s\n%s\n%s\n====" % (self.cfgs['github']['request_reason'], self.cfgs['github']['request_summary'], self.cfgs['github']['request_url'], self.cfgs['github']['branches_default'])

        return initial_message % (summary, url)

    def request_repo(self, name, summary=False, url=False, force=False):
        """ Request a new github repository

        :param str name: repository name
        """

        if not summary or not url:
            reason = self._request_by_editor(name)
        elif summary and url:
            reason = self._request_from_srpm(summary, url, force)
        #    print "SRPM initial message:\n\n%s" % reason
        elif not summary:
            raise SkeinError("Missing summary.")
        elif not url:
            raise SkeinError("Missing url.")

        try:
            issues = self.github.issues.list(self.cfgs['github']['issue_project'], state='open')
            for i in issues:
#            for i in self.github.issues.list_by_label(self.cfgs['github']['issue_project'], self.cfgs['github']['new_repo_issue_label']):
#                print "Title: %s | Name: %s | State: %s" % (i.title.lower(), name, i.state)
                if i.title.lower().find(name) != -1:
                    print "Possible conflict with package: '%s'" % i.title
                    print "%s/%s/%s/%d." % (self.cfgs['github']['url'], self.cfgs['github']['issue_project'], self.cfgs['github']['issues_uri'], i.number)
                    raise SkeinError("Please file this request at %s/%s/%s if you are sure this is not a conflict."
                            % (self.cfgs['github']['url'], self.cfgs['github']['issue_project'], self.cfgs['github']['issues_uri'] ))

            req = self.github.issues.open(self.cfgs['github']['issue_project'], self.cfgs['github']['issue_title'] % name, reason)
            self.github.issues.add_label(self.cfgs['github']['issue_project'], req.number, self.cfgs['github']['new_repo_issue_label'])

            if req:
                print "Issue %d created for new repo: %s." % (req.number, name)
                print "Visit https://github.com/%s/issues/%d to assign or view the issue." % (self.cfgs['github']['issue_project'], req.number)

            self.logger.info("  Request for '%s/%s' complete" % (self.org, name))
        except RuntimeError, e:
            # assume repo already exists if this is thrown
            self.logger.debug("  error: %s" %e)

    def search_repo_requests(self, state='open'):
        self.logger.info("== Searching '%s' github repository requests from '%s' ==" % (state, self.cfgs['github']['issue_project']))

        newrepo = []
        try:
            issues = self.github.issues.list(self.cfgs['github']['issue_project'], state=state)

            [newrepo.append(i) for i in issues if self.cfgs['github']['new_repo_issue_label'] in i.labels]
            self.logger.info("  Grabbed %d new repo requests" % (len(newrepo)))
        except RuntimeError, e:
            # assume repo already exists if this is thrown
            self.logger.debug("  github error: %s" %e)

        print u"#\tDescription\t\t\t\t\tRequestor\tURL"
        print u"-----------------------------------------------------------------------------"

        for r in newrepo:
            print u"%d\t%s\t\t%s\t\t%s/%s/%s/%d" % ( r.number, r.title.ljust(35), r.user, self.cfgs['github']['url'], self.cfgs['github']['issue_project'], self.cfgs['github']['issues_uri'], r.number)

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
            raise SkeinError("Request %d doesn't exist for %s" % (request_id, self.cfgs['github']['issue_project']))

    def create_remote_repo(self, name, summary, url):
        self.logger.info("== Creating github repository '%s/%s' ==" % (self.org, name))

        try:
            repo = self.github.repos.create(u"%s/%s" % (self.org, name.encode('utf-8')), summary.encode('utf-8'), url.encode('utf-8'))
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
    
    def revoke_repo_request(self, request_id, name):
        self.logger.info("== Revoking github repository request '%s/%s' ==" % (self.org, name))

        try:
            self.github.issues.add_label(self.cfgs['github']['issue_project'], request_id, self.cfgs['github']['revoked_repo_issue_label'])
            self.github.issues.remove_label(u"%s" % (self.cfgs['github']['issue_project']), request_id, self.cfgs['github']['new_repo_issue_label'])
            self.github.issues.comment(self.cfgs['github']['issue_project'], request_id, self.cfgs['github']['revoking_comment_text'] % name)
            self.github.issues.close(self.cfgs['github']['issue_project'], request_id)
        except (KeyError, RuntimeError) as e:
            self.logger.debug("  github error: %s" %e)
            print "Ticket id '%s' could not be closed automatically, please close by hand" % request_id

    def create_team(self, name, permission, githubowner, repos):
        self.logger.info("== Creating github team '%s' ==" % name)

        team = None
        team_exists = False
        if not githubowner:
            githubowner = self.cfgs['github']['username']

        try:
            value = self.github.organizations.add_team(self.org, name, permission, repos)
            team = value['team']
            self.logger.info("  Team '%s' created with id: '%s'" % (team['name'], team['id']))
            print "Team '%s' created with id: '%s'" % (team['name'], team['id'])
            team_exists = True
        except (KeyError, RuntimeError) as e:
            # assume team already exists if this is thrown
            self.logger.debug("  github error: %s" %e)
            self.logger.info("  Team '%s' already exists" % name)
            print "Team '%s' already exists, skipping" % name

        if not team:
            self.logger.info("  Checking to see if team '%s' exists" % name)
            teams = self.github.organizations.teams(self.cfgs['github']['org'])
            for t in teams:
                if t['name'] == name:
                    team = t
                    team_exists = True
                    break

        if team_exists:
            try:
                self.logger.info("  Adding '%s' to '%s' " % (githubowner, name))
                self.github.teams.add_member(team['id'], githubowner)
                print "Added '%s' to team '%s'" % (githubowner, name)
            except (KeyError, RuntimeError) as e:
                # assume team already exists if this is thrown
                self.logger.debug("  github error: %s" %e)
                self.logger.info("  %s' is already a member of '%s', skipping" % (githubowner, team['name']))
                print "'%s' is already a member of '%s', skipping" % (githubowner, team['name'])
        else:
            raise SkeinError("Team '%s' does not exists, check skein.log for more information" % name)

    def request_is_open(self, request_id):
        return self.github.issues.show(self.cfgs['github']['issue_project'], request_id).state == 'open'

    def close_repo_request(self, request_id, name):

        try:
            self.github.issues.comment(self.cfgs['github']['issue_project'], request_id, self.cfgs['github']['closing_comment_text'] % name)
            self.github.issues.close(self.cfgs['github']['issue_project'], request_id)
        except (KeyError, RuntimeError) as e:
            self.logger.debug("  github error: %s" %e)
            print "Ticket id '%s' could not be closed automatically, please close by hand" % request_id

    def get_scm_url(self, name):
        return "%s/%s.git" % (self.cfgs['github']['remote_base'], name)

    def repo_info(self, name):
        """ Get information about a selected repository

        :param str name: repository name
        """

        try:
            repo = self.github.repos.show("%s/%s" % (self.cfgs['github']['org'], name))
            return { 'description': repo.description, 'homepage': repo.homepage, 'url': repo.url, 'created_time': repo.created_at }
        except HttpError:
            raise SkeinError("Unable to locate repository for '%s' at '%s'" % (name, self.cfgs['github']['org']))

