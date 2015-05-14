#/usr/bin/env bash

set -e

./gen_robolectric_files_pom.py > pom.xml
mvn dependency:copy-dependencies -DremoteRepositories=http://repo1.maven.org/maven2/ -DoutputDirectory=/tmp/robolectric-files

echo
echo 'Now go find the Robolectric test runner files under /tmp/robolectric-files/'
