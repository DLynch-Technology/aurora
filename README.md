# Aurora

[![Build Status](https://travis-ci.org/RockefellerArchiveCenter/aurora.svg?branch=master)](https://travis-ci.org/RockefellerArchiveCenter/aurora)
![GitHub (pre-)release](https://img.shields.io/github/release/RockefellerArchiveCenter/aurora/all.svg)

Aurora is a Django web application that can receive, virus check and validate transfers of digital archival records, and allows archivists to appraise and accession those records.

The name of the application is a reference both to the natural light display often seen in the northern hemisphere - sometimes referred to as _aurora borealis_ - as well as the Roman goddess of dawn.

Aurora is part of [Project Electron](http://projectelectron.rockarch.org/), an initiative to build sustainable, open and user-centered infrastructure for the archival management of digital records at the [Rockefeller Archive Center](http://rockarch.org/). Project updates are available on [Bits & Bytes](http://blog.rockarch.org/), the RAC's blog.

## Installation

### Quick Start

If you have [git](https://git-scm.com/) and [Docker](https://www.docker.com/community-edition) installed, getting Aurora up and running is as simple as:
```
git clone https://github.com/RockefellerArchiveCenter/aurora.git
cd aurora
docker-compose up
```
Once the build and startup process has completed, log into Aurora at `http://localhost:8000` with the user/password pair `admin` and `password`.

### Detailed Installation Instructions

1. Install [git](https://git-scm.com/) and [Docker](https://www.docker.com/community-edition)
2. Download or clone this repository
```
$ git clone https://github.com/RockefellerArchiveCenter/aurora.git
```
3. Build and run Aurora. The initial build may take some time, so be patient!
```
$ cd aurora
$ docker-compose up
```

4. Once this process has completed, Aurora is available in your web browser at `http://localhost:8000`. Log in using one of the default user accounts (see "User accounts" below).

#### Installation Notes for Windows Users

Install the correct version of Docker based on the Windows platform being used. [Docker Toolbox](https://docs.docker.com/toolbox/toolbox_install_windows/) is available for versions of Windows that do not support [Docker for Windows](https://docs.docker.com/docker-for-windows/).

To avoid line ending conflicts, clone the repo to Windows using `core.autocrlf`
```
$ git clone https://github.com/RockefellerArchiveCenter/aurora.git --config core.autocrlf=input
```
When using Docker Toolbox, clone aurora to a location in the C:\Users directory. By default, Docker Toolbox only has access to this directory.

Note that with Docker Toolbox, Aurora will not default to run on `http://localhost:8000`. Check the docker ip default:
```
$ docker-machine ip default
```

### Sample Data

If desired, you can import a set of sample bags (not all of which are valid) by running the `import_sample_data.sh` script.

Open up a new terminal window and navigate to the root of the application, then run

```
$ docker-compose exec web import_sample_data
```

If you're using the Docker container and would like to upload a bag you've made, you can do that by navigating to the uploads root located on your local machine at `~/.pe-shared/aurora-upload/` and moving the bag into the `/upload/` directory of the desired organization. To process the transfers, run

```
$ docker-compose exec web python manage.py runcrons
```

### Data Persistence

The Docker container is currently configured to persist the MySQL database in local storage. This means that when you shut down the container using `docker-compose down` all the data in the application will still be there the next time you run `docker-compose up`. If you want to wipe out the database at shut down, simply run `docker-compose down -v`.

### User accounts

By default, Aurora comes with five user accounts:

|Username|Password|User Role|
|---|---|---|
|admin|password|System Administrator|
|donor|password|Read Only User|
|appraiser|password|Appraisal Archivist|
|accessioner|password|Accessioning Archivist|
|manager|password|Managing Archivist|

See the Aurora User Documentation for more information about permissions associated with each user role.

## Transferring digital records

Aurora scans subdirectories at the location specified by the `TRANSFER_UPLOADS_ROOT` setting. It expects each organization to have its own directory, containing two subdirectories: `uploads` and `processing`. Any new files or directories in the `uploads` subdirectory are added to Aurora's processing queue.

At a high level, transfers are processed as follows:
- Transfers are checked to ensure they have a valid filename, in other words that the top-level directory (for unserialized bags) or filename (for serialized bags) does not contain illegal characters.
- Transfers are checked for viruses.
- Transfers are checked to ensure they have only one top-level directory.
- Size of transfers is checked to ensure it doesn't exceed `TRANSFER_FILESIZE_MAX`.
- Transfers are validated against the BagIt specification using `bagit-python`.
- Transfers are validated against the BagIt Profile specified in their `bag-info.txt` file using `bagit-profiles-validator`.
- Relevant PREMIS rights statements are assigned to transfers (see Organization Management section for details).

## API

Aurora comes with a RESTful API, built using the Django Rest Framework. In addition to interacting with the API via your favorite command-line client, you can also use the browsable API interface available in the application.

### Authentication

Aurora uses JSON Web Tokens for validation. As with all token-based authentication, you should ensure the application is only available over SSL/TLS in order to avoid token tampering and replay attacks.

To get your token, send a POST request to the `/get-token/` endpoint, passing your username and password:

```
$ curl -X POST -d "username=admin&password=password123" http://localhost:8000/api/get-token/
```

Your token will be returned in the response. You can then use the token in requests such as:

```
$ curl -H "Authorization: JWT <your_token>" http://localhost:8000/api/orgs/1/
```

In a production environment, successfully authenticating against this endpoint may require setting Apache's  `WSGIPassAuthorization` to `On`.


## Django Admin Configuration

Aurora comes with the default [Django admin site](https://docs.djangoproject.com/en/1.11/ref/contrib/admin/). Only users with superuser privileges are able to view this interface, which can be accessed by clicking on the profile menu and selecting "Administration".

In addition to allowing for the manual creation and deletion of certain objects, this interface also allows authorized users to edit system values which are used by the application, including the human-readable strings associated with Bag Log Codes. Care should be taken when making changes in the Django admin interface, particularly the creation or deletion of objects, since they can have unintended consequences.

## Contributing

Aurora is an open source project and we welcome contributions! If you want to fix a bug, or have an idea of how to enhance the application, the process looks like this:

1. File an issue in this repository. This will provide a location to discuss proposed implementations of fixes or enhancements, and can then be tied to a subsequent pull request.
2. If you have an idea of how to fix the bug (or make the improvements), fork the repository and work in your own branch. When you are done, push the branch back to this repository and set up a pull request. Automated unit tests are run on all pull requests. Any new code should have unit test coverage, documentation (if necessary), and should conform to the Python PEP8 style guidelines.
3. After some back and forth between you and core committers (or individuals who have privileges to commit to the master branch of this repository), your code will probably be merged, perhaps with some minor changes.


## License

Aurora is released under an [MIT License](LICENSE).
