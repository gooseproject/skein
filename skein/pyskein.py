# Main class for pycamps

import os
import re
import sys
import rpm
import time
import glob
import stat
import shutil
import hashlib
import logging
import tempfile
import argparse
import subprocess
import ConfigParser

from urllib2 import HTTPError

import koji
import xmlrpclib

# GitPython
import git
from git import InvalidGitRepositoryError, NoSuchPathError, GitCommandError

# settings, including lookaside uri and temporary paths
from gitremote import GitRemote

class SkeinError(Exception):

    def __init__(self, value):
        self.value = value

    def __str__(self):
        repr(self.value)

# Add a class stolen from /usr/bin/koji to watch tasks
# this was cut/pasted from koji, and then modified for local use.
# The formatting is koji style, not the stile of this file.  Do not use these
# functions as a style guide.
# This is fragile and hopefully will be replaced by a real kojiclient lib.
class TaskWatcher(object):

    def __init__(self,task_id,session,level=0,quiet=False):
        self.id = task_id
        self.session = session
        self.info = None
        self.level = level
        self.quiet = quiet
        self.logger = logging.getLogger('skein')

    #XXX - a bunch of this stuff needs to adapt to different tasks

    def str(self):
        if self.info:
            label = koji.taskLabel(self.info)
            return "%s%d %s" % ('  ' * self.level, self.id, label)
        else:
            return "%s%d" % ('  ' * self.level, self.id)

    def __str__(self):
        return self.str()

    def get_failure(self):
        """Print infomation about task completion"""
        if self.info['state'] != koji.TASK_STATES['FAILED']:
            return ''
        error = None
        try:
            result = self.session.getTaskResult(self.id)
        except (xmlrpclib.Fault,koji.GenericError),e:
            error = e
        if error is None:
            # print "%s: complete" % self.str()
            # We already reported this task as complete in update()
            return ''
        else:
            return '%s: %s' % (error.__class__.__name__, str(error).strip())

    def update(self):
        """Update info and log if needed.  Returns True on state change."""
        if self.is_done():
            # Already done, nothing else to report
            return False
        last = self.info
        self.info = self.session.getTaskInfo(self.id, request=True)
        if self.info is None:
            self.logger.error("No such task id: %i" % self.id)
            print "No such task id: %i" % self.id
            sys.exit(1)
        state = self.info['state']
        if last:
            #compare and note status changes
            laststate = last['state']
            if laststate != state:
                msg = "%s: %s -> %s" % (self.str(), self.display_state(last), self.display_state(self.info))
                self.logger.info(msg)
                print msg
                return True
            return False
        else:
            # First time we're seeing this task, so just show the current state
            self.logger.info("%s: %s" % (self.str(), self.display_state(self.info)))
            print "%s: %s" % (self.str(), self.display_state(self.info))
            return False

    def is_done(self):
        if self.info is None:
            return False
        state = koji.TASK_STATES[self.info['state']]
        return (state in ['CLOSED','CANCELED','FAILED'])

    def is_success(self):
        if self.info is None:
            return False
        state = koji.TASK_STATES[self.info['state']]
        return (state == 'CLOSED')

    def display_state(self, info):
        # We can sometimes be passed a task that is not yet open, but
        # not finished either.  info would be none.
        if not info:
            return 'unknown'
        if info['state'] == koji.TASK_STATES['OPEN']:
            if info['host_id']:
                host = self.session.getHost(info['host_id'])
                return 'open (%s)' % host['name']
            else:
                return 'open'
        elif info['state'] == koji.TASK_STATES['FAILED']:
            return 'FAILED: %s' % self.get_failure()
        else:
            return koji.TASK_STATES[info['state']].lower()

