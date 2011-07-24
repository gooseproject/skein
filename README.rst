What is Skein?
--------------

Skein is the tool which gooseproject uses to gather and import srpms. 

Such an odd name, you might say. Skein is actually geese or swan flying in 'v' formation, which is such a beautiful sight. Maybe not so odd, after all.

More can be read about Skein at http://github.com/gooseproject/skein/.

Using Skein
-----------

Using skein is simple, but there are a few different functions available.::

    $ skein -h
    usage: skein [-h] [--dist DIST] {help,import,mass-import,upload,gen-make,new-sources}

skein dependencies
==================

* git-python = 0.2x (http://gitorious.org/projects/git-python/)
* rpm-python >= 4.9.0 (http://www.rpm.org/)
* github2 (http://packages.python.org/github2/)


skein import
============

Imports a directory of srpms or single srpms. If a remote git repository is needed, it will be created. The spec and patch files are copied into a local git repo and committed, then pushed to the remote git repository. The default location for the local and remote git repositories, as well as the location to upload the archive is configured in the skein_settings.py.

