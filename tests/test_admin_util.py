import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock
from unittest.mock import patch

from cravat.admin_util import get_install_deps
from cravat.admin_util import request_user_email

# package configurations for test use
no_dependencies_package = {"name": "a", "requires": []}
two_dependencies_package = {"name": "two_deps", "requires": ["a", "b"]}
deep_dependencies_package = {"name": "deep_dependencies", "requires": ["w"]}
circular_dependencies_packages = {
    "name": "circular_dependencies", "requires": ["circle_back"]}
dep_w = {"name": "w", "requires": ["x"]}
dep_x = {"name": "x", "requires": ["y"]}
dep_y = {"name": "y", "requires": ["z"]}
dep_z = {"name": "z", "requires": ["a"]}
dep_a = no_dependencies_package
dep_b = {"name": "b"}
circle_back = {"name": "circle_back", "requires": ["circular_dependencies"]}
multi_version_dependencies = {"name": "multi", "requires": ["multi_a", "multi_b"]}
multi_a = {"name": "multi_a", "requires": ["a>1.0"]}
multi_b = {"name": "multi_b", "requires": ["a<1.2"]}
pin_a = {"name": "pin_a", "requires": ["pin_b==1.0", "pin_c"]}
pin_b = {"name": "pin_b", "requires": ["pin_c==1.1"]}
pin_c = {"name": "pin_c", "requires": []}


def mic_get_remote_info_mock(*args, **kwargs):
    """Constant map for mocking get_remote_info()"""
    match args[0]:
        case 'a':
            return dep_a
        case 'b':
            return dep_b
        case 'w':
            return dep_w
        case 'x':
            return dep_x
        case 'y':
            return dep_y
        case 'z':
            return dep_z
        case 'two_deps':
            return two_dependencies_package
        case 'deep_dependencies':
            return deep_dependencies_package
        case 'circular_dependencies':
            return circular_dependencies_packages
        case 'circle_back':
            return circle_back
        case 'multi':
            return multi_version_dependencies
        case 'multi_a':
            return multi_a
        case 'multi_b':
            return multi_b
        case 'pin_a':
            return pin_a
        case 'pin_b':
            return pin_b
        case 'pin_c':
            return pin_c
        case _:
            return None


remote_module_info_one_version = MagicMock(versions=["1.0"])
remote_module_info_three_versions = MagicMock(versions=["1.0", "1.1", "1.2"])


