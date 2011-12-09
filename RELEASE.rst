-----------------------
Skein 2.0 release notes
-----------------------

2.0 Brings the following new features to Skein: 

A completely new workflow
=========================

Per discussions on the GoOSe Project mailing list, the following functions have been
added to skein:

* request - request a new repository either by name, or by SRPM
* query - query upstream repo requests
* show - show detail of a particular request
* grant - create new upstream repo and add package to koji
* revoke - revoke a repo create request
* extract - extract srpm(s)
* push - commit and push existing git repo to remote
* upload - upload source archives to lookaside
* import - import srpm(s). Performs extract, push and upload.
* info - request information about a repository
* build - build an already imported package

Below is a detailed set of commits:

FIXED
`````

* fixed up some encoded urls to print properly with a pipe
* fixed a few bugs and cleaned up some code
* fixed logic issue
* fixing i18n encoding where needed for now. Probably should dig into it and add a bunch more
* fixed search by issue state and adjusted formatting
* fixed logging to work with skein.cfg
* fixed quoting on issue_title

NEW
```

* added reference to python-argparse
* adding basic import functionality
* added --nowait option and cleaned up some tasks
* added --nowait option and cleaned up some tasks
* added commits option
* added force and prompt
* added configurations for new version of skein request
* added functionalty to request from srpm, does not prompt. Much faster than entering data by hand
* adding latest configuration file
* added documentation to many functions
* Adding in revoke functionality to skein.
* adding GPLv3 license
* added extract to the cli
* added verification and a few good options to grant. Also updated logger to the new location
* added show functionality to help identify details about particular requests
* added skein query and corresponding githubremote method search_repo_requests
* adding bulk functionality for skein build
* adding build to cli
* added SkeinError and checking for EDITOR variable in the shell
* adding documentation for new features to new USAGE.rst

BRANCHES MERGED IN
``````````````````

* Merged: skein_import -> develop
* Merged: expand_skein_info -> develop
* Merged: enable_config_path -> develop
* Merged: fix_broken_github2_calls -> develop
* Merged: request_by_srpm_with_prompting -> develop
* Merged: fix_minor_bugs -> develop
* Merged: query_from_srpm -> develop
* Merged: gather_repo_info -> develop
* Merged: new_workflow -> develop
* Merged: updates_docs_for_2.0 -> develop

OTHER CHANGES
`````````````

* changed the order to extract, upload then push to ensure all data was in place before a build would be launched
* improved status statements
* print friendly messages when doing stuff
* adjusted _push_to_remote to work with both do_push and do_import methods
* completing functionality for commits in skein info
* updated code to proces first /etc/skein/skein.cfg and override with ~/.skein/skein.cfg
* cleaning up stack traces unless debug is True
* adjusted skein.cfg to support /etc/skein and then ~/.skein/
* major improvement for request by using github2 search instead of a for loop
* url can be empty quite often, setting to none in those instances
* adjusting values to represent proper variables from skein.cfg
* something happened to list_by_label, using list
* adjusted extract to use rpminfo
* removing unneeded print message
* query skein to see if a repo exists in git remote
* sync_files script provides restricted rsync access the lookaside cache
* upload works so much better
* merging revoke functionality
* New workflow - added revoke function
* created skein push
* Provides optional commit command if the repo is a 'dirty girl' or has untracked files.
* Corrected typos and fixed revoke functions in gitremote and githubremote.
* updated makefile function
* updated gitignore function
* updated generate_sha256
* doing a little housecleaning
* now supports adding repo owner to the git_repo team with administrative rights
* extract functionality should now work
* updated owner functionality to include owner from config file
* updating configuration file to support the majority of new workflow changes
* initial transition to separating import into extract function
* closing tickets is important too
* adjusted close_repo_request to the proper api call
* close_repo_request added along with fixing some self-references
* create team for granted repo
* rough-in for skein grant functionality
* cleaned up request and added helper methods to get existing requests
* initial effort to make github as a remote more modular
* moved method name for 'request'
* migrated request_gh_repo to use configparser
* converting request_gh_repo from skein_settings to skien.cfg format
* updating .gitignore to exclude tracking skein.cfg.* files that may be created by users
* moving configurations around
* removing comments and unneeded code
* moving a few configurations into a new category
* tweaking the new skein.cfg for logging, part I
* moving skein.cfg to support SafeConfigParser
* migrating logging configs to ConfigParser format
* minor change to initial_message for gh issues
* initial skein.cfg file to replace skein_settings.py
* set the default editor and help message to put into the temporary file
* catching SkeinErrors
* initial work for repo request functionality
* removing documentation from README.rst
* moving documentation into doc directory