class PySkein:
    """
    Support class for skein. Does single and mass imports, upload, verify, sources, 
    generate makefiles and more for the goose linux rebuilds.
    """

    def __init__(self):
        """Constructor for skein, will create self.cfgs and self.logger
        """

        self.username = None
        self.cfgs = {}

        for path in ['/etc/skein', '~/.skein']:
            expanded_path = "%s/%s" % (os.path.expanduser(path), 'skein.cfg')
            if os.path.exists(expanded_path):
                self._load_config(expanded_path)

        self._makedir(self.cfgs['skein']['install_root'])

        # create logger with 'spam_application'
        self.logger = logging.getLogger('skein')
        self.logger.setLevel(eval(self.cfgs['logger']['loglevel']))

        # create file handler which logs even debug messages
        fh = logging.FileHandler(self.cfgs['logger']['file'])
        fh.setLevel(eval(self.cfgs['logger']['loglevel']))

        # create formatter and add it to the handlers
        formatter = logging.Formatter(self.cfgs['logger']['format'])
        fh.setFormatter(formatter)
        # add the handlers to the logger
        self.logger.addHandler(fh)

    def _load_config(self, path):
        """Constructor for skein, will create self.cfgs and self.logger

        :param str path: skein.cfg path
        """

        config = ConfigParser.SafeConfigParser()
        try:
            f = open(path)
            config.readfp(f)
            f.close()
        except ConfigParser.InterpolationSyntaxError as e:
            raise SkeinError("Unable to parse configuration file properly: %s" % e)

        for section in config.sections():
            if not self.cfgs.has_key(section):
                self.cfgs[section] = {}

            for k, v in config.items(section):
                self.cfgs[section][k] = v

    def _makedir(self, target, perms=0775):
        """Make a directory, possibly with specific permissions

        :param str target: directory to create
        :param int perms: mode of directory
        """

        if not os.path.isdir(u"%s" % (target)):
            os.makedirs(u"%s" % (target), perms)

    def _init_koji(self, user=None, kojiconfig=None, url=None):
        """Initiate a koji session.  This function attempts to log in and returns nothing or raises.

        :param str srpm: path to the source RPM (SRPM)
        :param str user: User to log into koji (if no user, no login)
        :param str kojiconfig: Use an alternate koji config file
        """

        # Code from /usr/bin/koji. Should be in a library!
        defaults = {
                    'server' : 'http://localhost/kojihub',
                    'weburl' : 'http://localhost/koji',
                    'pkgurl' : 'http://localhost/packages',
                    'topdir' : '/mnt/koji',
                    'cert': '~/.koji/client.crt',
                    'ca': '~/.koji/clientca.crt',
                    'serverca': '~/.koji/serverca.crt',
                    'authtype': None
                    }
        # Process the configs in order, global, user, then any option passed
        configs = ['/etc/koji.conf', os.path.expanduser('~/.koji/config')]
        if kojiconfig:
            configs.append(os.path.join(kojiconfig))
        for configFile in configs:
            if os.access(configFile, os.F_OK):
                f = open(configFile)
                config = ConfigParser.ConfigParser()
                config.readfp(f)
                f.close()
                if config.has_section('koji'):
                    for name, value in config.items('koji'):
                        if defaults.has_key(name):
                            defaults[name] = value
        # Expand out the directory options
        for name in ('topdir', 'cert', 'ca', 'serverca'):
            defaults[name] = os.path.expanduser(defaults[name])
        session_opts = {'user': user}
        # We assign the kojisession to our self as it can be used later to
        # watch the tasks.
        self.logger.debug('Initiating a koji session to %s' % defaults['server'])
        try:
            if user:
                self.kojisession = koji.ClientSession(defaults['server'],
                                                      session_opts)

                self.logger.debug('Logged into a koji session to %s as %s' % (defaults['server'], user ))
            else:
                self.kojisession = koji.ClientSession(defaults['server'])
        except:
            raise SkeinError('Could not initiate koji session')
        # save the weburl for later use too
        self.kojiweburl = defaults['weburl']
        self.logger.debug('Kojiweb URL: %s' % self.kojiweburl)
        # log in using ssl
        if user:
            try:
                self.kojisession.ssl_login(defaults['cert'], defaults['ca'],
                                           defaults['serverca'])
            except Exception as e:
                raise SkeinError("Opening a SSL connection failed: '%s'" % e)
            if not self.kojisession.logged_in:
                raise SkeinError('Could not auth with koji as %s' % user)
        return self.kojisession

    # grab the details from the rpm and add them to the object
    def _set_srpm_details(self, srpm):
        """Gather details from the SRPM

        :param str srpm: path to the source RPM (SRPM)
        """

        self.logger.info("== Querying srpm ==")
        print "Querying srpm"
        ts = rpm.ts()
        ts.setVSFlags(rpm._RPMVSF_NOSIGNATURES)

        fdno = open(u"%s" % srpm, 'r')
        try:
            hdr = ts.hdrFromFdno(fdno)
        except rpm.error, e:
            if str(e) == "public key not available":
                print str(e)
        fdno.close()

        self.rpminfo = {}
        self.logger.info("  Setting srpm name ==")
        self.rpminfo['name'] = hdr[rpm.RPMTAG_NAME]
        self.logger.info("  Setting srpm version ==")
        self.rpminfo['version'] = hdr[rpm.RPMTAG_VERSION]
        self.logger.info("  Setting srpm release ==")
        self.rpminfo['release'] = hdr[rpm.RPMTAG_RELEASE]
        self.logger.info("  Setting srpm sources ==")

        # some sources use %{name} and %{version}
        srcs = hdr[rpm.RPMTAG_SOURCE]
        sources = []

        for src in srcs:
            source = src.replace('%{name}', self.rpminfo['name'])
            source = source.replace('%{version}', self.rpminfo['version'])
            sources.append(source)

        self.rpminfo['sources'] = sources

        self.logger.info("  Setting srpm patches ==")
        patches = []
        for patch in hdr[rpm.RPMTAG_PATCH]:
            patches.append(patch.replace('%{name}', self.rpminfo['name']))
        self.rpminfo['patches'] = patches
