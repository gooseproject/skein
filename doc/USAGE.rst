Using Skein
-----------

Using skein is simple, but there are a few different functions available::

    $ skein -h
    usage: skein [-h] {deplist,import} ...

    Imports all src.rpms into git and lookaside cache

    positional arguments:
      {deplist,import}
        import          import srpm(s)
        deplist         return dependencies to build srpm

    optional arguments:
      -h, --help        show this help message and exit


skein deplist
=============

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

.. note:: The following set of actions in skein are used together. The order in which things should be done is similar to what is listed below. The hope is that this documentation also serve as a workflow document for building rpms using skein. The process listed here is the definitive way to build rpms for the GoOSe Linux Project.

.. warning:: There are other prerequisites which need to be completed before attempting to use skein. Please visit #gooseproject in irc.freenode.net to get started. 

skein create
============

Request remote repository and koji be setup for a source rpm:: 

    $ skein create -h
    usage: skein create [-h] name

    positional arguments:
      name        name of the srpm

Please note, a formal request can be made with a browser. The format of the issue filed is **very** specific, however. To file a request, visit https://github.com/gooseproject/gooseproject-main/issues/new and enter the following information::

    Title: newrepo: bash

    Summary: The GNU Bourne Again shell
    URL: http://www.gnu.org/software/bash
    <blank line>

.. warning:: The above information **must** be listed exactly as above, or the request will be delayed.

.. note:: Other information can be provided, but must be **after** at least on blank line. This information is processed by a the admin 'query' and 'grant' features listed below.

An example of the exact inputs can be found at https://github.com/gooseproject/gooseproject-main/issues/6. 

skein admin
===========

After making a formal request

skein extract
=============

Extract the components of a source rpm::

    $ skein extract -h
    usage: skein extract [-h] path

    positional arguments:
      path        path to srpm. If dir given, will extract all srpms

The 'extract' performs several actions on each srpm:

* The srpm is installed into a temporary directory
* Two directories are created, if they do not already exist, $SKEIN_ROOT/sources and $SKEIN_ROOT/srpm_name

  * If the environment variable $SKEIN_ROOT does not exist, the current directory is used

* Any archives (usually files ending tar.gz, tar.bz2, zip, etc.) will be placed in $SKEIN_ROOT/sources

  * These file(s) will be used during the 'upload' action detailed below
* $SKEIN_ROOT/srpm_name is initialized as a git repository with github as the origin remote. A 'git pull' is performed to ensure the local repository is up to date with the remote.
* The spec file and any patch files from the srpm are copied to the local git repository
* Each source is added to a file named 'sources' in the local git repository along with a sha256sum
* A Makefile is generated from a template (located in src/templates/Makefile.tpl, but must be moved) to match the name of the srpm
* The .gitignore file is created/updated in the local repository with each source file. This ensures binaries are not uploaded to the remote git repository.

skein upload
============

    $ skein upload -h
    usage: skein upload [-h] name

    positional arguments:
      name        name of package to upload 

All files matching the contents of $SKEIN_ROOT/name/sources will be uploaded to the remote lookaside cache from $SKEIN_ROOT/sources

skein push
==========

    $ skein push -h
    usage: skein push [-h] name

    positional arguments:
      name        name of package to push to git remote 

All files in the local git repository are added to the index, committed with a standard message and pushed to the remote git repository

skein import
============

Skein provides the ability to import a single source rpm (srpm) or a directory of srpms::

    $ skein import -h
    usage: skein import [-h] path

    positional arguments:
      path        path to srpm. If dir given, will import all srpms

skein import is made up of three separate (and also useful) subcommands, extract, upload and push, in that order. Please see those commands for explanation.

.. note:: The 'extract', 'upload', 'push' (and of course import) transactions are stored in a log file (/tmp/projects/skein.log by default).
