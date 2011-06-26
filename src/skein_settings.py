# settings for create_gh_repo.py / import_srpms.py
import os
import logging

import github_settings as ghs

login = os.getenv('LOGNAME')
home = os.environ['HOME']

install_root = u"/tmp/projects"

distro = u"GoOSe"
version = u"6.0"
commit_message="srpm imported (%s %s) 'Testing'" % (distro, version)

project_root = u"%s/Projects" % home
base_dir = u"%s/%s" % (project_root, ghs.org)
git_remote = u"git@github.com:%s" % ghs.org
lookaside_dir = u"%s/%s/%s" % (base_dir, ghs.org, 'lookaside')

#path for Makefile.tpl
makefile_path = "%s:~/.skein" % base_dir
makefile_name = "Makefile.tpl"

#lookaside server configs
lookaside_user = "pkgmgr" # this user *must* have an public ssh key on the lookaside_host for the local user
lookaside_host = "http://pkgs.gooselinux.org"
lookaside_uri = "%s/pkgs" % lookaside_host

#logging settings
logfile=u"%s/%s" % (install_root, "skein.log")
logformat="%(levelname)s %(asctime)s %(message)s"
logdateformat="%m/%d/%Y %I:%M:%S %p"
loglevel=logging.DEBUG