#        self.patches = hdr[rpm.RPMTAG_PATCH].replace('%{name}', self.name)
        self.logger.info("  Setting srpm summary ==")
        self.rpminfo['summary'] = hdr[rpm.RPMTAG_SUMMARY]
        self.logger.info("  Setting srpm url ==")
        self.rpminfo['url'] = hdr[rpm.RPMTAG_URL]
        self.logger.info("  Setting srpm requires ==")
        # note to self, the [:-2] strips off the rpmlib(FileDigests)' and 
        #'rpmlib(CompressedFileNames)' which are provided by the 'rpm' rpm
        self.rpminfo['buildrequires'] = hdr[rpm.RPMTAG_REQUIRES]

    # install the srpm in a temporary directory
    def _install_srpm(self, srpm):
        """Prepare SRPM to be extracted by installing in a temporary location

        :param str srpm: path to srpm
        """

        # rpm.ts is an alias for rpm.TransactionSet
        self.logger.info("== Installing srpm ==")
        print "Installing srpm"

        self._makedir(u"%s/%s" % (self.cfgs['skein']['install_root'], self.rpminfo['name']))

        self.logger.info("  installing %s into %s/%s" % (srpm, self.cfgs['skein']['install_root'], self.rpminfo['name']))
        devnull = open('/dev/null', 'w')
        args = ["/bin/rpm", "-i", "--root=%s/%s" % (self.cfgs['skein']['install_root'], self.rpminfo['name']), srpm]
        p = subprocess.check_call(args, stdout = devnull, stderr = devnull )

    def _extract_srpm(self, sources_dest, git_dest):
        """Extract files from a source rpm (SRPM)

        :param str source_dest: path to specific source location, where to put the source file(s)
        :param str git_dest: path to git repo, patch file, spec file and other non-archive sources 
        """

        self.logger.info("== Copying sources ==")
        print("Copying sources")

        sources_path = "%s/%s%s/rpmbuild/SOURCES" % (self.cfgs['skein']['install_root'], self.rpminfo['name'], self.cfgs['skein']['home'])
        spec_path = "%s/%s%s/rpmbuild/SPECS/*.spec" % (self.cfgs['skein']['install_root'], self.rpminfo['name'], self.cfgs['skein']['home'])

        source_exts = self.cfgs['skein']['source_exts'].split(',')

        # copy the spec, patches, etc.
        files = glob.glob(spec_path)

        for f in files:
            self.logger.info("  copying '%s' to '%s'" % (os.path.basename(f), git_dest))
            shutil.copy2(f, git_dest)

        for source in self.rpminfo['sources']:
            src = "%s/%s" % (sources_path, source)

            if src.rsplit('.')[-1] in source_exts:
                self.logger.info("  copying '%s' to '%s'" % (source, sources_dest))
                shutil.copy2("%s/%s" % (sources_path, source), sources_dest)
            else:
                self.logger.info("  copying '%s' to '%s'" % (source, git_dest))
                shutil.copy2("%s/%s" % (sources_path, source), git_dest)

        # copy the patch files
        for source in self.rpminfo['patches']:
            self.logger.info("  copying '%s' to '%s'" % (source, git_dest))
            shutil.copy2("%s/%s" % (sources_path, source), git_dest)

    # this method assumes the sources are new and overwrites the 'sources' file in the git repository
    def _generate_sha256(self, sources_dest, git_dest):
        """Generate a sha256sum for each legitimate source file

        :param str source_dest: path to specific source location
        :param str git_dest: path to git repo, sources file is placed there with sums and filenames
        """

        self.logger.info("== Generating sha256sum for sources ==")
        print "Generating sha256sum for sources"

        source_exts = self.cfgs['skein']['source_exts'].split(',')
        sfile = open(u"%s/sources" % git_dest, 'w+')

        for src in self.rpminfo['sources']:

            if src.rsplit('.')[-1] in source_exts:
                sha256sum = hashlib.sha256(open("%s/%s" % (sources_dest, src), 'rb').read()).hexdigest()
                sfile.write("%s *%s\n" % (sha256sum, src))

        sfile.close()

        self.logger.info("  sha256sums generated and added to %s/sources" % git_dest)

    def _init_git_repo(self, repo_dir, name, branch=None):
        """Create a git repository pointing to appropriate github repo

        :param str repo_dir: full path to existing or potential repo
        :param str name: name of package/repo
        """

        self.logger.info("== Using local git repository at '%s' ==" % repo_dir)
        print "Using local git repository at '%s'" % repo_dir

        self._init_git_remote()
        scm_url = self.gitremote.get_scm_url(name)

        try:
            self.repo = git.Repo(repo_dir)
        except NoSuchPathError as e:
            raise SkeinError("Path '%s' does not exist" % e)
        except InvalidGitRepositoryError as e:
            gitrepo = git.Git(repo_dir)
            cmd = ['git', 'init']
            result = git.Git.execute(gitrepo, cmd)
            self.repo = git.Repo(repo_dir)
        try:
            print("  Setting origin to '%s'" % scm_url)
            self.logger.info("  Setting origin to '%s'" % scm_url)
            self.repo.create_remote('origin', scm_url)
        except (AssertionError, GitCommandError) as e:
            print("repo remote 'origin' already exists, skipping")
            self.logger.info("repo remote 'origin' already exists, skipping")
            self.logger.debug("--- Exception thrown %s" % e)

        if branch:
            print ("performing origin.pull('master') on {0}".format(name))
            self.repo.remotes.origin.pull('master')
            try:
                print ('performing origin.update of {0}'.format(name))
                self.repo.remotes.origin.update()
            except GitCommandError as e:
                print("update() failed: '{0}'".format(e))
                self.logger.debug("update() failed: '{0}'".format(e))
                raise


    # attribution to fedpkg, written by 'Jesse Keating' <jkeating@redhat.com> for this snippet
    def _update_gitignore(self, path):

        self.logger.info("  Updating .gitignore with sources")
        gitignore_file = open("%s/%s" % (path, '.gitignore'), 'w')
        source_exts = self.cfgs['skein']['source_exts'].split(',')
        for src in self.rpminfo['sources']:

            if src.rsplit('.')[-1] in source_exts:
                self.logger.info("  writing '%s' to .gitignore" % src)
                gitignore_file.write("%s\n" % src)

        gitignore_file.close()

    # search for a makefile.tpl in the makefile_path and use
    # it as a template to put in each package's repository
    def _do_makefile(self, dest_path):
        self.logger.info("  Updating Makefile")
        found = False
        for path in self.cfgs['skein']['path'].split(':'):
            expanded_path = "%s/%s" % (os.path.expanduser(path), self.cfgs['makefile']['name'])
