# Main class for pycamps

import os
import stat
import sys
import re
import time
import shutil
import hashlib
import logging
import argparse
import subprocess

# import the rpm parsing stuff
import rpm

# GitPython
import git
from git.errors import InvalidGitRepositoryError, NoSuchPathError, GitCommandError

# settings, including lookaside uri and temporary paths
import skein_settings as sks

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
        logging.basicConfig(filename=sks.logfile, level=sks.loglevel, format=sks.logformat, datefmt=sks.logdateformat)

    def _makedir(self, target, perms=0775):
        if not os.path.isdir(u"%s" % (target)):
            os.makedirs(u"%s" % (target), perms)
    
    # install the srpm in a temporary directory
    def _install_srpm(self, srpm):
        # rpm.ts is an alias for rpm.TransactionSet
        logging.info("== Installing srpm ==")
        ts = rpm.ts()
        ts.setVSFlags(rpm._RPMVSF_NOSIGNATURES)
    
        fdno = open(u"%s" % srpm, 'r')
        try:
            hdr = ts.hdrFromFdno(fdno)
        except rpm.error, e:
            if str(e) == "public key not available":
                print str(e)
        fdno.close()
        
        self.name = hdr[rpm.RPMTAG_NAME]
        self.version = hdr[rpm.RPMTAG_VERSION]
        self.release = hdr[rpm.RPMTAG_RELEASE]
        self.sources = hdr[rpm.RPMTAG_SOURCE]
        self.patches = hdr[rpm.RPMTAG_PATCH]
        self.summary = hdr[rpm.RPMTAG_SUMMARY]
        self.url = hdr[rpm.RPMTAG_URL]
    
        self._makedir(u"%s/%s" % (sks.install_root, self.name))
    
        logging.info("  installing %s into %s/%s" % (srpm, sks.install_root, self.name))
        args = ["/bin/rpm", "-i", "--root=%s/%s" % (sks.install_root, self.name), "%s" % (srpm)]
        p = subprocess.call(args, stdout = subprocess.PIPE, stderr = subprocess.PIPE )

    def _copy_sources(self, sources_src, sources_dest):
        logging.info("== Copying sources ==")
        # copy the source files
        for source in self.sources:
        #    print "source: %s/%s" % (sources_src, source)
            logging.info("  %s to %s" % (source, sources_dest))
            shutil.copy2("%s/%s" % (sources_src, source), sources_dest)
    
    # this method assumes the sources are new and overwrites the 'sources' file in the git repository
    def _generate_sha256(self, sources_dest, spec_dest):
        logging.info("== Generating sha256sum for sources ==")
        sfile = open(u"%s/sources" % spec_dest, 'w+')
        for source in self.sources:
            sha256sum = hashlib.sha256(open(u"%s/%s" % (sources_dest, source), 'rb').read()).hexdigest()
            sfile.write(u"%s %s\n" % (sha256sum, source))
        #close the file
        sfile.close()

        logging.info("  sha256sums generated and added to %s/sources" % spec_dest)

    def _copy_spec(self, spec_src, spec_dest):
        logging.info("== Copying spec ==")

        # copy the spec file
        logging.info("  %s.spec to %s" % (self.name, spec_dest))
        shutil.copy2(spec_src, spec_dest)

    def _copy_patches(self, patches_src, patches_dest):
        logging.info("== Copying patches ==")
        # copy the patch files
        for patch in self.patches:
            logging.info("  %s to %s" % (patch, patches_dest))
            shutil.copy2("%s/%s" % (patches_src, patch), patches_dest)
    
    def _create_gh_repo(self):
        logging.info("== Creating github repository '%s/%s' ==" % (ghs.org, self.name))
        try:
            github = Github(username=ghs.username, api_token=ghs.api_token)
            repo = github.repos.create(u"%s/%s" % (ghs.org, self.name), self.summary, self.url)
            logging.info("  Remote '%s/%s' created" % (ghs.org, repo.name))
        except RuntimeError, e:
            # assume repo already exists if this is thrown
            logging.info("  Remote '%s/%s' already exists" % (ghs.org, self.name))
            #print str(e.message)
            pass

    # create a git repository pointing to appropriate github repo
    def _clone_git_repo(self, repo_dir, scm_url):
        logging.info("== Creating local git repository at '%s' ==" % repo_dir)

        try:
            self.repo = git.Repo(repo_dir)
        except InvalidGitRepositoryError, e:
            gitrepo = git.Git(repo_dir)
            cmd = ['git', 'init']
            result = git.Git.execute(gitrepo, cmd)
            self.repo = git.Repo(repo_dir)

        logging.info("  Performing git pull from origin at '%s'" % scm_url)

        try:
            self.repo.create_remote('origin', scm_url)
            self.repo.remotes['origin'].pull('refs/heads/master:refs/heads/master')
        except (AssertionError, GitCommandError), e:
            logging.debug("--- Exception thrown %s" % e)
            origin = self.repo.remotes['origin']
            reader = origin.config_reader
            url = reader.get("url")
            if not url == scm_url:
                logging.info(u"  origin is %s, should be %s. Adjusting" % (url, scm_url))
                try:
                    self.repo.delete_remote('old_origin')
                except GitCommandError, e:
                    origin.rename('old_origin')
                    self.repo.create_remote('origin', scm_url)
                    self.repo.remotes['origin'].pull('refs/heads/master:refs/heads/master')
                    
    # attribution to fedpkg, written by 'Jesse Keating' <jkeating@redhat.com> for this snippet
    def _update_gitignore(self, path):
        logging.info("  Updating .gitignore with sources" % repo_dir)
        gitignore_file = open("%s/%s" % (path, '.gitignore'), 'w')
        for line in self.sources:
            gitignore_file.write("%s\n" % line)
        gitignore_file.close()

    # search for a makefile.tpl in the makefile_path and use
    # it as a template to put in each package's repository
    def _do_makefile(self):
        logging.info("  Updating Makefile" % repo_dir)
        found = False
        for path in sks.makefile_path.split(':'):
            expanded_path = "%s/%s" % (os.path.expanduser(path), sks.makefile_name)
