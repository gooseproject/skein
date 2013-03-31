#!/bin/bash

basedir='/home/herlo/Projects/gooselinux'
rpmdir='/home/herlo/Downloads/el6.0-ftp/gl6_0'
#rpmdir='/home/herlo/Downloads/el6.0-ftp/test'

x=0

for file in $(ls -1 ${rpmdir}/*); do
  pkg=$(rpm -qip ${file} 2> /dev/null | head -n 1| awk -F':' '{ print $2 }' | cut -c2-);
  mod_pkg=0
  orig_pkg=${pkg}


  if [ ! "$(grep ${pkg} /tmp/hasgl6.0-branch.txt)" ]; then
    x=$(($x + 1))
    echo "=== ${pkg} ==="
    if [ ! -d ${basedir}/${pkg} ]; then
      mkdir -p ${basedir}/${pkg}
    fi
    pushd ${basedir}/${pkg} &> /dev/null;
    if [ -d "${basedir}/${pkg}/git" ]; then
      echo "removing git dir for ${pkg}"
      rm -rf "${basedir}/${pkg}/git";
    fi
    if [ $(echo ${pkg} | grep '+') ]; then
      pkg=$(echo ${pkg} | sed 's/+/-/g')
      mod_pkg=1
    fi

    git clone git@github.com:gooselinux/${pkg}.git git || exit 1;
    pushd git &> /dev/null || exit 2
    git branch gl6.0 || exit 3;
    [ ${mod_pkg} ] && pkg=${orig_pkg}

    #echo -n "Sleeping "
    #for i in {1..30}; do
    #  echo -n ". "
    #  sleep 2
    #done
    #echo

    skein push ${pkg} -b all || exit 4
    popd &> /dev/null
    popd &> /dev/null
    echo "${pkg}" >> /tmp/hasgl6.0-branch.txt
    echo

    #if [ $(($x % 5)) -eq 0 ]; then
    #  sleep 30
    #fi
  fi

done