#            print "expanded_path: %s" % expanded_path
            if os.path.exists(expanded_path):
                makefile_template = expanded_path
                found = True
                break

        if not found:
            self.logger.error("'%s' not found in path '%s', please adjust skein.cfg" % (self.cfgs['makefile']['name'], self.cfgs['skein']['path']))
            raise SkeinError("'%s' not found in path '%s', please adjust skein.cfg" % (self.cfgs['makefile']['name'], self.cfgs['skein']['path']))

#        print "makefile template found at %s" % makefile_template

        src_makefile = open(makefile_template)
        dst_makefile = open("%s/Makefile" % dest_path, 'w')

        dst_makefile.write( src_makefile.read() % {'name': self.rpminfo['name']})
        dst_makefile.close()

    def _upload_source(self, name):

        self.logger.info("== Uploading Source(s) ==")
        source_dir = "%s/%s/%s" % (self.cfgs['skein']['proj_dir'], name, self.cfgs['skein']['lookaside_dir'])
        lookaside_host = self.cfgs['lookaside']['host']
        source_exts = self.cfgs['skein']['source_exts'].split(',')

        os.chdir(source_dir)
        uploaded = False

        for src in os.listdir(os.path.expanduser(source_dir)):
            if src.rsplit('.')[-1] in source_exts:
                self.logger.info("  uploading '%s/%s' to '%s'" % (source_dir, src, lookaside_host))
                print "uploading '%s' to '%s'" % (src, lookaside_host)

                args = ["/usr/bin/rsync", "--progress", "-loDtRz", "-e", "ssh", "%s" % src, "%s@%s:%s/%s/" % ( self.cfgs['lookaside']['user'], lookaside_host, self.cfgs['lookaside']['remote_dir'], name)]
                p = subprocess.call(args, cwd="%s" % (source_dir), stdout = subprocess.PIPE)
                uploaded = True

        if not uploaded:
            self.logger.info("  nothing to upload for '%s'" % name)
            print "nothing to upload for '%s'" % name


    def _commit(self, name, branch, reason=None, init_repo=True):
        """Commit is only called in two cases, if there are uncommitted changes
        or if there are newly added (aka untracked) files which need to be added to
        the local repository prior to being pushed up to the remote repository.

        :param str message: Optional message, will be prompted if not supplied inline.

        """

        proj_dir = "%s/%s" % (self.cfgs['skein']['proj_dir'], name)

        if init_repo:
            self._init_git_repo("%s/%s" % (proj_dir, self.cfgs['skein']['git_dir']), name, branch=branch)

        self.repo.heads['master'].checkout()

        self.logger.info("||== Committing git repo ==||")

        if not reason:
            editor = os.environ.get('EDITOR') if os.environ.get('EDITOR') else self.cfgs['skein']['editor']

            tmp_file = tempfile.NamedTemporaryFile(suffix=".tmp")

            initial_message = self.cfgs['git']['commit_message']

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

        index = self.repo.index

        self.logger.info("  adding updated files to the index")
        index_changed = False

        if self.repo.is_dirty():
            index.add([diff.a_blob.path.rstrip('\n') for diff in index.diff(None)])
            index_changed = True

        self.logger.info("  adding untracked files to the index") 
        # add untracked files
        path = os.path.split(self.cfgs['skein']['proj_dir'])[0]

        if self.repo.untracked_files:
            index.add(self.repo.untracked_files)
            index_changed = True

        print("about to check index_changed")
        if index_changed:
            self.logger.info("  committing index")

            # commit files added to the index
            c = index.commit(reason)

            # create and checkout branch
            print("about to run _create_branch for {0}".format(branch))
            self._create_branch(name, branch, pull=False, commit=c)
            print("about to checkout branch {0}".format(branch))
            self.repo.heads[branch].checkout()


    def do_commit(self, args):
        """Commit changes to a branch. Only branches in skein.cfg will be
        allowed.

        :param dict args: args from commit command
        """

        name = args.name
        branch = args.branch
        message = args.message

        self._commit(name, branch, message)

    def _push_to_remote(self, name, branches=['master']):
        """Push any/all changes to remote repository

        :param str name: repository name (same as package)
        """

        self.logger.info("== Pushing git repo ==")

        proj_dir = "%s/%s" % (self.cfgs['skein']['proj_dir'], name)
        self._init_git_repo("%s/%s" % (proj_dir, self.cfgs['skein']['git_dir']), name)

        if 'all' in branches:
            # determine the local branches
            branches = self.repo.branches

        for branch in reversed(branches):
            try:
                self.logger.debug("Pushing branch '{0}' on repo '{1}' to remote '{2}'".format(branch, name, self.repo.remotes['origin'].url))
                print("Pushing branch '{0}' on repo '{1}'".format(branch, name, self.repo.remotes['origin'].url))
                self.repo.remotes['origin'].push('refs/heads/{0}:refs/heads/{0}'.format(branch))
            except IndexError, e:
                print "--- Push failed with error: %s ---" % e
                self.logger.debug("--- Push failed with error: %s" % e)
                raise
            except AssertionError, e:
                # odds are that unless the exception 'e' has a value
                # the assertionerror is wrong.  Usually, this is because
                # gitPython shows a warning, not an actual error
                if e and len(str(e)) != 0:
                    print "--- Push failed with error: %s ---" % e
                    self.logger.debug("--- Push failed with error: %s" % e)
                    raise
            except Exception, e:
                if e and len(str(e)) != 0:
                    print "Push failed with error: {0}".format(e)
                    self.logger.debug("--- Push failed with error: {0}".format(e))
                raise

    def _get_srpm_list(self, path):

        if os.path.isdir(path):
            return os.listdir(path)
        elif os.path.isfile(path):
            return [path]
        else:
            print "'%s' is not valid" % path
            sys.exit(1)

    def _watch_koji_tasks(self, session, tasklist, quiet=False):
        if not tasklist:
            return
        self.logger.info('Watching tasks (this may be safely interrupted)...')
        print 'Watching tasks (this may be safely interrupted)...'
        # Place holder for return value
        rv = 0
        try:
            tasks = {}
            for task_id in tasklist:
                tasks[task_id] = TaskWatcher(task_id, session, quiet=quiet)
            while True:
                all_done = True
                for task_id,task in tasks.items():
                    changed = task.update()
                    if not task.is_done():
                        all_done = False
                    else:
                        if changed:
                            # task is done and state just changed
                            if not quiet:
                                pass
                                #_display_tasklist_status(tasks)
                        if not task.is_success():
                            rv = 1
                    for child in session.getTaskChildren(task_id):
                        child_id = child['id']
                        if not child_id in tasks.keys():
                            tasks[child_id] = TaskWatcher(child_id, session, task.level + 1, quiet=quiet)
                            tasks[child_id].update()
                            # If we found new children, go through the list again,
                            # in case they have children also
                            all_done = False
                if all_done:
                    if not quiet:
                        print
                        #_display_task_results(tasks)
                    break

                time.sleep(1)
        except (KeyboardInterrupt):
            if tasks:
                kbd_msg = """\nTasks still running. You can continue to watch with the 'koji watch-task' command.  Running Tasks: %s""" % '\n'.join(['%s: %s' % (t.str(), t.display_state(t.info)) for t in tasks.values() if not t.is_done()])
                self.logger.info(kbd_msg)
                print kbd_msg

            # /us/rbin/koji considers a ^c while tasks are running to be a
            # non-zero exit.  I don't quite agree, so I comment it out here.
            #rv = 1
        return rv

    def _init_git_remote(self):

        remoteClassName = self.cfgs['git']['remote_class']
        remoteModuleName = self.cfgs['git']['remote_module']

        try:
            remoteModule = __import__(remoteModuleName,
                                      globals(),
                                      locals(),
                                      [remoteClassName])
            self.gitremote = GitRemote(remoteModule.__dict__[remoteClassName], self.cfgs, self.logger)
        except ImportError, e:
            self.logger.debug("Remote class %s in module %s not found: %s" % (remoteClassName, remoteModuleName, e))
            raise SkeinError("Remote class %s in module %s not found: %s" % (remoteClassName, remoteModuleName, e))

    def _create_lookaside_dir(self, name):
        self.logger.info("== Creating project dir on lookaside cache ==")
        print "Creating project dir on lookaside cache"

        lookaside_dir = "%s/%s" % (self.cfgs['lookaside']['remote_dir'], name)
        lookaside_host = self.cfgs['lookaside']['host']
        lookaside_user = self.cfgs['lookaside']['grant_user']

        args = ["/usr/bin/ssh", "%s@%s" % (lookaside_user, lookaside_host), '/bin/mkdir %s' % lookaside_dir]
        p = subprocess.call(args, cwd=".", stdout = subprocess.PIPE)

    def _enable_pkg(self, name, summary, url, gitowner=None, kojiowner=None, tag=None):

        if not tag:
            tag = self.cfgs['koji']['latest_tag']

        self.logger.info("  Requesting remote repo for '%s'" % name)
        print "Requesting remote repo for '%s'" % name

        self.gitremote.create_remote_repo(name, summary, url)
        self.gitremote.create_team("%s_%s" % (self.cfgs['skein']['team_prefix'], name), 'admin', gitowner, [name])

        try:
            if not self.kojisession.checkTagPackage(tag, name):
                self.kojisession.packageListAdd(tag, name, owner=kojiowner)
                self.logger.info("== Added package '%s' to the tag '%s'" % (name, tag))
                print "Added package '%s' to the tag '%s'" % (name, tag)
            else:
                self.logger.info("== Package '%s' already added to tag '%s'" % (name, tag))
                print "Package '%s' already added to tag '%s', skipping" % (name, tag)

        except (xmlrpclib.Fault,koji.GenericError) as e:
            raise SkeinError("Unable to tag package %s due to error: %s" % (name, e))

    def repo_info(self, args):
        """Grab useful information from a repository

        :param str args.name: repository name
        """

        name = args.name

        self.logger.info("== Gathering repo information for '%s'" % name)
        print "Gathering repo information for '%s'" % name

        self._init_git_remote()
        repo_info = self.gitremote.repo_info(name)

        print "Repo: %s" % name
        print "-------------------------"
        for k in repo_info.iterkeys():
            if k != 'commits':
                print "%s\t\t\t%s" % (k.ljust(15), unicode(repo_info[k]).encode('utf-8'))

        if args.commits:
            print "\n-- Commit Detail -- (All times are PST)"
            if repo_info['size']:
                commit_detail = repo_info['commits']
                for k in sorted(commit_detail.keys(), reverse=True):
                    print "%8s\t%s\t%s\t%s" % (commit_detail[k]['id'][:8], k[:16], commit_detail[k]['committer']['login'], commit_detail[k]['message'])
            else:
                print "No commits have been pushed."

        print

    def request_remote_repo(self, args):
        """Request a new remote repository for importing

        """

        if not args.name and not args.path:
            raise SkeinError("Please supply either a name or path")
        if args.name and args.path:
            raise SkeinError("Please supply either a name or path, not both")

        self._init_git_remote()

        if args.name:
            name = args.name
            return self.gitremote.request_repo(name)

        if args.path:
            path = args.path
            force = args.force
            # need to get the name, summary and url values from the srpm
            self._set_srpm_details(path)
            return self.gitremote.request_repo(self.rpminfo['name'], self.rpminfo['summary'], self.rpminfo['url'], force)

    def search_repo_requests(self, args):
        self._init_git_remote()
        state = 'open'

        if args.state:
            state = 'closed'

        return self.gitremote.search_repo_requests(state=state)

    def show_request_by_id(self, args):
        self._init_git_remote()

        name, summary, url, owner = self.gitremote.show_request_by_id(args.id)

        print "\nDetails for request # %s, requested by: %s" % (args.id, owner)
        print "-------------------------"
        print "Package Name: %s" % name.encode('utf-8')
        print "Package Summary: %s" % summary.encode('utf-8')
        print "Package URL: %s\n" % url.encode('utf-8')

    def revoke_request(self, args):

        self._init_git_remote()

        name, summary, url, gitowner = self.gitremote.show_request_by_id(args.id)

        if not self.gitremote.request_is_open(args.id):
            raise SkeinError("Request for '%s' is not open...\n     Move along, nothing to see here!" % name)

        print "Name: %s\nSummary: %s\nURL: %s\n" % (name, summary, url)
        valid = 'n'
        valid = raw_input("Is the above information correct? (y/N) ")

        if valid.lower() == 'y':
            self.gitremote.revoke_repo_request(args.id, name)

    def grant_request(self, args):

        self._init_git_remote()

        tag = None
        if args.tag:
            tag = args.tag

        name, summary, url, gitowner = self.gitremote.show_request_by_id(args.id)

        try:
            kojiowner = self.cfgs['koji']['owner']
        except:
            pass

        if args.kojiowner:
            kojiowner = args.kojiowner
        if args.gitowner:
            gitowner = args.gitowner

        if not self.gitremote.request_is_open(args.id):
            raise SkeinError("Request for '%s' is already completed...\n     Move along, nothing to see here!" % name)

        print "Name: %s\nSummary: %s\nURL: %s\n" % (name, summary, url)
        valid = 'n'
        valid = raw_input("Is the above information correct? (y/N) ")

        if valid.lower() == 'y':
            kojiconfig = None
            if args.config:
                kojiconfig = args.config
            elif self.cfgs['koji'].has_key('config'):
                kojiconfig = self.cfgs['koji']['config']

            self._init_koji(user=self.cfgs['koji']['username'], kojiconfig=kojiconfig)
            self._enable_pkg(name, summary, url, gitowner, kojiowner, tag)
            self._create_lookaside_dir(name)
            self.gitremote.close_repo_request(args.id, name)

    def do_extract_pkg(self, args):
        """Extract a package. Copies the spec, sources and patches
        appropriately in preparation for a push (skein push) and upload
        to the lookaside cache (skein upload)

        :param str args.path: path to source rpm
        :param str args.message (optional): commit message
        """

        message = None
        if args.message:
            message = args.message

        for p in args.path:
            srpms = self._get_srpm_list(p)

            for srpm in srpms:

                # ensure branch exists, if not create it and switch

                self.logger.info("== Extracting %s ==" % (srpm))
                # print "Extracting %s" % (srpm)
                self._set_srpm_details(u"%s" % (srpm))

                self._install_srpm(u"%s" % (srpm))

                proj_dir = "%s/%s" % (self.cfgs['skein']['proj_dir'], self.rpminfo['name'])
                #print "spec_dest: %s" % proj_dir

                self._makedir("%s/%s" % (proj_dir, self.cfgs['skein']['lookaside_dir']))
                self._makedir("%s/%s" % (proj_dir, self.cfgs['skein']['git_dir']))

                self._init_git_repo("%s/%s" % (proj_dir, self.cfgs['skein']['git_dir']), self.rpminfo['name'], branch=args.branch)

                # copy sources, both archives and patches. Archives go to lookaside_dir, patches and other sources go to git_dir
                src_dest = "%s/%s" % (proj_dir, self.cfgs['skein']['lookaside_dir'])
                git_dest = "%s/%s" % (proj_dir, self.cfgs['skein']['git_dir'])

                name = self.rpminfo['name']

                self._extract_srpm(src_dest, git_dest)
                self._generate_sha256(src_dest, git_dest)
                self._update_gitignore(git_dest)
                self._do_makefile(git_dest)

                if not args.no_commit:
                    self._commit(name, args.branch, args.message, init_repo=False)


    def _create_branch(self, name, branch, pull=True, commit=None):
        """Create or verify branch creation.

        :param str name: repository name
        :param str branch: branch name
        :param bool fetch: whether to perform a fetch first (default: True)
        """

        # if we haven't already done so, pull branches to local repository

        if pull:
            try:
                print ('performing origin.update of {0}'.format(branch))
                self.repo.remotes.origin.update()
            except GitCommandError as e:
                print("update() failed: '{0}'".format(e))
                self.logger.debug("update() failed: '{0}'".format(e))
                raise

        # does branch exist, then just return success
        if branch in self.repo.branches:
            return

        # if branch doesn't exist, create
        return self.repo.create_head(branch, commit=commit)


    def do_push(self, args):
        """Push to remote git repository

        :param str args.name: repository name
        """

        name = args.name
        branches = ['master']
        if args.branches:
            if args.nomaster:
                branches = args.branches
            else:
                branches.extend(args.branches)
        elif args.all_branches:
            # determine the local branches
            branches = ['all']

        #print "branches: {0}".format(branches)

        self._push_to_remote(name, branches)

    def do_upload(self, args):
        """Upload source(s) to lookaside cache

        :param str args.name: repository name
        """

        name = args.name
        self._upload_source(name)

    def do_import_pkg(self, args):
        """Import a package. Performs extract, push and upload (in that order)

        :param str args.path: path to source rpm
        :param str args.message (optional): commit message
        """

        self.do_extract_pkg(args)

        name = self.rpminfo['name']
        message = None
        if args.message:
            message = args.message

        self._upload_source(name)
        self._push_to_remote(name, message)

    def _get_git_hash(self, name, branch):

        proj_dir = "{0}/{1}".format(self.cfgs['skein']['proj_dir'], name)
        self._init_git_repo("{0}/{1}".format(proj_dir, self.cfgs['skein']['git_dir']), name)

        if branch in self.repo.branches:
          print("   checking out branch '{0}'".format(branch))
          self.logger.debug("   checking out branch '{0}'".format(branch))
          return self.repo.heads[branch].object.hexsha
        else:
          raise SkeinError('branch {0} does not exist'.format(branch))

    def do_build_pkg(self, args):

        kojiconfig = None
        if args.config:
            kojiconfig = args.config
        elif self.cfgs['koji'].has_key('config'):
            kojiconfig = self.cfgs['koji']['config']

        self.logger.info("== Attempting to build '%s' for target '%s' ==" % (args.name, args.target))
        print "Attempting to build '%s' for target '%s'" % (args.name, args.target)

        self._init_koji(user=self.cfgs['koji']['username'], kojiconfig=kojiconfig)
        build_target = self.kojisession.getBuildTarget(args.target)

        git_hash = self._get_git_hash(args.name, args.target)

        print('git_hash: {0}'.format(git_hash))

        #print "Args.Target: %s" % args
        #print "Build Target: %s" % build_target

        if not build_target:
            raise SkeinError('Unknown build target: %s' % args.target)

        dest_tag = self.kojisession.getTag(build_target['dest_tag_name'])
        #print "Dest Tag: %s" % dest_tag

        if not dest_tag:
            raise SkeinError('Unknown destination tag %s' %
                              build_target['dest_tag_name'])

        if dest_tag['locked']:
            raise SkeinError('Destination tag %s is locked' % dest_tag['name'])

        opts = {}
        priority = 5

        task_id = self.kojisession.build('{0}/{1}.git#{2}'.format(self.cfgs['github']['anon_base'], args.name, git_hash), args.target, opts, priority=priority)

        #print "Task-ID: %s" % task_id
        print "Task URL: %s/%s?taskID=%s" % ('http://koji.gooselinux.org/koji', 'taskinfo', task_id) 

        self.kojisession.logout()

        if not args.nowait:
            self._watch_koji_tasks(self.kojisession, [task_id])

    def list_deps(self, args):

        path = args.path
        srpms = self._get_srpm_list(path)

        for srpm in srpms:
            self._set_srpm_details(u"%s" % (srpm))

            self.logger.info("== Getting deps for %s==" % (srpm))
            print "Getting dependencies for %s" % (srpm)

            for br in self.buildrequires:
                self.logger.info("  %s" % br)
                print "  %s" % br
            print ""

def main():

    ps = PySkein()

    ps._init_git_remote()
    name = 'gtk+extras'
    scm_url = ps.gitremote.get_scm_url(name)
    print "scm_url: %s" % scm_url

#    p = argparse.ArgumentParser(
#            description='''Imports all src.rpms into git and lookaside cache''',
#        )
#
#
#
#    p.add_argument("name", help=u"directory to create in lookaside")
#    p.set_defaults(func=ps.create_lookaside)
#
#    args = p.parse_args()
#    args.func(args)


if __name__ == "__main__":
    sys.exit(main())