#            print "expanded_path: %s" % expanded_path
            if os.path.exists(expanded_path):
                makefile_template = expanded_path
                found = True
                break

        if not found:
            logging.error("'%s' not found in path '%s', please fix in the skein_settings.py" % (sks.makefile_name, sks.makefile_path))
            raise IOError("'%s' not found in path '%s', please fix in the skein_settings.py" % (sks.makefile_name, sks.makefile_path))

#        print "makefile template found at %s" % makefile_template

        src_makefile = open(makefile_template)
        dst_makefile = open("%s/%s/Makefile" % (sks.base_dir, self.name), 'w')

        dst_makefile.write( src_makefile.read() % {'name': self.name})
        dst_makefile.close()

    def _upload_sources(self, sources_path):

        logging.info("== Uploading Sources ==")
#        os.chdir( sks.lookaside_dir  )
#        print "CWD: %s" % os.getcwd()
#        print "PKG: %s" % self.name

        for source in self.sources:
#            print "rsync -vloDtRz -e ssh %s/%s %s@%s:%s/" % (self.name, source, sks.lookaside_user, sks.lookaside_host, sks.lookaside_remote_dir)

            logging.info("  uploading %s to %s" % (source, sks.lookaside_host))
            args = ["/usr/bin/rsync", "-loDtRz", "-e", "ssh", "%s/%s" % (self.name, source), "%s@%s:%s/" % ( sks.lookaside_user, sks.lookaside_host, sks.lookaside_remote_dir)]
            p = subprocess.call(args, cwd="%s" % (sks.lookaside_dir), stdout = subprocess.PIPE)
#            os.waitpid(p.pid, 0)
#            print "result %s" % p.communicate()[0]
#            time.sleep(2)

    def _commit_and_push(self, repo=None):

        logging.info("== Committing and pushing git repo ==")
        if not repo:
            repo = self.repo

        index = repo.index

        logging.info("  adding updated files to the index") 
        index_changed = False
        if repo.is_dirty():
            print "index: %s" % index
            for diff in index.diff(None):
                print diff.a_blob.path

            index.add([diff.a_blob.path for diff in index.diff(None)])
            index_changed = True

        logging.info("  adding untracked files to the index") 
        # add untracked files
        path = os.path.split(sks.base_dir)[0]
        print "path: %s" % path
        if repo.untracked_files:
            index.add(repo.untracked_files)
            index_changed = True

        if index_changed:
            logging.info("  committing index") 
            # commit files added to the index
            index.commit(sks.commit_message)

        logging.info(" Pushing '%s' to '%s'" % (self.name, sks.git_remote)) 
        try:
            self.repo.remotes['origin'].push('refs/heads/master:refs/heads/master')
        except IndexError, e:
            print "--- Push failed with error: %s ---" % e
            logging.debug("--- Push failed with error: %s" % e)
            raise
        except AssertionError, e:
            # odds are that unless the exception 'e' has a value
            # the assertionerror is wrong.  Usually, this is because
            # gitPython shows a warning, not an actual error
            if e and len(str(e)) != 0:
                print "--- Push failed with error: %s ---" % e
                logging.debug("--- Push failed with error: %s" % e)
                raise 

    def do_sources(self, sources, new=False):
        pass

    def do_import(self, args):

        print "Logging transactions in %s\n" % sks.logfile
        path = args.path
        if os.path.isdir(path):
            srpms = os.listdir(path) 
        elif os.path.isfile(path):
            path, srpm = os.path.split(path)
            srpms = [srpm]
    
        for srpm in srpms:
            print "Importing %s" % (srpm)
            logging.info("== Importing %s==" % (srpm))
            self._install_srpm(u"%s/%s" % (path, srpm))
            # must wait a second or two for the install to finish
            time.sleep(1)

            # make sure the github repo exists
            self._create_gh_repo()
            time.sleep(1)

            spec_src = u"%s/%s%s/%s/%s.spec" % (sks.install_root, self.name, sks.home, 'rpmbuild/SPECS', self.name)
            spec_dest = u"%s/%s" % (sks.base_dir, self.name)
            sources_src = u"%s/%s%s/%s" % (sks.install_root, self.name, sks.home, 'rpmbuild/SOURCES')
            sources_dest = u"%s/%s" % (sks.lookaside_dir, self.name)

#            print "spec_src: %s" % spec_src
#            print "spec_dest: %s" % spec_dest
#            print "sources_src: %s" % sources_src
#            print "sources_dest: %s" % sources_dest

            self._makedir(spec_dest)
            self._clone_git_repo(spec_dest, u"%s/%s.git" %(sks.git_remote, self.name))

            self._copy_spec(spec_src, spec_dest)
            self._copy_patches(sources_src, spec_dest)

            self._makedir(sources_dest)
            self._copy_sources(sources_src, sources_dest)
            self._generate_sha256(sources_dest, spec_dest)

            self._update_gitignore(spec_dest)

            self._do_makefile()
            self._upload_sources(sources_dest)

            self._commit_and_push()


            print "Import %s complete\n" % (self.name)
            logging.info("== Import of '%s' complete ==\n" % (srpm))

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



