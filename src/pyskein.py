# Main class for pycamps

import os
import stat
import sys
import re
import time
import shutil
import hashlib
import argparse
import subprocess

# import the rpm parsing stuff
import rpm

# GitPython
import git
from git.errors import InvalidGitRepositoryError, NoSuchPathError, GitCommandError

# settings, including lookaside uri and temporary paths
import goose_settings as gs

# github api and token should be kept secret
import github_settings as ghs
from github2.client import Github

class PySkein:
    """
    Support class for skein. Does single and mass imports, upload, verify, sources, 
    generate makefiles and more for the goose linux rebuilds.
    """
    
    def __init__(self):
        self.org = ghs.org

    def _makedir(self, target, perms=0775):
        if not os.path.isdir(u"%s" % (target)):
            os.makedirs(u"%s" % (target), perms)
    
    # install the srpm in a temporary directory
    def _install_srpm(self, srpm):
        # rpm.ts is an alias for rpm.TransactionSet
        print "importing srpm from %s" % srpm
        ts = rpm.ts()
        ts.setVSFlags(rpm._RPMVSF_NOSIGNATURES)
    
        fdno = os.open(u"%s" % srpm, os.O_RDONLY)
        try:
            hdr = ts.hdrFromFdno(fdno)
        except rpm.error, e:
            if str(e) == "public key not available":
                print str(e)
        os.close(fdno)
        
        self.name = hdr[rpm.RPMTAG_NAME]
        self.version = hdr[rpm.RPMTAG_VERSION]
        self.release = hdr[rpm.RPMTAG_RELEASE]
        self.sources = hdr[rpm.RPMTAG_SOURCE]
        # print sources
        self.patches = hdr[rpm.RPMTAG_PATCH]
        # print patches
    
        self._makedir(u"%s/%s" % (gs.install_root, self.name))
    
        args = ["/bin/rpm", "-i", "--root=%s/%s" % (gs.install_root, self.name), "%s" % (srpm)]
        p = subprocess.Popen(args)

        # must wait a second or two for the install to finish
        time.sleep(2)

    def _copy_sources(self, sources_src, sources_dest):
        print "== Copying sources =="
        # copy the source files
        for source in self.sources:
        #    print "source: %s/%s" % (sources_src, source)
            print "  %s to %s" % (source, sources_dest)
            shutil.copy2("%s/%s" % (sources_src, source), sources_dest)
    
    # this method assumes the sources are new and overwrites the 'sources' file in the git repository
    def _generate_sha256(self, sources_dest, spec_dest):
        print "== Generating sha256sum for sources =="
        sfile = open(u"%s/sources" % spec_dest, 'w+')
        for source in self.sources:
            sha256sum = hashlib.sha256(open(u"%s/%s" % (sources_dest, source), 'rb').read()).hexdigest()
            sfile.write(u"%s %s\n" % (sha256sum, source))
        #close the file
        sfile.close()

    def _copy_spec(self, spec_src, spec_dest):
        print "== Copying spec =="

        # copy the spec file
        print "  %s.spec to %s" % (self.name, spec_dest)
        shutil.copy2(spec_src, spec_dest)

    def _copy_patches(self, patches_src, patches_dest):
        print "== Copying patches =="
        # copy the patch files
        for patch in self.patches:
            print "  %s to %s" % (patch, patches_dest)
            shutil.copy2("%s/%s" % (patches_src, patch), patches_dest)
    
    def _create_gh_repo(self):
        print "== Creating github repository '%s/%s' ==" % (ghs.org, self.name)
        try:
            github = Github(username=ghs.username, api_token=ghs.api_token)
            repo = github.repos.create(u"%s/%s" % (ghs.org, self.name))
            print "  Remote '%s/%s' created" % (ghs.org, repo.name)
        except RuntimeError, e:
            # assume repo already exists if this is thrown
            print "  Remote '%s/%s' already exists" % (ghs.org, self.name)
            #print str(e.message)
            pass

    # create a git repository pointing to appropriate github repo
    def _clone_git_repo(self, repo_dir, scm_url):
        print "== Creating local git repository at '%s' ==" % repo_dir

        try:
            self.repo = git.Repo(repo_dir)
        except InvalidGitRepositoryError, e:
            gitrepo = git.Git(repo_dir)
            cmd = ['git', 'init']
            result = git.Git.execute(gitrepo, cmd)
            self.repo = git.Repo(repo_dir)

        print "  Performing git pull from origin at '%s'" % scm_url
        try:
            self.repo.create_remote('origin', scm_url)
            self.repo.remotes['origin'].pull('refs/heads/master:refs/heads/master')
        except GitCommandError, e:
            origin = self.repo.remotes['origin']
            reader = origin.config_reader
            url = reader.get("url")
            if not url == scm_url:
                print u"origin is %s, should be %s. Adjusting" % (url, scm_url)
                try:
                    self.repo.delete_remote('old_origin')
                except GitCommandError, e:
                    origin.rename('old_origin')
                    self.repo.create_remote('origin', scm_url)
                    self.repo.remotes['origin'].pull('refs/heads/master:refs/heads/master')
    
    def do_sources(self, sources, new=False):
        pass

    def do_import(self, args):

        path = args.path
        try:
            srpms = os.listdir(path)
            print "srpms: %s" % str(srpms)
        except OSError, e:
            pass
    
        for srpm in srpms:
            self._install_srpm(u"%s/%s" % (path, srpm))

            # make sure the github repo exists
            self._create_gh_repo()

            spec_src = u"%s/%s%s/%s/%s.spec" % (gs.install_root, self.name, gs.home, 'rpmbuild/SPECS', self.name)
            spec_dest = u"%s/%s" % (gs.git_dir, self.name)
            sources_src = u"%s/%s%s/%s" % (gs.install_root, self.name, gs.home, 'rpmbuild/SOURCES')
            sources_dest = u"%s/%s" % (gs.lookaside_dir, self.name)

            self._makedir(spec_dest)
            self._clone_git_repo(spec_dest, u"%s/%s.git" %(gs.git_remote, self.name))

            self._copy_spec(spec_src, spec_dest)
            self._copy_patches(sources_src, spec_dest)

            self._makedir(sources_dest)
            self._copy_sources(sources_src, sources_dest)
            self._generate_sha256(sources_dest, spec_dest)

def main():

    ps = PySkein()

    p = argparse.ArgumentParser(
            description='''Imports all src.rpms into git and lookaside cache''',
        )

    p.add_argument('path', help='path to src.rpms')
    p.set_defaults(func=ps.do_import)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())



