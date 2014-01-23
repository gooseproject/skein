#!/bin/bash

############################################################
# This script provides tooling to take any                 #
# directory of rpms and determine the which version        #
# of GoOSe it belongs. This is done based upon the         #
# schedule detailed by the following url:                  #
# https://access.redhat.com/knowledge/articles/3078#RHEL6  #
############################################################


if [ $# -lt 2 ]; then
  echo "Usage $0 <source> <dest>"
  exit 1
fi

GL_DIR=${1}
DEST_DIR=${2}

# list the release dates here
# from left to right 6.0 -> 6.4 (so far)
RELEASE_DATES='6_0:201011090000 6_1:201105190000 6_2:201112060000 6_3:201206200000 6_4:201302210000 6_5:201311210000'

FILES=''

touch -t 200001010000 .oldfile
rel="6_0"

for date in ${RELEASE_DATES}; do

  oldrel=${rel}
  rel=$(echo ${date} | awk -F':' '{ print $1 }')
  d=$(echo ${date} | awk -F':' '{ print $2 }')

  touch -t ${d} .newfile

  FILES=$(find ${GL_DIR} -type f -newer .oldfile ! -newer .newfile)

  if [ ! -d ${DEST_DIR}/gl${rel} ]; then
    mkdir -p ${DEST_DIR}/gl${rel}
  fi
  if [ ! -d ${DEST_DIR}/gl${rel}-updates/ ]; then
    mkdir -p ${DEST_DIR}/gl${rel}-updates/
  fi

  for file in ${FILES}; do
    f=${file##*/}
    if [ ! -h ${DEST_DIR}/gl${rel}/${f} -a ! -h ${DEST_DIR}/gl${oldrel}-updates/${f} ]; then
      if [ $(echo ${f} | grep "el${oldrel}") ]; then
#        echo ${DEST_DIR}/gl${oldrel}-updates/${f}
        ln -s "${file}" "${DEST_DIR}/gl${oldrel}-updates/"
      else
#        echo ${DEST_DIR}/gl${rel}/${f}
        ln -s "${file}" "${DEST_DIR}/gl${rel}/"
      fi
    fi
  done

  createrepo -d ${DEST_DIR}/gl${oldrel}-updates
  createrepo -d ${DEST_DIR}/gl${rel}

  touch -t ${d} .oldfile
done
