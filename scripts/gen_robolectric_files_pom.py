#!/usr/bin/env python

"""
This is a quick and dirty script to parse SdkConfig.java from the
Robolectric sources on GitHub to determine the list of dependencies we need
to use the Robolectric Test Runner in offline mode. It then generates a Maven
pom.xml file that can be used to download all the necessary depedenency jars
from maven central.

Author: @codeblast
"""

from __future__ import print_function
import re

from jinja2 import Template
import requests


__author__ = 'glombard'

SDK_CONFIG_URL = (
  'https://raw.githubusercontent.com/robolectric/robolectric/master'
  '/robolectric/src/main/java/org/robolectric/internal/SdkConfig.java')
LATEST_VERSION_URL = 'https://api.bintray.com/packages/bintray/jcenter/org' \
                     '.robolectric%3Arobolectric'

# Determine the latest version from the JCenter API (e.g. '3.0-rc2'):
robolectric_version = requests.get(LATEST_VERSION_URL).json()['latest_version']

# Determine the latest supported SDK version (e.g. '5.0.0_r2-robolectric-1'):
sdk_config_src = requests.get(SDK_CONFIG_URL).text
matches = re.findall('SdkVersion\("(.+)",\s*"(.+)"\)', sdk_config_src)
latest_version = sorted(matches, key=lambda tup: tup[0], reverse=True)[0]
sdk_version = '{}-robolectric-{}'.format(latest_version[0],
                                         latest_version[1])

# Extract the list of dependencies form SdkConfig.java:
matches = re.findall('^\s*createDependency\("(.+?)",\s*"(.+?)",\s*(.+?),',
                     sdk_config_src, re.MULTILINE)
dependencies = list()
for tup in matches:
  if tup[2] == 'artifactVersionString':
    ver = sdk_version
  elif tup[2] == 'ROBOLECTRIC_VERSION':
    ver = robolectric_version
  else:
    ver = tup[2].replace('"', '')
  dependencies.append(
    {'groupId': tup[0], 'artifactId': tup[1], 'version': ver})

pom_template_text = """
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
http://maven.apache.org/maven-v4_0_0.xsd">

<!--
Robolectric version: {{ robolectric_version }}
SDK version: {{ sdk_version }}

Save this output to pom.xml and download jars with:

mvn dependency:copy-dependencies
-DremoteRepositories=http://repo1.maven.org/maven2/
-DoutputDirectory=/tmp/robolectric-files
-->

  <modelVersion>4.0.0</modelVersion>

  <groupId>org.robolectric</groupId>
  <artifactId>robolectric-files</artifactId>
  <version>{{ robolectric_version }}</version>
  <packaging>pom</packaging>
  <description>Robolectric Test Runner files.</description>
  <url>http://robolectric.org/</url>

  <dependencies>
    {% for d in dependencies -%}
    <dependency>
      <groupId>{{ d.groupId }} </groupId>
      <artifactId>{{ d.artifactId }}</artifactId>
      <version>{{ d.version }}</version>
    </dependency>
    {%- endfor %}
  </dependencies>
</project>
"""

context = {
  'robolectric_version': robolectric_version,
  'sdk_version': sdk_version,
  'dependencies': dependencies
}

template = Template(pom_template_text)
print(template.render(context))
