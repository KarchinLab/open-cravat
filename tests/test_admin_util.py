import unittest
from unittest.mock import Mock
from unittest.mock import patch

from cravat.admin_util import get_install_deps

# package configurations for test use
no_dependencies_package = { "name": "a", "requires": [] }
remote_module_info_one_version = { "versions": [ "0.0" ]}


class TestAdminUtil(unittest.TestCase):
    @patch('cravat.admin_util.get_remote_module_info')
    @patch('cravat.admin_util.mic')
    def test_get_import_deps_empty_when_no_dependencies(self, mock_mic, mock_get_remote_module_info):
        mock_mic.update_remote()
        mock_mic.get_remote_config.return_value = no_dependencies_package
        mock_get_remote_module_info.return_value = remote_module_info_one_version
        
        deps = get_install_deps(module_name="A", version="1.0")
        self.assertEqual(deps, {})
    

if __name__ == '__main__':
    unittest.main()