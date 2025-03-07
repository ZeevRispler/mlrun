# Copyright 2024 Iguazio
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import io
import os
import sys

import mlrun.runtimes
import tests.system.base


@tests.system.base.TestMLRunSystem.skip_test_if_env_not_configured
class TestApplicationRuntime(tests.system.base.TestMLRunSystem):
    project_name = "application-system-test"

    def custom_setup(self):
        super().custom_setup()
        self._vizro_app_code_filename = "vizro_app.py"
        self._files_to_upload = [self._vizro_app_code_filename]
        self._source = os.path.join(self.remote_code_dir, self._vizro_app_code_filename)

    def test_deploy_application(self):
        self._upload_code_to_cluster()

        self._logger.debug("Creating application")
        function, source = self._create_vizro_application()

        self._logger.debug("Deploying vizro application")
        function.deploy(with_mlrun=False)

        assert function.invoke("/", verify=False)

        # Application runtime function is created without external url
        # check that empty string is not added to func.status.external_invocation_urls
        assert "" not in function.status.external_invocation_urls

        assert function.spec.build.source == source
        assert (
            function.status.application_image
            == f".mlrun/func-{self.project.metadata.name}-{function.metadata.name}:latest"
        )

        self._logger.debug("Redeploying the same application with capturing stdout")
        output = self._deploy_application_with_stdout_capture(function)

        # Assert nuclio image build was skipped
        assert "(info) Skipping build" in output

        assert function.invoke("/", verify=False)
        assert function.spec.build.source == source
        assert (
            function.status.application_image
            == f".mlrun/func-{self.project.metadata.name}-{function.metadata.name}:latest"
        )

    def test_deploy_application_from_image(self):
        self._logger.debug("Creating first application")
        function, source = self._create_vizro_application(name="first-app")

        self._logger.debug("Deploying first application")
        function.deploy(with_mlrun=False)

        assert function.invoke("/", verify=False)

        # take the application image and container image, and use them to deploy a new function
        application_image = function.status.application_image
        container_image = function.status.container_image

        function, _ = self._create_vizro_application(
            name="second-app", app_image=application_image
        )
        function.from_image(container_image)

        self._logger.debug("Deploying a second application")
        output = self._deploy_application_with_stdout_capture(function)

        # make sure the build was skipped
        assert "(info) Skipping build" in output

    def test_deploy_application_from_project_source(self):
        self._upload_code_to_cluster()

        # pull_at_runtime is not supported and should be overridden
        self.project.set_source(self._source, pull_at_runtime=True)
        self.project.save()

        self._logger.debug("Creating application")
        function, source = self._create_vizro_application(with_repo=True)

        self._logger.debug("Deploying vizro application")
        function.deploy(with_mlrun=False)

        assert function.invoke("/", verify=False)

    def test_deploy_reverse_proxy_base_image(self):
        tests.system.base.TestMLRunSystem._logger.debug(
            "Deploying reverse proxy base image"
        )
        mlrun.runtimes.ApplicationRuntime.deploy_reverse_proxy_image()
        assert mlrun.runtimes.ApplicationRuntime.reverse_proxy_image

        # deploy an application and expect it to use the reverse proxy image
        function, source = self._create_vizro_application()

        self._logger.debug("Deploying vizro application")
        function.deploy(with_mlrun=False)

        assert (
            function.status.container_image
            == mlrun.runtimes.ApplicationRuntime.reverse_proxy_image
        )

    def _create_vizro_application(
        self, name="vizro-app", app_image=None, with_repo: bool = False
    ):
        function = self.project.set_function(
            name=name,
            kind="application",
            requirements=["vizro", "gunicorn", "Werkzeug==2.2.2"],
            with_repo=with_repo,
        )
        function.set_internal_application_port(8050)
        function.spec.command = "gunicorn"
        function.spec.args = [
            "vizro_app:server",
            "--bind",
            "0.0.0.0:8050",
            "--log-level",
            "debug",
        ]
        if app_image:
            function.spec.image = app_image
        elif not with_repo:
            function.with_source_archive(source=self._source)
        return function, self._source

    @staticmethod
    def _deploy_application_with_stdout_capture(function):
        # Create a StringIO object to capture stdout
        old_stdout = sys.stdout
        new_stdout = io.StringIO()
        sys.stdout = new_stdout
        try:
            function.deploy(with_mlrun=False)
        finally:
            sys.stdout = old_stdout
        output = new_stdout.getvalue()
        new_stdout.close()
        return output
