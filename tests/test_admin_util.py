import unittest
from unittest.mock import MagicMock, Mock
from unittest.mock import patch

from cravat.admin_util import get_install_deps

# package configurations for test use
no_dependencies_package = { "name": "a", "requires": [] }
two_dependencies_package = { "name": "two_deps", "requires": ["a", "b"]}
deep_dependencies_package = { "name": "deep_dependencies", "requires": ["w"]}
dep_b = { "name": "b"}

remote_module_info_one_version = MagicMock(versions = [ "1.0" ])
remote_module_info_two_versions = { "versions": [ "1.0", "1.1" ]}


class TestAdminUtil(unittest.TestCase):
    @patch('cravat.admin_util.get_remote_module_info', name="no_deps_rmi")
    @patch('cravat.admin_util.mic', name="no_deps_mic")
    def test_get_import_deps_empty_when_no_dependencies(self, mock_mic, mock_get_remote_module_info):
        mock_mic.update_remote()
        mock_mic.get_remote_config.return_value = no_dependencies_package
        mock_get_remote_module_info.return_value = remote_module_info_one_version
        
        deps = get_install_deps(module_name="A", version="1.0")
        self.assertEqual(deps, {})

    
    @patch('cravat.admin_util.get_remote_module_info', name="direct_rmi")
    @patch('cravat.admin_util.mic', name="direct_mic")
    def test_get_import_deps_direct_dependencies(self, mock_mic, mock_get_remote_module_info):
        mock_mic.update_remote()
        # mock get_remote_config to return the dependencies in the order they are resolved
        mock_mic.get_remote_config.side_effect = [
            two_dependencies_package,
            no_dependencies_package,
            dep_b
        ]
        mock_get_remote_module_info.return_value = remote_module_info_one_version

        deps = get_install_deps(module_name="two_deps", version="1.0")
        self.assertEqual({ "a": "1.0", "b": "1.0" }, deps)
    

if __name__ == '__main__':
    unittest.main()