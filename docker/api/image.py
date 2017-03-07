import logging
import os
import warnings

import six

from .. import auth, errors, utils
from ..constants import INSECURE_REGISTRY_DEPRECATION_WARNING

log = logging.getLogger("DockerLogger")


class ImageApiMixin(object):

    @utils.check_resource
    def get_image(self, image):
        """
        Get a tarball of an image. Similar to the ``docker save`` command.

        Args:
            image (str): Image name to get

        Returns:
            (urllib3.response.HTTPResponse object): The response from the
            daemon.

        Raises:
            :py:class:`docker.errors.APIError`
                If the server returns an error.

        Example:

            >>> image = cli.get_image("fedora:latest")
            >>> f = open('/tmp/fedora-latest.tar', 'w')
            >>> f.write(image.data)
            >>> f.close()
        """
        res = self._get(self._url("/images/{0}/get", image), stream=True)
        self._raise_for_status(res)
        return res.raw

    @utils.check_resource
    def history(self, image):
        """
        Show the history of an image.

        Args:
            image (str): The image to show history for

        Returns:
            (str): The history of the image

        Raises:
            :py:class:`docker.errors.APIError`
                If the server returns an error.
        """
        res = self._get(self._url("/images/{0}/history", image))
        return self._result(res, True)

    def images(self, name=None, quiet=False, all=False, viz=False,
               filters=None):
        """
        List images. Similar to the ``docker images`` command.

        Args:
            name (str): Only show images belonging to the repository ``name``
            quiet (bool): Only return numeric IDs as a list.
            all (bool): Show intermediate image layers. By default, these are
                filtered out.
            filters (dict): Filters to be processed on the image list.
                Available filters:
                - ``dangling`` (bool)
                - ``label`` (str): format either ``key`` or ``key=value``

        Returns:
            (dict or list): A list if ``quiet=True``, otherwise a dict.

        Raises:
            :py:class:`docker.errors.APIError`
                If the server returns an error.
        """
        if viz:
            if utils.compare_version('1.7', self._version) >= 0:
                raise Exception('Viz output is not supported in API >= 1.7!')
            return self._result(self._get(self._url("images/viz")))
        params = {
            'filter': name,
            'only_ids': 1 if quiet else 0,
            'all': 1 if all else 0,
        }
        if filters:
            params['filters'] = utils.convert_filters(filters)
        res = self._result(self._get(self._url("/images/json"), params=params),
                           True)
        if quiet:
            return [x['Id'] for x in res]
        return res

    def import_image(self, src=None, repository=None, tag=None, image=None,
                     changes=None, stream_src=False):
        """
        Import an image. Similar to the ``docker import`` command.

        If ``src`` is a string or unicode string, it will first be treated as a
        path to a tarball on the local system. If there is an error reading
        from that file, ``src`` will be treated as a URL instead to fetch the
        image from. You can also pass an open file handle as ``src``, in which
        case the data will be read from that file.

        If ``src`` is unset but ``image`` is set, the ``image`` parameter will
        be taken as the name of an existing image to import from.

        Args:
            src (str or file): Path to tarfile, URL, or file-like object
            repository (str): The repository to create
            tag (str): The tag to apply
            image (str): Use another image like the ``FROM`` Dockerfile
                parameter
        """
        if not (src or image):
            raise errors.DockerException(
                'Must specify src or image to import from'
            )
        u = self._url('/images/create')

        params = _import_image_params(
            repository, tag, image,
            src=(src if isinstance(src, six.string_types) else None),
            changes=changes
        )
        headers = {'Content-Type': 'application/tar'}

        if image or params.get('fromSrc') != '-':  # from image or URL
            return self._result(
                self._post(u, data=None, params=params)
            )
        elif isinstance(src, six.string_types):  # from file path
            with open(src, 'rb') as f:
                return self._result(
                    self._post(
                        u, data=f, params=params, headers=headers, timeout=None
                    )
                )
        else:  # from raw data
            if stream_src:
                headers['Transfer-Encoding'] = 'chunked'
            return self._result(
                self._post(u, data=src, params=params, headers=headers)
            )

    def import_image_from_data(self, data, repository=None, tag=None,
                               changes=None):
        """
        Like :py:meth:`~docker.api.image.ImageApiMixin.import_image`, but
        allows importing in-memory bytes data.

        Args:
            data (bytes collection): Bytes collection containing valid tar data
            repository (str): The repository to create
            tag (str): The tag to apply
        """

        u = self._url('/images/create')
        params = _import_image_params(
            repository, tag, src='-', changes=changes
        )
        headers = {'Content-Type': 'application/tar'}
        return self._result(
            self._post(
                u, data=data, params=params, headers=headers, timeout=None
            )
        )

    def import_image_from_file(self, filename, repository=None, tag=None,
                               changes=None):
        """
        Like :py:meth:`~docker.api.image.ImageApiMixin.import_image`, but only
        supports importing from a tar file on disk.

        Args:
            filename (str): Full path to a tar file.
            repository (str): The repository to create
            tag (str): The tag to apply

        Raises:
            IOError: File does not exist.
        """

        return self.import_image(
            src=filename, repository=repository, tag=tag, changes=changes
        )

    def import_image_from_stream(self, stream, repository=None, tag=None,
                                 changes=None):
        return self.import_image(
            src=stream, stream_src=True, repository=repository, tag=tag,
            changes=changes
        )

    def import_image_from_url(self, url, repository=None, tag=None,
                              changes=None):
        """
        Like :py:meth:`~docker.api.image.ImageApiMixin.import_image`, but only
        supports importing from a URL.

        Args:
            url (str): A URL pointing to a tar file.
            repository (str): The repository to create
            tag (str): The tag to apply
        """
        return self.import_image(
            src=url, repository=repository, tag=tag, changes=changes
        )

    def import_image_from_image(self, image, repository=None, tag=None,
                                changes=None):
        """
        Like :py:meth:`~docker.api.image.ImageApiMixin.import_image`, but only
        supports importing from another image, like the ``FROM`` Dockerfile
        parameter.

        Args:
            image (str): Image name to import from
            repository (str): The repository to create
            tag (str): The tag to apply
        """
        return self.import_image(
            image=image, repository=repository, tag=tag, changes=changes
        )

    @utils.check_resource
    def insert(self, image, url, path):
        if utils.compare_version('1.12', self._version) >= 0:
            raise errors.DeprecatedMethod(
                'insert is not available for API version >=1.12'
            )
        api_url = self._url("/images/{0}/insert", image)
        params = {
            'url': url,
            'path': path
        }
        return self._result(self._post(api_url, params=params))

    @utils.check_resource
    def inspect_image(self, image):
        """
        Get detailed information about an image. Similar to the ``docker
        inspect`` command, but only for containers.

        Args:
            container (str): The container to inspect

        Returns:
            (dict): Similar to the output of ``docker inspect``, but as a
        single dict

        Raises:
            :py:class:`docker.errors.APIError`
                If the server returns an error.
        """
        return self._result(
            self._get(self._url("/images/{0}/json", image)), True
        )

    def load_image(self, data):
        """
        Load an image that was previously saved using
        :py:meth:`~docker.api.image.ImageApiMixin.get_image` (or ``docker
        save``). Similar to ``docker load``.

        Args:
            data (binary): Image data to be loaded.
        """
        res = self._post(self._url("/images/load"), data=data)
        self._raise_for_status(res)

    @utils.minimum_version('1.25')
    def prune_images(self, filters=None):
        """
        Delete unused images

        Args:
            filters (dict): Filters to process on the prune list.
                Available filters:
                    - dangling (bool):  When set to true (or 1), prune only
                        unused and untagged images.

        Returns:
            (dict): A dict containing a list of deleted image IDs and
                the amount of disk space reclaimed in bytes.

        Raises:
            :py:class:`docker.errors.APIError`
                If the server returns an error.
        """
        url = self._url("/images/prune")
        params = {}
        if filters is not None:
            params['filters'] = utils.convert_filters(filters)
        return self._result(self._post(url, params=params), True)

    def pull(self, repository, tag=None, stream=False,
             insecure_registry=False, auth_config=None, decode=False):
        """
        Pulls an image. Similar to the ``docker pull`` command.

        Args:
            repository (str): The repository to pull
            tag (str): The tag to pull
            stream (bool): Stream the output as a generator
            insecure_registry (bool): Use an insecure registry
            auth_config (dict): Override the credentials that
                :py:meth:`~docker.api.daemon.DaemonApiMixin.login` has set for
                this request. ``auth_config`` should contain the ``username``
                and ``password`` keys to be valid.

        Returns:
            (generator or str): The output

        Raises:
            :py:class:`docker.errors.APIError`
                If the server returns an error.

        Example:

            >>> for line in cli.pull('busybox', stream=True):
            ...     print(json.dumps(json.loads(line), indent=4))
            {
                "status": "Pulling image (latest) from busybox",
                "progressDetail": {},
                "id": "e72ac664f4f0"
            }
            {
                "status": "Pulling image (latest) from busybox, endpoint: ...",
                "progressDetail": {},
                "id": "e72ac664f4f0"
            }

        """
        if insecure_registry:
            warnings.warn(
                INSECURE_REGISTRY_DEPRECATION_WARNING.format('pull()'),
                DeprecationWarning
            )

        if not tag:
            repository, tag = utils.parse_repository_tag(repository)
        registry, repo_name = auth.resolve_repository_name(repository)

        params = {
            'tag': tag,
            'fromImage': repository
        }
        headers = {}

        if utils.compare_version('1.5', self._version) >= 0:
            if auth_config is None:
                header = auth.get_config_header(self, registry)
                if header:
                    headers['X-Registry-Auth'] = header
            else:
                log.debug('Sending supplied auth config')
                headers['X-Registry-Auth'] = auth.encode_header(auth_config)

        response = self._post(
            self._url('/images/create'), params=params, headers=headers,
            stream=stream, timeout=None
        )

        self._raise_for_status(response)

        if stream:
            return self._stream_helper(response, decode=decode)

        return self._result(response)

    def push(self, repository, tag=None, stream=False,
             insecure_registry=False, auth_config=None, decode=False):
        """
        Push an image or a repository to the registry. Similar to the ``docker
        push`` command.

        Args:
            repository (str): The repository to push to
            tag (str): An optional tag to push
            stream (bool): Stream the output as a blocking generator
            insecure_registry (bool): Use ``http://`` to connect to the
                registry
            auth_config (dict): Override the credentials that
                :py:meth:`~docker.api.daemon.DaemonApiMixin.login` has set for
                this request. ``auth_config`` should contain the ``username``
                and ``password`` keys to be valid.

        Returns:
            (generator or str): The output from the server.

        Raises:
            :py:class:`docker.errors.APIError`
                If the server returns an error.

        Example:
            >>> for line in cli.push('yourname/app', stream=True):
            ...   print line
            {"status":"Pushing repository yourname/app (1 tags)"}
            {"status":"Pushing","progressDetail":{},"id":"511136ea3c5a"}
            {"status":"Image already pushed, skipping","progressDetail":{},
             "id":"511136ea3c5a"}
            ...

        """
        if insecure_registry:
            warnings.warn(
                INSECURE_REGISTRY_DEPRECATION_WARNING.format('push()'),
                DeprecationWarning
            )

        if not tag:
            repository, tag = utils.parse_repository_tag(repository)
        registry, repo_name = auth.resolve_repository_name(repository)
        u = self._url("/images/{0}/push", repository)
        params = {
            'tag': tag
        }
        headers = {}

        if utils.compare_version('1.5', self._version) >= 0:
            if auth_config is None:
                header = auth.get_config_header(self, registry)
                if header:
                    headers['X-Registry-Auth'] = header
            else:
                log.debug('Sending supplied auth config')
                headers['X-Registry-Auth'] = auth.encode_header(auth_config)

        response = self._post_json(
            u, None, headers=headers, stream=stream, params=params
        )

        self._raise_for_status(response)

        if stream:
            return self._stream_helper(response, decode=decode)

        return self._result(response)

    @utils.check_resource
    def remove_image(self, image, force=False, noprune=False):
        """
        Remove an image. Similar to the ``docker rmi`` command.

        Args:
            image (str): The image to remove
            force (bool): Force removal of the image
            noprune (bool): Do not delete untagged parents
        """
        params = {'force': force, 'noprune': noprune}
        res = self._delete(self._url("/images/{0}", image), params=params)
        self._raise_for_status(res)

    def search(self, term):
        """
        Search for images on Docker Hub. Similar to the ``docker search``
        command.

        Args:
            term (str): A term to search for.

        Returns:
            (list of dicts): The response of the search.

        Raises:
            :py:class:`docker.errors.APIError`
                If the server returns an error.
        """
        return self._result(
            self._get(self._url("/images/search"), params={'term': term}),
            True
        )

    @utils.check_resource
    def tag(self, image, repository, tag=None, force=False):
        """
        Tag an image into a repository. Similar to the ``docker tag`` command.

        Args:
            image (str): The image to tag
            repository (str): The repository to set for the tag
            tag (str): The tag name
            force (bool): Force

        Returns:
            (bool): ``True`` if successful

        Raises:
            :py:class:`docker.errors.APIError`
                If the server returns an error.

        Example:

            >>> client.tag('ubuntu', 'localhost:5000/ubuntu', 'latest',
                           force=True)
        """
        params = {
            'tag': tag,
            'repo': repository,
            'force': 1 if force else 0
        }
        url = self._url("/images/{0}/tag", image)
        res = self._post(url, params=params)
        self._raise_for_status(res)
        return res.status_code == 201


def is_file(src):
    try:
        return (
            isinstance(src, six.string_types) and
            os.path.isfile(src)
        )
    except TypeError:  # a data string will make isfile() raise a TypeError
        return False


def _import_image_params(repo, tag, image=None, src=None,
                         changes=None):
    params = {
        'repo': repo,
        'tag': tag,
    }
    if image:
        params['fromImage'] = image
    elif src and not is_file(src):
        params['fromSrc'] = src
    else:
        params['fromSrc'] = '-'

    if changes:
        params['changes'] = changes

    return params
