# Using Robolectric in offline mode

## The problem

The Robolectric test runner downloads some dependency jars that it needs to run at *runtime* (not compile-time). Normally you don't even notice this when running your unit tests locally, but this could be a problem on Jenkins/CI if your company doesn't allow internet access from the CI boxes (as it should be). What happens is, when the Robolectric tests try to run on your CI box, it will fail with a MultipleArtifactsNotFoundException error like the following:

    com.example.app.MainActivityTest > testFoo FAILED
        org.apache.tools.ant.BuildException
            Caused by: org.apache.maven.artifact.resolver.MultipleArtifactsNotFoundException

Or the error may also look like this:

    :app:testDebug

    com.example.app.MainActivityTest > testFoo FAILED
        org.apache.tools.ant.BuildException
            Caused by: org.apache.maven.artifact.resolver.ArtifactResolutionException
                Caused by: org.apache.maven.artifact.metadata.ArtifactMetadataRetrievalException
                    Caused by: org.apache.maven.project.ProjectBuildingException
                        Caused by: org.apache.maven.project.ProjectBuildingException
                            Caused by: org.apache.maven.artifact.resolver.ArtifactNotFoundException
                                Caused by: org.apache.maven.wagon.ResourceDoesNotExistException

    1 test completed, 1 failed
    :app:testDebug FAILED

