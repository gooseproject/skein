What is Skein?
--------------

Skein is the tool which gooseproject uses to gather and import srpms. 

Such an odd name, you might say. Skein is actually geese or swan flying in 'v' formation, which is such a beautiful sight. Maybe not so odd, after all.

More can be read about Skein at http://github.com/gooseproject/skein/.

Dependencies
============

Skein will not function without the following dependencies.

* git-python = 0.2x (http://gitorious.org/projects/git-python/)
* rpm-python >= 4.9.0 (http://www.rpm.org/)
* python-argparse (http://code.google.com/p/argparse/)
* github2 (http://packages.python.org/github2/)
* koji >= 1.6.0 (http://packages.python.org/github2/)

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

Using skein
===========

To use skein, please find the USAGE.rst document located in this directory.
