These are the release notes for skein. For more information, visit https://github.com/gooseproject/skein.

1.0 (2011-08-05)
================

* additional github error logging
* added --no-push option to import
* added --no-upload option to import
* simple fix to allow multiple srpms to be listed on a single line during import tasks
* creating install_root dir before starting logging
* skein.py keeps getting added, removing again

0.2 (2011-08-01) 
================

* Added setup.py
* Updated README.rst
* Add imported package github repo to approved teams

0.1 (2011-07-14)
================

* Added Import functionality
* Grabs rpm from a specific directory (or single file)
* Extracts the rpm spec, sources and patchs.
* Uploads sources to lookaside cache
* Generates 'sources' file in git repository
* Generates 'Makefile' in git repository
* Generates '.gitignore' in git repository
* Commits and pushes above files plus spec and patch files to github for organization