If you run gradlew with `-i` or `-d` options, you'll see more details of what's happening and then you realize it's because Robolectric is trying to download jars from `repo1.maven.org` which you may not have access to if you're using a local repo such as [Artifactory](http://www.jfrog.com/open-source/).

We want to stop Robolectric from trying to download its jars from Maven Central and force it to use a local copy of the jars, which we can manually copy to the CI build slave servers.

Robolectric 2.4 introduced two new [settings](http://robolectric.org/configuring/) to prevent downloading the dependencies from the hardcoded sonatype / maven URL:

- robolectric.offline
- robolectric.dependency.dir

However, it's not completely clear from the documentation how to use these settings. The documentation just mentions that they're "system properties".

There were a few questions I had when I started with this:

1. Which jars are needed by the Robolectric test runner?
2. How do I configure these two system properties in my project's build.gradle file?

## The solution

**Step 1: Which jars are needed?**

In order to place the jars in a known location on the CI build slaves, we first need to figure out exactly which jars are used by Robolectric during run-time.

One way to do this, is to run `gradlew testDebug -d` (i.e. with debug output) and examine the logs to figure out which jars were downloaded during test run-time.

I decided to take another approach, and go to the Robolectric sources to see which dependencies it needs. The info we want is in [SdkConfig.java](https://github.com/robolectric/robolectric/blob/master/robolectric/src/main/java/org/robolectric/internal/SdkConfig.java).

From SdkConfig.java I could tell that the following four dependencies are needed by Robolectric 3.0 at run-time:

- org.robolectric:android-all:5.0.0_r2-robolectric-1
- org.robolectric:shadows-core:3.0-rc2:21
- org.json:json:20080701
- org.ccil.cowan.tagsoup:tagsoup:1.2

However, we also need the transitive dependencies of these jars, i.e. the dependencies of these dependencies.

I figured the easiest way to correctly download these 4 jars and all their dependencies, is to let Maven do it. We can create a simple Maven `pom.xml` file that just lists these 4 dependency artifacts, and then we let `mvn dependency:copy-dependencies` download everything for us.

I wrote a quick 'n dirty [Python script](https://gist.github.com/glombard/2fdb883de1d50fb51d1a) to generate the [`pom.xml` file](https://gist.github.com/glombard/2fdb883de1d50fb51d1a#file-pom-xml) for me.

<script src="https://gist.github.com/glombard/2fdb883de1d50fb51d1a.js?file=pom.xml"></script>

Now I can use the Maven POM file to download the jars that Robolectric needs to a specific directory like `/tmp/robolectric-files/`:

    mvn dependency:copy-dependencies -DremoteRepositories=http://repo1.maven.org/maven2/ -DoutputDirectory=/tmp/robolectric-files

These are all the files downloaded by `mvn`:

    $ mvn dependency:copy-dependencies -DremoteRepositories=http://repo1.maven.org/maven2/ -DoutputDirectory=/tmp/robolectric-files
    [INFO] Scanning for projects...
    [INFO]
    [INFO] ------------------------------------------------------------------------
    [INFO] Building robolectric-files 3.0-rc2
    [INFO] ------------------------------------------------------------------------
    [INFO]
    [INFO] --- maven-dependency-plugin:2.8:copy-dependencies (default-cli) @ robolectric-files ---
    [INFO] Copying vtd-xml-2.11.jar to /tmp/robolectric-files/vtd-xml-2.11.jar
    [INFO] Copying accessibility-test-framework-1.0.jar to /tmp/robolectric-files/accessibility-test-framework-1.0.jar
    [INFO] Copying tagsoup-1.2.jar to /tmp/robolectric-files/tagsoup-1.2.jar
    [INFO] Copying json-20080701.jar to /tmp/robolectric-files/json-20080701.jar
    [INFO] Copying robolectric-resources-3.0-rc2.jar to /tmp/robolectric-files/robolectric-resources-3.0-rc2.jar
    [INFO] Copying shadows-core-3.0-rc2-21.jar to /tmp/robolectric-files/shadows-core-3.0-rc2-21.jar
    [INFO] Copying sqlite4java-0.282.jar to /tmp/robolectric-files/sqlite4java-0.282.jar
    [INFO] Copying icu4j-53.1.jar to /tmp/robolectric-files/icu4j-53.1.jar
    [INFO] Copying android-all-5.0.0_r2-robolectric-1.jar to /tmp/robolectric-files/android-all-5.0.0_r2-robolectric-1.jar
    [INFO] Copying robolectric-annotations-3.0-rc2.jar to /tmp/robolectric-files/robolectric-annotations-3.0-rc2.jar
    [INFO] Copying robolectric-utils-3.0-rc2.jar to /tmp/robolectric-files/robolectric-utils-3.0-rc2.jar
    [INFO] ------------------------------------------------------------------------
    [INFO] BUILD SUCCESS
    [INFO] ------------------------------------------------------------------------
    [INFO] Total time: 08:55 min
    [INFO] Finished at: 2015-05-13T18:26:23-07:00
    [INFO] Final Memory: 13M/239M
    [INFO] ------------------------------------------------------------------------

Now copy all those files from `/tmp/robolectric-files/` to some known location on your CI build slave box, say to `/home/jenkins/robolectric-files` (assuming `jenkins` is your CI build user account).

**Step 2: Set the offline-mode System Properties in build.gradle**

We need to set the following two Java System Properties for the Robolectric Test Runner to use the local files:

* robolectric.offline = true
* robolectric.dependency.dir = /home/jenkins/robolectric-files

One way to do this, is to add the following to our app's `build.gradle` file:

    afterEvaluate {
        project.tasks.withType(Test) {
            systemProperties.put('robolectric.offline', 'true')
            systemProperties.put('robolectric.dependency.dir', '/home/jenkins/robolectric-files')
        }
    }

Now we can run Gradle and our unit tests completely in offline mode:

    $ ./gradlew clean testDebug --offline

(Note: hardcoding a specific user's home directory in the gradle file isn't a good idea, but you get the point. Use a directory that works for you.)

**Alternate solution:**

Instead of Step 2 above, of course you could just install the necessary files into your CI box's Maven repository (~/.m2/repository/) using something like this for each of them:

    mvn install:install-file -DgroupId=org.robolectric \
      -DartifactId=shadows-core -Dversion=3.0-rc2 \
      -Dclassifier=21 -Dpackaging=jar \
      -Dfile=/tmp/robolectric-files/shadows-core-3.0-rc2-21.jar

But in my solution above I opted for overriding the location of the files using the `robolectric.offline` and `robolectric.dependency.dir` system settings, because that way I have more clear control and visibility over which files I'm responsible for maintaining manually.
