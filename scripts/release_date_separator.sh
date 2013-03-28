#!/bin/bash

############################################################
# This script provides tooling to take any                 #
# directory of rpms and determine the which version        #
# of GoOSe it belongs. This is done based upon the         #
# schedule detailed by the following url:                  #
# https://access.redhat.com/knowledge/articles/3078#RHEL6  #
############################################################


if [ $# -lt 1 ]; then
  echo "Usage $0 <directory>"
  exit 1
fi

GL_DIR=${1}

# list the release dates here
# from left to right 6.0 -> 6.4 (so far)
RELEASE_DATES='6_0:201011090000 6_1:201105190000 6_2:201112060000 6_3:201206200000 6_4:201302210000'

FILES=''

touch -t 200001010000 .oldfile
rel="6_0"

for date in ${RELEASE_DATES}; do

  oldrel=${rel}
  rel=$(echo ${date} | awk -F':' '{ print $1 }')
  d=$(echo ${date} | awk -F':' '{ print $2 }')

  touch -t ${d} .newfile
  echo "DATE: ${d}"

  FILES=$(find ${GL_DIR} -type f -newer .oldfile ! -newer .newfile)

  echo "RELEASE: ${rel}"
  echo "==============="

  for file in ${FILES}; do
    if [ ! -f ${GL_DIR}/gl${rel}/${file} ]; then
      cp_dir="gl${d}"
      if [ $(echo ${file} | grep "el${oldrel}") ]; then
#        echo "el${rel}"
        ln -s "${file}" "${GL_DIR}/gl${oldrel}-updates/"
      else
#        echo "el${rel}-updates"
        ln -s "${file}" "${GL_DIR}/gl${rel}/"
      fi
    fi
  done

  echo

  touch -t ${d} .oldfile
done