class TestAdminUtil(unittest.TestCase):
    @patch('cravat.admin_util.get_remote_module_info', name="no_deps_rmi")
    @patch('cravat.admin_util.mic', name="no_deps_mic")
    def test_get_import_deps_empty_when_no_dependencies(self, mock_mic, mock_get_remote_module_info):
        mock_mic.update_remote()
        mock_mic.get_remote_config.return_value = no_dependencies_package
        mock_get_remote_module_info.return_value = remote_module_info_one_version

        deps = get_install_deps(module_name="A", version="1.0")
        self.assertEqual({}, deps)

    @patch('cravat.admin_util.get_remote_module_info', name="direct_rmi")
    @patch('cravat.admin_util.mic', name="direct_mic")
    def test_get_import_deps_direct_dependencies(self, mock_mic, mock_get_remote_module_info):
        mock_mic.update_remote()
        # mock get_remote_config to return the dependencies in the order they are resolved
        mock_mic.get_remote_config.side_effect = mic_get_remote_info_mock
        mock_get_remote_module_info.return_value = remote_module_info_one_version

        deps = get_install_deps(module_name="two_deps", version="1.0")
        self.assertEqual({"a": "1.0", "b": "1.0"}, deps)

    @patch('cravat.admin_util.get_remote_module_info', name="direct_rmi")
    @patch('cravat.admin_util.mic', name="direct_mic")
    def test_get_import_deps_deep_dependencies(self, mock_mic, mock_get_remote_module_info):
        mock_mic.update_remote()
        # mock get_remote_config to return the dependencies in the order they are resolved
        mock_mic.get_remote_config.side_effect = mic_get_remote_info_mock
        mock_get_remote_module_info.return_value = remote_module_info_one_version

        deps = get_install_deps(module_name="deep_dependencies", version="1.0")
        self.assertEqual({"w": "1.0", "x": "1.0", "y": "1.0",
                          "z": "1.0", "a": "1.0"}, deps)

    @patch('cravat.admin_util.get_remote_module_info')
    @patch('cravat.admin_util.mic')
    def test_get_import_deps_circular_dependencies_resolves(self, mock_mic, mock_get_remote_module_info):
        mock_mic.update_remote()
        # mock get_remote_config to return the dependencies in the order they are resolved
        mock_mic.get_remote_config.side_effect = mic_get_remote_info_mock
        mock_get_remote_module_info.return_value = remote_module_info_one_version

        deps = get_install_deps(
            module_name="circular_dependencies", version="1.0")
        self.assertEqual({"circular_dependencies": "1.0",
                          "circle_back": "1.0"}, deps)

    @patch('cravat.admin_util.get_remote_module_info')
    @patch('cravat.admin_util.mic')
    def test_get_import_deps_different_versions_are_matched(self, mock_mic, mock_get_remote_module_info):
        mock_mic.update_remote()
        # mock get_remote_config to return the dependencies in the order they are resolved
        mock_mic.get_remote_config.side_effect = mic_get_remote_info_mock
        mock_get_remote_module_info.return_value = remote_module_info_three_versions

        deps = get_install_deps(module_name="multi", version="1.0")
        self.assertEqual(
            {
                "multi_a": "1.2",
                "multi_b": "1.2",
                "a": "1.1"
            }, deps)

    @patch('cravat.admin_util.get_remote_module_info')
    @patch('cravat.admin_util.mic')
    def test_get_import_deps_pinned_version(self, mock_mic, mock_get_remote_module_info):
        mock_mic.update_remote()
        mock_mic.get_remote_config.side_effect = mic_get_remote_info_mock
        mock_get_remote_module_info.return_value = remote_module_info_three_versions
        deps = get_install_deps(module_name='pin_a')
        self.assertEqual(
            {
                'pin_b': '1.0',
                'pin_c': '1.1',
            }, deps)

    @patch('cravat.admin_util.update_system_conf_file')
    def test_request_user_email_skip_if_not_interactive(self, mock_update_system_conf_file):
        # sys.stdin.isatty = False when run in a test runner, we're testing that request_user_email does nothing
        args = {}
        request_user_email(args)
        mock_update_system_conf_file.assert_not_called()

    @patch('sys.stdin.isatty')
    @patch('cravat.admin_util.get_system_conf')
    @patch('cravat.admin_util.update_system_conf_file')
    def test_request_user_email_skip_if_opt_out(self, mock_update_system_conf_file, mock_get_system_conf, mock_isatty):
        mock_isatty.return_value = True
        mock_get_system_conf.return_value = {
            'user_email': '',
            'user_email_opt_out': True
        }
        args = {}
        request_user_email(args)
        mock_update_system_conf_file.assert_not_called()

    @patch('sys.stdin.isatty')
    @patch('cravat.admin_util.get_system_conf')
    @patch('cravat.admin_util.update_system_conf_file')
    def test_request_user_email_skip_if_email_set(self, mock_update_system_conf_file, mock_get_system_conf, mock_isatty):
        mock_isatty.return_value = True
        mock_get_system_conf.return_value = {
            'user_email': 'test@config',
            'user_email_opt_out': False
        }
        args = {}
        request_user_email(args)
        mock_update_system_conf_file.assert_not_called()

    @patch('sys.stdin.isatty')
    @patch('builtins.input')
    @patch('cravat.admin_util.get_system_conf')
    @patch('cravat.admin_util.update_system_conf_file')
    def test_request_user_email_set_email_from_input(self, mock_update_system_conf_file, mock_get_system_conf, mock_input, mock_isatty):
        mock_isatty.return_value = True
        mock_input.return_value = 'test@input'
        mock_get_system_conf.return_value = {
            'user_email': '',
            'user_email_opt_out': False
        }
        args = SimpleNamespace(
            user_email='',
            user_email_opt_out=False
        )
        request_user_email(args)
        mock_update_system_conf_file.assert_called_once_with({'user_email': 'test@input', 'user_email_opt_out': False})

    @patch('sys.stdin.isatty')
    @patch('builtins.input')
    @patch('cravat.admin_util.get_system_conf')
    @patch('cravat.admin_util.update_system_conf_file')
    def test_request_user_email_set_opt_out_from_input(self, mock_update_system_conf_file, mock_get_system_conf, mock_input, mock_isatty):
        mock_isatty.return_value = True
        mock_input.return_value = 'No'
        mock_get_system_conf.return_value = {
            'user_email': '',
            'user_email_opt_out': False
        }
        args = SimpleNamespace(
            user_email='',
            user_email_opt_out=True
        )
        request_user_email(args)
        mock_update_system_conf_file.assert_called_once_with({'user_email': '', 'user_email_opt_out': True})

    @patch('sys.stdin.isatty')
    @patch('cravat.admin_util.get_system_conf')
    @patch('cravat.admin_util.update_system_conf_file')
    def test_request_user_email_set_email_from_argument(self, mock_update_system_conf_file, mock_get_system_conf, mock_isatty):
        mock_isatty.return_value = True
        mock_get_system_conf.return_value = {
            'user_email': '',
            'user_email_opt_out': False
        }
        args = SimpleNamespace(
            user_email='test@argument',
            user_email_opt_out=False
        )
        request_user_email(args)
        mock_update_system_conf_file.assert_called_once_with({'user_email': 'test@argument', 'user_email_opt_out': False})

    @patch('sys.stdin.isatty')
    @patch('cravat.admin_util.get_system_conf')
    @patch('cravat.admin_util.update_system_conf_file')
    def test_request_user_email_set_opt_out_from_argument(self, mock_update_system_conf_file, mock_get_system_conf, mock_isatty):
        mock_isatty.return_value = True
        mock_get_system_conf.return_value = {
            'user_email': '',
            'user_email_opt_out': False
        }
        args = SimpleNamespace(
            user_email='',
            user_email_opt_out=True
        )
        request_user_email(args)
        mock_update_system_conf_file.assert_called_once_with({'user_email': '', 'user_email_opt_out': True})


if __name__ == '__main__':
    unittest.main()
