What is Skein?
--------------

Skein is the tool which gooseproject uses to gather and import srpms. 

Such an odd name, you might say. Skein is actually geese or swan flying in 'v' formation, which is such a beautiful sight. Maybe not so odd, after all.

More can be read about Skein at http://github.com/gooseproject/skein/.

Using Skein
-----------

Using skein is simple, but there are a few different functions available.::

    $ skein -h
    usage: skein [-h] {deplist,import} ...

    Imports all src.rpms into git and lookaside cache

    positional arguments:
      {deplist,import}
        import          import srpm(s)
        deplist         return dependencies to build srpm

    optional arguments:
      -h, --help        show this help message and exit

Dependencies
============

Skein will not function without the following dependencies.

* git-python = 0.2x (http://gitorious.org/projects/git-python/)
* rpm-python >= 4.9.0 (http://www.rpm.org/)
* github2 (http://packages.python.org/github2/)

Configuration
=============

Before using skein, several configurations may need to be adjusted. There are two main configuration files that need to be inspected/adjusted before skein will function properly. These files are skein_settings.py and github_settings.py. 

* The github_settings.py.sample needs to be renamed to github_settings.py. The username and API key also need to be adjusted to enable any github functionality. 
* Inside the skein_settings.py several configurations need to be verified and adjusted as desired
  * install_root - the directory in which source rpms are installed. This directory must be created prior to running skein
    * Files and directories inside 'install_root' can be removed at any time. They are not automatically removed.
  * base_dir - the base directory of both the local git repositories and the local lookaside cache
    * Files and directories inside the 'base_dir' can be removed at anytime. They are not automatically removed.
    * Each project directory inside the 'base_dir', except the 'lookaside_dir' are local git repositories of imported srpms
  * makefile_name - reference file used by skein to generate Makefile for each imported srpm
  * makefile_path - location of Makefile.tpl which is used to generate the Makefile for each imported srpm

.. note:: Moving the Makefile.tpl from the src/templates/ dir into a location in the path *must* occur or skein will fail with errors.

SRPM Imports
============

Skein provides the ability to import a single source rpm (srpm) or a directory of srpms.::

    $ skein import -h
    usage: skein import [-h] path

    positional arguments:
      path        path to srpm. If dir given, will import all srpms

The import performs several actions on each srpm:

* The srpm is installed into a temporary directory
* If not already created, a remote git repository is generated. By default, these are created on github.
* A local git repository is initialized and the origin is configured to the remote git repository.
* A 'git pull' is performed to ensure the local repository is up to date with the remote repository
* The spec file and any patch files from the srpm are copied to the local git repository
* The sources from the srpm are copied to a lookaside directory
* Each source is added to a file named 'sources' in the local git repository along with a sha256sum.
* The .gitignore file is created/updated in the local repository with each source file. This ensures binaries are not uploaded to the remote git repository.
* A Makefile is generated from a template (src/templates/Makefile.tpl) to match the name of the srpm
* The sources in the lookaside directory are uploaded to the remote lookaside cache
* All files in the local git repository are added to the index, committed with a standard message and pushed to the remote git repository

The import transactions are stored in a log file (/tmp/projects/skein.log by default) which contains a record of actions for each srpm imported.

SRPM Dependency List
====================

Skein can determine the BuildRequires for an srpm or the Requires for an rpm.::

    $ ./skein deplist /mnt/rhel6-source/SRPMS/bash-4.1.2-3.el6.src.rpm 
    == Deps for /mnt/rhel6-source/SRPMS/bash-4.1.2-3.el6.src.rpm ==
      texinfo
      bison
      ncurses-devel
      autoconf
      gettext
      rpmlib(FileDigests)
      rpmlib(CompressedFileNames)

.. note:: The bash srpm dependencies are listed above. Each dependency must be met to build the bash rpm in koji. The rpmlib(FileDigests) and rpmlib(CompressedFileNames) dependencies are generally already resolved once the buildroot is setup in koji and can usually be ignored.


