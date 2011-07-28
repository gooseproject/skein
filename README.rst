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

skein dependencies
==================

* git-python = 0.2x (http://gitorious.org/projects/git-python/)
* rpm-python >= 4.9.0 (http://www.rpm.org/)
* github2 (http://packages.python.org/github2/)

SRPM Imports
============

Skein provides the ability to import a single source rpm (srpm) or a directory of srpms.::

    $ skein import -h
    usage: skein import [-h] path

    positional arguments:
      path        path to srpm. If dir given, will import all srpms

    optional arguments:
      -h, --help  show this help message and exit

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




