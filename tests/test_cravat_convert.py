import unittest
from unittest.mock import MagicMock
from unittest.mock import patch

from cravat.cravat_convert import MasterCravatConverter

wdict1 = {'chrom': 'chr1', 'pos': 123}

# Example Converter Object for test use
def build_MasterCravatCoverter():
    # make sure to mock cravat.util.get_args
    mcc = MasterCravatConverter()
    mcc.input_paths = ['a', 'b']
    mcc.ready_to_convert = True  # skip setup step
    mcc.pipeinput = True  # don't do file manipulation
    mcc.primary_converter = MagicMock(return_value={
        'setup': MagicMock(),
        'convert_file': MagicMock(return_value=[(0, 'line 0', {}), (1, 'line 1', {}), (2, 'line 2', {})])
    })
    mcc.status_writer = MagicMock()
    return mcc


class TestAdminUtil(unittest.TestCase):
    @patch('cravat.util.get_args')
    def test_get_import_deps_empty_when_no_dependencies(self, mock_get_args):
        mock_get_args.return_value = {'path': '/', 'inputs': ['a', 'b'], 'output_dir': '/', 'genome': 'hg38', 'format': None}
        try:
            # TODO fix error with mocking setup
            # E       AttributeError: 'dict' object has no attribute 'format'
            # ../cravat/cravat_convert.py:142: AttributeError

            mcc = build_MasterCravatCoverter()
            mcc.run()
        except KeyError:
            self.fail('MasterCravatConverter.run() raised a KeyError')


if __name__ == '__main__':
    unittest.main()
