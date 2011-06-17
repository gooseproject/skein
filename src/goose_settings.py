# settings for create_gh_repo.py / import_srpms.py
import os
import github_settings as ghs

login = os.getenv('LOGNAME')
home = os.environ['HOME']

install_root = u"/tmp/projects"

projects_dir = u"Projects"
base_dir = u"%s/%s" % (home, projects_dir)
git_dir = u"%s/%s" % (base_dir, ghs.org)
git_remote = u"git@github.com:%s" % ghs.org
lookaside_dir = u"%s/%s/%s" % (base_dir, ghs.org, 'lookaside')

lookaside_host = "http://pkgs.gooselinux.org"
lookaside_uri = "%s/pkgs" % lookaside_host
